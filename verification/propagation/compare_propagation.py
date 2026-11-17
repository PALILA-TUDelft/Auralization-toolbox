"""
Verification: compare Python propagation vectors against MATLAB reference.

Usage:
  1. Run the auralization pipeline in Python  -> saves propagation_python.npz
  2. Export matching variables from MATLAB     -> propagation_matlab.mat
  3. Run this script:  python verification/propagation/compare_propagation.py

Expected MATLAB .mat variable names:
  time, freq,
  thetaReflectedRay, propDistanceReflectedRay, propagation_time,
  launchAngle_direct, launchAngle_reflected,
  spherical_direct (N x 2), spherical_reflected (N x 2),
  spherical_reflected_smooth (N x 2),
  overhead_idx (scalar),
  tf_overhead_individual (nFreq x 2, complex),
  tf_overhead_combined   (nFreq,   complex)
"""
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

import numpy as np
from scipy.io import loadmat
import matplotlib.pyplot as plt

FOLDER = os.path.dirname(__file__) or "verification/propagation"
PY_PATH = os.path.join(FOLDER, "propagation_python.npz")
MAT_PATH = os.path.join(FOLDER, "propagation_matlab.mat")


def load_data():
    if not os.path.isfile(PY_PATH):
        raise FileNotFoundError(f"Python data not found: {PY_PATH}\nRun the auralization pipeline first.")
    if not os.path.isfile(MAT_PATH):
        raise FileNotFoundError(f"MATLAB data not found: {MAT_PATH}\nExport from MATLAB first.")
    py = np.load(PY_PATH)
    mat = loadmat(MAT_PATH)
    return py, mat


def sq(arr):
    return np.asarray(arr).squeeze()


def print_metric(label, py_arr, mat_arr):
    py_arr = sq(py_arr)
    mat_arr = sq(mat_arr)
    min_len = min(len(py_arr), len(mat_arr))
    py_arr = py_arr[:min_len]
    mat_arr = mat_arr[:min_len]
    max_abs = np.max(np.abs(py_arr - mat_arr))
    mean_abs = np.mean(np.abs(py_arr - mat_arr))
    denom = np.maximum(np.abs(mat_arr), 1e-12)
    max_rel = np.max(np.abs(py_arr - mat_arr) / denom)
    print(f"  {label:40s}  max_abs={max_abs:.6e}  mean_abs={mean_abs:.6e}  max_rel={max_rel:.6e}")
    return max_abs


def overlay_plot(ax, t_py, y_py, t_mat, y_mat, ylabel, title=None):
    ax.plot(t_py, y_py, label="Python")
    ax.plot(t_mat, y_mat, "--", label="MATLAB")
    ax.set_ylabel(ylabel)
    if title:
        ax.set_title(title)
    ax.legend(frameon=False, fontsize=8)
    ax.grid(True, linestyle="--", alpha=0.15)


def error_plot(ax, t, err, ylabel):
    ax.plot(t[:len(err)], err, color="tab:red")
    ax.set_ylabel(ylabel)
    ax.grid(True, linestyle="--", alpha=0.15)


def main():
    py, mat = load_data()

    t_py = sq(py["time"])
    t_mat = sq(mat["time"])
    freq_py = sq(py["freq"])
    freq_mat = sq(mat["freq"])

    print("\n======== PROPAGATION VERIFICATION ========\n")
    print("[LENGTH CHECK]")
    print(f"  time:  Python={len(t_py)}, MATLAB={len(t_mat)}")
    print(f"  freq:  Python={len(freq_py)}, MATLAB={len(freq_mat)}")

    min_n = min(len(t_py), len(t_mat))
    t_plot = t_py[:min_n]

    # ---- Numerical metrics ----
    print("\n[NUMERICAL COMPARISON]")
    print_metric("time", t_py, t_mat)
    print_metric("freq", freq_py, freq_mat)
    print_metric("thetaReflectedRay", py["thetaReflectedRay"], mat["thetaReflectedRay"])
    print_metric("propDistanceReflectedRay", py["propDistanceReflectedRay"], mat["propDistanceReflectedRay"])
    print_metric("propagation_time (direct)", py["propagation_time"][:, 0], sq(mat["propagation_time"])[:, 0])
    print_metric("propagation_time (reflected)", py["propagation_time"][:, 1], sq(mat["propagation_time"])[:, 1])
    print_metric("launchAngle_direct", py["launchAngle_direct"], mat["launchAngle_direct"])
    print_metric("launchAngle_reflected", py["launchAngle_reflected"], mat["launchAngle_reflected"])
    print_metric("spherical_direct (azimuth)", py["spherical_direct"][:, 0], sq(mat["spherical_direct"])[:, 0])
    print_metric("spherical_direct (elevation)", py["spherical_direct"][:, 1], sq(mat["spherical_direct"])[:, 1])
    print_metric("spherical_reflected (azimuth)", py["spherical_reflected"][:, 0], sq(mat["spherical_reflected"])[:, 0])
    print_metric("spherical_reflected (elevation)", py["spherical_reflected"][:, 1], sq(mat["spherical_reflected"])[:, 1])
    print_metric("spherical_reflected_smooth (az)", py["spherical_reflected_smooth"][:, 0], sq(mat["spherical_reflected_smooth"])[:, 0])
    print_metric("spherical_reflected_smooth (el)", py["spherical_reflected_smooth"][:, 1], sq(mat["spherical_reflected_smooth"])[:, 1])

    # TF at overhead
    tf_ind_py = py["tf_overhead_individual"]
    tf_comb_py = sq(py["tf_overhead_combined"])
    tf_ind_mat = sq(mat["tf_overhead_individual"])
    tf_comb_mat = sq(mat["tf_overhead_combined"])
    min_f = min(len(freq_py), len(freq_mat))
    print_metric("|TF| direct (overhead)", np.abs(tf_ind_py[:min_f, 0]), np.abs(tf_ind_mat[:min_f, 0]))
    print_metric("|TF| reflected (overhead)", np.abs(tf_ind_py[:min_f, 1]), np.abs(tf_ind_mat[:min_f, 1]))
    print_metric("|TF| combined (overhead)", np.abs(tf_comb_py[:min_f]), np.abs(tf_comb_mat[:min_f]))

    # ---- helper ----
    theta_py = sq(py["thetaReflectedRay"])[:min_n]
    theta_mat = sq(mat["thetaReflectedRay"])[:min_n]
    dist_py = sq(py["propDistanceReflectedRay"])[:min_n]
    dist_mat = sq(mat["propDistanceReflectedRay"])[:min_n]

    # ================================================================
    # Fig 1 – reflected ray: incidence angle & propagation distance
    # ================================================================
    fig, axes = plt.subplots(2, 2, figsize=(14, 7), sharex="col")
    fig.suptitle("Fig 1 — Reflected ray: incidence angle and propagation distance")

    overlay_plot(axes[0, 0], t_plot, np.degrees(theta_py), t_plot, np.degrees(theta_mat),
                 r"$\theta_{\mathrm{in}}$ (deg)", "Incidence angle")
    error_plot(axes[1, 0], t_plot, np.degrees(np.abs(theta_py - theta_mat)),
               r"$|\Delta\theta_{\mathrm{in}}|$ (deg)")
    axes[1, 0].set_xlabel("Time (s)")

    overlay_plot(axes[0, 1], t_plot, dist_py, t_plot, dist_mat,
                 "$r_2$ (m)", "Propagation distance")
    error_plot(axes[1, 1], t_plot, np.abs(dist_py - dist_mat), "$|\\Delta r_2|$ (m)")
    axes[1, 1].set_xlabel("Time (s)")
    fig.tight_layout()

    # ================================================================
    # Fig 2 – launch angles (direct & reflected)
    # ================================================================
    la_d_py = sq(py["launchAngle_direct"])[:min_n]
    la_d_mat = sq(mat["launchAngle_direct"])[:min_n]
    la_r_py = sq(py["launchAngle_reflected"])[:min_n]
    la_r_mat = sq(mat["launchAngle_reflected"])[:min_n]

    fig, axes = plt.subplots(2, 2, figsize=(14, 7), sharex="col")
    fig.suptitle("Fig 2 — Launch angles (ART)")

    overlay_plot(axes[0, 0], t_plot, la_d_py, t_plot, la_d_mat,
                 r"$\alpha^*$ (deg)", "Direct path")
    error_plot(axes[1, 0], t_plot, np.abs(la_d_py - la_d_mat), r"$|\Delta\alpha^*|$ (deg)")
    axes[1, 0].set_xlabel("Time (s)")

    overlay_plot(axes[0, 1], t_plot, la_r_py, t_plot, la_r_mat,
                 r"$\alpha^*$ (deg)", "Reflected path")
    error_plot(axes[1, 1], t_plot, np.abs(la_r_py - la_r_mat), r"$|\Delta\alpha^*|$ (deg)")
    axes[1, 1].set_xlabel("Time (s)")
    fig.tight_layout()

    # ================================================================
    # Fig 3 – propagation time (direct & reflected)
    # ================================================================
    pt_py = py["propagation_time"][:min_n, :]
    pt_mat = sq(mat["propagation_time"])[:min_n, :]

    fig, axes = plt.subplots(2, 2, figsize=(14, 7), sharex="col")
    fig.suptitle("Fig 3 — Propagation time")

    overlay_plot(axes[0, 0], t_plot, pt_py[:, 0], t_plot, pt_mat[:, 0],
                 "Prop. time (s)", "Direct path")
    error_plot(axes[1, 0], t_plot, np.abs(pt_py[:, 0] - pt_mat[:, 0]), "$|\\Delta t|$ (s)")
    axes[1, 0].set_xlabel("Time (s)")

    overlay_plot(axes[0, 1], t_plot, pt_py[:, 1], t_plot, pt_mat[:, 1],
                 "Prop. time (s)", "Reflected path")
    error_plot(axes[1, 1], t_plot, np.abs(pt_py[:, 1] - pt_mat[:, 1]), "$|\\Delta t|$ (s)")
    axes[1, 1].set_xlabel("Time (s)")
    fig.tight_layout()

    # ================================================================
    # Fig 4 – spherical angles (FABIAN convention)
    # ================================================================
    sd_py = py["spherical_direct"][:min_n, :]
    sd_mat = sq(mat["spherical_direct"])[:min_n, :]
    sr_py = py["spherical_reflected"][:min_n, :]
    sr_mat = sq(mat["spherical_reflected"])[:min_n, :]
    srs_py = py["spherical_reflected_smooth"][:min_n, :]
    srs_mat = sq(mat["spherical_reflected_smooth"])[:min_n, :]

    fig, axes = plt.subplots(2, 2, figsize=(14, 8), sharex="col")
    fig.suptitle("Fig 4 — Spherical angles (FABIAN convention)")

    overlay_plot(axes[0, 0], t_plot, sd_py[:, 0], t_plot, sd_mat[:, 0],
                 "Azimuth (deg)", "Direct path — azimuth")
    overlay_plot(axes[0, 1], t_plot, sd_py[:, 1], t_plot, sd_mat[:, 1],
                 "Elevation (deg)", "Direct path — elevation")
    overlay_plot(axes[1, 0], t_plot, sr_py[:, 0], t_plot, sr_mat[:, 0],
                 "Azimuth (deg)", "Reflected path — azimuth")
    overlay_plot(axes[1, 1], t_plot, sr_py[:, 1], t_plot, sr_mat[:, 1],
                 "Elevation (deg)", "Reflected path — elevation")
    for ax in axes[1, :]:
        ax.set_xlabel("Time (s)")
    fig.tight_layout()

    fig, axes = plt.subplots(1, 2, figsize=(14, 4))
    fig.suptitle("Fig 4b — Reflected path spherical angles (smoothed)")
    overlay_plot(axes[0], t_plot, srs_py[:, 0], t_plot, srs_mat[:, 0],
                 "Azimuth (deg)", "Smoothed azimuth")
    overlay_plot(axes[1], t_plot, srs_py[:, 1], t_plot, srs_mat[:, 1],
                 "Elevation (deg)", "Smoothed elevation")
    axes[0].set_xlabel("Time (s)")
    axes[1].set_xlabel("Time (s)")
    fig.tight_layout()

    # ================================================================
    # Fig 5 – transfer function at overhead position
    # ================================================================
    f_plot = freq_py[:min_f]

    att_d_py = 10.0 * np.log10(np.abs(tf_ind_py[:min_f, 0]) ** 2 + 1e-30)
    att_r_py = 10.0 * np.log10(np.abs(tf_ind_py[:min_f, 1]) ** 2 + 1e-30)
    att_c_py = 10.0 * np.log10(np.abs(tf_comb_py[:min_f]) ** 2 + 1e-30)

    att_d_mat = 10.0 * np.log10(np.abs(tf_ind_mat[:min_f, 0]) ** 2 + 1e-30)
    att_r_mat = 10.0 * np.log10(np.abs(tf_ind_mat[:min_f, 1]) ** 2 + 1e-30)
    att_c_mat = 10.0 * np.log10(np.abs(tf_comb_mat[:min_f]) ** 2 + 1e-30)

    fig, axes = plt.subplots(3, 2, figsize=(14, 10))
    fig.suptitle("Fig 5 — Transfer function at overhead position")

    axes[0, 0].semilogx(f_plot, att_d_py, label="Python")
    axes[0, 0].semilogx(f_plot, att_d_mat, "--", label="MATLAB")
    axes[0, 0].set_title("Direct path")
    axes[0, 0].set_ylabel("Attenuation (dB)")
    axes[0, 0].legend(frameon=False, fontsize=8)
    axes[0, 0].set_xlim(20, 25e3)
    axes[0, 0].grid(True, linestyle="--", alpha=0.15)

    axes[0, 1].semilogx(f_plot, np.abs(att_d_py - att_d_mat), color="tab:red")
    axes[0, 1].set_title("Direct — abs error")
    axes[0, 1].set_ylabel("|error| (dB)")
    axes[0, 1].set_xlim(20, 25e3)
    axes[0, 1].grid(True, linestyle="--", alpha=0.15)

    axes[1, 0].semilogx(f_plot, att_r_py, label="Python")
    axes[1, 0].semilogx(f_plot, att_r_mat, "--", label="MATLAB")
    axes[1, 0].set_title("Reflected path")
    axes[1, 0].set_ylabel("Attenuation (dB)")
    axes[1, 0].legend(frameon=False, fontsize=8)
    axes[1, 0].set_xlim(20, 25e3)
    axes[1, 0].grid(True, linestyle="--", alpha=0.15)

    axes[1, 1].semilogx(f_plot, np.abs(att_r_py - att_r_mat), color="tab:red")
    axes[1, 1].set_title("Reflected — abs error")
    axes[1, 1].set_ylabel("|error| (dB)")
    axes[1, 1].set_xlim(20, 25e3)
    axes[1, 1].grid(True, linestyle="--", alpha=0.15)

    axes[2, 0].semilogx(f_plot, att_c_py, label="Python")
    axes[2, 0].semilogx(f_plot, att_c_mat, "--", label="MATLAB")
    axes[2, 0].set_title("Combined (direct + reflected)")
    axes[2, 0].set_ylabel("Attenuation (dB)")
    axes[2, 0].set_xlabel("Frequency (Hz)")
    axes[2, 0].legend(frameon=False, fontsize=8)
    axes[2, 0].set_xlim(20, 25e3)
    axes[2, 0].grid(True, linestyle="--", alpha=0.15)

    axes[2, 1].semilogx(f_plot, np.abs(att_c_py - att_c_mat), color="tab:red")
    axes[2, 1].set_title("Combined — abs error")
    axes[2, 1].set_ylabel("|error| (dB)")
    axes[2, 1].set_xlabel("Frequency (Hz)")
    axes[2, 1].set_xlim(20, 25e3)
    axes[2, 1].grid(True, linestyle="--", alpha=0.15)

    fig.tight_layout()

    print("\n======== DONE ========\n")
    plt.show()


if __name__ == "__main__":
    main()
