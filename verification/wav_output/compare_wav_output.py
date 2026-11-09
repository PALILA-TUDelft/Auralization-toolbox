"""
Verification: compare Python wav output signal against MATLAB reference.

Compares the final signal after propagation and attenuation (what gets written to .wav).

Expected MATLAB .mat variables:
  outputSignal    — propagated signal before attenuation (from apply_propagation)
  AttenuationdB   — attenuation in dB
"""
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

import numpy as np
from scipy.io import loadmat
from scipy.signal import correlate
import matplotlib.pyplot as plt
from matplotlib.colors import Normalize
from mpl_toolkits.axes_grid1 import make_axes_locatable
from utilities.plot_utils import myspecgram

FS = 48000
PREF = 20e-6
WINDOW_SIZE = 1024
OVERLAP = 0.75

FOLDER = os.path.dirname(__file__) or "verification/wav_output"
PY_PATH = os.path.join(FOLDER, "wav_output_python.npz")
MAT_PATH = os.path.join(FOLDER, "wav_output_matlab.mat")


def sq(arr):
    return np.asarray(arr).squeeze()


def compute_spl(signal):
    P, F, T = myspecgram(signal, FS, WINDOW_SIZE, OVERLAP)
    SPL = 20 * np.log10(np.abs(P) / PREF + 1e-12)
    return SPL, F, T


def print_metric(label, py_arr, mat_arr):
    py_arr = sq(py_arr).ravel()
    mat_arr = sq(mat_arr).ravel()
    n = min(len(py_arr), len(mat_arr))
    py_arr, mat_arr = py_arr[:n], mat_arr[:n]
    diff = np.abs(py_arr - mat_arr)
    denom = np.maximum(np.abs(mat_arr), 1e-12)
    print(f"  {label:40s}  max_abs={np.max(diff):.6e}  mean_abs={np.mean(diff):.6e}  max_rel={np.max(diff / denom):.6e}")


def main():
    py = np.load(PY_PATH)
    mat = loadmat(MAT_PATH)

    out_py = sq(py["output_signal"])
    out_mat = sq(mat["outputSignal"])
    atten_py = float(py["attenuation_db"])
    atten_mat = float(sq(mat["AttenuationdB"]))

    atten_factor_py = 10.0 ** (atten_py / 20.0)
    atten_factor_mat = 10.0 ** (atten_mat / 20.0)

    wav_py = np.float32(out_py * atten_factor_py)
    wav_mat = np.float32(out_mat * atten_factor_mat)

    min_len = min(len(wav_py), len(wav_mat))
    wav_py = wav_py[:min_len]
    wav_mat = wav_mat[:min_len]

    print("\n======== WAV OUTPUT VERIFICATION ========\n")

    # ---- Attenuation check ----
    print("[ATTENUATION]")
    print(f"  Python:  {atten_py:.2f} dB (factor={atten_factor_py:.6f})")
    print(f"  MATLAB:  {atten_mat:.2f} dB (factor={atten_factor_mat:.6f})")

    # ---- Numerical metrics ----
    print("\n[NUMERICAL COMPARISON]")
    print_metric("output_signal (pre-atten)", out_py, out_mat)
    print_metric("wav_signal (post-atten, float32)", wav_py, wav_mat)

    # ---- Lag detection ----
    corr = correlate(wav_py, wav_mat, mode="full")
    lags = np.arange(-len(wav_py) + 1, len(wav_mat))
    lag_offset = lags[np.argmax(corr)]
    print(f"\n[LAG DETECTION]")
    print(f"  Max correlation lag: {lag_offset} samples ({lag_offset / FS * 1000:.3f} ms)")

    # ---- Spectrogram comparison ----
    spl_py, f_py, t_py = compute_spl(wav_py)
    spl_mat, _, _ = compute_spl(wav_mat)
    spl_err = np.abs(spl_py - spl_mat)
    mae_spl = np.mean(spl_err)
    print(f"\n[SPECTROGRAM]")
    print(f"  SPL-based MAE: {mae_spl:.2f} dB")

    # ---- Fig 0 — Waveform ----
    t = np.arange(min_len) / FS
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 6), sharex=True)
    fig.suptitle("Fig 0 — Wav output waveform")
    ax1.plot(t, wav_py, label="Python", linewidth=0.3)
    ax1.plot(t, wav_mat, "--", label="MATLAB", linewidth=0.3)
    ax1.set_ylabel("Amplitude")
    ax1.legend(frameon=False, fontsize=8)
    ax1.grid(True, linestyle="--", alpha=0.15)

    ax2.plot(t, wav_py - wav_mat, color="tab:red", linewidth=0.3)
    ax2.set_ylabel("Error")
    ax2.set_xlabel("Time (s)")
    ax2.grid(True, linestyle="--", alpha=0.15)
    fig.tight_layout()

    # ---- Fig 1 — Spectrogram comparison ----
    fig, axs = plt.subplots(1, 3, figsize=(18, 5), sharey=True)
    fig.suptitle(f"Fig 1 — Wav output spectrogram\nMean SPL Abs Error = {mae_spl:.2f} dB")

    titles = ["Python", "MATLAB", "Abs Error (dB)"]
    data = [spl_py, spl_mat, spl_err]
    cmaps = ["jet", "jet", "inferno"]
    vmin = 100
    vmax = max(np.max(spl_py), np.max(spl_mat))

    for ax, title, spl, cmap in zip(axs, titles, data, cmaps):
        im = ax.imshow(spl, extent=[t_py[0], t_py[-1], f_py[0] / 1000, f_py[-1] / 1000],
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

    # ---- Fig 2 — SPL error breakdown ----
    mean_err_freq = np.mean(spl_err, axis=1)
    mean_err_time = np.mean(spl_err, axis=0)

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 4))
    fig.suptitle("Fig 2 — SPL error breakdown")
    ax1.plot(f_py / 1000, mean_err_freq)
    ax1.set_xlabel("Frequency (kHz)")
    ax1.set_ylabel("Mean |SPL error| (dB)")
    ax1.set_title("Per frequency bin")
    ax1.grid(True, linestyle="--", alpha=0.15)

    ax2.plot(t_py, mean_err_time)
    ax2.set_xlabel("Time (s)")
    ax2.set_ylabel("Mean |SPL error| (dB)")
    ax2.set_title("Per time frame")
    ax2.grid(True, linestyle="--", alpha=0.15)
    fig.tight_layout()

    print("\n======== DONE ========\n")
    plt.show()


if __name__ == "__main__":
    main()
