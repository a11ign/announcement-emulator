"""The replay server's mitmproxy addon (A11-165): answers every request from one recorded archive, and fetches nothing.

    REPLAY_ROOT=<dir of archives> [REPLAY_ARCHIVE=<archive>] mitmdump -s addon.py --listen-host H --listen-port P --set confdir=<the run's CA directory>

Every request, whichever client sends it, is answered from the archive loaded (`archive.Archive.find`); one the archive does not hold is answered `404` with `x-replay: miss`. No connection to any real server is ever made
(`server_connect` refuses it, and logs it), so a replay cannot be told apart from the recording by the network it had. A recorded response is sent with its encoding taken off, `cache-control: no-store` (the browser's
cache must not answer in the archive's place, or hold the answer for the next page) and `x-replay` naming how it was found; its body is the recorded bytes.

The server is steered by requests to the reserved host `replay.control`, sent through the proxy like any other:

  GET http://replay.control/use?archive=<file name under REPLAY_ROOT>   load that archive (and its `<file>.served.json`, if there is one), clear the log
  GET http://replay.control/log                                          the requests since `use`, each with how it was answered, and the archive's sha256
  GET http://replay.control/ping                                         ok

A page the server answered with an error status when it was recorded (a site down for maintenance) is a page the fleet's worker refuses to capture, whatever its body says. Its archive has a sidecar, `<archive>.served.json`
(`{"address": ..., "recordedStatus": 503, "servedStatus": 200}`): the exchange for that address that was recorded with that status is answered with the served one, the body as recorded, and the log says what was recorded.

A page recorded with consent given (A11-166) has a second sidecar, `<archive>.consent.json` (consent.py): the cookies the recording's browser held once it had activated the page's "accept all" control. The server adds them, as `Set-Cookie`,
to every document (navigation) response whose host may set them, the same for every client, so the fleet's Edge and the emulator's Chrome both hold the consent before any script of the page runs. The log says how many it added.

The log holds no client address: each side has its own server and its own log."""
import hashlib, json, os, sys, time
from urllib.parse import urlsplit, parse_qs
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from archive import Archive, normal_url
from flows import entries_of
import consent
from mitmproxy import http

CONTROL_HOST = 'replay.control'
HOP_BY_HOP = {'connection', 'keep-alive', 'proxy-connection', 'transfer-encoding', 'content-encoding', 'content-length', 'upgrade', 'te', 'trailer'}


class Replay:
    def __init__(self):
        self.root = os.path.realpath(os.environ.get('REPLAY_ROOT') or '.')
        self.archive = None; self.name = None; self.sha = None; self.log = []; self.served_as = None; self.consent = None
        if os.environ.get('REPLAY_ARCHIVE'): self.use(os.environ['REPLAY_ARCHIVE'])

    def use(self, name):
        path = os.path.realpath(os.path.join(self.root, name))
        if os.path.commonpath([path, self.root]) != self.root: raise ValueError('an archive is a file under the archive directory')
        with open(path, 'rb') as f: sha = hashlib.sha256(f.read()).hexdigest()
        sidecar = path + '.served.json'; served_as = None
        if os.path.exists(sidecar):
            with open(sidecar) as f: served_as = json.load(f)
        sidecars = (consent.read_sidecar(path), served_as)      # read before anything is switched: a sidecar that cannot be read leaves the archive in use, and its cookies, as they were
        self.archive = Archive(entries_of(path)); self.name = name; self.sha = sha; self.log = []; self.consent, self.served_as = sidecars

    def control(self, flow):
        q = parse_qs(urlsplit(flow.request.pretty_url).query); path = urlsplit(flow.request.pretty_url).path
        try:
            if path == '/use': self.use(q['archive'][0]); body = {'archive': self.name, 'sha256': self.sha, 'entries': len(self.archive.entries)}
            elif path == '/log': body = {'archive': self.name, 'sha256': self.sha, 'requests': self.log}
            elif path == '/ping': body = {'ok': True}
            else: raise ValueError('no such control: ' + path)
            flow.response = http.Response.make(200, json.dumps(body), {'content-type': 'application/json'})
        except Exception as e:
            flow.response = http.Response.make(500, json.dumps({'error': f'{type(e).__name__}: {e}'}), {'content-type': 'application/json'})

    def served_status(self, method, url, entry):
        """The status to answer with: the recorded one, or the sidecar's for the page's own address when it was recorded with the status the sidecar names."""
        if entry is None: return None
        sc = self.served_as
        if sc and method == 'GET' and normal_url(url) == normal_url(sc['address']) and entry.status == sc['recordedStatus']: return sc['servedStatus']
        return entry.status

    @staticmethod
    def is_document(request):
        """A navigation: the browser says so (`sec-fetch-dest: document`), or, where it sends no fetch metadata (an http address), it asked for a page."""
        dest = request.headers.get('sec-fetch-dest', '')
        return dest == 'document' or (dest == '' and request.method == 'GET' and 'text/html' in request.headers.get('accept', ''))

    def consent_cookies(self, request):
        """The `Set-Cookie` values consent adds to the answer to this request."""
        return consent.set_cookie_headers(self.consent, request.pretty_url) if self.is_document(request) else []

    def request(self, flow: http.HTTPFlow):
        if flow.request.pretty_host == CONTROL_HOST: return self.control(flow)
        url = flow.request.pretty_url
        entry, kind, reused = (None, 'miss', False) if self.archive is None else self.archive.find(flow.request.method, url, flow.request.raw_content or b'')
        status = self.served_status(flow.request.method, url, entry)
        self.log.append({'at': round(time.time(), 3), 'method': flow.request.method, 'url': url, 'kind': kind, 'reused': reused, 'status': status if entry else 404,
                         'dest': flow.request.headers.get('sec-fetch-dest', ''), 'mode': flow.request.headers.get('sec-fetch-mode', ''), **({'recordedStatus': entry.status} if entry and status != entry.status else {})})
        if entry is None:
            flow.response = http.Response.make(404, b'replay: no recording of this request', {'content-type': 'text/plain', 'x-replay': 'miss', 'cache-control': 'no-store'}); return
        headers = http.Headers([(k.encode('latin-1'), v.encode('latin-1')) for k, v in entry.headers if k.lower() not in HOP_BY_HOP and k.lower() not in ('cache-control', 'expires', 'pragma', 'etag', 'last-modified', 'age')])
        headers['cache-control'] = 'no-store'; headers['x-replay'] = kind
        cookies = self.consent_cookies(flow.request)
        if cookies: headers.set_all('set-cookie', [*headers.get_all('set-cookie'), *cookies]); self.log[-1]['consentCookies'] = len(cookies)
        flow.response = http.Response.make(status, entry.body, headers)

    def server_connect(self, data):
        """Nothing is fetched live: a connection to a real server is refused, and logged, so that it shows."""
        data.server.error = 'replay: no live connections'
        self.log.append({'at': round(time.time(), 3), 'method': 'CONNECT', 'url': '%s:%s' % data.server.address, 'kind': 'blocked', 'reused': False, 'status': 0, 'dest': '', 'mode': ''})


addons = [Replay()]
