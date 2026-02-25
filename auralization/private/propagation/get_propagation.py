from __future__ import annotations
import numpy as np
import globals
from globals import input_file

from auralization.private.propagation.art_bindings import find_eigenrays
from auralization.private.propagation.atmosphere import AtmosphereConfig, StratifiedAtmospherePy
from auralization.private.propagation.ground_reflection import get_ground_reflection_coefficient
from auralization.private.propagation.tf_model import compute_tf_stack
from auralization.private.propagation.angles import fabian_angles_from_eigenrays, moving_average


def _get_field(obj, name):
    """Support both dict-style and attribute-style access."""
    if isinstance(obj, dict):
        if name not in obj:
            raise KeyError(f"flight_profile is dict but missing key '{name}'. Available keys: {list(obj.keys())}")
        return obj[name]
    if hasattr(obj, name):
        return getattr(obj, name)
    raise AttributeError(f"flight_profile has no attribute/key '{name}'")


def _freq_vector(nfft: int, fs: float) -> np.ndarray:
    n_bins = int(np.ceil((nfft + 1) / 2))
    return np.linspace(0.0, fs / 2.0, n_bins)


def get_propagation(flight_profile, receiver, nfft, time, emission_angle_panam, show, tag_auralization):
    """
    Python equivalent of MATLAB get_propagation.m.
    Returns dict with:
      TF: list of (n_freq,3) complex arrays
      spherical_angles_HRTF: {direct_path: (N,2), reflected_path: (N,2)}
      propagation_time: (N,2)
      freq: (n_freq,)
    """
    receiver = np.asarray(receiver, dtype=float).reshape(1, 3)
    if receiver[0, 2] == 0.0:
        receiver[0, 2] = 0.01

    # trajectory (works for dict OR object)
    x = np.asarray(_get_field(flight_profile, "x"), dtype=float).reshape(-1)
    y = np.asarray(_get_field(flight_profile, "y"), dtype=float).reshape(-1)
    z = np.asarray(_get_field(flight_profile, "z"), dtype=float).reshape(-1)

    if not (len(x) == len(y) == len(z)):
        raise ValueError(f"flight_profile x/y/z length mismatch: len(x)={len(x)}, len(y)={len(y)}, len(z)={len(z)}")

    source = np.column_stack([x, y, z]).astype(float)
    N = source.shape[0]

    # atmosphere config from your ini / globals input_file
    temp_c = float(input_file.get("temperature_celsius", 15.0))
    temp_profile = str(input_file.get("temperature_profile", "constant"))
    hum = float(input_file.get("const_rel_humidity", 50.0))
    p0 = float(input_file.get("const_static_pressure", 101325.0))

    atmos_cfg = AtmosphereConfig(
        temperature_profile=temp_profile,
        temperature_celsius=temp_c,
        const_static_pressure=p0,
        rel_humidity_percent=hum
    )
    atmos_py = StratifiedAtmospherePy(atmos_cfg)

    # frequency vector (MATLAB-like)
    freq = _freq_vector(int(nfft), float(globals.fs))

    # ground parameters
    if "sigma_e" in input_file:
        sigma_e = float(input_file["sigma_e"])
    else:
        sigma_e = 100000e3  # MATLAB default hard surface

    sound_speed = 331.3 + 0.606 * temp_c

    # ART settings (match MATLAB defaults)
    settings = {
        "maxReceiverRadius": 0.1,
        "maxReflectionOrder": 1,
    }

    TF_list: list[np.ndarray] = []
    propagation_time = np.zeros((N, 2), dtype=float)

    # NEW: collect rays + reflection points for angle conversion after loop
    eigenrays_direct_all = []
    eigenrays_reflected_all = []
    reflection_points_all = []

    atmosphere_json = "{}"

    for i in range(N):
        rays = find_eigenrays(
            atmosphere_json=atmosphere_json,
            source_xyz=source[i, :],
            receiver_xyz=receiver[0, :],
            settings=settings
        )

        # Assumes rays[0]=direct, rays[1]=reflected (same as your current code)
        ray_direct = rays[0]
        ray_reflected = rays[1]

        # store for later FABIAN conversion
        eigenrays_direct_all.append(ray_direct)
        eigenrays_reflected_all.append(ray_reflected)

        # times
        propagation_time[i, 0] = float(ray_direct.t[-1])
        propagation_time[i, 1] = float(ray_reflected.t[-1])

        # reflection point detection (closest point to z=0)
        z_abs = np.abs(ray_reflected.r[:, 2])
        idx_ref = int(np.argmin(z_abs))
        reflection_xyz = ray_reflected.r[idx_ref, :]
        reflection_points_all.append(np.asarray(reflection_xyz, dtype=float).reshape(3))

        # theta for ground reflection coefficient (MATLAB style)
        hyp = float(np.linalg.norm(reflection_xyz - source[i, :]))
        if hyp <= 0:
            theta_in_rad = 0.0
        else:
            theta_in_rad = float(np.arcsin(abs(source[i, 2]) / hyp))

        path_length_reflected = float(np.sum(np.linalg.norm(np.diff(ray_reflected.r, axis=0), axis=1)))

        R_ground = get_ground_reflection_coefficient(
            freq_hz=freq,
            sigma_e=sigma_e,
            theta_rad=abs(theta_in_rad),
            path_length_m=path_length_reflected,
            sound_speed_mps=sound_speed,
        )

        tf_stack = compute_tf_stack(
            atmos=atmos_py,
            rays=rays,
            freq_hz=freq,
            reflection_factor=R_ground
        )
        TF_list.append(tf_stack)

    angles = fabian_angles_from_eigenrays(
        eigenrays_direct=eigenrays_direct_all,
        eigenrays_reflected=eigenrays_reflected_all,
        receiver_xyz=receiver[0, :],
        reflected_reflection_point_xyz=reflection_points_all
    )

    ang_direct = angles["direct_path"]
    ang_ref = angles["reflected_path"]

    # smooth reflected elevation like MATLAB smoothdata movmean 10
    ang_ref_smooth = moving_average(ang_ref, window=10)

    out = {
        "freq": freq,
        "TF": TF_list,
        "propagation_time": propagation_time,
        "spherical_angles_HRTF": {
            "direct_path": ang_direct,
            "reflected_path": ang_ref_smooth,
        }
    }
    return out