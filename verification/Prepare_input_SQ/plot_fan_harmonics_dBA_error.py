import numpy as np
import matplotlib.pyplot as plt
from scipy.io import loadmat

# === Load MATLAB output ===
mat = loadmat("verification/Prepare_input_SQ/MATLAB_trimmed_output.mat", simplify_cells=True)
mat_spec = mat["source_SPECTROGRAM_trimmed"]
mat_spec_dba = mat["source_SPECTROGRAM_dBA_trimmed"]
fan_toc_mat = np.array(mat_spec["fan_harmonics_toc"])  # shape [nFreq, nTime]
fan_dba_mat = np.array(mat_spec_dba["fan_harmonics"])

# === Load Python output ===
npz = np.load("verification/Prepare_input_SQ/python_trimmed_output.npz", allow_pickle=True)
py_spec = npz["source_SPECTROGRAM_trimmed"].item()
py_spec_dba = npz["source_SPECTROGRAM_dBA_trimmed"].item()
fan_toc_py = np.array(py_spec["fan_harmonics_toc"])
fan_dba_py = np.array(py_spec_dba["fan_harmonics"])

# === Compute mean per band (SPL and dBA) ===
mean_fan_toc_mat = np.mean(fan_toc_mat, axis=1)
mean_fan_toc_py = np.mean(fan_toc_py, axis=1)
mean_fan_dba_mat = np.mean(fan_dba_mat, axis=1)
mean_fan_dba_py = np.mean(fan_dba_py, axis=1)

# === Plot SPL and dBA Comparison ===
plt.figure(figsize=(10, 6))
plt.subplot(2, 1, 1)
plt.plot(mean_fan_toc_mat, 'k--', label="MATLAB SPL")
plt.plot(mean_fan_toc_py, 'k-', label="Python SPL")
plt.title("Mean fan_harmonics_toc (SPL)")
plt.ylabel("dB")
plt.grid(True)
plt.legend()

plt.subplot(2, 1, 2)
plt.plot(mean_fan_dba_mat, 'b--', label="MATLAB A-weighted")
plt.plot(mean_fan_dba_py, 'b-', label="Python A-weighted")
plt.title("Mean fan_harmonics_dBA")
plt.xlabel("Frequency Band Index")
plt.ylabel("dBA")
plt.grid(True)
plt.legend()
plt.tight_layout()
plt.show()

# === Print tabulated differences ===
print("\n{:<10} {:>12} {:>12} {:>12} {:>12}".format("FreqIdx", "SPL_MAT", "SPL_PY", "dBA_MAT", "dBA_PY"))
for i in range(len(mean_fan_toc_py)):
    print("{:<10d} {:>12.4f} {:>12.4f} {:>12.4f} {:>12.4f}".format(
        i, mean_fan_toc_mat[i], mean_fan_toc_py[i], mean_fan_dba_mat[i], mean_fan_dba_py[i]
    ))
