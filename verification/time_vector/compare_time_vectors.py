import numpy as np
import matplotlib.pyplot as plt
from scipy.io import loadmat

# Load both time vectors
python_data = np.load("verification/time_vector/time_vectors_python.npz")
matlab_data = loadmat("verification/time_vector/time_vectors_matlab2.mat")
# Extract
t_py_pan = python_data["time_PANAM_auralization"]
t_py = python_data["time"]
t_mat_pan = matlab_data["time_PANAM_auralization"].squeeze()
t_mat = matlab_data["time"].squeeze()

print(f"[DEBUG] t_py_pan shape: {t_py_pan.shape}")
print(f"[DEBUG] t_mat_pan shape: {t_mat_pan.shape}")
print(f"[DEBUG] t_py shape: {t_py.shape}")
print(f"[DEBUG] t_mat shape: {t_mat.shape}")


# Compare PANAM auralization time
plt.figure()
plt.plot(t_py_pan, label="Python PANAM Auralization Time")
plt.plot(t_mat_pan, '--', label="MATLAB PANAM Auralization Time")
plt.title("PANAM Auralization Time Comparison")
plt.legend()
plt.grid()

# Compare synthesis time
plt.figure()
plt.plot(t_py, label="Python Synth Time")
plt.plot(t_mat, '--', label="MATLAB Synth Time")
plt.title("Synthesized Time Comparison")
plt.legend()
plt.grid()

# Print some metrics
print("\n[COMPARISON METRICS]")
print(f"time_PANAM_auralization length match: {len(t_py_pan) == len(t_mat_pan)}")
print(f"time_PANAM_auralization max abs diff: {np.max(np.abs(t_py_pan - t_mat_pan)):.6e}")
print(f"time length match: {len(t_py) == len(t_mat)}")
print(f"time max abs diff: {np.max(np.abs(t_py - t_mat)):.6e}")

plt.show()