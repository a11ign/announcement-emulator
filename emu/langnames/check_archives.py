"""Check that the replay archives about to be read are the ones A11-165 recorded: each file's sha256 against the committed manifest.

    python3 emu/langnames/check_archives.py <run dir> [<manifest>]      # exit 1 on any mismatch or missing archive"""
import hashlib, json, pathlib, sys

HERE = pathlib.Path(__file__).resolve().parent
MANIFEST = HERE.parent.parent / 'q3' / 'results' / 'replay' / 'archive-manifest.json'


def mismatches(run_dir, manifest=MANIFEST):
    """(slug, why) for each page of the manifest whose archive under `run_dir` is missing or is not the recorded bytes, and how many pages the manifest has."""
    pages = json.loads(pathlib.Path(manifest).read_text(encoding='utf-8'))['pages']
    bad = []
    for page in pages:
        path = pathlib.Path(run_dir) / page['archive']
        if not path.exists(): bad.append((page['slug'], 'missing'))
        elif hashlib.sha256(path.read_bytes()).hexdigest() != page['sha256']: bad.append((page['slug'], 'sha256 differs from the manifest'))
    return bad, len(pages)


def main(argv):
    if not argv: sys.exit(__doc__)
    bad, n = mismatches(argv[0], *argv[1:2])
    for slug, why in bad: print(f'FAIL  {slug}: {why}')
    print(f'{n - len(bad)} of {n} archives are the recorded bytes')
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
