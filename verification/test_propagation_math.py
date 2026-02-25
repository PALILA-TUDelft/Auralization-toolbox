import os
import sys
import numpy as np
from scipy.io import loadmat

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, REPO_ROOT)

from auralization.private.propagation.atmosphere import StratifiedAtmospherePy, air_attenuation_iso_9613_1
from auralization.private.propagation.ground_reflection import ground_reflection_coefficient

def main():
    # Where MATLAB will write its reference file
    ref_mat_path = os.path.join("verification", "matlab_reference", "propagation_reference.mat")
    if not os.path.isfile(ref_mat_path):
        raise FileNotFoundError(
            f"MATLAB reference file not found: {ref_mat_path}\n"
            "Run the MATLAB script verification/matlab_reference/make_propagation_reference.m first."
        )

    ref = loadmat(ref_mat_path)

    # MATLAB exports
    f = ref["freq_hz"].reshape(-1)
    altitude = float(ref["altitude_m"].squeeze())
    T_K = float(ref["T_K"].squeeze())
    hr = float(ref["rel_humidity_pct"].squeeze())
    p0 = float(ref["static_pressure_pa"].squeeze())
    alpha_db_per_m_mat = ref["alpha_db_per_m"].reshape(-1)

    sigma_e = float(ref["sigma_e"].squeeze())
    theta_rad = float(ref["theta_rad"].squeeze())
    r2_m = float(ref["r2_m"].squeeze())
    c_ms = float(ref["sound_speed"].squeeze())
    Q_mat = ref["Q_complex"].reshape(-1).astype(np.complex128)

    # --------------------------
    # Python: atmosphere settings
    # --------------------------
    atmos = StratifiedAtmospherePy()
    atmos.temperatureProfile = "constant"
    atmos.constTemperature = T_K
    atmos.humidityProfile = "constant"
    atmos.constRelHumidity = hr
    atmos.constStaticPressure = p0

    # 1) Compare ISO attenuation coefficient [dB/m]
    alpha_py = air_attenuation_iso_9613_1(atmos, altitude, f)

    rel_err_alpha = _rel_err(alpha_py, alpha_db_per_m_mat)
    print(f"[ISO attenuation] max rel err: {np.max(rel_err_alpha):.3e}, mean rel err: {np.mean(rel_err_alpha):.3e}")

    # 2) Compare ground reflection coefficient Q(f)
    Q_py = ground_reflection_coefficient(f, sigma_e, theta_rad, r2_m, c_ms)

    abs_err_Q = np.abs(Q_py - Q_mat)
    print(f"[Ground reflection] max abs err: {np.max(abs_err_Q):.3e}, mean abs err: {np.mean(abs_err_Q):.3e}")

    # Decide pass/fail thresholds
    # ISO attenuation: should be extremely close (floating-point differences only)
    if np.max(rel_err_alpha) > 1e-10:
        raise AssertionError("ISO attenuation mismatch exceeds tolerance.")

    # Ground reflection: depends on SciPy wofz numerical details; should still be tight
    if np.max(abs_err_Q) > 1e-9:
        raise AssertionError("Ground reflection mismatch exceeds tolerance.")

    print("All propagation math tests PASSED.")


def _rel_err(a, b, eps=1e-12):
    a = np.asarray(a)
    b = np.asarray(b)
    return np.abs(a - b) / np.maximum(np.abs(b), eps)


if __name__ == "__main__":
    main()
