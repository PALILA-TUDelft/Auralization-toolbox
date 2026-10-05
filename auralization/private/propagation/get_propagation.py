from __future__ import annotations
import numpy as np
from utilities.verification_paths import verif_path
import globals

from auralization.private.propagation.art_bindings import find_eigenrays, create_atmosphere_json, wind_profile_from_ini
from auralization.private.propagation.atmosphere import AtmosphereConfig, StratifiedAtmospherePy
from auralization.private.propagation.ground_reflection import get_ground_reflection_coefficient
from auralization.private.propagation.tf_model import compute_tf_stack
from auralization.private.propagation.angles import fabian_angles_from_eigenrays, moving_average
from utilities.plot_utils import show_figure


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


def get_propagation(input_file, flight_profile, receiver, nfft, time, emission_angle_panam, show, tag_auralization):
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

    # ---- atmosphere ----
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

    atmosphere_json = create_atmosphere_json(
        temp_profile=temp_profile,
        temperature_celsius=temp_c,
        humidity_percent=hum,
        static_pressure_pa=p0,
        wind=wind_profile_from_ini(input_file),   # 'zero' | 'constant' | 'log', same defaults as MATLAB
    )

    # ---- frequency vector ----
    freq = _freq_vector(int(nfft), float(globals.fs))

    # ---- ground parameters ----
    if "sigma_e" in input_file:
        sigma_e = float(input_file["sigma_e"])
    else:
        sigma_e = 100000e3  # MATLAB default hard surface

    # Coarse sound speed, used ONLY for the ground-reflection coefficient
    # (matches MATLAB's `soundSpeed` variable in get_propagation.m, so the
    # ground-reflection TF stays bit-for-bit comparable).
    sound_speed = 331.3 + 0.606 * temp_c

    # ---- ART settings (match MATLAB defaults) ----
    settings = {
        "maxReceiverRadius": 0.1,
        "maxReflectionOrder": 1,
        "maxPropagationTime": 15.0,   # MATLAB AtmosphericRayTracer default (the C++ default is 30 s)
    }

    # ---- pre-allocate ----
    TF_list: list[np.ndarray] = []
    propagation_time = np.zeros((N, 2), dtype=float)
    thetaReflectedRay = np.zeros(N, dtype=float)
    propDistanceReflectedRay = np.zeros(N, dtype=float)
    launchAngle_direct = np.zeros(N, dtype=float)
    launchAngle_reflected = np.zeros(N, dtype=float)

    eigenrays_direct_all = []
    eigenrays_reflected_all = []
    reflection_points_all = []

    # ---- eigenray loop ----
    for i in range(N):
        eigenrays = find_eigenrays(
            atmosphere_json=atmosphere_json,
            source_xyz=source[i, :],
            receiver_xyz=receiver[0, :],
            settings=settings
        )

        ray_direct = eigenrays[0]
        ray_reflected = eigenrays[1]

        # ray.t[-1] is ART's integrated travel time in physical seconds, exactly what
        # MATLAB reads via eigenrays.t(end); no rescaling (correct for ISA as well).
        eigenrays_direct_all.append(ray_direct)
        eigenrays_reflected_all.append(ray_reflected)

        # propagation time
        propagation_time[i, 0] = float(ray_direct.t[-1])
        propagation_time[i, 1] = float(ray_reflected.t[-1])

        # reflection point (closest to z=0)
        z_abs = np.abs(ray_reflected.r[:, 2])
        idx_ref = int(np.argmin(z_abs))
        reflection_xyz = ray_reflected.r[idx_ref, :]
        reflection_points_all.append(np.asarray(reflection_xyz, dtype=float).reshape(3))

        # incidence angle of reflected ray (MATLAB: asin(source_z / hypotenuse))
        hyp = float(np.linalg.norm(reflection_xyz - source[i, :]))
        if hyp > 0:
            thetaReflectedRay[i] = np.arcsin(abs(source[i, 2]) / hyp)

        # propagation distance of reflected ray
        propDistanceReflectedRay[i] = ray_reflected.pathLength()

        # ground reflection coefficient
        R_ground = get_ground_reflection_coefficient(
            freq_hz=freq,
            sigma_e=sigma_e,
            theta_rad=abs(thetaReflectedRay[i]),
            r2_m=propDistanceReflectedRay[i],
            sound_speed=sound_speed,
        )

        # transfer function
        tf_stack = compute_tf_stack(
            atmos=atmos_py,
            rays=eigenrays,
            freq_hz=freq,
            reflection_factor=R_ground
        )
        TF_list.append(tf_stack)

        # launch angles (MATLAB convention: 360 - alpha_deg)
        launchAngle_direct[i] = 360.0 - ray_direct.alpha_deg
        launchAngle_reflected[i] = 360.0 - ray_reflected.alpha_deg

    # ---- debug: print overhead comparison ----
    overhead_idx = int(np.argmax(np.degrees(thetaReflectedRay)))
    rd = eigenrays_direct_all[overhead_idx]
    rr = eigenrays_reflected_all[overhead_idx]
    print(f"\n=== Overhead position (i={overhead_idx}) ===")
    print(f"Direct:    alpha={rd.alpha_deg:.4f} deg, t={rd.t[-1]:.6f} s, "
          f"spreadingLoss={rd.spreadingLoss:.8f}, pathLength={rd.pathLength():.2f} m, "
          f"numReflections={rd.numReflections}")
    print(f"Reflected: alpha={rr.alpha_deg:.4f} deg, t={rr.t[-1]:.6f} s, "
          f"spreadingLoss={rr.spreadingLoss:.8f}, pathLength={rr.pathLength():.2f} m, "
          f"numReflections={rr.numReflections}")
    print(f"  sigma_e={sigma_e:.1f}, theta_reflected={np.degrees(thetaReflectedRay[overhead_idx]):.4f} deg, "
          f"r2={propDistanceReflectedRay[overhead_idx]:.2f} m")
    R_debug = get_ground_reflection_coefficient(np.array([100, 500, 1000, 5000]),
                                                 sigma_e, abs(thetaReflectedRay[overhead_idx]),
                                                 propDistanceReflectedRay[overhead_idx], sound_speed)
    print(f"  |Q| at [100,500,1k,5k] Hz: {np.abs(R_debug)}")

    # ---- spherical angles (FABIAN convention) ----
    angles = fabian_angles_from_eigenrays(
        eigenrays_direct=eigenrays_direct_all,
        eigenrays_reflected=eigenrays_reflected_all,
        receiver_xyz=receiver[0, :],
        reflected_reflection_point_xyz=reflection_points_all
    )

    launchAngle_direct_spherical = angles["direct_path"]
    launchAngle_reflected_spherical = angles["reflected_path"]
    launchAngle_reflected_spherical_smooth = moving_average(launchAngle_reflected_spherical, window=10)

    # ---- output ----
    out = {
        "freq": freq,
        "TF": TF_list,
        "propagation_time": propagation_time,
        "spherical_angles_HRTF": {
            "direct_path": launchAngle_direct_spherical,
            "reflected_path": launchAngle_reflected_spherical_smooth,
        }
    }

    # ---- plots (MATLAB equivalent) ----
    # `show` is either a bool (all plots on/off) or a dict with keys
    # "propagation_rays" (figs 1-4) and "propagation_tf" (fig 5)
    if isinstance(show, dict):
        show_rays = bool(show.get("propagation_rays", False))
        show_tf = bool(show.get("propagation_tf", False))
    else:
        show_rays = show_tf = bool(show)

    if show_rays or show_tf:
        import matplotlib.pyplot as plt
        from utilities.plot_utils import export_figures

        xx = np.asarray(time, dtype=float).reshape(-1)
        overhead_idx = int(np.argmax(np.degrees(thetaReflectedRay)))

    if show_rays:
        from utilities.plot_style import MATLAB_COLORS, color_yyaxis
        c1, c2 = MATLAB_COLORS[0], MATLAB_COLORS[1]

        # --- Fig 1: reflected ray incidence angle & propagation distance (MATLAB: yyaxis left / right) ---
        fig, ax1 = plt.subplots()
        fig.canvas.manager.set_window_title("PROCESSING - 1st order reflection from ART (theta and propagation distance)")
        ax1.plot(xx, np.degrees(thetaReflectedRay), color=c1)
        ax1.set_ylabel(r"Incidence angle, $\theta_{\mathrm{in}}$ (deg)")
        ax1.set_xlabel("Time, $t$ (s)")

        ax2 = ax1.twinx()
        ax2.plot(xx, propDistanceReflectedRay, color=c2)
        ax2.set_ylabel(r"Propagated distance, $r_2$ (m)")
        color_yyaxis(ax1, ax2, c1, c2)
        fig.tight_layout()
        if tag_auralization:
            export_figures(tag_auralization + "_propagation_reflected_ray_parameters", save_png=True, save_pdf=True)

        # --- Fig 2: launch angles PANAM vs ART (all lines of a yyaxis side share the colour of that side) ---
        if emission_angle_panam is not None:
            fig, ax1 = plt.subplots()
            fig.canvas.manager.set_window_title("PROCESSING - launch direction from ART")
            phix = np.asarray(_get_field(emission_angle_panam, "phix"), dtype=float).reshape(-1)
            a, = ax1.plot(xx, phix, "-", color=c1, label="PANAM")
            b, = ax1.plot(xx, launchAngle_direct, "--x", color=c1, markevery=10, label="ART - direct path")
            ax1.set_ylabel(r"Emission angle, $\alpha^{*}$ (deg)")

            ax2 = ax1.twinx()
            ax2.plot(xx, launchAngle_direct - phix, color=c2)
            ax2.set_ylabel(r"$\alpha^{*}_\mathrm{ART}- \alpha^{*}_\mathrm{PANAM}$ (deg)")
            ax1.set_xlabel("Time, $t$ (s)")
            color_yyaxis(ax1, ax2, c1, c2)
            ax1.legend([a, b], ["PANAM", "ART - direct path"], loc="lower right", frameon=False)   # MATLAB: legend box off
            fig.tight_layout()
            if tag_auralization:
                export_figures(tag_auralization + "_ART_emission_angle", save_png=True, save_pdf=True)

        # --- Fig 3: direct ray spherical angles (FABIAN) ---
        fig, (ax1, ax2) = plt.subplots(2, 1, sharex=True)
        fig.canvas.manager.set_window_title("PROCESSING - launch direction from ART in spherical coord (direct)")

        ax1.plot(xx, launchAngle_direct_spherical[:, 0], "-")
        ax1.axvline(xx[overhead_idx], color="k", linestyle="--", label="Overhead")
        ax1.set_ylim(0, 360)
        ax1.set_yticks([0, 90, 180, 270, 360])
        ax1.set_ylabel("Azimuth (deg)")
        ax1.set_title("Spherical coordinates")
        ax1.legend(loc="upper right")
        ax1.grid(True, linestyle="--", alpha=0.15)

        ax2.plot(xx, launchAngle_direct_spherical[:, 1], "-")
        ax2.axvline(xx[overhead_idx], color="k", linestyle="--")
        ax2.set_ylim(0, 90)
        ax2.set_yticks([0, 30, 60, 90])
        ax2.set_ylabel("Elevation (deg)")
        ax2.set_xlabel("Time (s)")
        ax2.grid(True, linestyle="--", alpha=0.15)
        fig.tight_layout()
        if tag_auralization:
            export_figures(tag_auralization + "_ART_emission_angle_spherical_direct_path", save_png=True, save_pdf=True)

        # --- Fig 4: reflected ray spherical angles (FABIAN) ---
        fig, (ax1, ax2) = plt.subplots(2, 1, sharex=True)
        fig.canvas.manager.set_window_title("PROCESSING - launch direction from ART in spherical coord (reflection)")

        ax1.plot(xx, launchAngle_reflected_spherical[:, 0], "-")
        ax1.axvline(xx[overhead_idx], color="k", linestyle="--", label="Overhead")
        ax1.set_ylim(0, 360)
        ax1.set_yticks([0, 90, 180, 270, 360])
        ax1.set_ylabel("Azimuth (deg)")
        ax1.set_title("Spherical coordinates")
        ax1.legend(loc="upper right")
        ax1.grid(True, linestyle="--", alpha=0.15)

        ax2.plot(xx, launchAngle_reflected_spherical[:, 1], label="ART")
        ax2.plot(xx, launchAngle_reflected_spherical_smooth[:, 1], "r-", label="Smoothed")
        ax2.axvline(xx[overhead_idx], color="k", linestyle="--")
        ax2.set_ylim(-90, 0)
        ax2.set_yticks([-90, -60, -30, 0])
        ax2.set_ylabel("Elevation (deg)")
        ax2.set_xlabel("Time (s)")
        ax2.legend(loc="lower right")
        ax2.grid(True, linestyle="--", alpha=0.15)
        fig.tight_layout()
        if tag_auralization:
            export_figures(tag_auralization + "_ART_emission_angle_spherical_reflected_path", save_png=True, save_pdf=True)

    if show_tf:
        # --- Fig 5: transfer function at overhead position ---
        tf_overhead = TF_list[overhead_idx]
        att_direct = 10.0 * np.log10(np.abs(tf_overhead["individual_tf"][:, 0]) ** 2)
        att_reflected = 10.0 * np.log10(np.abs(tf_overhead["individual_tf"][:, 1]) ** 2)
        att_combined = 10.0 * np.log10(np.abs(tf_overhead["combined_tf"]) ** 2)

        fig, ax = plt.subplots()
        fig.canvas.manager.set_window_title("OUTPUT - atmospheric transfer function")
        a, = ax.semilogx(freq, att_combined, color=(0.93, 0.69, 0.13), linewidth=0.5)
        b, = ax.semilogx(freq, att_direct, color=(0.00, 0.45, 0.74), linewidth=1)
        c, = ax.semilogx(freq, att_reflected, color=(0.85, 0.33, 0.10), linewidth=1)
        ax.set_xlabel("Frequency, $f$ (Hz)")
        ax.set_ylabel(r"$10\cdot\log_{10}\left(|H_{\mathrm{atm,ART}}|^2 \right)$")
        ax.set_xlim(20, 25e3)
        ax.set_ylim(-200, 0)
        ax.set_yticks(np.arange(-200, 1, 20))
        ax.set_xticks([20, 100, 1000, 10000, 20000])
        ax.set_xticklabels(["20", "100", "1k", "10k", "20k"])
        ax.minorticks_off()
        from matplotlib.ticker import MultipleLocator
        ax.yaxis.set_minor_locator(MultipleLocator(10))
        ax.yaxis.set_tick_params(which="minor", left=True, right=False)
        ax.legend([b, c, a], ["Direct path", "Reflected path", "Direct path + reflected path"], loc="lower left")
        fig.tight_layout()
        if tag_auralization:
            export_figures(tag_auralization + "_atmospheric_transfer_function_overhead", save_png=True, save_pdf=True)

    if show_rays or show_tf:
        show_figure()

    # ---- save vectors for verification ----
    if globals.verification:
        import os
        verif_dir = verif_path("propagation")
        overhead_idx_save = int(np.argmax(np.degrees(thetaReflectedRay)))
        tf_oh = TF_list[overhead_idx_save]
        np.savez(
            os.path.join(verif_dir, "propagation_python.npz"),
            time=np.asarray(time, dtype=float).reshape(-1),
            freq=freq,
            thetaReflectedRay=thetaReflectedRay,
            propDistanceReflectedRay=propDistanceReflectedRay,
            propagation_time=propagation_time,
            launchAngle_direct=launchAngle_direct,
            launchAngle_reflected=launchAngle_reflected,
            spherical_direct=launchAngle_direct_spherical,
            spherical_reflected=launchAngle_reflected_spherical,
            spherical_reflected_smooth=launchAngle_reflected_spherical_smooth,
            overhead_idx=overhead_idx_save,
            tf_overhead_individual=tf_oh["individual_tf"],
            tf_overhead_combined=tf_oh["combined_tf"],
        )
        print(f"[VERIFICATION] Saved propagation vectors to {verif_dir}/propagation_python.npz")

    return out
