#utilites/trim_data_time_distance_based.py

import numpy as np
import matplotlib.pyplot as plt
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
    trim_bins = int(trim_time / dt)

    idx_min_dist = int(np.argmin(dist))
    idx_max_SPL = int(np.argmax(SPL_vs_time))

    idx_lower = max(0, round(idx_min_dist - trim_bins))
    idx_upper = min(len(time) - 1, round(idx_min_dist + trim_bins))

    duration_trimmed = (idx_upper - idx_lower) * dt
    conv = 1000  # m -> km

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
        # === Plot SPL vs Time ===
        plt.figure()
        plt.plot(time, SPL_vs_time, label="SPL vs. Time")
        plt.axvline(time[idx_min_dist], color='r', linestyle='--', label="Closest approach")
        plt.axvspan(time[idx_lower], time[idx_upper], color='gray', alpha=0.3, label="Trim window")
        plt.xlabel("Source time, $t_s$ (s)")
        plt.ylabel("SPL (dB re 20 μPa)")
        plt.title("Trimming Window on SPL")
        plt.grid(True)
        plt.legend()
        export_figures(f"{tag}_TrimData_SPL", save_mat_fig=False, save_png=True, save_pdf=True)
        plt.close()

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

    # Begin plot
    plt.figure()
    plt.plot(x_km, z_km, 'k', label="Flight path")

    # Patch for trimmed area
    x_patch = [xmin, xmin, xmax, xmax]
    y_patch = [0, ymin, ymax, 0]
    plt.fill(x_patch, y_patch, color='gray', alpha=0.3, label="Trim window")

    # Closest approach (aircraft position)
    plt.plot(x_overhead, z_overhead, 'o', markersize=8,
            markerfacecolor='#4fa9dc', markeredgecolor='black', label='Aircraft')

    # Receiver
    plt.plot(xobs, zobs, 'o', markersize=8,
            markerfacecolor='#63d10f', markeredgecolor='black', label='Receiver')

    # Dashed line and label for overhead altitude
    plt.axhline(y=z_overhead, linestyle='--', color='gray')
    plt.text(x_overhead + 0.1, z_overhead + 0.02,
            f"Overhead: {z_overhead:.3f} km",
            fontsize=12, va='bottom', ha='left')

    # Labels and legend
    plt.xlabel("$x$ (km)")
    plt.ylabel("Altitude AGL, $h_{\\mathrm{AGL}}$ (km)")
    plt.title("Flight Profile & Trimming Window")
    plt.legend(loc='upper right')
    plt.grid(True)
    plt.tight_layout()

    export_figures(f"{tag}_TrimData_flight_profile", save_mat_fig=False, save_png=True, save_pdf=True)
    plt.close()
    return idx_lower, idx_upper