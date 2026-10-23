"""Consent given in the recording, and served to both sides the same way (A11-166).

A page is recorded with consent already given, so neither the fleet's Edge nor the emulator's Chrome is shown a cookie dialog. The rule that finds the "accept all" control is `consent.mjs` over the one list in
`consent-names.json` (run by `record.mjs`); this module is what is kept of it and what the replay server does with it:

  `<archive>.consent.json`   written beside the archive like `<archive>.served.json`, one of three outcomes:
      given        a control in the list was activated; `cookies` are what the browser then held (read through CDP)
      no-dialog    no control, no dialog and no cookie-named region in the page
      not-matched  a dialog role or a cookie-named region is in the page and no control in the list matched (or the one that did could not be activated); nothing is served
  `set_cookie_headers`        the sidecar's cookies that the replay server adds, as `Set-Cookie`, to the page's documents (a navigation), whichever client asks. A browser then holds the consent before any script of the page runs.

Standard library only."""
import os, json, re
from urllib.parse import urlsplit

GIVEN, NO_DIALOG, NOT_MATCHED = 'given', 'no-dialog', 'not-matched'
OUTCOMES = (GIVEN, NO_DIALOG, NOT_MATCHED)
SERVED_MAX_AGE = 7 * 24 * 3600      # a cookie the recording held with an expiry is served for a week, the same for every client; one without an expiry is a session cookie


def sidecar_path(archive_path): return archive_path + '.consent.json'


def make_sidecar(address, outcome, why, control=None, cookies=None, recorded_at=None):
    """The sidecar's content. Only `given` carries cookies and a control."""
    if outcome not in OUTCOMES: raise ValueError(f'consent outcome {outcome!r} is none of {OUTCOMES}')
    out = {'address': address, 'outcome': outcome, 'why': why}
    if recorded_at: out['recordedAt'] = recorded_at
    if outcome == GIVEN: out.update({'control': control, 'cookies': list(cookies or [])})
    return out


def write_sidecar(archive_path, sidecar):
    path = sidecar_path(archive_path)
    with open(path + '.part', 'w') as f: json.dump(sidecar, f, indent=1, ensure_ascii=False)
    os.replace(path + '.part', path)


def read_sidecar(archive_path):
    """The sidecar of an archive, or None."""
    path = sidecar_path(archive_path)
    if not os.path.exists(path): return None
    with open(path) as f: sidecar = json.load(f)
    if sidecar.get('outcome') not in OUTCOMES: raise ValueError(f'{path}: outcome {sidecar.get("outcome")!r} is none of {OUTCOMES}')
    return sidecar


def domain_matches(cookie, host):
    """Whether a cookie of CDP's Network.getAllCookies may be set by a response from `host`: a host-only cookie by its own host, a domain cookie (leading dot) by the domain and its subdomains."""
    domain = cookie['domain'].lower(); host = host.lower()
    if not domain.startswith('.'): return host == domain
    bare = domain[1:]
    return host == bare or host.endswith('.' + bare)


def set_cookie_header(cookie):
    """One cookie as a `Set-Cookie` value, with the attributes the browser reported (path, domain for a domain cookie, Secure, HttpOnly, SameSite) and a fixed lifetime for a persistent one."""
    parts = [f'{cookie["name"]}={cookie["value"]}']
    if cookie['domain'].startswith('.'): parts.append(f'Domain={cookie["domain"][1:]}')
    parts.append(f'Path={cookie.get("path") or "/"}')
    if not cookie.get('session', cookie.get('expires', -1) in (-1, None)): parts.append(f'Max-Age={SERVED_MAX_AGE}')
    if cookie.get('secure'): parts.append('Secure')
    if cookie.get('httpOnly'): parts.append('HttpOnly')
    if cookie.get('sameSite') in ('Strict', 'Lax', 'None'): parts.append(f'SameSite={cookie["sameSite"]}')
    return '; '.join(parts)


def set_cookie_headers(sidecar, url):
    """The `Set-Cookie` values to add to a document response at `url`: nothing unless consent was given, and only the cookies the response's host may set. A Secure cookie goes out only over https."""
    if not sidecar or sidecar.get('outcome') != GIVEN: return []
    parts = urlsplit(url)
    return [set_cookie_header(c) for c in sidecar['cookies'] if domain_matches(c, parts.hostname or '') and (parts.scheme == 'https' or not c.get('secure'))]


def counts(pages):
    """How many manifest pages ended on each outcome (a manifest page carries `consent`)."""
    out = {o: 0 for o in OUTCOMES}
    for p in pages: out[p['consent']] = out.get(p['consent'], 0) + 1
    return out
