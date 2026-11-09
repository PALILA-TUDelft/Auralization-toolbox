"""
Verification: flight-profile vectors (x, z/altitude, TAS, thrust).

Python side  : verification/flight_profile/flight_profile_python.npz
               (written by main.py when run with --verification)
MATLAB side  : verification/flight_profile/flight_profile_matlab.mat
               (drop it here; see expected variable names below)

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
PY_PATH = os.path.join(FOLDER, "flight_profile_python.npz")
MAT_PATH = os.path.join(FOLDER, "flight_profile_matlab.mat")

# Expected MATLAB variable names (adjust to match your export .m):
MAT_VARS = {"x": "x", "z": "z", "TAS": "TAS", "thrust": "thrust"}


def main():
    py = np.load(PY_PATH)
    x_py = py["x"] / 1000.0          # m -> km
    z_py = py["z"] / 1000.0
    tas_py = py["TAS"]
    thr_py = py["thrust"]

    have_mat = loadmat is not None and os.path.isfile(MAT_PATH)
    if have_mat:
        mat = loadmat(MAT_PATH)
        x_m = np.squeeze(mat[MAT_VARS["x"]]) / 1000.0
        z_m = np.squeeze(mat[MAT_VARS["z"]]) / 1000.0
        tas_m = np.squeeze(mat[MAT_VARS["TAS"]])
        thr_m = np.squeeze(mat[MAT_VARS["thrust"]])

        print("\n[FLIGHT PROFILE COMPARISON]")
        for name, a, b in (("z (altitude)", z_py, z_m), ("TAS", tas_py, tas_m), ("thrust", thr_py, thr_m)):
            n = min(len(a), len(b))
            diff = np.abs(a[:n] - b[:n])
            print(f"  {name:14s}  max_abs={np.max(diff):.6e}  mean_abs={np.mean(diff):.6e}")
    else:
        print(f"[INFO] {MAT_PATH} not found — plotting Python vectors only.")

    fig, ax1 = plt.subplots(figsize=(9, 5))
    ax2 = ax1.twinx()
    ax1.plot(x_py, z_py, "k-", label="Altitude (Py)")
    ax2.plot(x_py, tas_py, "b-", label="TAS (Py)")
    ax2.plot(x_py, thr_py, "r-", label="Thrust (Py)")
    if have_mat:
        ax1.plot(x_m, z_m, "k--", label="Altitude (MATLAB)")
        ax2.plot(x_m, tas_m, "b--", label="TAS (MATLAB)")
        ax2.plot(x_m, thr_m, "r--", label="Thrust (MATLAB)")
    ax1.set_xlabel("Distance, $x$ (km)")
    ax1.set_ylabel("Altitude AGL (km)")
    ax2.set_ylabel("TAS (m/s), Thrust (kN)")
    lines = ax1.get_lines() + ax2.get_lines()
    ax1.legend(lines, [l.get_label() for l in lines], loc="best", fontsize=8)
    ax1.set_title("Flight profile — Python vs MATLAB")
    fig.tight_layout()
    plt.show()


if __name__ == "__main__":
    main()
