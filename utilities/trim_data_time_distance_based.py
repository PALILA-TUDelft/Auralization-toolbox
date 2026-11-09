#utilites/trim_data_time_distance_based.py

import os
import numpy as np
from utilities.verification_paths import verif_path
import matplotlib.pyplot as plt
import globals
from utilities.plot_utils import export_figures

def trim_data_time_distance_based(source_data, trim_time, flight_profile, tag=None):
    """
    Determine the index bounds around closest source-receiver distance for trimming.

    Args:
        source_data (list of dict): Time-series data for one receiver.
        trim_time (float): Time (s) before and after the closest approach to trim.
        flight_profile (dict): Flight profile (x, z, etc.).
        tag (str): Optional tag for saving figures.

    Returns:
        idx_lower, idx_upper (int): Index bounds for trimming.
    """
    SPL_vs_time = np.array([
        10 * np.log10(np.sum(10 ** (d["overall"][:, 1] / 10)))
        for d in source_data
    ])
    time = np.array([d['source_time'] for d in source_data])
    dist = np.array([d['dist'] for d in source_data])

    dt = time[1] - time[0]
    trim_bins = trim_time / dt  # MATLAB keeps this as a float (not necessarily a whole number of bins)

    idx_min_dist = int(np.argmin(dist))
    idx_max_SPL = int(np.argmax(SPL_vs_time))

    # MATLAB (1-based): idx_lower = round(idx_min_dist - TrimTimebins), idx_upper = round(idx_min_dist + TrimTimebins),
    # with round() rounding halves away from zero; converted back to 0-based below.
    def matlab_round(x):
        return int(np.sign(x) * np.floor(abs(x) + 0.5))

    idx_lower = matlab_round((idx_min_dist + 1) - trim_bins) - 1
    idx_upper = matlab_round((idx_min_dist + 1) + trim_bins) - 1

    # MATLAB: if the window leaves the data on EITHER side, the original signal is kept entirely
    # (both bounds are reset), instead of clamping each side separately.
    if idx_lower < 0 or idx_upper > len(time) - 1:
        idx_lower = 0
        idx_upper = len(time) - 1

    duration_trimmed = (idx_upper - idx_lower) * dt
    conv = 1000  # m -> km

    # === Verification: vectors behind the TrimData_SPL figure ===
    if globals.verification:
        verif_dir = verif_path("trim_data")
        np.savez(os.path.join(verif_dir, "trim_data_python.npz"),
                 time=time,
                 SPL_vs_time=SPL_vs_time,
                 dist=dist,
                 idx_lower=idx_lower,
                 idx_upper=idx_upper,
                 idx_min_dist=idx_min_dist)
        print(f"[VERIFICATION] Saved trim-data SPL vectors to {verif_dir}/trim_data_python.npz")

    # === Console Log ===
    print("\n*--------------------------------------------------------------------------*")
    print("Log of trim function (time and distance based)")
    print(f"- Min. distance between source and receiver: {dist[idx_min_dist]:.4g} m")
    print(f"- SPL at min. distance point: {SPL_vs_time[idx_min_dist]:.4g} dB")
    print(f"- Max SPL in data: {SPL_vs_time[idx_max_SPL]:.4g} dB")
    print(f"- Desired time before/after max SPL: {trim_time:.4g} s")
    print(f"- Final trimmed time span: {duration_trimmed:.4g} s")
    print("*--------------------------------------------------------------------------*\n")

    if tag:
        # === Plot SPL vs Time (MATLAB: trim_data_TimeDistanceBased.m) ===
        from matplotlib.patches import Patch
        from utilities.plot_style import MATLAB_COLORS
        fig, ax = plt.subplots(layout="constrained")
        fig.canvas.manager.set_window_title("PROCESSING - data trimming function (time-based)")
        ax.axvspan(time[idx_lower], time[idx_upper], facecolor=(0.95, 0.95, 0.95), edgecolor="k", linewidth=0.5)
        h1, = ax.plot(time, SPL_vs_time, color=MATLAB_COLORS[0])
        h2, = ax.plot(time[idx_min_dist], SPL_vs_time[idx_min_dist], "o", color=MATLAB_COLORS[1], markerfacecolor="none")
        h3 = Patch(facecolor=(0.95, 0.95, 0.95), edgecolor="none")          # MATLAB: dummy line for the rectangle
        ax.set_xlabel(r"Source time, $t_{\mathrm{s}}$ (s)")
        ax.set_ylabel(r"SPL (dB re 20 $\mu$Pa)")
        ax.set_ylim(np.min(SPL_vs_time), np.max(SPL_vs_time) + 5)
        fig.legend([h1, h2, h3],
                   ["PANAM input data", "Point of min. distance between source/receiver",
                    f"Total auralization time is {duration_trimmed:.4g} s"],
                   loc="outside upper center")
        export_figures(f"{tag}_TrimData_SPL", save_mat_fig=False, save_png=True, save_pdf=True)
        plt.close()

    if not tag:
        return idx_lower, idx_upper

    # Extract values (convert to floats to avoid shape bugs)
    conv = 1000  # meters to km
    x_km = np.array(flight_profile["x"]) / conv
    z_km = np.array(flight_profile["z"]) / conv
    xmin = float(flight_profile["x"][idx_lower]) / conv
    xmax = float(flight_profile["x"][idx_upper]) / conv
    ymin = float(flight_profile["z"][idx_lower]) / conv
    ymax = float(flight_profile["z"][idx_upper]) / conv
    xobs = float(source_data[0]["xobs"]) / conv
    zobs = float(source_data[0]["zobs"]) / conv
    x_overhead = float(flight_profile["x"][idx_min_dist]) / conv
    z_overhead = float(flight_profile["z"][idx_min_dist]) / conv

    # Begin plot (MATLAB: patch, flight path, aircraft and receiver markers, dashed overhead line, legend on top)
    from matplotlib.patches import Patch
    fig, ax = plt.subplots(layout="constrained")
    fig.canvas.manager.set_window_title("PROCESSING - data trimming function (time-based)")
    ax.fill([xmin, xmin, xmax, xmax], [0, ymin, ymax, 0], facecolor=(0.94, 0.94, 0.94), edgecolor="k", linewidth=0.5)
    a, = ax.plot(x_km, z_km, 'k')
    b, = ax.plot(x_overhead, z_overhead, 'o', markersize=8, markerfacecolor=(0.30, 0.75, 0.93), markeredgecolor='k')
    c, = ax.plot(xobs, zobs, 'o', markersize=8, markerfacecolor=(0.39, 0.83, 0.07), markeredgecolor='k')
    ax.axhline(y=z_overhead, linestyle='--', color=(0.15, 0.15, 0.15), linewidth=0.5)     # MATLAB: yline(..., '--', label)
    ax.text(1.0, z_overhead, f"Overhead: {z_overhead:.3g} km", transform=ax.get_yaxis_transform(),
            ha='right', va='bottom', fontsize=14, fontfamily='cmr10')
    S = Patch(facecolor=(0.94, 0.94, 0.94), edgecolor='k', linewidth=0.5)
    ax.set_xlabel("$x$ (km)")
    ax.set_ylabel("Altitude AGL, $h_{\\mathrm{AGL}}$ (km)")
    ax.spines[["top", "right"]].set_visible(False)                                         # MATLAB: box off
    ax.tick_params(top=False, right=False)
    fig.legend([a, b, c, S], ['Flight path', 'Aircraft', 'Receiver', f"Auralized signal: {duration_trimmed:.4g} s"],
               loc="outside upper center", ncol=2)

    export_figures(f"{tag}_TrimData_flight_profile", save_mat_fig=False, save_png=True, save_pdf=True)
    plt.close()
    return idx_lower, idx_upper