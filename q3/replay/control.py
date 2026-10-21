"""Ask a replay proxy on this machine to do something, through the proxy itself (A11-165): GET http://replay.control<path> via 127.0.0.1:<port>. Standard library only."""
import json, http.client


def control(port, path, timeout=60):
    c = http.client.HTTPConnection('127.0.0.1', port, timeout=timeout)
    try:
        c.request('GET', 'http://replay.control' + path); r = c.getresponse(); body = json.loads(r.read())
    finally: c.close()
    if r.status != 200: raise RuntimeError(f'replay.control{path}: {r.status} {body}')
    return body
