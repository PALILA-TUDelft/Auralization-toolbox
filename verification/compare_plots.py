"""Side-by-side comparison of the MATLAB and Python figures of every scenario.

Both toolboxes save their figures with the same naming scheme,
    <results>/<scenario>/results_auralization/Receiver_<n>/<scenario>_Receiver_<n>_<name>.png|pdf
    <results>/<scenario>/results_auralization/flight_profile_<scenario>.png|pdf
so the figures are paired by <name>. The tool writes one HTML page per scenario (MATLAB left, Python right) plus an
index with the number of paired figures and the figures that exist on one side only.

The figures are COPIED next to the pages (folder `assets/<scenario>/`, short file names, relative links): the MATLAB
results usually live in a very deep folder (OneDrive), and browsers on Windows cannot open file paths of 260 characters
or more, which showed up as "It may have been moved, edited, or deleted". As a bonus the output folder is
self-contained and can be zipped or moved. PNGs are scaled down to --max-width pixels (default 1600) so that the pages
load quickly; PDFs are copied unchanged; --full-res copies the PNGs as they are.

Python figures come from   python verification/run_scenarios.py --figures all   (see run_scenarios.py).

Usage:
    python verification/compare_plots.py                          # every scenario found in input_data/scenarios
    python verification/compare_plots.py 3 6                      # scenario numbers or name substrings
    python verification/compare_plots.py --matlab-results "<matlab toolbox>/results_auralization"
    python verification/compare_plots.py --full-res --open        # original resolution, open the index afterwards

The MATLAB results folder can also be given once through the environment variable MATLAB_RESULTS_DIR.
"""
import argparse
import html
import os
import re
import shutil
import sys
import webbrowser
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
INI_DIR = REPO / "input_data" / "scenarios"

DEFAULT_MATLAB_RESULTS = (
    r"C:\Users\tocas\OneDrive\Documents\University\MSc\Open_Your_Ears_Project\Original Code"
    r"\auralization_master-main\results_auralization"
)
FORMATS = ("png", "pdf")          # preference order when both sides have several


def scenario_names(tokens):
    names = sorted(p.stem for p in INI_DIR.glob("*.ini"))
    if not tokens:
        return names
    out = []
    for n in names:
        for t in tokens:
            if (t.isdigit() and n.startswith(f"scenario_{t}_")) or (not t.isdigit() and t in n):
                out.append(n)
                break
    return out


def collect(results_root, scenario):
    """{key: {ext: Path}} for one side. key = 'R<n>: <name>' for receiver figures, '<name>' for case-level ones."""
    base = Path(results_root) / scenario / "results_auralization"
    found = {}
    if not base.is_dir():
        return found
    rx = re.compile(rf"^{re.escape(scenario)}_Receiver_(\d+)_(.+)\.(png|pdf)$", re.IGNORECASE)
    rx_case = re.compile(rf"^(.+?)_{re.escape(scenario)}\.(png|pdf)$", re.IGNORECASE)
    for f in base.rglob("*"):
        if not f.is_file():
            continue
        m = rx.match(f.name)
        if m:
            key = f"R{m.group(1)}: {m.group(2).replace(' ', '')}"
            ext = m.group(3).lower()
        else:
            m = rx_case.match(f.name)
            if not m:
                continue
            key, ext = m.group(1).replace(" ", ""), m.group(2).lower()
        found.setdefault(key, {})[ext] = f
    return found


def pick(m_files, p_files):
    """Choose the file to show on each side: a format both have (png first), else each side's own best."""
    for ext in FORMATS:
        if ext in m_files and ext in p_files:
            return m_files[ext], p_files[ext]
    best = lambda d: next((d[e] for e in FORMATS if e in d), None)  # noqa: E731
    return best(m_files) if m_files else None, best(p_files) if p_files else None


def long_path(p):
    """Windows extended-length form, so that copying from very deep folders works."""
    p = os.path.abspath(str(p))
    return "\\\\?\\" + p if os.name == "nt" and not p.startswith("\\\\?\\") else p


def stage(src, dest, max_width):
    """Copy src to dest (PNG scaled down to max_width if given). Skips work if dest is already up to date.
    Returns the size of the staged file in bytes."""
    src_l, dest_l = long_path(src), long_path(dest)
    if os.path.exists(dest_l) and os.path.getmtime(dest_l) >= os.path.getmtime(src_l):
        return os.path.getsize(dest_l)
    os.makedirs(os.path.dirname(dest_l), exist_ok=True)
    if src.suffix.lower() == ".png" and max_width:
        from PIL import Image
        Image.MAX_IMAGE_PIXELS = None
        with Image.open(src_l) as im:
            if im.width > max_width:
                im = im.resize((max_width, round(im.height * max_width / im.width)), Image.LANCZOS)
            else:
                im = im.copy()
            im.save(dest_l, format="PNG", optimize=True)
    else:
        shutil.copyfile(src_l, dest_l)
    return os.path.getsize(dest_l)


def cell(rel_href, orig_name, size):
    if rel_href is None:
        return '<div class="missing">not available</div>'
    if rel_href.lower().endswith(".pdf"):
        body = f'<embed src="{rel_href}" type="application/pdf" width="100%" height="520">'
    else:
        body = f'<a href="{rel_href}"><img src="{rel_href}" loading="lazy"></a>'
    return f'{body}<div class="cap">{html.escape(orig_name)} ({size / 1e6:.1f} MB)</div>'


CSS = """
:root{color-scheme:light dark;font-family:system-ui,sans-serif}
body{margin:16px auto;max-width:1500px;padding:0 16px}
table{border-collapse:collapse;width:100%}
td,th{border:1px solid #8884;padding:6px;vertical-align:top}
th{position:sticky;top:0;background:Canvas;z-index:1}
img{width:100%;height:auto}
.cap{font-size:12px;opacity:.7;margin-top:2px;word-break:break-all}
.missing{padding:40px;text-align:center;opacity:.6;background:#8882}
h2{margin:24px 0 8px}
.only{background:#f803}
"""


def write_scenario_page(out_dir, scenario, matlab, python, max_width):
    keys = sorted(set(matlab) | set(python))
    rows = []
    n_pair = 0
    for i, k in enumerate(keys, start=1):
        m_path, p_path = pick(matlab.get(k, {}), python.get(k, {}))
        cells = []
        for side, path in (("matlab", m_path), ("python", p_path)):
            if path is None:
                cells.append(cell(None, "", 0))
                continue
            rel = f"assets/{scenario}/{i:02d}_{side}{path.suffix.lower()}"
            size = stage(path, out_dir / rel, max_width)
            cells.append(cell(rel, path.name, size))
        both = m_path is not None and p_path is not None
        n_pair += both
        rows.append(f'<tr{"" if both else " class=only"}><td colspan="2"><b>{html.escape(k)}</b>'
                    f'{"" if both else " &mdash; only on one side"}</td></tr>'
                    f"<tr><td>{cells[0]}</td><td>{cells[1]}</td></tr>")
    page = (f"<!doctype html><meta charset=utf-8><title>{html.escape(scenario)}</title><style>{CSS}</style>"
            f"<p><a href=index.html>&larr; index</a></p><h1>{html.escape(scenario)}</h1>"
            f"<p>{n_pair} paired, {len(keys) - n_pair} on one side only. Click an image for the staged file.</p>"
            f"<table><tr><th>MATLAB</th><th>Python</th></tr>{''.join(rows)}</table>")
    (out_dir / f"{scenario}.html").write_text(page, encoding="utf-8")
    only_m = sorted(k for k in keys if k in matlab and k not in python)
    only_p = sorted(k for k in keys if k in python and k not in matlab)
    return n_pair, only_m, only_p


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("scenarios", nargs="*", help="scenario numbers or name substrings (default: all)")
    ap.add_argument("--matlab-results", default=os.environ.get("MATLAB_RESULTS_DIR", DEFAULT_MATLAB_RESULTS),
                    help="MATLAB toolbox results_auralization folder (holds one sub-folder per scenario)")
    ap.add_argument("--python-results", default=str(REPO / "results_auralization"),
                    help="Python results_auralization folder (default: this repository's)")
    ap.add_argument("--out", default=str(HERE / "plot_comparison"), help="folder for the generated HTML pages")
    ap.add_argument("--max-width", type=int, default=1600, help="scale PNGs down to this width in pixels (default 1600)")
    ap.add_argument("--full-res", action="store_true", help="copy the PNGs at their original resolution")
    ap.add_argument("--open", action="store_true", help="open the index in the default browser")
    args = ap.parse_args()

    names = scenario_names(args.scenarios)
    if not names:
        print("No matching scenarios.")
        return 1
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    max_width = None if args.full_res else args.max_width

    lines = []
    print(f"MATLAB results: {args.matlab_results}\nPython results: {args.python_results}\n")
    for s in names:
        matlab = collect(args.matlab_results, s)
        python = collect(args.python_results, s)
        n_pair, only_m, only_p = write_scenario_page(out_dir, s, matlab, python, max_width)
        print(f"{s}: MATLAB {len(matlab)} figures, Python {len(python)} figures, {n_pair} paired")
        if only_m:
            print(f"     only MATLAB: {', '.join(only_m)}")
        if only_p:
            print(f"     only Python: {', '.join(only_p)}")
        lines.append(f'<tr><td><a href="{s}.html">{html.escape(s)}</a></td><td>{len(matlab)}</td><td>{len(python)}</td>'
                     f"<td>{n_pair}</td><td>{html.escape(', '.join(only_m))}</td><td>{html.escape(', '.join(only_p))}</td></tr>")
    index = (f"<!doctype html><meta charset=utf-8><title>Plot comparison</title><style>{CSS}</style>"
             "<h1>MATLAB vs Python figures</h1><table><tr><th>scenario</th><th>MATLAB</th><th>Python</th><th>paired</th>"
             f"<th>only MATLAB</th><th>only Python</th></tr>{''.join(lines)}</table>")
    (out_dir / "index.html").write_text(index, encoding="utf-8")
    print(f"\nWritten: {out_dir / 'index.html'}")
    if args.open:
        webbrowser.open((out_dir / "index.html").resolve().as_uri())
    return 0


if __name__ == "__main__":
    sys.exit(main())
