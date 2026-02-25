import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

import numpy as np
from scipy.io import loadmat
import matplotlib.pyplot as plt
from matplotlib.colors import Normalize
from mpl_toolkits.axes_grid1 import make_axes_locatable
from utilities.plot_utils import myspecgram  # Now it should work
from scipy.signal import correlate
    
# Paths
folder = "verification/spectrogram_overall_signal"
matlab_data = loadmat(os.path.join(folder, "overall_signal_matlab.mat"))

signal_matlab = matlab_data["auralizedOverallSignal"].squeeze()

python_data = np.load("verification/spectrogram_overall_signal/overall_signal_python.npz")
signal_python = python_data["signal"].squeeze()


# Ensure same length
min_len = min(len(signal_matlab), len(signal_python))
signal_matlab = signal_matlab[:min_len]
signal_python = signal_python[:min_len]

# Constants
fs = 48000
pref = 20e-6
window_size = 1024
overlap = 0.75

def compute_spl(signal):
    P, F, T = myspecgram(signal, fs, window_size, overlap)
    SPL = 20 * np.log10(np.abs(P) / pref + 1e-12)
    return SPL, F, T

spl_py, f_py, t_py = compute_spl(signal_python)
spl_mat, f_mat, t_mat = compute_spl(signal_matlab)
spl_err = np.abs(spl_py - spl_mat)
mae_spl = np.mean(spl_err)

print(f"[COMPARE] SPL-based MAE: {mae_spl:.2f} dB")

# --- Plot side-by-side spectrograms ---
fig, axs = plt.subplots(1, 3, figsize=(18, 5), sharey=True)
fig.suptitle(f"Overall Signal Comparison\nMean SPL Abs Error = {mae_spl:.2f} dB", fontsize=14)

titles = ["Python", "MATLAB", "Abs Error [dB]"]
data = [spl_py, spl_mat, spl_err]
cmaps = ["jet", "jet", "inferno"]
vmin = 100
vmax = max(np.max(spl_py), np.max(spl_mat))

for ax, title, spl, cmap in zip(axs, titles, data, cmaps):
    im = ax.imshow(spl, extent=[t_py[0], t_py[-1], f_py[0]/1000, f_py[-1]/1000],
                   aspect='auto', origin='lower', cmap=cmap,
                   norm=Normalize(vmin=vmin, vmax=vmax) if "Error" not in title else None)
    ax.set_title(title)
    ax.set_xlabel("Time, $t$ (s)")
    ax.set_xlim(t_py[0], t_py[-1])
    ax.set_ylim(0, 15)
    if title == "Python":
        ax.set_ylabel("Frequency, $f$ (kHz)")
    divider = make_axes_locatable(ax)
    cax = divider.append_axes("right", size="4%", pad=0.1)
    fig.colorbar(im, cax=cax).set_label('SPL, $L_{\\mathrm{Z}}$ (dB re 20$~\\mu$Pa)', fontsize=10)

plt.tight_layout(rect=[0, 0.05, 1, 0.92])
plt.show()

# --- Additional error plots ---
plt.figure(figsize=(10, 4))
plt.imshow(spl_err, extent=[t_py[0], t_py[-1], f_py[0]/1000, f_py[-1]/1000],
           aspect='auto', origin='lower', cmap='inferno')
plt.title("SPL Absolute Error (Python - MATLAB)")
plt.xlabel("Time [s]")
plt.ylabel("Frequency [kHz]")
plt.colorbar(label="Error [dB]")
plt.tight_layout()
plt.show()

mean_error_per_freq = np.mean(spl_err, axis=1)
plt.figure(figsize=(8, 4))
plt.plot(f_py / 1000, mean_error_per_freq)
plt.title("Mean SPL Error per Frequency Bin")
plt.xlabel("Frequency [kHz]")
plt.ylabel("Mean Absolute Error [dB]")
plt.grid(True)
plt.tight_layout()
plt.show()

mean_error_per_time = np.mean(spl_err, axis=0)
plt.figure(figsize=(8, 4))
plt.plot(t_py, mean_error_per_time)
plt.title("Mean SPL Error over Time")
plt.xlabel("Time [s]")
plt.ylabel("Mean Absolute Error [dB]")
plt.grid(True)
plt.tight_layout()
plt.show()

# --- Correlation ---
corr = correlate(signal_python, signal_matlab, mode='full')
lags = np.arange(-len(signal_python) + 1, len(signal_matlab))
lag_offset = lags[np.argmax(corr)]
print(f"[DEBUG] Max correlation lag offset: {lag_offset} samples (≈ {lag_offset/fs:.6f} s)")