"""Run every scenario in input_data/scenarios in a chain, then check + grade each one.

For each scenario <name> (= ini file stem) this:
  1. deletes stale *_python.npz / scenario_params_python.json in verification/scenarios/<name>/
     (MATLAB files are never touched)
  2. runs   python main.py --ini <ini> --tag <name> --verification
                            --verification-dir verification/scenarios/<name>
     with the log saved to verification/scenarios/<name>/run_python.log
  3. runs   check_scenario_complete.py  (did Python AND MATLAB save everything?)
  4. runs   run_all_verifications.py --root verification/scenarios/<name>
     with the report saved to verification/scenarios/<name>/grade_report.txt
and prints one summary table at the end.

Usage:
    python verification/run_scenarios.py                    # all scenarios
    python verification/run_scenarios.py --only 1 3         # by number or name substring
    python verification/run_scenarios.py --skip-run         # only check + grade existing dumps
                                                            # (use after the MATLAB side has run)
    python verification/run_scenarios.py --figures all      # also save all figures (default: none), see below
    python verification/run_scenarios.py --figures trim_data,propagation_tf   # only some figure keys
    python verification/run_scenarios.py --only 3 --figures all --figure-formats png
    python verification/run_scenarios.py --stop-on-error

Figures: with --figures all (or a comma list of keys, see main.FIGURE_KEYS) the figures are saved next to the
wav file, in results_auralization/<scenario>/results_auralization/Receiver_<n>/<scenario>_Receiver_<n>_<name>.png|pdf
-- the same folder layout and file names the MATLAB toolbox uses, so verification/compare_plots.py can pair them.

Exit code 0 only if every selected scenario ran, is complete on both sides and has no FAILs.
"""
import argparse
import glob
import os
import re
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
INI_DIR = os.path.join(REPO, "input_data", "scenarios")
SCENARIO_ROOT = os.path.join(HERE, "scenarios")

sys.path.insert(0, HERE)
from check_scenario_complete import check_scenario  # noqa: E402


def warn_if_scenario0_differs():
    """Scenario 0 is a copy of input_data/input_file_auralization.ini (which has to stay where it is: the default
    runs look for exactly one .ini there). Warn if the two drift apart."""
    original = os.path.join(REPO, "input_data", "input_file_auralization.ini")
    copies = glob.glob(os.path.join(INI_DIR, "scenario_0_*.ini"))
    if not (os.path.isfile(original) and copies):
        return
    norm = lambda p: open(p, "rb").read().replace(b"\r\n", b"\n")  # noqa: E731
    for c in copies:
        if norm(c) != norm(original):
            print(f"WARNING: {os.path.basename(c)} differs from input_data/input_file_auralization.ini; "
                  "scenario 0 is meant to be a verbatim copy of it.")


def find_scenarios(only):
    inis = sorted(glob.glob(os.path.join(INI_DIR, "*.ini")))
    if not only:
        return inis
    picked = []
    for ini in inis:
        stem = os.path.splitext(os.path.basename(ini))[0]
        for token in only:
            # a bare number matches "scenario_<n>_..." exactly; anything else is a substring
            if (token.isdigit() and stem.startswith(f"scenario_{token}_")) or \
               (not token.isdigit() and token in stem):
                picked.append(ini)
                break
    return picked


def run_logged(cmd, log_path, cwd=REPO):
    """Run cmd, streaming output to the console and to log_path. Return exit code."""
    # MPLBACKEND=Agg: figures are saved to disk, never shown (plt.show() would block the chain on a GUI backend)
    env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUNBUFFERED="1", MPLBACKEND="Agg")
    with open(log_path, "w", encoding="utf-8") as log:
        proc = subprocess.Popen(cmd, cwd=cwd, env=env, stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace")
        for line in proc.stdout:
            sys.stdout.write("    | " + line)
            log.write(line)
        return proc.wait()


def clean_stale_python_dumps(scenario_dir):
    if not os.path.isdir(scenario_dir):
        return
    n = 0
    for pattern in ("*/*_python.npz", "*/python_trimmed_output.npz", "scenario_params_python.json"):
        for f in glob.glob(os.path.join(scenario_dir, pattern)):
            os.remove(f)
            n += 1
    if n:
        print(f"  removed {n} stale Python dump(s)")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--only", nargs="+", default=None, help="scenario numbers or name substrings")
    ap.add_argument("--skip-run", action="store_true", help="do not run Python; just check + grade")
    ap.add_argument("--figures", default="none",
                    help="'none' (default, faster), 'all', or a comma-separated list of figure keys (main.FIGURE_KEYS)")
    ap.add_argument("--figure-formats", default=None,
                    help="comma-separated file formats for the saved figures (png, pdf); default: both")
    ap.add_argument("--stop-on-error", action="store_true", help="abort the chain on the first failed run")
    args = ap.parse_args()

    warn_if_scenario0_differs()
    inis = find_scenarios(args.only)
    if not inis:
        print(f"No scenario .ini files found in {INI_DIR} matching {args.only}")
        return 1

    summary = []
    for ini in inis:
        name = os.path.splitext(os.path.basename(ini))[0]
        sdir = os.path.join(SCENARIO_ROOT, name)
        os.makedirs(sdir, exist_ok=True)
        row = dict(name=name, run="skipped", secs=0.0, miss_py=None, miss_ml=None,
                   pass_=None, fail=None, skip=None, na=None)
        print("\n" + "#" * 100 + f"\n# {name}\n" + "#" * 100)

        if not args.skip_run:
            clean_stale_python_dumps(sdir)
            cmd = [sys.executable, "main.py", "--ini", ini, "--tag", name,
                   "--results", os.path.join("results_auralization", name),
                   "--verification", "--verification-dir", sdir]
            fig = args.figures.strip().lower()
            if fig == "none":
                cmd += ["--figures", "none", "--no-save-figs"]
            elif fig != "all":                      # 'all' = main.py default: every figure, saved to disk
                cmd += ["--figures", args.figures]
            if args.figure_formats:
                cmd += ["--figure-formats", args.figure_formats]
            print("  running:", " ".join(cmd))
            t0 = time.time()
            rc = run_logged(cmd, os.path.join(sdir, "run_python.log"))
            row["secs"] = time.time() - t0
            row["run"] = "ok" if rc == 0 else f"FAILED (exit {rc})"
            if rc != 0:
                print(f"  !! run failed, see {os.path.relpath(os.path.join(sdir, 'run_python.log'), REPO)}")
                summary.append(row)
                if args.stop_on_error:
                    break
                continue

        # completeness
        try:
            row["miss_py"], row["miss_ml"], _ = check_scenario(sdir, ini)
        except Exception as e:  # e.g. Python params json absent because the run never produced it
            print(f"  completeness check error: {e}")

        # grading
        report = os.path.join(sdir, "grade_report.txt")
        rc = run_logged([sys.executable, os.path.join("verification", "run_all_verifications.py"),
                         "--root", sdir], report)
        with open(report, encoding="utf-8", errors="replace") as fh:
            m = re.search(r"PASS:\s*(\d+)\s+FAIL:\s*(\d+)\s+SKIP:\s*(\d+)(?:\s+N/A:\s*(\d+))?", fh.read())
        if m:
            row["pass_"], row["fail"], row["skip"] = (int(x) for x in m.groups()[:3])
            row["na"] = int(m.group(4) or 0)
        summary.append(row)

    # ------------------------------------------------------------------ summary
    def fmt(v):
        return "-" if v is None else str(v)

    print("\n" + "=" * 100 + "\nSCENARIO CHAIN SUMMARY\n" + "=" * 100)
    print(f"{'scenario':<42}{'python run':<18}{'missing py':>11}{'missing ml':>11}{'PASS':>6}{'FAIL':>6}{'SKIP':>6}{'N/A':>5}")
    ok = True
    for r in summary:
        print(f"{r['name']:<42}{r['run']:<18}{fmt(r['miss_py']):>11}{fmt(r['miss_ml']):>11}"
              f"{fmt(r['pass_']):>6}{fmt(r['fail']):>6}{fmt(r['skip']):>6}{fmt(r['na']):>5}")
        if r["run"].startswith("FAILED") or r["miss_py"] or r["miss_ml"] or r["fail"] or r["fail"] is None:
            ok = False
    print("=" * 100)
    print("Per-scenario logs/reports: verification/scenarios/<name>/{run_python.log,grade_report.txt}")
    if any(r["miss_ml"] for r in summary):
        print("MATLAB dumps are missing for some scenarios: run the MATLAB toolbox with the same ini, "
              "then re-run with --skip-run.")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
