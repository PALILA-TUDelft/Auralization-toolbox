# utilities/flight_profile_utils.py

from pathlib import Path
import numpy as np
import matplotlib.pyplot as plt
from utilities.io import mhdrload
from utilities.plot_utils import export_figures, show_figure

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
    data = data[:, :, 0]

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
        fig, ax1 = plt.subplots(layout="constrained")
        fig.canvas.manager.set_window_title("INPUT - flight profile from PANAM")
        ax2 = ax1.twinx()

        # MATLAB (as saved): left axis and altitude in the 1st colour, right axis in the 2nd; TAS 'b-', thrust 'r-'
        from utilities.plot_style import MATLAB_COLORS, color_yyaxis
        a, = ax1.plot(x_km, altitude_km, '-', color=MATLAB_COLORS[0])
        ax1.set_ylabel('Altitude AGL, $h_{\\mathrm{AGL}}$ (km)')

        if procedure == 0:
            ax1.set_xlabel('Distance from runway threshold, $x_{\\mathrm{app}}$ (km)')
        elif procedure == 1:
            ax1.set_xlabel('Distance from brake release, $x_{\\mathrm{dep}}$ (km)')
        elif procedure == 2:
            ax1.set_xlabel('Distance, $x$ (km)')

        b, = ax2.plot(x_km, TAS, 'b-')
        c, = ax2.plot(x_km, thrust, 'r-')
        ax2.set_ylabel('True airspeed (m/s), Thrust (kN)')
        color_yyaxis(ax1, ax2, MATLAB_COLORS[0], MATLAB_COLORS[1])

        ax1.legend([a, b, c], ['Altitude', 'True airspeed', 'Thrust'], loc='best', frameon=False)   # MATLAB: legend boxoff
        fig.patch.set_facecolor('white')

        if save_figs:
            output_path = Path(output_dir)
            filename = output_path / f"flight_profile_{tag}"
            export_figures(filename, save_mat_fig=False, save_png=True, save_pdf=True)

        show_figure()

    return result