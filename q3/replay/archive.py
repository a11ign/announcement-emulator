"""What a replay server answers, as plain Python (A11-165): no browser and no mitmproxy needed, so it is tested without either.

An archive is the list of exchanges one page made when it was recorded (`Entry`). `Archive.find` answers a request from it, by the same rule for every client:

  exact   the method and the address (fragment dropped, host lower-cased, default port dropped, query as recorded) were recorded. A request made again is answered with the next recording of
          that address, in the order they were made; once the recordings are used up the last is answered again (`reused`).
  fuzzy   no exact one, but the method, the host and the path were recorded with the same query parameter NAMES (the values differ: a timestamp, a random number). The recording whose
          values agree on most parameters answers, the earlier one on a tie.
  miss    anything else. A miss is answered with an error by the server, never fetched.

`page_join` puts the logs the two sides of one page left side by side."""
import hashlib
from dataclasses import dataclass, field
from urllib.parse import urlsplit, parse_qsl

DEFAULT_PORTS = {'http': 80, 'https': 443}


@dataclass
class Entry:
    method: str
    url: str
    status: int
    headers: list            # [(name, value)], in the order recorded
    body: bytes              # the content with its encoding taken off
    request_body_sha: str = ''


def normal_url(url):
    """The address a recording is looked up by: no fragment, host lower-case, the scheme's own port dropped. The query stays as it was written."""
    p = urlsplit(url)
    host = (p.hostname or '').lower(); port = p.port
    netloc = host if port in (None, DEFAULT_PORTS.get(p.scheme)) else f'{host}:{port}'
    return f'{p.scheme}://{netloc}{p.path or "/"}' + (f'?{p.query}' if p.query else '')


def path_key(url):
    """The address without its query."""
    return normal_url(url).split('?', 1)[0]


def params(url): return parse_qsl(urlsplit(url).query, keep_blank_values=True)


def body_sha(body): return hashlib.sha256(body or b'').hexdigest()


@dataclass
class Archive:
    entries: list
    _exact: dict = field(default_factory=dict, repr=False)
    _by_path: dict = field(default_factory=dict, repr=False)
    _served: dict = field(default_factory=dict, repr=False)

    def __post_init__(self):
        for e in self.entries:
            self._exact.setdefault((e.method, normal_url(e.url)), []).append(e)
            self._by_path.setdefault((e.method, path_key(e.url)), []).append(e)

    def reset(self): self._served.clear()

    def find(self, method, url, request_body=b''):
        """(entry, kind, reused) for a request, kind 'exact' or 'fuzzy'; (None, 'miss', False) when the archive holds nothing for it."""
        key = (method, normal_url(url))
        exact = self._exact.get(key)
        if exact:
            if method in ('POST', 'PUT', 'PATCH'):      # a request with a body is told from another to the same address by the body, when one was recorded for it
                same = [e for e in exact if e.request_body_sha == body_sha(request_body)]
                exact = same or exact
            return self._next(key, exact, 'exact')
        wanted = params(url); names = sorted(n for n, _ in wanted)
        candidates = [e for e in self._by_path.get((method, path_key(url)), []) if sorted(n for n, _ in params(e.url)) == names]
        if not candidates: return None, 'miss', False
        have = set(wanted)
        best = max(range(len(candidates)), key=lambda i: (len(have & set(params(candidates[i].url))), -i))      # most values in common; the earlier recording on a tie
        return self._next(('fuzzy', method, normal_url(candidates[best].url)), [candidates[best]], 'fuzzy')

    def _next(self, key, options, kind):
        n = self._served.get(key, 0); self._served[key] = n + 1
        return options[min(n, len(options) - 1)], kind, n >= len(options)


def summarise(requests):
    """Counts of a log: how many requests, and how many exact, fuzzy and missed."""
    out = {'requests': len(requests), 'exact': 0, 'fuzzy': 0, 'miss': 0}
    for r in requests: out[r['kind']] = out.get(r['kind'], 0) + 1
    return out


def page_join(fleet_log, emulator_log):
    """One page's two logs side by side: what each side asked for, and what the archive did not answer that the other side's WAS answered.

    A request is named by its method and address as the browser sent it. A side's answered set is what its log says was exact or fuzzy. A request the archive did not answer on one side
    but answered on the other is the evidence that the two sides were not served the same bytes; a miss on both sides (a browser's own background request) is not."""
    def split(log):
        answered = {(r['method'], normal_url(r['url'])) for r in log if r['kind'] in ('exact', 'fuzzy')}
        missed = {(r['method'], normal_url(r['url'])) for r in log if r['kind'] == 'miss'}
        return answered, missed
    fa, fm = split(fleet_log); ea, em = split(emulator_log)
    show = lambda s: sorted(f'{m} {u}' for m, u in s)
    return {'fleet': summarise(fleet_log), 'emulator': summarise(emulator_log),
            'missedOnFleetAnsweredOnEmulator': show((fm - fa) & ea), 'missedOnEmulatorAnsweredOnFleet': show((em - ea) & fa),
            'onlyFleetAnswered': show(fa - ea - em), 'onlyEmulatorAnswered': show(ea - fa - fm)}
