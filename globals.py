# globals.py

# Global constants and configuration parameters
fs = None               # Sampling frequency
dt_panam = None         # Time step from PANAM
panam_upsampling = 1    # Interpolated PANAM samples per original step (1 = none, 2 = one midpoint per step)
input_file = {}         # Dictionary parsed from .ini
pref = 20e-6            # Reference pressure (Pa)
save_mat_fig = True   # Whether to save .fig.pickle versions of plots
figure_formats = {"png", "pdf"}  # Which raster/vector formats export_figures() writes
verification = False  # When True, dump per-step verification vectors (.npz) and print [VERIFICATION] logs