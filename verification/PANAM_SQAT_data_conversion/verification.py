import sys
from pathlib import Path
import numpy as np
import matplotlib.pyplot as plt
from scipy.io import loadmat

# Setup path
this_file = Path(__file__).resolve()
project_root = this_file.parents[1].parents[0]
utilities_path = project_root / 'utilities'
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(utilities_path))

from utilities.io import PANAM_SQAT_data_conversion

# Load MATLAB output
matlab_output = loadmat('verification/PANAM_SQAT_data_conversion/MATLAB_output.mat', simplify_cells=True)
mat_oaspl = matlab_output['source_OASPL']
mat_oaspl_dBA = matlab_output['source_OASPL_dBA']
mat_spec = matlab_output['source_SPECTROGRAM']
mat_spec_dBA = matlab_output['source_SPECTROGRAM_dBA']

print(f"MATLAB engine OASPL: {mat_oaspl['engine']}")

# Load Python output
_, py_oaspl, py_oaspl_dBA, py_spec, py_spec_dBA = PANAM_SQAT_data_conversion('verification/PANAM_SQAT_data_conversion/auralization_input.dat')

print(f"Python engine OASPL: {py_oaspl[0]['engine']}")

# print(f"Python OASPL_dBA: {py_oaspl_dBA.shape}")
# print(f"Python SPECTROGRAM: {py_spec.shape}")
# print(f"Python SPECTROGRAM_dBA: {py_spec_dBA.shape}")


import matplotlib.pyplot as plt
import numpy as np

def compare_and_plot(mat_data, py_data, key, title_prefix):
    for j in range(len(py_data)):  # loop over observers
        if j >= len(py_data) or key not in py_data[j]:
            print(f"[SKIP] Python: Missing key '{key}' for observer {j+1}")
            continue
        if key not in mat_data:
            print(f"[SKIP] MATLAB: Missing key '{key}'")
            continue
        
        py_vals = np.array(py_data[j][key])
        mat_vals = np.array(mat_data[key])
        if py_vals.shape != mat_vals.shape:
            print(f"[DEBUG] {title_prefix} - {key} - py_vals shape: {py_vals.shape}, mat_vals shape: {mat_vals.shape}")

            print(f"[WARN] Shape mismatch for '{key}' - Python: {py_vals.shape}, MATLAB: {mat_vals.shape}")
            continue

        mean_error = np.mean(np.abs(py_vals - mat_vals))

        fig, axs = plt.subplots(1, 2, figsize=(12, 4), sharey=True)
        fig.suptitle(f'{title_prefix} - {key} (Observer {j+1})')

        axs[0].plot(py_vals, label='Python', color='tab:blue')
        axs[0].set_title('Python Output')
        axs[0].set_xlabel('Time Step')
        axs[0].set_ylabel('SPL [dB]')
        axs[0].grid(True)

        axs[1].plot(mat_vals, label='MATLAB', color='tab:orange', linestyle='--')
        axs[1].set_title('MATLAB Output')
        axs[1].set_xlabel('Time Step')
        axs[1].grid(True)

        plt.tight_layout(rect=[0, 0.03, 1, 0.95])
        plt.show()

        print(f"{title_prefix} - {key} (Observer {j+1}): Mean Absolute Error = {mean_error:.4f} dB")

def compare_spectrograms(mat_data, py_data, key, title_prefix):
    for j in range(len(py_data)):  # loop over observers
        if j >= len(py_data) or key not in py_data[j]:
            print(f"[SKIP] Python: Missing key '{key}' for observer {j+1}")
            continue
        if key not in mat_data:
            print(f"[SKIP] MATLAB: Missing key '{key}'")
            continue

        py_vals = np.array(py_data[j][key])
        mat_vals = np.array(mat_data[key])

        # if py_vals.shape != mat_vals.shape:
        #     print(f"[WARN1] Shape mismatch for '{key}' - Python: {py_vals.shape}, MATLAB: {mat_vals.shape}")
        #     continue

        # if py_vals.shape == mat_vals.shape:
        #     print(f"No shape mismatch for '{key}' - Python: {py_vals.shape}, MATLAB: {mat_vals.shape}")

        abs_error = np.abs(py_vals - mat_vals)
        mean_error = np.mean(abs_error)

        fig, axs = plt.subplots(1, 3, figsize=(18, 5), sharey=True)
        fig.suptitle(f'{title_prefix} - {key} (Observer {j+1})', fontsize=14)

        im0 = axs[0].imshow(py_vals, aspect='auto', origin='lower', cmap='viridis')
        axs[0].set_title('Python')
        axs[0].set_xlabel('Time Step')
        axs[0].set_ylabel('Frequency Bin')
        fig.colorbar(im0, ax=axs[0], fraction=0.046, pad=0.04)

        im1 = axs[1].imshow(mat_vals, aspect='auto', origin='lower', cmap='viridis')
        axs[1].set_title('MATLAB')
        axs[1].set_xlabel('Time Step')
        fig.colorbar(im1, ax=axs[1], fraction=0.046, pad=0.04)

        im2 = axs[2].imshow(abs_error, aspect='auto', origin='lower', cmap='inferno')
        axs[2].set_title('Absolute Error [dB]')
        axs[2].set_xlabel('Time Step')
        fig.colorbar(im2, ax=axs[2], fraction=0.046, pad=0.04)

        plt.tight_layout(rect=[0, 0.03, 1, 0.95])
        plt.show()

        print(f"{title_prefix} - {key} (Observer {j+1}): Mean Absolute Error = {mean_error:.4f} dB")


# Compare OASPL
for key in ['overall','engine', 'airframe']: # overall, airframe
    compare_and_plot(mat_oaspl, py_oaspl, key, 'OASPL')
    compare_and_plot(mat_oaspl_dBA, py_oaspl_dBA, key, 'OASPL_dBA')

# Compare spectrograms
spectro_keys = ['overall', 'engine', 'airframe_toc'] #overall, airframe_toc
spectro_dba_keys = ['overall', 'engine', 'airframe'] # overall , airframe
for key in spectro_keys:
    compare_spectrograms(mat_spec, py_spec, key, 'SPECTROGRAM')
for key in spectro_dba_keys:
    compare_spectrograms(mat_spec_dBA, py_spec_dBA, key, 'SPECTROGRAM_dBA')