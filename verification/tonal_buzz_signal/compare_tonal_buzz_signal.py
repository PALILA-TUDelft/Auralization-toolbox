import sys, os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

import numpy as np
import matplotlib.pyplot as plt
from scipy.io import loadmat
from scipy.signal import correlate
from matplotlib.colors import Normalize
from mpl_toolkits.axes_grid1 import make_axes_locatable

from utilities.plot_utils import myspecgram
from utilities.ini_parser import ini2dict
import globals

# === Setup Globals ===
globals.input_file = ini2dict("input_data/input_file_auralization.ini")
globals.pref = 20e-6
globals.fs = int(globals.input_file.get("sampling_freq", 48000))

fs = globals.fs
pref = globals.pref
window_size = 1024
overlap = 0.75

# === Load signals ===
matlab_data = loadmat("verification/tonal_buzz_signal/tonal_buzz_signal_matlab.mat")
signal_matlab = matlab_data["TonalSignal_Buzzsaw"].squeeze()

python_data = np.load("verification/tonal_buzz_signal/tonal_buzz_signal_python.npz")
signal_python = python_data["signal"].squeeze()

min_len = min(len(signal_matlab), len(signal_python))
signal_matlab = signal_matlab[:min_len]
signal_python = signal_python[:min_len]
# Align Python to MATLAB (remove 960 samples from start)
signal_python_aligned = signal_python[960:]
signal_matlab_aligned = signal_matlab[:len(signal_python_aligned)]

def compute_spl(signal):
    P, F, T = myspecgram(signal, fs, window_size, overlap)
    SPL = 20 * np.log10(np.abs(P) / pref + 1e-12)
    return SPL, F, T

spl_py, f_py, t_py = compute_spl(signal_python)
spl_mat, f_mat, t_mat = compute_spl(signal_matlab)
spl_err = np.abs(spl_py - spl_mat)
mae_spl = np.mean(spl_err)

max_error = np.max(spl_err)
max_idx = np.unravel_index(np.argmax(spl_err), spl_err.shape)
f_max = f_py[max_idx[0]] / 1000
t_max = t_py[max_idx[1]]

print(f"[DEBUG] Max SPL error = {max_error:.2f} dB at f = {f_max:.2f} kHz, t = {t_max:.2f} s")

print(f"[DEBUG] Python SPL at max error: {spl_py[max_idx]:.2f} dB")
print(f"[DEBUG] MATLAB SPL at max error: {spl_mat[max_idx]:.2f} dB")


# === Load trimmed source data for tonal inspection ===
# Load trimmed source and flight profile
debug_data = np.load("verification/Prepare_input_SQ/python_trimmed_output.npz", allow_pickle=True)
source_data_trimmed = debug_data["source_data_trimmed"]
time_panam = np.array([entry["source_time"] for entry in source_data_trimmed])

# Find the time index near the spike
i_time = np.argmin(np.abs(time_panam - t_max))

# Clamp for safety
window = 1
start = max(i_time - window, 0)
end = min(i_time + window + 1, len(source_data_trimmed))

input_subset = source_data_trimmed[start:end]
time_subset = time_panam[start:end]



from auralization.private.get_tonal_input import get_tonal_input
input_buzz = get_tonal_input(input_subset, time_subset, "buzzsaw", tag_auralization="")

print(f"\n[DEBUG] Tonal content around t = {time_panam[i_time]:.3f} s:")
for b in range(input_buzz["tones"]):
    f_khz = input_buzz["tonesFreqTime"][b, window] / 1000
    spl = input_buzz["tonesSPLTime"][b, window]
    if 23.5 < f_khz < 24.5:
        print(f" - Tone {b}: {f_khz:.2f} kHz, SPL = {spl:.2f} dB")

# === Correlation offset ===
corr = correlate(signal_python, signal_matlab, mode='full')
lags = np.arange(-len(signal_python) + 1, len(signal_matlab))
lag_offset = lags[np.argmax(corr)]
print(f"[DEBUG] Max correlation lag offset: {lag_offset} samples (≈ {lag_offset/fs:.6f} s)")

plt.figure()
plt.imshow(spl_err, aspect='auto', origin='lower', extent=[t_py[0], t_py[-1], f_py[0]/1e3, f_py[-1]/1e3], cmap='hot', norm=Normalize(vmin=0, vmax=10))
plt.colorbar(label='SPL Error (dB)')
plt.xlabel("Time (s)")
plt.ylabel("Frequency (kHz)")
plt.title("SPL Error Between Python and MATLAB Tonal Buzzsaw Signal")
plt.tight_layout()
plt.show()