"""Check that Python AND MATLAB saved every file/variable needed for verification.

Usage:
    python verification/check_scenario_complete.py                      # every folder in verification/scenarios/
    python verification/check_scenario_complete.py scenario_1_isa_asphalt_mono
    python verification/check_scenario_complete.py --root path/to/scenario_dir --ini path/to.ini

Reports, per scenario, each required file/variable as OK / MISSING FILE / MISSING KEY.
Also compares scenario_params_python.json with scenario_params_matlab.json (if MATLAB
wrote one) so input mismatches are caught before you chase phantom "bugs".
Exit code 0 if nothing is missing on either side, 1 otherwise.
"""
import argparse
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, REPO)
sys.path.insert(0, HERE)

from manifest import required_entries  # noqa: E402

try:
    from scipy.io import whosmat
except ImportError:  # pragma: no cover
    whosmat = None

SCENARIO_ROOT = os.path.join(HERE, "scenarios")
INI_DIR = os.path.join(REPO, "input_data", "scenarios")


def _load_ini(scenario_dir, ini_path):
    """Prefer the params Python actually parsed; fall back to parsing the ini."""
    pj = os.path.join(scenario_dir, "scenario_params_python.json")
    if os.path.isfile(pj):
        with open(pj, encoding="utf-8") as fh:
            return json.load(fh)
    if ini_path is None:
        cand = os.path.join(INI_DIR, os.path.basename(os.path.normpath(scenario_dir)) + ".ini")
        ini_path = cand if os.path.isfile(cand) else None
    if ini_path is None:
        raise FileNotFoundError(
            f"No scenario_params_python.json in {scenario_dir} and no matching ini found; pass --ini")
    from utilities.ini_parser import ini2dict
    return ini2dict(ini_path)


def _npz_keys(path):
    with np.load(path, allow_pickle=True) as z:
        return set(z.files)


def _mat_keys(path):
    if whosmat is None:
        raise RuntimeError("scipy not installed -- cannot read .mat files")
    return {name for name, _, _ in whosmat(path)}


def _check_file(path, keys, reader):
    if not os.path.isfile(path):
        return "MISSING FILE", ""
    try:
        present = reader(path)
    except Exception as e:  # unreadable/corrupt file
        return "UNREADABLE", str(e)
    missing = [k for k in keys if k not in present]
    if missing:
        return "MISSING KEY", ", ".join(missing)
    return "OK", ""


def _compare_params(scenario_dir):
    """Return a list of mismatch strings (empty if identical or MATLAB params absent)."""
    py_p = os.path.join(scenario_dir, "scenario_params_python.json")
    ml_p = os.path.join(scenario_dir, "scenario_params_matlab.json")
    if not (os.path.isfile(py_p) and os.path.isfile(ml_p)):
        return None
    with open(py_p, encoding="utf-8") as fh:
        py = json.load(fh)
    with open(ml_p, encoding="utf-8") as fh:
        ml = json.load(fh)
    diffs = []
    for k, v in ml.items():
        if k == "ini_file" or k not in py:
            continue
        try:
            same = np.isclose(float(v), float(py[k]))
        except (TypeError, ValueError):
            same = str(v).strip().lower() == str(py[k]).strip().lower()
        if not same:
            diffs.append(f"{k}: python={py[k]!r} matlab={v!r}")
    return diffs


def check_scenario(scenario_dir, ini_path=None, verbose=True):
    """Return (n_missing_python, n_missing_matlab, rows)."""
    ini = _load_ini(scenario_dir, ini_path)
    rows = []
    for e in required_entries(ini):
        folder = os.path.join(scenario_dir, e["step"])
        for side, fname, keys, reader in (
            ("python", e["py_file"], e["py_keys"], _npz_keys),
            ("matlab", e["mat_file"], e["mat_keys"], _mat_keys),
        ):
            status, detail = _check_file(os.path.join(folder, fname), keys, reader)
            rows.append(dict(step=e["step"], side=side, file=fname, status=status, detail=detail))

    miss_py = sum(r["status"] != "OK" for r in rows if r["side"] == "python")
    miss_ml = sum(r["status"] != "OK" for r in rows if r["side"] == "matlab")

    if verbose:
        name = os.path.basename(os.path.normpath(scenario_dir))
        print(f"\n=== {name} ===")
        for r in rows:
            if r["status"] != "OK":
                print(f"  [{r['status']:<12}] {r['side']:<6} {r['step']}/{r['file']}"
                      + (f"  -> {r['detail']}" if r["detail"] else ""))
        n_py = sum(r["side"] == "python" for r in rows)
        n_ml = sum(r["side"] == "matlab" for r in rows)
        print(f"  python: {n_py - miss_py}/{n_py} complete   matlab: {n_ml - miss_ml}/{n_ml} complete")
        diffs = _compare_params(scenario_dir)
        if diffs is None:
            print("  inputs: scenario_params_matlab.json not found -- cannot confirm MATLAB used the same ini")
        elif diffs:
            print("  inputs: MISMATCH between Python and MATLAB parameters:")
            for d in diffs:
                print(f"     - {d}")
        else:
            print("  inputs: Python and MATLAB parameters match")
    return miss_py, miss_ml, rows


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("scenarios", nargs="*", help="scenario names under verification/scenarios (default: all)")
    ap.add_argument("--root", default=None, help="explicit scenario directory (overrides names)")
    ap.add_argument("--ini", default=None, help="ini file (only if no scenario_params_python.json exists)")
    args = ap.parse_args()

    if args.root:
        dirs = [args.root]
    elif args.scenarios:
        dirs = [os.path.join(SCENARIO_ROOT, s) for s in args.scenarios]
    else:
        dirs = sorted(os.path.join(SCENARIO_ROOT, d) for d in os.listdir(SCENARIO_ROOT)
                      if os.path.isdir(os.path.join(SCENARIO_ROOT, d))) if os.path.isdir(SCENARIO_ROOT) else []
    if not dirs:
        print("No scenario folders found.")
        return 1

    total_missing = 0
    for d in dirs:
        py, ml, _ = check_scenario(d, args.ini)
        total_missing += py + ml
    print(f"\nTOTAL missing/incomplete entries: {total_missing}")
    return 0 if total_missing == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
