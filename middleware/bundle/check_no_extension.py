#!/usr/bin/env python3
"""The rules for an extension in the runtime bundle; check_no_browser.py runs them (python3 middleware/bundle/check_no_browser.py <bundle directory | bundle archive>), so that the one command the build and CI run guards both.

An entry of the runtime bundle that is a browser extension or the switch away from one fails the build (exit 1, one line for each entry). The tree comes through the browser's DevTools port and nothing else
(A11-229, the chairman, 2026-10-25), so the lean bundle carries no extension and no extension-only code (A11-231). The rules are a closed list: where the extension's files lived (emu/ext2/, q1/ext-id.txt),
a packed extension (*.crx), a manifest that declares manifest_version (an extension's; site-packages holds other manifest.json files, so python/ and any site-packages are not read), and the runtime's fallback.py, which chose
between the extension and DevTools."""
import os, re, tarfile

EXTENSION_PATHS = (('emu', 'ext2'), ('q1', 'ext-id.txt'), ('middleware', 'runtime', 'fallback.py'))
EXTENSION_PACKAGE = re.compile(r'\.crx$', re.I)
EXTENSION_MANIFEST = re.compile(rb'"manifest_version"\s*:')
MANIFEST_BYTES = 1 << 20      # an extension's manifest is a few hundred bytes; a larger manifest.json is not read past its first megabyte


def parts_of(name):
    return [p for p in name.replace('\\', '/').split('/') if p and p != '.']


def is_manifest(parts):
    return bool(parts) and parts[-1] == 'manifest.json' and parts[0] != 'python' and 'site-packages' not in parts


def extension_path_in(parts):
    """The one of EXTENSION_PATHS that `parts` runs through (wherever the bundle is rooted), or None."""
    return next((path for path in EXTENSION_PATHS if any(tuple(parts[i:i + len(path)]) == path for i in range(len(parts)))), None)


def offending(names, read):
    """The entries among `names` (paths inside the bundle) that are an extension, each with the rule it broke. `read(name)` gives the first bytes of a manifest.json (None if it cannot be read)."""
    found = []
    for name in names:
        parts = parts_of(name)
        path = extension_path_in(parts)
        if path: found.append((name, f'an extension or its switch ({"/".join(path)})'))
        elif parts and EXTENSION_PACKAGE.search(parts[-1]): found.append((name, f'a packed extension ({parts[-1]})'))
        elif is_manifest(parts) and EXTENSION_MANIFEST.search(read(name) or b''): found.append((name, 'an extension manifest (declares manifest_version)'))
    return found


def manifests_in(path):
    """The first bytes of each manifest.json outside python/ in a bundle directory or archive, by its name there."""
    held = {}
    if os.path.isdir(path):
        for root, _, files in os.walk(path):
            for entry in files:
                name = os.path.relpath(os.path.join(root, entry), path)
                if is_manifest(parts_of(name)) and not os.path.islink(os.path.join(root, entry)):
                    with open(os.path.join(root, entry), 'rb') as f: held[name] = f.read(MANIFEST_BYTES)
    else:
        with tarfile.open(path) as archive:
            for member in archive:
                if (member.isfile() or member.islnk()) and is_manifest(parts_of(member.name)): held[member.name] = archive.extractfile(member).read(MANIFEST_BYTES)
    return held
