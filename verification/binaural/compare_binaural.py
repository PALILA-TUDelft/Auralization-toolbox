"""
Verification: compare Python binaural vectors against MATLAB reference.

Usage:
  1. Run the auralization pipeline in Python  -> saves binaural_python.npz
  2. Export matching variables from MATLAB     -> binaural_matlab.mat
  3. Run:  python verification/binaural/compare_binaural.py

Expected MATLAB .mat variable names:
  ir_binaural_left       (nTaps x nTimeSteps)
  ir_binaural_right      (nTaps x nTimeSteps)
  output_binaural_left   (N x 1)
  output_binaural_right  (N x 1)
  hrir_direct_left       (nSamples x nTimeSteps)
  hrir_direct_right      (nSamples x nTimeSteps)
  hrir_reflected_left    (nSamples x nTimeSteps)  [optional]
  hrir_reflected_right   (nSamples x nTimeSteps)  [optional]
"""
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

import numpy as np
from scipy.io import loadmat
import matplotlib.pyplot as plt
from matplotlib.colors import Normalize
from mpl_toolkits.axes_grid1 import make_axes_locatable
from utilities.plot_utils import myspecgram

FOLDER = os.path.dirname(__file__) or "verification/binaural"
PY_PATH = os.path.join(FOLDER, "binaural_python.npz")
MAT_PATH = os.path.join(FOLDER, "binaural_matlab.mat")

FS = 48000
PREF = 20e-6
WINDOW_SIZE = 1024
OVERLAP = 0.75


def load_data():
    if not os.path.isfile(PY_PATH):
        raise FileNotFoundError(f"Python data not found: {PY_PATH}\nRun the auralization pipeline first.")
    if not os.path.isfile(MAT_PATH):
        raise FileNotFoundError(f"MATLAB data not found: {MAT_PATH}\nExport from MATLAB first.")
    py = np.load(PY_PATH)
    mat = loadmat(MAT_PATH)
    return py, mat


def sq(arr):
    return np.asarray(arr).squeeze()


def print_metric(label, py_arr, mat_arr):
    py_arr = sq(py_arr).ravel()
    mat_arr = sq(mat_arr).ravel()
    min_len = min(len(py_arr), len(mat_arr))
    py_arr = py_arr[:min_len]
    mat_arr = mat_arr[:min_len]
    max_abs = np.max(np.abs(py_arr - mat_arr))
    mean_abs = np.mean(np.abs(py_arr - mat_arr))
    denom = np.maximum(np.abs(mat_arr), 1e-12)
    max_rel = np.max(np.abs(py_arr - mat_arr) / denom)
    print(f"  {label:40s}  max_abs={max_abs:.6e}  mean_abs={mean_abs:.6e}  max_rel={max_rel:.6e}")


def compute_spl(signal):
    P, F, T = myspecgram(signal, FS, WINDOW_SIZE, OVERLAP)
    SPL = 20 * np.log10(np.abs(P) / PREF + 1e-12)
    return SPL, F, T


def main():
    py, mat = load_data()

    print("\n======== BINAURAL VERIFICATION ========\n")

    # ---- Load vectors ----
    ir_left_py = py["ir_binaural_left"]
    ir_right_py = py["ir_binaural_right"]
    ir_left_mat = sq(mat["ir_binaural_left"])
    ir_right_mat = sq(mat["ir_binaural_right"])

    out_left_py = sq(py["output_binaural_left"])
    out_right_py = sq(py["output_binaural_right"])
    out_left_mat = sq(mat["output_binaural_left"])
    out_right_mat = sq(mat["output_binaural_right"])

    hrir_dl_py = py["hrir_direct_left"]
    hrir_dr_py = py["hrir_direct_right"]
    hrir_dl_mat = sq(mat["hrir_direct_left"])
    hrir_dr_mat = sq(mat["hrir_direct_right"])

    has_reflected = "hrir_reflected_left" in py.files and "hrir_reflected_left" in mat

    # ---- Size check ----
    print("[SIZE CHECK]")
    print(f"  ir_binaural_left:      Python={ir_left_py.shape}, MATLAB={ir_left_mat.shape}")
    print(f"  ir_binaural_right:     Python={ir_right_py.shape}, MATLAB={ir_right_mat.shape}")
    print(f"  output_binaural_left:  Python={out_left_py.shape[0]}, MATLAB={out_left_mat.shape[0]}")
    print(f"  output_binaural_right: Python={out_right_py.shape[0]}, MATLAB={out_right_mat.shape[0]}")
    print(f"  hrir_direct_left:      Python={hrir_dl_py.shape}, MATLAB={hrir_dl_mat.shape}")
    print(f"  hrir_direct_right:     Python={hrir_dr_py.shape}, MATLAB={hrir_dr_mat.shape}")
    if has_reflected:
        hrir_rl_py = py["hrir_reflected_left"]
        hrir_rr_py = py["hrir_reflected_right"]
        hrir_rl_mat = sq(mat["hrir_reflected_left"])
        hrir_rr_mat = sq(mat["hrir_reflected_right"])
        print(f"  hrir_reflected_left:   Python={hrir_rl_py.shape}, MATLAB={hrir_rl_mat.shape}")
        print(f"  hrir_reflected_right:  Python={hrir_rr_py.shape}, MATLAB={hrir_rr_mat.shape}")

    # ---- Numerical comparison ----
    print("\n[NUMERICAL COMPARISON]")

    min_rows_ir = min(ir_left_py.shape[0], ir_left_mat.shape[0])
    min_cols_ir = min(ir_left_py.shape[1], ir_left_mat.shape[1])
    print_metric("ir_binaural_left (all)", ir_left_py[:min_rows_ir, :min_cols_ir].ravel(),
                 ir_left_mat[:min_rows_ir, :min_cols_ir].ravel())
    print_metric("ir_binaural_right (all)", ir_right_py[:min_rows_ir, :min_cols_ir].ravel(),
                 ir_right_mat[:min_rows_ir, :min_cols_ir].ravel())

    min_out = min(len(out_left_py), len(out_left_mat))
    print_metric("output_binaural_left", out_left_py[:min_out], out_left_mat[:min_out])
    print_metric("output_binaural_right", out_right_py[:min_out], out_right_mat[:min_out])

    min_rows_h = min(hrir_dl_py.shape[0], hrir_dl_mat.shape[0])
    min_cols_h = min(hrir_dl_py.shape[1], hrir_dl_mat.shape[1])
    print_metric("hrir_direct_left (all)", hrir_dl_py[:min_rows_h, :min_cols_h].ravel(),
                 hrir_dl_mat[:min_rows_h, :min_cols_h].ravel())
    print_metric("hrir_direct_right (all)", hrir_dr_py[:min_rows_h, :min_cols_h].ravel(),
                 hrir_dr_mat[:min_rows_h, :min_cols_h].ravel())

    if has_reflected:
        min_rows_hr = min(hrir_rl_py.shape[0], hrir_rl_mat.shape[0])
        min_cols_hr = min(hrir_rl_py.shape[1], hrir_rl_mat.shape[1])
        print_metric("hrir_reflected_left (all)", hrir_rl_py[:min_rows_hr, :min_cols_hr].ravel(),
                     hrir_rl_mat[:min_rows_hr, :min_cols_hr].ravel())
        print_metric("hrir_reflected_right (all)", hrir_rr_py[:min_rows_hr, :min_cols_hr].ravel(),
                     hrir_rr_mat[:min_rows_hr, :min_cols_hr].ravel())

    # ================================================================
    # Fig 1 — HRIR comparison (direct path, selected time steps)
    # ================================================================
    sample_steps = [0, min_cols_h // 2, min_cols_h - 1]
    fig, axes = plt.subplots(len(sample_steps), 2, figsize=(14, 3 * len(sample_steps)), squeeze=False)
    fig.suptitle("Fig 1 — HRIR direct path (selected time steps)")

    for row, ti in enumerate(sample_steps):
        axes[row, 0].plot(hrir_dl_py[:min_rows_h, ti], label="Python", linewidth=0.5)
        axes[row, 0].plot(hrir_dl_mat[:min_rows_h, ti], "--", label="MATLAB", linewidth=0.5)
        axes[row, 0].set_title(f"Left ear — step {ti}")
        axes[row, 0].set_ylabel("Amplitude")
        axes[row, 0].legend(frameon=False, fontsize=7)
        axes[row, 0].grid(True, linestyle="--", alpha=0.15)

        axes[row, 1].plot(hrir_dr_py[:min_rows_h, ti], label="Python", linewidth=0.5)
        axes[row, 1].plot(hrir_dr_mat[:min_rows_h, ti], "--", label="MATLAB", linewidth=0.5)
        axes[row, 1].set_title(f"Right ear — step {ti}")
        axes[row, 1].legend(frameon=False, fontsize=7)
        axes[row, 1].grid(True, linestyle="--", alpha=0.15)

    for ax in axes[-1, :]:
        ax.set_xlabel("Sample")
    fig.tight_layout()

    # ================================================================
    # Fig 2 — Binaural IR comparison (selected blocks)
    # ================================================================
    sample_blocks = [0, min_cols_ir // 2, min_cols_ir - 1]
    fig, axes = plt.subplots(len(sample_blocks), 2, figsize=(14, 3 * len(sample_blocks)), squeeze=False)
    fig.suptitle("Fig 2 — Binaural impulse response (selected blocks)")

    for row, bi in enumerate(sample_blocks):
        axes[row, 0].plot(ir_left_py[:min_rows_ir, bi], label="Python", linewidth=0.5)
        axes[row, 0].plot(ir_left_mat[:min_rows_ir, bi], "--", label="MATLAB", linewidth=0.5)
        axes[row, 0].set_title(f"Left ear — block {bi}")
        axes[row, 0].set_ylabel("Amplitude")
        axes[row, 0].legend(frameon=False, fontsize=7)
        axes[row, 0].grid(True, linestyle="--", alpha=0.15)

        axes[row, 1].plot(ir_right_py[:min_rows_ir, bi], label="Python", linewidth=0.5)
        axes[row, 1].plot(ir_right_mat[:min_rows_ir, bi], "--", label="MATLAB", linewidth=0.5)
        axes[row, 1].set_title(f"Right ear — block {bi}")
        axes[row, 1].legend(frameon=False, fontsize=7)
        axes[row, 1].grid(True, linestyle="--", alpha=0.15)

    for ax in axes[-1, :]:
        ax.set_xlabel("Sample")
    fig.tight_layout()

    # ================================================================
    # Fig 3 — Binaural IR magnitude spectrum (selected blocks)
    # ================================================================
    fig, axes = plt.subplots(len(sample_blocks), 2, figsize=(14, 3 * len(sample_blocks)), squeeze=False)
    fig.suptitle("Fig 3 — Binaural IR magnitude spectrum (selected blocks)")
    freq_ir = np.fft.rfftfreq(min_rows_ir, d=1.0 / FS)

    for row, bi in enumerate(sample_blocks):
        mag_l_py = 20 * np.log10(np.abs(np.fft.rfft(ir_left_py[:min_rows_ir, bi])) + 1e-30)
        mag_l_mat = 20 * np.log10(np.abs(np.fft.rfft(ir_left_mat[:min_rows_ir, bi])) + 1e-30)
        axes[row, 0].semilogx(freq_ir, mag_l_py, linewidth=0.5, label="Python")
        axes[row, 0].semilogx(freq_ir, mag_l_mat, "--", linewidth=0.5, label="MATLAB")
        axes[row, 0].set_title(f"Left ear — block {bi}")
        axes[row, 0].set_ylabel("Magnitude (dB)")
        axes[row, 0].set_xlim(20, 24000)
        axes[row, 0].legend(frameon=False, fontsize=7)
        axes[row, 0].grid(True, linestyle="--", alpha=0.15)

        mag_r_py = 20 * np.log10(np.abs(np.fft.rfft(ir_right_py[:min_rows_ir, bi])) + 1e-30)
        mag_r_mat = 20 * np.log10(np.abs(np.fft.rfft(ir_right_mat[:min_rows_ir, bi])) + 1e-30)
        axes[row, 1].semilogx(freq_ir, mag_r_py, linewidth=0.5, label="Python")
        axes[row, 1].semilogx(freq_ir, mag_r_mat, "--", linewidth=0.5, label="MATLAB")
        axes[row, 1].set_title(f"Right ear — block {bi}")
        axes[row, 1].set_xlim(20, 24000)
        axes[row, 1].legend(frameon=False, fontsize=7)
        axes[row, 1].grid(True, linestyle="--", alpha=0.15)

    for ax in axes[-1, :]:
        ax.set_xlabel("Frequency (Hz)")
    fig.tight_layout()

    # ================================================================
    # Fig 4 — Output waveform comparison (left + right)
    # ================================================================
    t = np.arange(min_out) / FS
    fig, axes = plt.subplots(2, 2, figsize=(14, 8), sharex=True)
    fig.suptitle("Fig 4 — Binaural output waveform")

    axes[0, 0].plot(t, out_left_py[:min_out], label="Python", linewidth=0.3)
    axes[0, 0].plot(t, out_left_mat[:min_out], "--", label="MATLAB", linewidth=0.3)
    axes[0, 0].set_title("Left ear")
    axes[0, 0].set_ylabel("Amplitude (Pa)")
    axes[0, 0].legend(frameon=False, fontsize=8)
    axes[0, 0].grid(True, linestyle="--", alpha=0.15)

    axes[0, 1].plot(t, out_right_py[:min_out], label="Python", linewidth=0.3)
    axes[0, 1].plot(t, out_right_mat[:min_out], "--", label="MATLAB", linewidth=0.3)
    axes[0, 1].set_title("Right ear")
    axes[0, 1].legend(frameon=False, fontsize=8)
    axes[0, 1].grid(True, linestyle="--", alpha=0.15)

    axes[1, 0].plot(t, np.abs(out_left_py[:min_out] - out_left_mat[:min_out]), color="tab:red", linewidth=0.3)
    axes[1, 0].set_ylabel("|error| (Pa)")
    axes[1, 0].set_xlabel("Time (s)")
    axes[1, 0].grid(True, linestyle="--", alpha=0.15)

    axes[1, 1].plot(t, np.abs(out_right_py[:min_out] - out_right_mat[:min_out]), color="tab:red", linewidth=0.3)
    axes[1, 1].set_xlabel("Time (s)")
    axes[1, 1].grid(True, linestyle="--", alpha=0.15)
    fig.tight_layout()

    # ================================================================
    # Fig 5 — Output spectrogram comparison (left ear)
    # ================================================================
    spl_l_py, f, t_spl = compute_spl(out_left_py[:min_out])
    spl_l_mat, _, _ = compute_spl(out_left_mat[:min_out])
    spl_l_err = np.abs(spl_l_py - spl_l_mat)
    mae_l = np.mean(spl_l_err)
    print(f"\n  [SPECTROGRAM LEFT]  SPL-based MAE: {mae_l:.2f} dB")

    fig, axs = plt.subplots(1, 3, figsize=(18, 5), sharey=True)
    fig.suptitle(f"Fig 5 — Left ear spectrogram   |   MAE = {mae_l:.2f} dB")
    vmax = max(np.max(spl_l_py), np.max(spl_l_mat))
    vmin = 100 if vmax > 110 else 0
    extent = [t_spl[0], t_spl[-1], f[0] / 1000, f[-1] / 1000]

    for ax, title, spl, cmap in zip(axs, ["Python", "MATLAB", "Abs Error"],
                                     [spl_l_py, spl_l_mat, spl_l_err],
                                     ["jet", "jet", "inferno"]):
        im = ax.imshow(spl, extent=extent, aspect="auto", origin="lower", cmap=cmap,
                       norm=Normalize(vmin=vmin, vmax=vmax) if "Error" not in title else None)
        ax.set_title(title)
        ax.set_xlabel("Time (s)")
        ax.set_ylim(0, 15)
        if title == "Python":
            ax.set_ylabel("Frequency (kHz)")
        divider = make_axes_locatable(ax)
        cax = divider.append_axes("right", size="4%", pad=0.1)
        fig.colorbar(im, cax=cax).set_label("dB")
    plt.tight_layout(rect=[0, 0.05, 1, 0.92])

    # ================================================================
    # Fig 6 — Output spectrogram comparison (right ear)
    # ================================================================
    spl_r_py, _, _ = compute_spl(out_right_py[:min_out])
    spl_r_mat, _, _ = compute_spl(out_right_mat[:min_out])
    spl_r_err = np.abs(spl_r_py - spl_r_mat)
    mae_r = np.mean(spl_r_err)
    print(f"  [SPECTROGRAM RIGHT] SPL-based MAE: {mae_r:.2f} dB")

    fig, axs = plt.subplots(1, 3, figsize=(18, 5), sharey=True)
    fig.suptitle(f"Fig 6 — Right ear spectrogram   |   MAE = {mae_r:.2f} dB")

    for ax, title, spl, cmap in zip(axs, ["Python", "MATLAB", "Abs Error"],
                                     [spl_r_py, spl_r_mat, spl_r_err],
                                     ["jet", "jet", "inferno"]):
        im = ax.imshow(spl, extent=extent, aspect="auto", origin="lower", cmap=cmap,
                       norm=Normalize(vmin=vmin, vmax=vmax) if "Error" not in title else None)
        ax.set_title(title)
        ax.set_xlabel("Time (s)")
        ax.set_ylim(0, 15)
        if title == "Python":
            ax.set_ylabel("Frequency (kHz)")
        divider = make_axes_locatable(ax)
        cax = divider.append_axes("right", size="4%", pad=0.1)
        fig.colorbar(im, cax=cax).set_label("dB")
    plt.tight_layout(rect=[0, 0.05, 1, 0.92])

    print("\n======== DONE ========\n")
    plt.show()


if __name__ == "__main__":
    main()
