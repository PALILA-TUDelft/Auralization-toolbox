# utilities/flight_profile_utils.py

from pathlib import Path
import numpy as np
import matplotlib.pyplot as plt
from utilities.io import mhdrload

def get_flight_profile(path, show=True, procedure=2, save_figs=True, tag="default", output_dir="."):
    """
    Reads, optionally plots, and returns flight profile data from PANAM.

    Parameters:
    - path (str or Path): Path to the PANAM flight profile data file (usually 'geschw_hoehe_verlauf.dat')
    - show (bool): Whether to show the flight profile plot
    - procedure (int): 0 (approach), 1 (departure), 2 (flyover); sets the x-axis label
    - save_figs (bool): Whether to save the plot to file
    - tag (str): Case tag used in the filename when saving plots
    - figures_dir (str or Path): Directory where plots should be saved

    Returns:
    - dict: Contains x, y, z, TAS, and thrust arrays
    """

    # Load using mhdrload
    path = Path(path)
    _, data = mhdrload(path)

    conv_factor = 1000  # meters -> km for plotting
    x_km = data[:, 0] / conv_factor
    altitude_km = data[:, 2] / conv_factor
    TAS = data[:, 3]
    thrust = data[:, 4]

    result = {
        'x': data[:, 0],
        'y': data[:, 1],
        'z': data[:, 2],
        'TAS': TAS,
        'thrust': thrust
    }

    if show:
        fig, ax1 = plt.subplots()
        ax2 = ax1.twinx()
        
        ax1.plot(x_km, altitude_km, 'k-', label='Altitude')
        ax1.set_ylabel('Altitude AGL, $h_{\\mathrm{AGL}}$ (km)', fontsize=12)

        if procedure == 0:
            ax1.set_xlabel('Distance from runway threshold, $x_{\\mathrm{app}}$ (km)', fontsize=12)
        elif procedure == 1:
            ax1.set_xlabel('Distance from brake release, $x_{\\mathrm{dep}}$ (km)', fontsize=12)
        elif procedure == 2:
            ax1.set_xlabel('Distance, $x$ (km)', fontsize=12)

        ax2.plot(x_km, TAS, 'b-', label='True airspeed')
        ax2.plot(x_km, thrust, 'r-', label='Thrust')
        ax2.set_ylabel('True airspeed (m/s), Thrust (kN)', fontsize=12)

        # Combined legend
        lines, labels = [], []
        for ax in [ax1, ax2]:
            for line, label in zip(*ax.get_legend_handles_labels()):
                lines.append(line)
                labels.append(label)
        ax1.legend(lines, labels, loc='best')

        fig.tight_layout()
        fig.patch.set_facecolor('white')

        if save_figs:
            output_path = Path(output_dir)
            output_path.mkdir(parents=True, exist_ok=True)
            filename = output_path / f"flight_profile_{tag}.pdf"
            fig.savefig(filename, bbox_inches='tight')
            print(f"[INFO] Flight profile plot saved to {filename}")


        plt.show()

    return result