from scipy.io import loadmat
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path

# === Load MATLAB-trimmed output ===
mat_path = Path(__file__).resolve().parent / "MATLAB_trimmed_output.mat"
mat = loadmat(mat_path, simplify_cells=True)

mat_data = mat['source_data_trimmed']
mat_spec = mat['source_SPECTROGRAM_trimmed']
mat_spec_dba = mat['source_SPECTROGRAM_dBA_trimmed']
mat_fp = mat['flight_profile_trimmed']

# === Load Python-trimmed output from memory ===
# === Load Python-trimmed output from file ===
npz = np.load("verification/Prepare_input_SQ/python_trimmed_output.npz", allow_pickle=True)
source_data_py = npz["source_data_trimmed"].tolist()
source_spec_py = npz["source_SPECTROGRAM_trimmed"].tolist()
source_spec_dba_py = npz["source_SPECTROGRAM_dBA_trimmed"].tolist()
flight_profile_py = npz["flight_profile_trimmed"].tolist()

# === Compare SPL (dB) over time ===
spl_py = np.array([
    10 * np.log10(np.sum(10 ** (d['overall'][:, 1] / 10))) for d in source_data_py
])
spl_mat = np.array([
    10 * np.log10(np.sum(10 ** (d['overall'][:, 1] / 10))) for d in mat_data
])


plt.figure()
plt.plot(spl_py, label='Python SPL')
plt.plot(spl_mat, '--', label='MATLAB SPL')
plt.title("Trimmed Overall SPL")
plt.xlabel("Time Index")
plt.ylabel("SPL (dB)")
plt.legend()
plt.grid(True)
plt.tight_layout()
plt.show()

# === Compare altitude profile ===
z_py = np.array(flight_profile_py['z'])
z_mat = np.array(mat_fp['z'])

plt.figure()
plt.plot(z_py, label='Python Altitude')
plt.plot(z_mat, '--', label='MATLAB Altitude')
plt.title("Trimmed Altitude Profile")
plt.xlabel("Time Index")
plt.ylabel("Altitude (m)")
plt.legend()
plt.grid(True)
plt.tight_layout()
plt.show()

z_py = np.array(flight_profile_py['z']).flatten()
z_mat = np.array(mat_fp['z'])

# === Report mean absolute errors ===
spl_error = np.mean(np.abs(spl_py - spl_mat))
alt_error = np.mean(np.abs(z_py - z_mat))

print(f"Mean Absolute Error (SPL): {spl_error:.4f} dB")
print(f"Mean Absolute Error (Altitude): {alt_error:.4f} m")

def compare_2d_array(label, mat_arr, py_arr):
    mat_arr = np.array(mat_arr)
    py_arr = np.array(py_arr)
    if mat_arr.shape != py_arr.shape:
        print(f"[WARN] Shape mismatch in {label}: {mat_arr.shape} vs {py_arr.shape}")
        return
    mae = np.mean(np.abs(mat_arr - py_arr))
    print(f"Mean Absolute Error ({label}): {mae:.4f} dB")

# ==== Fields from source_SPECTROGRAM_trimmed ====
linear_fields = [
    "overall", "overall_broadband", "airframe_toc", "engine", "engine_without_fan_harmonics",
    "engine_broadband_toc", "engine_buzzsaw_toc", "fan_harmonics_toc"
]

# ==== Fields from source_SPECTROGRAM_dBA_trimmed ====
dba_fields = [
    "overall", "overall_broadband", "airframe", "engine", "engine_without_fan_harmonics",
    "engine_broadband", "engine_buzzsaw", "fan_harmonics"
]

# ==== Compare linear spectrograms ====
print("\n=== Verifying source_SPECTROGRAM_trimmed ===")
for field in linear_fields:
    compare_2d_array(f"Spectrogram - {field}", mat_spec[field], source_spec_py[field])

# ==== Compare A-weighted spectrograms ====
print("\n=== Verifying source_SPECTROGRAM_dBA_trimmed ===")
for field in dba_fields:
    compare_2d_array(f"Spectrogram_dBA - {field}", mat_spec_dba[field], source_spec_dba_py[field])
