"""The two views of a static-copy oracle that the Q3 scripts need (A11-155).

    python make_views.py <static_oracle_dir> <orig_dir> <run_dir> <run_base>

`run_all.py` runs the emulator on `capture.url` and `measure.py` splits, compares and prints by `capture.url`. For a copy, those are two different addresses, and neither script is to change (the split rule is a function of the ORIGINAL address):
  <orig_dir>  each record with `capture.url` = the original address (`staticOf`): `measure.py` reads this one;
  <run_dir>   each record with `capture.url` = `<run_base>/<slug>/index.html` (the emulator's own address of the same copy, e.g. http://127.0.0.1:8001): `run_all.py` reads this one, with `--split all`.
The emulator's outputs are named by the slug, which both views share."""
import sys, os, json, glob
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
import corpus_capture as cc

def main(src, orig_dir, run_dir, run_base):
    os.makedirs(orig_dir, exist_ok=True); os.makedirs(run_dir, exist_ok=True); n = 0
    for f in sorted(glob.glob(os.path.join(src, '*.json'))):
        rec = json.load(open(f)); original = rec['staticOf']; name = os.path.basename(f)
        view = json.loads(json.dumps(rec)); view['capture']['url'] = original; json.dump(view, open(os.path.join(orig_dir, name), 'w'))
        run = json.loads(json.dumps(rec)); run['capture']['url'] = f"{run_base.rstrip('/')}/{cc.slug_of(original)}/index.html"; json.dump(run, open(os.path.join(run_dir, name), 'w'))
        n += 1
    print(n, 'records in each view')

if __name__ == '__main__':
    if len(sys.argv) != 5: sys.exit(__doc__)
    main(*sys.argv[1:])
