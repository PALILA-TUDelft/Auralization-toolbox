"""
Verification: buzzsaw doppler / emission-angle vectors.

Python side  : verification/doppler_theta_buzzsaw/doppler_theta_buzzsaw_python.npz
               (theta_deg, doppler_ratio) written by get_tonal_input.py under --verification
MATLAB side  : verification/doppler_theta_buzzsaw/doppler_theta_buzzsaw_matlab.mat

These are the two curves in the MATLAB "plot angle theta_doppler" block.
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
PY_PATH = os.path.join(FOLDER, "doppler_theta_buzzsaw_python.npz")
MAT_PATH = os.path.join(FOLDER, "doppler_theta_buzzsaw_matlab.mat")

# Expected MATLAB variable names (adjust to match your export .m):
MAT_VARS = {"theta_deg": "theta_deg", "doppler_ratio": "doppler_ratio"}


def main():
    py = np.load(PY_PATH)
    theta_py = np.squeeze(py["theta_deg"])
    dopp_py = np.squeeze(py["doppler_ratio"])
    x = np.arange(len(theta_py))

    have_mat = loadmat is not None and os.path.isfile(MAT_PATH)
    if have_mat:
        mat = loadmat(MAT_PATH)
        theta_m = np.squeeze(mat[MAT_VARS["theta_deg"]])
        dopp_m = np.squeeze(mat[MAT_VARS["doppler_ratio"]])
        print("\n[DOPPLER / THETA COMPARISON]")
        for name, a, b in (("theta_deg", theta_py, theta_m), ("doppler_ratio", dopp_py, dopp_m)):
            n = min(len(a), len(b))
            diff = np.abs(a[:n] - b[:n])
            print(f"  {name:14s}  max_abs={np.max(diff):.6e}  mean_abs={np.mean(diff):.6e}")
    else:
        print(f"[INFO] {MAT_PATH} not found — plotting Python vectors only.")

    fig, ax1 = plt.subplots(figsize=(9, 5))
    a, = ax1.plot(x, theta_py, color="tab:blue", label=r"$\theta$ (Py)")
    ax1.axhline(90, color="black", linewidth=0.8)
    ax1.set_ylim(0, 180)
    ax1.set_ylabel(r"$\theta$ (deg)")
    ax1.set_xlabel("Time (bins)")

    ax2 = ax1.twinx()
    b, = ax2.plot(x, dopp_py, color="tab:orange", label=r"$f'/f_0$ (Py)")
    ax2.set_ylim(0.5, 1.5)
    ax2.set_ylabel(r"Doppler-shift, $f'/f_0$")

    handles = [a, b]
    if have_mat:
        c, = ax1.plot(np.arange(len(theta_m)), theta_m, "--", color="tab:cyan", label=r"$\theta$ (MATLAB)")
        d, = ax2.plot(np.arange(len(dopp_m)), dopp_m, "--", color="tab:red", label=r"$f'/f_0$ (MATLAB)")
        handles += [c, d]
    ax1.legend(handles, [h.get_label() for h in handles], loc="lower right")
    ax1.set_title("Buzzsaw doppler / emission angle — Python vs MATLAB")
    fig.tight_layout()
    plt.show()


if __name__ == "__main__":
    main()
