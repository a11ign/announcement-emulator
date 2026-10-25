#!/usr/bin/env python3
"""python3 middleware/bundle/check_no_browser.py <bundle directory | bundle .tar.gz or .tar.xz>

Fails (exit 1, one line for each entry) on an entry of the runtime bundle that is a browser or a browser library. The middleware runs in the Chromium the team's Playwright installed (A11-230),
so the bundle holds none. The rule is a closed list of patterns, and it names what a Chrome for Testing archive and the libraries it needs contain, so that a browser put back in is found
by what it is called and not by how big it is."""
import os, re, sys, tarfile

BROWSER_DIRECTORIES = {'chrome', 'chromium', 'libs', 'chrome-linux64', 'chrome-mac-arm64', 'chrome-headless-shell-linux64', 'chrome-headless-shell-mac-arm64'}
BROWSER_FILES = re.compile(r'^(chrome|chromium|chrome-wrapper|chrome_sandbox|chrome_crashpad_handler|headless_shell|chrome-headless-shell|xvfb|xvfb-run)$|^Google Chrome|^Chromium$', re.I)
BROWSER_LIBRARIES = re.compile(r'^lib(nss3|nssutil3|gbm|atk|atk-bridge|asound|cups)\b', re.I)
BROWSER_BUNDLES = re.compile(r'\.app$')      # a macOS application bundle (the one a browser comes in) has a Contents directory; terminfo's iTerm.app, a file, does not


def offending(names):
    """The entries among `names` (paths inside the bundle) that are a browser or a browser library, each with the rule it broke."""
    found = []
    for name in names:
        parts = [p for p in name.replace('\\', '/').split('/') if p and p != '.']
        for i, part in enumerate(parts):
            if part in BROWSER_DIRECTORIES: found.append((name, f'a browser or library directory ({part}/)')); break
            if BROWSER_BUNDLES.search(part) and parts[i + 1:i + 2] == ['Contents']: found.append((name, f'an application bundle ({part})')); break
        else:
            if parts and BROWSER_FILES.search(parts[-1]): found.append((name, f'a browser executable ({parts[-1]})'))
            elif parts and BROWSER_LIBRARIES.search(parts[-1]): found.append((name, f'a browser library ({parts[-1]})'))
    return found


def names_in(path):
    if os.path.isdir(path):
        for root, directories, files in os.walk(path):
            for entry in directories + files: yield os.path.relpath(os.path.join(root, entry), path)
    else:
        with tarfile.open(path) as archive:
            for member in archive: yield member.name


def main(argv):
    if len(argv) != 2: print(__doc__, file=sys.stderr); return 2
    found = offending(names_in(argv[1]))
    for name, why in found: print(f'{name}: {why}', file=sys.stderr)
    print(f'{argv[1]}: ' + (f'{len(found)} entries are a browser or a browser library' if found else 'no browser and no browser library'))
    return 1 if found else 0


if __name__ == '__main__': sys.exit(main(sys.argv))
