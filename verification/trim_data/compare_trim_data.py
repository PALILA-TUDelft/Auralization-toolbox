"""
Verification: trim-window SPL-vs-time vectors (the TrimData_SPL figure).

Python side  : verification/trim_data/trim_data_python.npz
               written by trim_data_time_distance_based.py under --verification.
               Keys: time, SPL_vs_time, dist, idx_lower, idx_upper, idx_min_dist
MATLAB side  : verification/trim_data/trim_data_matlab.mat

If the MATLAB file is missing, the Python vectors are plotted on their own.
"""
import os
import numpy as np
import matplotlib.pyplot as plt

try:
    from scipy.io import loadmat
except ImportError:
    loadmat = None

FOLDER = os.path.dirname(__file__)
PY_PATH = os.path.join(FOLDER, "trim_data_python.npz")
MAT_PATH = os.path.join(FOLDER, "trim_data_matlab.mat")

# Expected MATLAB variable names (adjust to match your export .m):
MAT_VARS = {"time": "time", "SPL_vs_time": "SPL_vs_time"}


def main():
    py = np.load(PY_PATH)
    t_py = np.squeeze(py["time"])
    spl_py = np.squeeze(py["SPL_vs_time"])
    idx_lo = int(py["idx_lower"])
    idx_hi = int(py["idx_upper"])
    idx_min = int(py["idx_min_dist"])

    have_mat = loadmat is not None and os.path.isfile(MAT_PATH)
    if have_mat:
        mat = loadmat(MAT_PATH)
        t_m = np.squeeze(mat[MAT_VARS["time"]])
        spl_m = np.squeeze(mat[MAT_VARS["SPL_vs_time"]])
        n = min(len(spl_py), len(spl_m))
        diff = np.abs(spl_py[:n] - spl_m[:n])
        print("\n[TRIM SPL COMPARISON]")
        print(f"  SPL_vs_time  max_abs={np.max(diff):.6e}  mean_abs={np.mean(diff):.6e}")
    else:
        print(f"[INFO] {MAT_PATH} not found — plotting Python vectors only.")

    fig, ax = plt.subplots(figsize=(9, 5))
    ax.plot(t_py, spl_py, label="SPL vs time (Py)")
    ax.axvline(t_py[idx_min], color="r", linestyle="--", label="Closest approach")
    ax.axvspan(t_py[idx_lo], t_py[idx_hi], color="gray", alpha=0.3, label="Trim window")
    if have_mat:
        ax.plot(t_m, spl_m, "--", label="SPL vs time (MATLAB)")
    ax.set_xlabel("Source time, $t_s$ (s)")
    ax.set_ylabel("SPL (dB re 20 µPa)")
    ax.set_title("Trim-window SPL — Python vs MATLAB")
    ax.legend()
    ax.grid(True)
    fig.tight_layout()
    plt.show()


if __name__ == "__main__":
    main()
