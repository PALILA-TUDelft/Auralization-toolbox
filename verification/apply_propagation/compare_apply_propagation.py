"""
Verification: compare Python apply_propagation vectors against MATLAB reference.

Usage:
  1. Run the auralization pipeline in Python  -> saves apply_propagation_python.npz
  2. Export matching variables from MATLAB     -> apply_propagation_matlab.mat
  3. Run:  python verification/apply_propagation/compare_apply_propagation.py

Expected MATLAB .mat variable names:
  ir              (nTaps x nBlocks)  impulse response after get_FIR + truncation
  output_signal   (M x 1)           output of overlap-add convolution
  input_signal    (N x 1)           input signal fed to apply_propagation
  block_len       (scalar)          block length in samples
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

FOLDER = os.path.dirname(__file__) or "verification/apply_propagation"
PY_PATH = os.path.join(FOLDER, "apply_propagation_python.npz")
MAT_PATH = os.path.join(FOLDER, "apply_propagation_matlab.mat")

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

    ir_py = py["ir"]
    ir_mat = sq(mat["ir"])
    out_py = sq(py["output_signal"])
    out_mat = sq(mat["output_signal"])
    in_py = sq(py["input_signal"])
    in_mat = sq(mat["input_signal"])
    bl_py = int(py["block_len"])
    bl_mat = int(sq(mat["block_len"]))

    print("\n======== APPLY_PROPAGATION VERIFICATION ========\n")

    print("[SIZE CHECK]")
    print(f"  ir:            Python={ir_py.shape}, MATLAB={ir_mat.shape}")
    print(f"  input_signal:  Python={in_py.shape[0]}, MATLAB={in_mat.shape[0]}")
    print(f"  output_signal: Python={out_py.shape[0]}, MATLAB={out_mat.shape[0]}")
    print(f"  block_len:     Python={bl_py}, MATLAB={bl_mat}")

    # ---- Numerical metrics ----
    print("\n[NUMERICAL COMPARISON]")
    print_metric("input_signal", in_py, in_mat)
    print_metric("block_len", [bl_py], [bl_mat])

    # IR comparison — column-wise
    min_cols = min(ir_py.shape[1], ir_mat.shape[1])
    min_rows = min(ir_py.shape[0], ir_mat.shape[0])
    ir_py_c = ir_py[:min_rows, :min_cols]
    ir_mat_c = ir_mat[:min_rows, :min_cols]
    print_metric("ir (all)", ir_py_c.ravel(), ir_mat_c.ravel())

    # IR at a few representative blocks
    for idx in [0, min_cols // 4, min_cols // 2, 3 * min_cols // 4, min_cols - 1]:
        print_metric(f"ir[:, {idx}]", ir_py[:min_rows, idx], ir_mat[:min_rows, idx])

    # Output signal
    min_out = min(len(out_py), len(out_mat))
    print_metric("output_signal", out_py[:min_out], out_mat[:min_out])

    # ================================================================
    # Fig 0 — Input signal diagnostics
    # ================================================================
    min_in = min(len(in_py), len(in_mat))
    t_in = np.arange(min_in) / FS

    # 0a — waveform overlay + error
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 6), sharex=True)
    fig.suptitle("Fig 0a — Input signal waveform")
    ax1.plot(t_in, in_py[:min_in], label="Python", linewidth=0.3)
    ax1.plot(t_in, in_mat[:min_in], "--", label="MATLAB", linewidth=0.3)
    ax1.set_ylabel("Amplitude (Pa)")
    ax1.legend(frameon=False, fontsize=8)
    ax1.grid(True, linestyle="--", alpha=0.15)

    in_err = in_py[:min_in] - in_mat[:min_in]
    ax2.plot(t_in, in_err, color="tab:red", linewidth=0.3)
    ax2.set_ylabel("Error (Pa)")
    ax2.set_xlabel("Time (s)")
    ax2.grid(True, linestyle="--", alpha=0.15)
    fig.tight_layout()

    # 0b — spectrogram comparison of input signals
    spl_in_py, f_in, t_in_spl = compute_spl(in_py[:min_in])
    spl_in_mat, _, _ = compute_spl(in_mat[:min_in])
    spl_in_err = np.abs(spl_in_py - spl_in_mat)
    mae_in = np.mean(spl_in_err)
    print(f"\n  [INPUT SPECTROGRAM] SPL-based MAE: {mae_in:.2f} dB")

    fig, axs = plt.subplots(1, 3, figsize=(18, 5), sharey=True)
    fig.suptitle(f"Fig 0b — Input signal spectrogram\nMean SPL Abs Error = {mae_in:.2f} dB")

    titles_in = ["Python", "MATLAB", "Abs Error (dB)"]
    data_in = [spl_in_py, spl_in_mat, spl_in_err]
    cmaps_in = ["jet", "jet", "inferno"]
    vmin_in = 100
    vmax_in = max(np.max(spl_in_py), np.max(spl_in_mat))

    for ax, title, spl, cmap in zip(axs, titles_in, data_in, cmaps_in):
        im = ax.imshow(spl, extent=[t_in_spl[0], t_in_spl[-1], f_in[0] / 1000, f_in[-1] / 1000],
                       aspect="auto", origin="lower", cmap=cmap,
                       norm=Normalize(vmin=vmin_in, vmax=vmax_in) if "Error" not in title else None)
        ax.set_title(title)
        ax.set_xlabel("Time (s)")
        ax.set_ylim(0, 15)
        if title == "Python":
            ax.set_ylabel("Frequency (kHz)")
        divider = make_axes_locatable(ax)
        cax = divider.append_axes("right", size="4%", pad=0.1)
        fig.colorbar(im, cax=cax).set_label("SPL (dB re 20 µPa)")
    plt.tight_layout(rect=[0, 0.05, 1, 0.92])

    # 0c — error statistics per block
    n_blocks = min_in // bl_py
    block_rms_err = np.zeros(n_blocks)
    block_rms_py = np.zeros(n_blocks)
    for b in range(n_blocks):
        s = b * bl_py
        e = s + bl_py
        block_rms_err[b] = np.sqrt(np.mean(in_err[s:e] ** 2))
        block_rms_py[b] = np.sqrt(np.mean(in_py[s:e] ** 2))

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 5), sharex=True)
    fig.suptitle("Fig 0c — Input signal error per synthesis block")
    ax1.plot(block_rms_py, label="Python RMS", linewidth=0.8)
    ax1.set_ylabel("RMS (Pa)")
    ax1.legend(frameon=False, fontsize=8)
    ax1.grid(True, linestyle="--", alpha=0.15)

    ax2.plot(block_rms_err, color="tab:red", linewidth=0.8)
    ax2.set_ylabel("RMS error (Pa)")
    ax2.set_xlabel("Block index")
    ax2.grid(True, linestyle="--", alpha=0.15)
    fig.tight_layout()

    # 0d — mean SPL error per frequency bin (input)
    mean_spl_err_freq = np.mean(spl_in_err, axis=1)
    mean_spl_err_time = np.mean(spl_in_err, axis=0)

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 4))
    fig.suptitle("Fig 0d — Input signal SPL error breakdown")
    ax1.plot(f_in / 1000, mean_spl_err_freq)
    ax1.set_xlabel("Frequency (kHz)")
    ax1.set_ylabel("Mean |SPL error| (dB)")
    ax1.set_title("Per frequency bin")
    ax1.grid(True, linestyle="--", alpha=0.15)

    ax2.plot(t_in_spl, mean_spl_err_time)
    ax2.set_xlabel("Time (s)")
    ax2.set_ylabel("Mean |SPL error| (dB)")
    ax2.set_title("Per time frame")
    ax2.grid(True, linestyle="--", alpha=0.15)
    fig.tight_layout()

    # ================================================================
    # Fig 1 — Impulse response comparison (a few blocks)
    # ================================================================
    sample_blocks = [0, min_cols // 2, min_cols - 1]
    fig, axes = plt.subplots(len(sample_blocks), 2, figsize=(14, 3 * len(sample_blocks)),
                             squeeze=False)
    fig.suptitle("Fig 1 — Impulse response (selected blocks)")

    for row, bi in enumerate(sample_blocks):
        axes[row, 0].plot(ir_py[:min_rows, bi], label="Python", linewidth=0.5)
        axes[row, 0].plot(ir_mat[:min_rows, bi], "--", label="MATLAB", linewidth=0.5)
        axes[row, 0].set_title(f"Block {bi}")
        axes[row, 0].set_ylabel("Amplitude")
        axes[row, 0].legend(frameon=False, fontsize=7)
        axes[row, 0].grid(True, linestyle="--", alpha=0.15)

        err = np.abs(ir_py[:min_rows, bi] - ir_mat[:min_rows, bi])
        axes[row, 1].plot(err, color="tab:red", linewidth=0.5)
        axes[row, 1].set_title(f"Block {bi} — abs error")
        axes[row, 1].set_ylabel("|error|")
        axes[row, 1].grid(True, linestyle="--", alpha=0.15)

    for ax in axes[-1, :]:
        ax.set_xlabel("Sample")
    fig.tight_layout()

    # ================================================================
    # Fig 2 — Output signal waveform
    # ================================================================
    t_py = np.arange(min_out) / FS
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 6), sharex=True)
    fig.suptitle("Fig 2 — Output signal waveform")

    ax1.plot(t_py, out_py[:min_out], label="Python", linewidth=0.3)
    ax1.plot(t_py, out_mat[:min_out], "--", label="MATLAB", linewidth=0.3)
    ax1.set_ylabel("Amplitude")
    ax1.legend(frameon=False, fontsize=8)
    ax1.grid(True, linestyle="--", alpha=0.15)

    ax2.plot(t_py, np.abs(out_py[:min_out] - out_mat[:min_out]), color="tab:red", linewidth=0.3)
    ax2.set_ylabel("|error|")
    ax2.set_xlabel("Time (s)")
    ax2.grid(True, linestyle="--", alpha=0.15)
    fig.tight_layout()

    # ================================================================
    # Fig 3 — Spectrogram comparison (Python / MATLAB / error)
    # ================================================================
    spl_py, f_py, t_spl_py = compute_spl(out_py[:min_out])
    spl_mat, f_mat, t_spl_mat = compute_spl(out_mat[:min_out])
    spl_err = np.abs(spl_py - spl_mat)
    mae_spl = np.mean(spl_err)
    print(f"\n  [SPECTROGRAM] SPL-based MAE: {mae_spl:.2f} dB")

    fig, axs = plt.subplots(1, 3, figsize=(18, 5), sharey=True)
    fig.suptitle(f"Fig 3 — Output spectrogram comparison\nMean SPL Abs Error = {mae_spl:.2f} dB")

    titles = ["Python", "MATLAB", "Abs Error (dB)"]
    data = [spl_py, spl_mat, spl_err]
    cmaps = ["jet", "jet", "inferno"]
    vmin = 100
    vmax = max(np.max(spl_py), np.max(spl_mat))

    for ax, title, spl, cmap in zip(axs, titles, data, cmaps):
        im = ax.imshow(spl, extent=[t_spl_py[0], t_spl_py[-1], f_py[0] / 1000, f_py[-1] / 1000],
                       aspect="auto", origin="lower", cmap=cmap,
                       norm=Normalize(vmin=vmin, vmax=vmax) if "Error" not in title else None)
        ax.set_title(title)
        ax.set_xlabel("Time (s)")
        ax.set_ylim(0, 15)
        if title == "Python":
            ax.set_ylabel("Frequency (kHz)")
        divider = make_axes_locatable(ax)
        cax = divider.append_axes("right", size="4%", pad=0.1)
        fig.colorbar(im, cax=cax).set_label("SPL (dB re 20 µPa)")

    plt.tight_layout(rect=[0, 0.05, 1, 0.92])

    # ================================================================
    # Fig 4 — IR magnitude spectrum comparison at a few blocks
    # ================================================================
    fig, axes = plt.subplots(1, len(sample_blocks), figsize=(5 * len(sample_blocks), 4))
    fig.suptitle("Fig 4 — IR magnitude spectrum (selected blocks)")
    freq_ir = np.fft.rfftfreq(min_rows, d=1.0 / FS)
    for ax, bi in zip(axes, sample_blocks):
        mag_py = 20 * np.log10(np.abs(np.fft.rfft(ir_py[:min_rows, bi])) + 1e-30)
        mag_mat = 20 * np.log10(np.abs(np.fft.rfft(ir_mat[:min_rows, bi])) + 1e-30)
        ax.semilogx(freq_ir, mag_py, linewidth=0.5, label="Python")
        ax.semilogx(freq_ir, mag_mat, "--", linewidth=0.5, label="MATLAB")
        ax.set_title(f"Block {bi}")
        ax.set_xlabel("Frequency (Hz)")
        ax.set_ylabel("Magnitude (dB)")
        ax.set_xlim(20, 24000)
        ax.legend(frameon=False, fontsize=7)
        ax.grid(True, linestyle="--", alpha=0.15)
    fig.tight_layout()

    print("\n======== DONE ========\n")
    plt.show()


if __name__ == "__main__":
    main()
