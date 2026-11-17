"""
Verification: atmospheric transfer function FIR-vs-ART magnitude comparison.

Python side  : verification/fir_transfer_function/fir_transfer_function_combined_python.npz
               (or _direct, depending on consider_ground_reflection), written by
               apply_propagation.py under --verification.
               Keys: freq_fir, mag_fir, freq_art, mag_art, t_block, n_taps
MATLAB side  : verification/fir_transfer_function/fir_transfer_function_combined_matlab.mat
               (or _direct)

Reproduces MATLAB's PLOT_FIR.m layout: main magnitude plot (ART vs FIR) plus
a right-axis FIR-ART delta when the two frequency vectors have equal length.
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

MAT_VARS = {
    "freq_fir": "freq_fir",
    "mag_fir": "mag_fir",
    "freq_art": "freq_art",
    "mag_art": "mag_art",
    "n_taps": "n_taps",
}


def main(variant="combined"):
    py_path = os.path.join(FOLDER, f"fir_transfer_function_{variant}_python.npz")
    mat_path = os.path.join(FOLDER, f"fir_transfer_function_{variant}_matlab.mat")

    py = np.load(py_path)
    freq_fir_py = np.squeeze(py["freq_fir"])
    mag_fir_py = np.squeeze(py["mag_fir"])
    freq_art_py = np.squeeze(py["freq_art"])
    mag_art_py = np.squeeze(py["mag_art"])
    n_taps = int(py["n_taps"])

    have_mat = loadmat is not None and os.path.isfile(mat_path)

    fig, ax1 = plt.subplots(figsize=(10, 5))
    a, = ax1.semilogx(freq_art_py, mag_art_py, "--", linewidth=1.5, label="ART (Py)")
    b, = ax1.semilogx(freq_fir_py, mag_fir_py, linewidth=0.7, label=f"FIR (Py) — {n_taps} Taps")
    handles, labels = [a, b], ["ART (Py)", f"FIR (Py) — {n_taps} Taps"]

    ax1.set_xlabel("Frequency, $f$ (Hz)")
    ax1.set_ylabel(r"$10\cdot\log_{10}\left(|A_{\mathrm{atm}}|^2\right)$")
    ax1.set_xlim(20, 25e3)
    ax1.set_ylim(-200, 0)
    ax1.set_xticks([20, 100, 1000, 10000, 20000])
    ax1.set_xticklabels(["20", "100", "1k", "10k", "20k"])
    ax1.grid(True, which="both", linestyle="--", alpha=0.15)

    if have_mat:
        mat = loadmat(mat_path)
        freq_fir_m = np.squeeze(mat[MAT_VARS["freq_fir"]])
        mag_fir_m = np.squeeze(mat[MAT_VARS["mag_fir"]])
        freq_art_m = np.squeeze(mat[MAT_VARS["freq_art"]])
        mag_art_m = np.squeeze(mat[MAT_VARS["mag_art"]])

        c, = ax1.semilogx(freq_art_m, mag_art_m, ":", linewidth=1.5, color="tab:red", label="ART (MATLAB)")
        d, = ax1.semilogx(freq_fir_m, mag_fir_m, "-.", linewidth=0.7, color="tab:green", label="FIR (MATLAB)")
        handles += [c, d]
        labels += ["ART (MATLAB)", "FIR (MATLAB)"]

        n = min(len(mag_art_py), len(mag_art_m))
        diff_art = np.abs(mag_art_py[:n] - mag_art_m[:n])
        n2 = min(len(mag_fir_py), len(mag_fir_m))
        diff_fir = np.abs(mag_fir_py[:n2] - mag_fir_m[:n2])
        print(f"\n[FIR TRANSFER FUNCTION COMPARISON — {variant}]")
        print(f"  ART magnitude  max_abs={np.max(diff_art):.4f} dB  mean_abs={np.mean(diff_art):.4f} dB")
        print(f"  FIR magnitude  max_abs={np.max(diff_fir):.4f} dB  mean_abs={np.mean(diff_fir):.4f} dB")

        # Right axis: FIR-ART delta (Python), only meaningful when lengths match
        if len(freq_art_py) == len(freq_fir_py):
            ax2 = ax1.twinx()
            delta = mag_fir_py[:len(freq_art_py)] - mag_art_py
            ax2.semilogx(freq_art_py, delta, "-", linewidth=0.5, color="tab:purple")
            ax2.set_ylabel("FIR$-$ART (dB)")
            ax2.set_ylim(-20, 20)
    else:
        print(f"[INFO] {mat_path} not found — plotting Python vectors only.")
        if len(freq_art_py) == len(freq_fir_py):
            ax2 = ax1.twinx()
            delta = mag_fir_py[:len(freq_art_py)] - mag_art_py
            ax2.semilogx(freq_art_py, delta, "-", linewidth=0.5, color="tab:purple")
            ax2.set_ylabel("FIR$-$ART (dB)")
            ax2.set_ylim(-20, 20)

    ax1.legend(handles, labels, loc="lower left", frameon=False, fontsize=8)
    ax1.set_title(f"Atmospheric transfer function (FIR filter) — {variant}")
    fig.tight_layout()
    plt.show()


if __name__ == "__main__":
    variant = sys.argv[1] if len(sys.argv) > 1 else "combined"
    main(variant)
