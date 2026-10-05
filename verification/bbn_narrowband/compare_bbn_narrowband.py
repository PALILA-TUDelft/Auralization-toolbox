"""
Verification: broadband TOC (1/3-octave) -> narrowband conversion.

Python side  : verification/bbn_narrowband/bbn_narrowband_<source>_python.npz
               written by broadband_synthesis_smooth.py under --verification.
               Keys: freq_bands, SPL_bands, freq_narrowband, SPL_narrowband, df
MATLAB side  : verification/bbn_narrowband/bbn_narrowband_<source>_matlab.mat

<source> is one of: engine, airframe, overall.
These are the curves in the MATLAB ConvertFreqBands "spl vs freq (1/3-OB and NB)" plot.
"""
import os
import sys
import numpy as np
import matplotlib.pyplot as plt

try:
    from scipy.io import loadmat
except ImportError:
    loadmat = None

FOLDER = os.path.dirname(__file__)

# Expected MATLAB variable names (adjust to match your export .m):
MAT_VARS = {
    "freq_bands": "freq_bands",
    "SPL_bands": "SPL_bands",
    "freq_narrowband": "freq_narrowband",
    "SPL_narrowband": "SPL_narrowband",
}


def main(source="engine"):
    py_path = os.path.join(FOLDER, f"bbn_narrowband_{source}_python.npz")
    mat_path = os.path.join(FOLDER, f"bbn_narrowband_{source}_matlab.mat")

    py = np.load(py_path)
    fb_py = np.squeeze(py["freq_bands"])
    sb_py = np.squeeze(py["SPL_bands"])
    fn_py = np.squeeze(py["freq_narrowband"])
    sn_py = np.squeeze(py["SPL_narrowband"])
    df = float(py["df"]) if "df" in py else np.nan

    have_mat = loadmat is not None and os.path.isfile(mat_path)

    # 1/3-octave band edges -- same formula as production plot_bbn_toc_to_narrowband
    # (utilities/plot_utils.py) and MATLAB's ConvertFreqBands plot block.
    b = 3
    G = 10 ** (3 / 10)
    f_lower = fb_py / G ** (1 / (2 * b))
    f_upper = fb_py * G ** (1 / (2 * b))

    fig, ax = plt.subplots(figsize=(9, 6))

    # Draw each 1/3-OB band as a proper step rectangle (top + two vertical
    # edges), matching the reference plots -- NOT scattered point markers.
    panam_handle = None
    for i in range(len(fb_py)):
        lines = ax.semilogx([f_lower[i], f_upper[i]], [sb_py[i]] * 2, color="black")
        ax.semilogx([f_lower[i]] * 2, [0, sb_py[i]], color="black")
        ax.semilogx([f_upper[i]] * 2, [0, sb_py[i]], color="black")
        if panam_handle is None:
            panam_handle = lines[0]

    # A handful of leading low-frequency bins can end up with no PANAM energy
    # assigned: some 1/3-OB bands below ~30 Hz are narrower than the df=10 Hz
    # FFT bin spacing, so by coincidence no bin lands inside that band's
    # window and its energy is silently dropped. SPL_narrowband is computed
    # as 20*log10(x/pref) with no epsilon (matching MATLAB's p2spl exactly),
    # so those bins are exactly -inf; mask non-finite values before drawing,
    # same as MATLAB's plotting naturally skipping them.
    valid_py = np.isfinite(sn_py)
    narrowband_line, = ax.semilogx(fn_py[valid_py], sn_py[valid_py], color="b")
    handles = [panam_handle, narrowband_line]
    labels = ["input: 1/3-OB", f"Equal Distribution (Py): $\\Delta f={df:.4g}$ Hz"]

    if have_mat:
        mat = loadmat(mat_path)
        fn_m = np.squeeze(mat[MAT_VARS["freq_narrowband"]])
        sn_m = np.squeeze(mat[MAT_VARS["SPL_narrowband"]])
        valid_m = np.isfinite(sn_m)
        mat_line, = ax.semilogx(fn_m[valid_m], sn_m[valid_m], "r--")
        handles.append(mat_line)
        labels.append("Narrowband (MATLAB)")

        # Numeric diff: only over bins finite on BOTH sides (an -inf vs -inf
        # comparison gives nan, which would silently corrupt max()/mean()).
        n = min(len(sn_py), len(sn_m))
        both_finite = np.isfinite(sn_py[:n]) & np.isfinite(sn_m[:n])
        n_excluded = n - int(both_finite.sum())
        diff = np.abs(sn_py[:n][both_finite] - sn_m[:n][both_finite])
        print(f"\n[BBN NARROWBAND COMPARISON — {source}]")
        print(f"  SPL_narrowband  max_abs={np.max(diff):.6e}  mean_abs={np.mean(diff):.6e}"
              f"  ({n_excluded} non-finite bin(s) excluded from this metric)")
    else:
        print(f"[INFO] {mat_path} not found — plotting Python vectors only.")

    ax.set_xlim(20, 15000)
    ax.set_ylim(bottom=0)
    ax.set_xlabel("Frequency, $f$ (Hz)")
    ax.set_ylabel("SPL, $L_{\\mathrm{p,Z}}$ (dB re 20 µPa)")
    ax.set_title(f"TOC -> narrowband — {source}")
    ax.legend(handles, labels, loc="lower left")
    ax.grid(True, which="both", linestyle="--", alpha=0.3)
    fig.tight_layout()
    plt.show()


if __name__ == "__main__":
    src = sys.argv[1] if len(sys.argv) > 1 else "engine"
    main(src)
