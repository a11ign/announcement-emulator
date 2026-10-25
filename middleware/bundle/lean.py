#!/usr/bin/env python3
"""python3 middleware/bundle/lean.py <bundle directory> <keep file>

Makes the runtime bundle lean (A11-231), in place: the full layout in, and out only what keep/<platform>.txt lists (the files a trace of the runtime read, trace.sh) and what is kept whatever the trace says.

    Python        the interpreter; the standard library's modules and extension modules the list names, as bytecode alone (build.sh compiled the standard library, so a module with a .pyc beside its
                  .py is shipped as the .pyc); the whole `encodings` package (a page's charset picks a codec at run time, which a run does not exhaust); the licence; and each site-packages
                  distribution that has a listed file, whole, with its dist-info and so its licence. No tests, idle, tkinter, ensurepip, pydoc data, headers, static libraries or caches
    NVDA          one tree, nvda-src/source: the listed files, locale/en, and NVDA's licence. The pinned CLDR names are copied over NVDA's own file in place; there is no second tree (nvda-appdir),
                  no cldr-src and no chromium-src
    the rest      this repository's runtime (emu, q1, q2, q3, middleware), bundle.json and the licence, as they are

A file the list names that the full layout lacks fails the run: the list is stale (NVDA or the Python moved), and trace.sh makes it again.
"""
import os, re, shutil, subprocess, sys

PYTHON_LIB = re.compile(r'^(python/lib/python3\.\d+)/')
ALWAYS = [re.compile(p) for p in (
    r'^(bundle\.json|LICENSE|nvda-src/copying\.txt)$',
    r'^python/bin/python3(\.\d+)?$',
    r'^python/lib/python3\.\d+/(LICENSE\.txt|encodings/.*)$',
    r'^nvda-src/source/locale/en/.*',
)]
RUNTIME = ('emu/', 'q1/', 'q2/', 'q3/', 'middleware/')      # this repository's own, a few hundred KB: kept whole
PRUNED = ('python/', 'nvda-src/')


def read_keep(path):
    with open(path) as f: return {line.strip() for line in f if line.strip() and not line.startswith('#')}


def library_of(rel):
    match = PYTHON_LIB.match(rel)
    return match.group(1) if match else None


def top_of_site_packages(rel):
    """The first name under a site-packages directory ('requests' for .../site-packages/requests/api.py), or None."""
    match = re.match(r'^python/lib/python3\.\d+/site-packages/([^/]+)', rel)
    return match.group(1) if match else None


def module_name(entry):
    """site-packages/fast_diff_match_patch.cpython-313-x86_64-linux-gnu.so and site-packages/nh3 are the modules fast_diff_match_patch and nh3."""
    return entry.split('.')[0].lower()


def python_libraries(root):
    """The names of the standard-library directories under python/lib ('python3.13')."""
    return sorted(d for d in os.listdir(os.path.join(root, 'python', 'lib')) if re.match(r'python3\.\d+$', d))


def distributions_kept(root, tops):
    """The *.dist-info directories whose distribution has a module in `tops` (its top_level.txt, else its name)."""
    kept = set()
    for lib in python_libraries(root):
        site = os.path.join(root, 'python', 'lib', lib, 'site-packages')
        if not os.path.isdir(site): continue
        for entry in sorted(os.listdir(site)):
            if not entry.endswith('.dist-info'): continue
            listing = os.path.join(site, entry, 'top_level.txt')
            if os.path.exists(listing):
                with open(listing) as f: provides = [l.strip() for l in f]
            else: provides = [entry.rsplit('-', 1)[0].replace('-', '_')]
            if any(module_name(p) in tops for p in provides if p): kept.add(f'python/lib/{lib}/site-packages/{entry}')
    return kept


def files_of(root):
    """Every file and link of the tree as a bundle-relative path, in order."""
    for here, directories, names in os.walk(root):
        directories.sort()
        for name in sorted(names + [d for d in directories if os.path.islink(os.path.join(here, d))]):
            yield os.path.relpath(os.path.join(here, name), root).replace(os.sep, '/')


def wanted(rel, keep):
    """Whether a path is kept whatever the trace says, or because it is listed."""
    return rel.startswith(RUNTIME) or any(p.match(rel) for p in ALWAYS) or rel in keep


def decide(root, keep):
    """The set of paths (files and links) to keep from the tree at `root`, given the listed paths."""
    present = set(files_of(root))
    tops = {module_name(top_of_site_packages(p)) for p in keep if top_of_site_packages(p)}
    dists = distributions_kept(root, tops)
    kept = set()
    for rel in present:
        if '/__pycache__/' in rel: continue
        if wanted(rel, keep) or (rel.endswith('.pyc') and library_of(rel) and wanted(rel[:-1], keep)): kept.add(rel); continue      # the bytecode build.sh compiled beside a module that is wanted
        top = top_of_site_packages(rel)
        if top and (module_name(top) in tops or any(rel.startswith(d + '/') for d in dists)): kept.add(rel)
    # a standard-library .py that has its .pyc beside it ships as the .pyc alone
    for rel in sorted(kept):
        if rel.endswith('.py') and library_of(rel) and not top_of_site_packages(rel) and rel + 'c' in present:
            kept.discard(rel); kept.add(rel + 'c')
    return kept


def prune(root, keep):
    """Remove everything from `root` that is not kept; returns the number of files removed. Fails when `keep` names a file the tree lacks."""
    present = set(files_of(root))
    stale = sorted(p for p in keep if p.startswith(PRUNED) and p not in present)
    if stale: raise SystemExit('the keep list names ' + str(len(stale)) + ' files the full layout lacks, such as ' + ', '.join(stale[:3]) + ': run middleware/bundle/trace.sh again')
    kept = decide(root, keep)
    removed = 0
    for rel in sorted(present - kept):
        os.unlink(os.path.join(root, rel)); removed += 1
    for here, directories, names in os.walk(root, topdown=False):      # a link that is left pointing at nothing, then every directory that is left empty
        for name in names:
            path = os.path.join(here, name)
            if os.path.islink(path) and not os.path.exists(path): os.unlink(path)
        for name in directories:
            path = os.path.join(here, name)
            if os.path.islink(path):
                if not os.path.exists(path): os.unlink(path)
            elif not os.listdir(path): os.rmdir(path)
    for lib in python_libraries(root):
        os.makedirs(os.path.join(root, 'python', 'lib', lib, 'lib-dynload'), exist_ok=True)      # where the interpreter looks for its extension modules: without it, it warns at every start that it "could not find platform dependent libraries"
    return removed


def overlay_in_place(root):
    """The pinned CLDR names go over NVDA's own file where it is, and the overlay, the CLDR checkout and the Chromium sources go: one copy of NVDA."""
    names = os.path.join(root, 'cldr-src', 'locale', 'en', 'cldr.dic')
    if os.path.exists(names): shutil.copyfile(names, os.path.join(root, 'nvda-src', 'source', 'locale', 'en', 'cldr.dic'))
    for extra in ('nvda-appdir', 'cldr-src', 'chromium-src'): shutil.rmtree(os.path.join(root, extra), ignore_errors=True)


def make_lean(root, keep):
    overlay_in_place(root)
    for here, directories, _ in os.walk(root):      # the caches pip and the compile left; the interpreter writes none (PYTHONDONTWRITEBYTECODE)
        for name in [d for d in directories if d == '__pycache__']:
            shutil.rmtree(os.path.join(here, name)); directories.remove(name)
    return prune(root, keep)


def main(argv):
    if len(argv) != 3: print(__doc__, file=sys.stderr); return 2
    removed = make_lean(os.path.abspath(argv[1]), read_keep(argv[2]))
    print(f'{argv[1]}: {removed} files removed')
    return 0


if __name__ == '__main__': sys.exit(main(sys.argv))
