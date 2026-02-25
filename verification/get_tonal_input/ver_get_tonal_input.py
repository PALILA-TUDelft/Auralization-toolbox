import numpy as np
import scipy.io
import matplotlib.pyplot as plt

# === CONFIG ===


PYTHON_FILE = "verification/get_tonal_input/tones_spl_debug_buzzsaw.npz"
MATLAB_FILE = "verification/get_tonal_input/tones_spl_debug_matlab_b.mat"
KEY_PYTHON = "signal"  # or "signal" ; tones_spl_time
KEY_MATLAB = "tonesSPLTime"


# PYTHON_FILE = "verification/get_tonal_input/tones_spl_debug_fan.npz"
# MATLAB_FILE = "verification/get_tonal_input/tones_spl_debug_matlab_f.mat"
# KEY_PYTHON = "signal"  # or "signal" ; tones_spl_time
# KEY_MATLAB = "tonesSPLTime"

# === LOAD ===
py = np.load(PYTHON_FILE)[KEY_PYTHON]
mat = scipy.io.loadmat(MATLAB_FILE)[KEY_MATLAB]

# === Sanity check ===z
print(f"[INFO] Python shape: {py.shape}")
print(f"[INFO] MATLAB shape: {mat.shape}")

# === Match shape (just compare tone 1) ===
tone_py = py[0, :]
tone_mat = mat[0, :]

# === Debug: print peaks ===
peak_py = np.max(tone_py)
peak_idx_py = np.where(tone_py == peak_py)[0]
print(f"[PYTHON] Peak SPL = {peak_py:.2f} dB at indices: {peak_idx_py}")

peak_mat = np.max(tone_mat)
peak_idx_mat = np.where(tone_mat == peak_mat)[0]
print(f"[MATLAB] Peak SPL = {peak_mat:.2f} dB at indices: {peak_idx_mat}")

# === Plot ===
plt.figure(figsize=(10, 4))
plt.plot(tone_py, label="Python Tone 1", linewidth=2)
plt.plot(tone_mat, label="MATLAB Tone 1", linestyle="--")
plt.title("Tone 1 SPL Over Time — Python vs MATLAB")
plt.xlabel("Time index")
plt.ylabel("SPL (dB)")
plt.legend()
plt.grid(True)
plt.tight_layout()
plt.show()
