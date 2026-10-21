"""Read a recorded flows file (mitmproxy's own format) into archive entries. Needs mitmproxy: run under the replay virtualenv (`setup.sh`).

    <replay venv python> flows.py info <flows> <address>      prints what the recording holds, as JSON"""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from archive import Entry, body_sha, normal_url
from urllib.parse import urlsplit, urljoin
from mitmproxy import http, io


def entries_of(path):
    """The exchanges of a recorded flows file that got a response."""
    out = []
    with open(path, 'rb') as f:
        for flow in io.FlowReader(f).stream():
            if not isinstance(flow, http.HTTPFlow) or flow.response is None: continue
            out.append(Entry(flow.request.method, flow.request.pretty_url, flow.response.status_code,
                             [(k.decode('latin-1'), v.decode('latin-1')) for k, v in flow.response.headers.fields],
                             flow.response.get_content(strict=False) or b'', body_sha(flow.request.raw_content)))
    return out


def info(path, address):
    """How many exchanges got a response, the hosts they went to, and the status the page's own address ended on (redirects followed through the recording; None if it was not recorded)."""
    entries = entries_of(path); at = address; status = None
    for _ in range(10):
        own = [e for e in entries if e.method == 'GET' and normal_url(e.url) == normal_url(at)]
        if not own: status = None; break
        status = own[0].status; where = dict((k.lower(), v) for k, v in own[0].headers).get('location')
        if status in (301, 302, 303, 307, 308) and where: at = urljoin(own[0].url, where)
        else: break
    return {'requests': len(entries), 'hosts': len({urlsplit(e.url).hostname for e in entries}), 'mainStatus': status, 'endedAt': at, 'bodyBytes': sum(len(e.body) for e in entries)}


if __name__ == '__main__':
    if len(sys.argv) == 4 and sys.argv[1] == 'info': print(json.dumps(info(sys.argv[2], sys.argv[3])))
    else: sys.exit(__doc__)
