"""
Verification: compare Python engine_signal against MATLAB reference.

Diagnostics included:
  - Numerical metrics (max/mean absolute & relative error)
  - Lag detection + lag-corrected MAE
  - Per-component breakdown (fan, buzzsaw, broadband engine)
  - Waveform overlay + time-domain error
  - Spectrogram comparison (Python / MATLAB / error)
  - Per-frequency and per-time SPL error breakdown
  - RMS error per synthesis block
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

# ---- Configuration ----
FS = 48000
PREF = 20e-6
WINDOW_SIZE = 1024
OVERLAP = 0.75
BLOCK_LEN = 4800  # fs * dt_panam (0.1 s)

FOLDER = os.path.dirname(__file__) or "verification/engine_signal_auralized"

# ---- Component paths ----
COMPONENTS = {
    "fan": {
        "py": "verification/tonal_fan_signal/tonal_fan_signal_python.npz",
        "mat": "verification/tonal_fan_signal/tonal_fan_signal_matlab.mat",
        "mat_var": "TonalSignal_FanHarmonics",
    },
    "buzzsaw": {
        "py": "verification/tonal_buzz_signal/tonal_buzz_signal_python.npz",
        "mat": "verification/tonal_buzz_signal/tonal_buzz_signal_matlab.mat",
        "mat_var": "TonalSignal_Buzzsaw",
    },
    "broadband_engine": {
        "py": "verification/specrogram_engine_bbn/BroadbandSignal_engine_python.npz",
        "mat": "verification/specrogram_engine_bbn/BroadbandSignal_engine_matlab.mat",
        "mat_var": "BroadbandSignal_engine",
    },
}


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


def load_signal(npz_path, mat_path, mat_var):
    py = np.load(npz_path)["signal"].squeeze()
    mat = loadmat(mat_path)[mat_var].squeeze()
    n = min(len(py), len(mat))
    return py[:n], mat[:n]


def main():
    # ==================================================================
    # Load engine signal
    # ==================================================================
    py_data = np.load(os.path.join(FOLDER, "engine_signal_python.npz"))
    mat_data = loadmat(os.path.join(FOLDER, "engine_signal_matlab.mat"))
    sig_py = py_data["signal"].squeeze()
    sig_mat = mat_data["auralizedEngineSignal"].squeeze()
    min_len = min(len(sig_py), len(sig_mat))
    sig_py = sig_py[:min_len]
    sig_mat = sig_mat[:min_len]

    print("\n======== ENGINE SIGNAL VERIFICATION ========\n")

    # ==================================================================
    # 1. Numerical metrics
    # ==================================================================
    print("[NUMERICAL COMPARISON]")
    print_metric("engine_signal", sig_py, sig_mat)

    # ==================================================================
    # 2. Lag detection
    # ==================================================================
    corr = correlate(sig_py, sig_mat, mode="full")
    lags = np.arange(-len(sig_py) + 1, len(sig_mat))
    lag_offset = lags[np.argmax(corr)]
    print(f"\n[LAG DETECTION]")
    print(f"  Max correlation lag: {lag_offset} samples ({lag_offset / FS * 1000:.3f} ms)")

    # ==================================================================
    # 3. Lag-corrected comparison
    # ==================================================================
    if lag_offset != 0:
        if lag_offset > 0:
            sig_py_aligned = sig_py[lag_offset:]
            sig_mat_aligned = sig_mat[:len(sig_py_aligned)]
        else:
            sig_mat_aligned = sig_mat[-lag_offset:]
            sig_py_aligned = sig_py[:len(sig_mat_aligned)]

        spl_py_a, _, _ = compute_spl(sig_py_aligned)
        spl_mat_a, _, _ = compute_spl(sig_mat_aligned)
        mae_aligned = np.mean(np.abs(spl_py_a - spl_mat_a))

        spl_py_orig, _, _ = compute_spl(sig_py)
        spl_mat_orig, _, _ = compute_spl(sig_mat)
        mae_original = np.mean(np.abs(spl_py_orig - spl_mat_orig))

        print(f"\n[LAG-CORRECTED COMPARISON]")
        print(f"  Original MAE:       {mae_original:.2f} dB")
        print(f"  Lag-corrected MAE:  {mae_aligned:.2f} dB")
        print(f"  Improvement:        {mae_original - mae_aligned:.2f} dB")
    else:
        spl_py_orig, _, _ = compute_spl(sig_py)
        spl_mat_orig, _, _ = compute_spl(sig_mat)
        mae_original = np.mean(np.abs(spl_py_orig - spl_mat_orig))
        mae_aligned = mae_original
        print(f"\n[LAG-CORRECTED COMPARISON]")
        print(f"  No lag detected — MAE: {mae_original:.2f} dB")

    # ==================================================================
    # 4. Component consistency check
    # ==================================================================
    print(f"\n[COMPONENT CONSISTENCY CHECK]")
    all_py_found = all(os.path.isfile(p["py"]) for p in COMPONENTS.values())
    all_mat_found = all(os.path.isfile(p["mat"]) for p in COMPONENTS.values())

    if all_py_found:
        fan_py = np.load(COMPONENTS["fan"]["py"])["signal"].squeeze()
        buzz_py = np.load(COMPONENTS["buzzsaw"]["py"])["signal"].squeeze()
        bbn_py = np.load(COMPONENTS["broadband_engine"]["py"])["signal"].squeeze()
        n_comp = min(len(fan_py), len(buzz_py), len(bbn_py))
        reconstructed_py = fan_py[:n_comp] + buzz_py[:n_comp] + bbn_py[:n_comp]
        n_check = min(len(reconstructed_py), len(sig_py))
        diff_py = np.max(np.abs(reconstructed_py[:n_check] - sig_py[:n_check]))
        print(f"  Python:  fan+buzz+bbn vs engine_signal  max_abs_diff = {diff_py:.6e}")
        if diff_py > 1e-6:
            print(f"  ** STALE: component .npz files do NOT match current engine_signal **")
        else:
            print(f"  OK: component .npz files are consistent with engine_signal")
    else:
        print(f"  Python: some component .npz files missing, skipping")

    if all_mat_found:
        fan_mat = loadmat(COMPONENTS["fan"]["mat"])[COMPONENTS["fan"]["mat_var"]].squeeze()
        buzz_mat = loadmat(COMPONENTS["buzzsaw"]["mat"])[COMPONENTS["buzzsaw"]["mat_var"]].squeeze()
        bbn_mat = loadmat(COMPONENTS["broadband_engine"]["mat"])[COMPONENTS["broadband_engine"]["mat_var"]].squeeze()
        n_comp_m = min(len(fan_mat), len(buzz_mat), len(bbn_mat))
        reconstructed_mat = fan_mat[:n_comp_m] + buzz_mat[:n_comp_m] + bbn_mat[:n_comp_m]
        n_check_m = min(len(reconstructed_mat), len(sig_mat))
        diff_mat = np.max(np.abs(reconstructed_mat[:n_check_m] - sig_mat[:n_check_m]))
        print(f"  MATLAB:  fan+buzz+bbn vs engine_signal  max_abs_diff = {diff_mat:.6e}")
        if diff_mat > 1e-6:
            print(f"  ** STALE: component .mat files do NOT match current engine_signal **")
        else:
            print(f"  OK: component .mat files are consistent with engine_signal")
    else:
        print(f"  MATLAB: some component .mat files missing, skipping")

    # ==================================================================
    # 5. Per-component breakdown
    # ==================================================================
    print(f"\n[PER-COMPONENT BREAKDOWN]")
    component_available = {}
    for name, paths in COMPONENTS.items():
        if os.path.isfile(paths["py"]) and os.path.isfile(paths["mat"]):
            c_py, c_mat = load_signal(paths["py"], paths["mat"], paths["mat_var"])
            c_diff = np.abs(c_py - c_mat)
            c_rms_py = np.sqrt(np.mean(c_py ** 2))
            c_rms_err = np.sqrt(np.mean(c_diff ** 2))

            c_corr = correlate(c_py, c_mat, mode="full")
            c_lags = np.arange(-len(c_py) + 1, len(c_mat))
            c_lag = c_lags[np.argmax(c_corr)]

            spl_c_py, _, _ = compute_spl(c_py)
            spl_c_mat, _, _ = compute_spl(c_mat)
            c_mae = np.mean(np.abs(spl_c_py - spl_c_mat))

            print(f"  {name:25s}  MAE={c_mae:.2f} dB  RMS_err={c_rms_err:.4e}  RMS_sig={c_rms_py:.4e}  lag={c_lag} samples")
            component_available[name] = (c_py, c_mat)
        else:
            print(f"  {name:25s}  (data not found, skipping)")

    # ==================================================================
    # Fig 0 — Waveform overlay + error
    # ==================================================================
    t = np.arange(min_len) / FS
    sig_err = sig_py - sig_mat

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 6), sharex=True)
    fig.suptitle("Fig 0 — Engine signal waveform")
    ax1.plot(t, sig_py, label="Python", linewidth=0.3)
    ax1.plot(t, sig_mat, "--", label="MATLAB", linewidth=0.3)
    ax1.set_ylabel("Amplitude (Pa)")
    ax1.legend(frameon=False, fontsize=8)
    ax1.grid(True, linestyle="--", alpha=0.15)

    ax2.plot(t, sig_err, color="tab:red", linewidth=0.3)
    ax2.set_ylabel("Error (Pa)")
    ax2.set_xlabel("Time (s)")
    ax2.grid(True, linestyle="--", alpha=0.15)
    fig.tight_layout()

    # ==================================================================
    # Fig 1 — Spectrogram comparison (Python / MATLAB / error)
    # ==================================================================
    spl_py_plot, f_py, t_py = compute_spl(sig_py)
    spl_mat_plot, _, _ = compute_spl(sig_mat)
    spl_err = np.abs(spl_py_plot - spl_mat_plot)

    fig, axs = plt.subplots(1, 3, figsize=(18, 5), sharey=True)
    fig.suptitle(f"Fig 1 — Engine signal spectrogram\nMean SPL Abs Error = {mae_original:.2f} dB")

    titles = ["Python", "MATLAB", "Abs Error (dB)"]
    data = [spl_py_plot, spl_mat_plot, spl_err]
    cmaps = ["jet", "jet", "inferno"]
    vmin = 100
    vmax = max(np.max(spl_py_plot), np.max(spl_mat_plot))

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

    # ==================================================================
    # Fig 2 — Per-frequency and per-time SPL error breakdown
    # ==================================================================
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

    # ==================================================================
    # Fig 3 — RMS error per synthesis block
    # ==================================================================
    n_blocks = min_len // BLOCK_LEN
    block_rms_py = np.zeros(n_blocks)
    block_rms_err = np.zeros(n_blocks)
    for b in range(n_blocks):
        s, e = b * BLOCK_LEN, (b + 1) * BLOCK_LEN
        block_rms_py[b] = np.sqrt(np.mean(sig_py[s:e] ** 2))
        block_rms_err[b] = np.sqrt(np.mean(sig_err[s:e] ** 2))

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 5), sharex=True)
    fig.suptitle("Fig 3 — Error per synthesis block")
    ax1.plot(block_rms_py, linewidth=0.8)
    ax1.set_ylabel("RMS signal (Pa)")
    ax1.grid(True, linestyle="--", alpha=0.15)

    ax2.plot(block_rms_err, color="tab:red", linewidth=0.8)
    ax2.set_ylabel("RMS error (Pa)")
    ax2.set_xlabel("Block index")
    ax2.grid(True, linestyle="--", alpha=0.15)
    fig.tight_layout()

    # ==================================================================
    # Fig 4 — Per-component SPL error spectrograms
    # ==================================================================
    if component_available:
        n_comp = len(component_available)
        fig, axes = plt.subplots(1, n_comp, figsize=(6 * n_comp, 4), squeeze=False)
        fig.suptitle("Fig 4 — SPL error per component")
        for ax, (name, (c_py, c_mat)) in zip(axes[0], component_available.items()):
            spl_c_py, f_c, t_c = compute_spl(c_py)
            spl_c_mat, _, _ = compute_spl(c_mat)
            c_err = np.abs(spl_c_py - spl_c_mat)
            im = ax.imshow(c_err, extent=[t_c[0], t_c[-1], f_c[0] / 1000, f_c[-1] / 1000],
                           aspect="auto", origin="lower", cmap="inferno")
            ax.set_title(f"{name}\nMAE={np.mean(c_err):.2f} dB")
            ax.set_xlabel("Time (s)")
            ax.set_ylim(0, 15)
            if ax is axes[0][0]:
                ax.set_ylabel("Frequency (kHz)")
            divider = make_axes_locatable(ax)
            cax = divider.append_axes("right", size="4%", pad=0.1)
            fig.colorbar(im, cax=cax).set_label("|SPL error| (dB)")
        plt.tight_layout()

    # ==================================================================
    # Fig 5 — Lag-corrected spectrogram comparison
    # ==================================================================
    if lag_offset != 0:
        spl_py_a, f_a, t_a = compute_spl(sig_py_aligned)
        spl_mat_a, _, _ = compute_spl(sig_mat_aligned)
        spl_err_a = np.abs(spl_py_a - spl_mat_a)

        fig, axs = plt.subplots(1, 3, figsize=(18, 5), sharey=True)
        fig.suptitle(f"Fig 5 — Lag-corrected spectrogram (shifted {lag_offset} samples)\n"
                     f"Original MAE = {mae_original:.2f} dB → Corrected MAE = {mae_aligned:.2f} dB")

        titles = ["Python (shifted)", "MATLAB", "Abs Error (dB)"]
        data = [spl_py_a, spl_mat_a, spl_err_a]
        cmaps = ["jet", "jet", "inferno"]
        vmin_a = 100
        vmax_a = max(np.max(spl_py_a), np.max(spl_mat_a))

        for ax, title, spl, cmap in zip(axs, titles, data, cmaps):
            im = ax.imshow(spl, extent=[t_a[0], t_a[-1], f_a[0] / 1000, f_a[-1] / 1000],
                           aspect="auto", origin="lower", cmap=cmap,
                           norm=Normalize(vmin=vmin_a, vmax=vmax_a) if "Error" not in title else None)
            ax.set_title(title)
            ax.set_xlabel("Time (s)")
            ax.set_ylim(0, 15)
            if title == "Python (shifted)":
                ax.set_ylabel("Frequency (kHz)")
            divider = make_axes_locatable(ax)
            cax = divider.append_axes("right", size="4%", pad=0.1)
            fig.colorbar(im, cax=cax).set_label("SPL (dB re 20 µPa)")
        plt.tight_layout(rect=[0, 0.05, 1, 0.92])

    print("\n======== DONE ========\n")
    plt.show()


if __name__ == "__main__":
    main()
