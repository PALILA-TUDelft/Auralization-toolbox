#utilities/io.py

from pathlib import Path
import numpy as np
from utilities.mhdrload import mhdrload

def decode_and_strip(cell):
    """Decode and strip header cell safely."""
    if isinstance(cell, np.ndarray):
        # If it's a char matrix (array of bytes), decode to string
        try:
            raw = ''.join(cell.astype(str).flatten())
        except Exception:
            raw = cell.tobytes().decode('utf-8', errors='ignore')
        cleaned = raw.replace('\x00', '').strip()
        return float(cleaned) if cleaned else 0.0
    elif isinstance(cell, (bytes, bytearray)):
        cleaned = cell.decode('utf-8', errors='ignore').replace('\x00', '').strip()
        return float(cleaned) if cleaned else 0.0
    elif isinstance(cell, str):
        return float(cell.strip()) if cell.strip() else 0.0
    else:
        raise TypeError(f"Unsupported header cell type: {type(cell)}")

def load_header_first(header_block):
    return {
        'retarded_time': decode_and_strip(header_block[3, 17:30]),
        'source_time': decode_and_strip(header_block[4, 15:30]),
        'sound_speed': decode_and_strip(header_block[5, 17:30]),
        'xpos': decode_and_strip(header_block[6, 8:30]),
        'ypos': decode_and_strip(header_block[7, 8:30]),
        'alt': decode_and_strip(header_block[8, 7:30]),
        'xobs': decode_and_strip(header_block[9, 9:30]),
        'yobs': decode_and_strip(header_block[10, 9:30]),
        'zobs': decode_and_strip(header_block[11, 9:30]),
        'phix': decode_and_strip(header_block[12, 9:30]),
        'phiy': decode_and_strip(header_block[13, 9:30]),
        'dist': decode_and_strip(header_block[14, 9:30]),
        'distxy': decode_and_strip(header_block[15, 9:30]),
        'vel': decode_and_strip(header_block[16, 9:30]),
        'n1': decode_and_strip(header_block[17, 9:30])
    }

def load_header(header_block):
    return {
        'retarded_time': decode_and_strip(header_block[1, 17:30]),
        'source_time': decode_and_strip(header_block[2, 15:30]),
        'sound_speed': decode_and_strip(header_block[3, 17:30]),
        'xpos': decode_and_strip(header_block[4, 8:30]),
        'ypos': decode_and_strip(header_block[5, 8:30]),
        'alt': decode_and_strip(header_block[6, 7:30]),
        'xobs': decode_and_strip(header_block[7, 9:30]),
        'yobs': decode_and_strip(header_block[8, 9:30]),
        'zobs': decode_and_strip(header_block[9, 9:30]),
        'phix': decode_and_strip(header_block[10, 9:30]),
        'phiy': decode_and_strip(header_block[11, 9:30]),
        'dist': decode_and_strip(header_block[12, 9:30]),
        'distxy': decode_and_strip(header_block[13, 9:30]),
        'vel': decode_and_strip(header_block[14, 9:30]),
        'n1': decode_and_strip(header_block[15, 9:30])
    }

def A_weighting():
    return np.array([
        [25, -44.7], [31.5, -39.4], [40, -34.6], [50, -30.2], [63, -26.2],
        [80, -22.5], [100, -19.1], [125, -16.1], [160, -13.4], [200, -10.9],
        [250, -8.6], [315, -6.6], [400, -4.8], [500, -3.2], [630, -1.9],
        [800, -0.8], [1000, 0], [1250, 0.6], [1600, 1], [2000, 1.2],
        [2500, 1.3], [3150, 1.2], [4000, 1], [5000, 0.5], [6300, -0.1],
        [8000, -1.1], [10000, -2.5], [12500, -4.3]
    ])

def correct_to_toc_band(raw, toc):
    f_target = 25
    b = np.abs(toc[2] - raw[:, 0])
    idx_min = np.argmin(b)
    cut = raw[idx_min:idx_min + 28].copy()
    cut[:, 0] = toc[2:30]
    return cut

def apply_a_weighting(spectrum, a_weights):
    weighted = np.zeros_like(spectrum)
    weighted[:, 0] = a_weights[:, 0]
    for k in range(len(a_weights)):
        level = spectrum[k, 1] + a_weights[k, 1]
        weighted[k, 1] = max(level, 0) # if < 0 -> 0 ; other level
    return weighted

def log_sum(*args):
    total = np.zeros_like(args[0])
    for vec in args:
        total += 10 ** (vec / 10)
    return 10 * np.log10(total)

def compute_OASPL(data):
    OASPL = []
    OASPL_dBA = []
    for j in range(len(data[0])):  # observer loop
        obs_data = {
            'airframe': [],
            'airframe_toc': [],
            'fan_harmonics': [],
            'fan_harmonics_toc': [],
            'engine_broadband': [],
            'engine_broadband_toc': [],
            'engine_buzzsaw': [],
            'engine_buzzsaw_toc': [],
            'engine_without_fan_harmonics': [],
            'engine': [],
            'overall_broadband': [],
            'overall': [],
            'source_time': [],
            'retarded_time': []
        }

        obs_data_dBA = {
            'airframe': [],
            'engine': [],
            'overall': [],
            'engine_without_fan_harmonics': [],
            'overall_broadband': [],
            'fan_harmonics': [],
            'source_time': [],
            'retarded_time': []
        }


        for i in range(len(data)):  # time loop
            d = data[i][j]
            for key in obs_data:
                if key in d:
                    val = d[key]

                    if isinstance(val, np.ndarray):
                        spl = val[:, 1]  # assuming [freq, SPL]
                        obs_data[key].append(10 * np.log10(np.sum(10 ** (spl / 10))))
                    else:
                        obs_data[key].append(val)
                        
            for key in obs_data_dBA:
                if key in ['source_time', 'retarded_time']:
                    obs_data_dBA[key].append(d[key])
                elif f"{key}_dBA" in d:
                    val = d[f"{key}_dBA"]
                    if isinstance(val, np.ndarray) and val.shape[1] >= 2:
                        spl = val[:, 1]
                        obs_data_dBA[key].append(10 * np.log10(np.sum(10 ** (spl / 10))))
                    else:
                        print(f"[WARN] Skipping dBA key '{key}' due to invalid shape or type.")
                else:
                    obs_data_dBA[key].append(0.0)



        OASPL.append(obs_data)
        OASPL_dBA.append(obs_data_dBA)
    return OASPL, OASPL_dBA


def compute_SPECTROGRAM(data):
    SPECTROGRAM = []
    SPECTROGRAM_dBA = []
    for j in range(len(data[0])):  # observer loop
        obs_spec = {
            'freq': data[0][j]['airframe_toc'][:, 0],
            'source_time': [],
            'retarded_time': [],
            'airframe_toc': [],
            'engine': [],
            'engine_without_fan_harmonics': [],
            'engine_broadband_toc': [],
            'engine_buzzsaw_toc': [],
            'fan_harmonics_toc': [],
            'overall_broadband': [],
            'overall': [],
        }
        obs_spec_dBA = {
            'freq': data[0][j]['airframe_dBA'][:, 0],
            'source_time': [],
            'retarded_time': [],
            'airframe': [],
            'engine': [],
            'engine_without_fan_harmonics': [],
            'engine_broadband': [],
            'engine_buzzsaw': [],
            'fan_harmonics': [],
            'overall_broadband': [],
            'overall': [],
        }

        for i in range(len(data)):  # time loop
            d = data[i][j]
            obs_spec['source_time'].append(d['source_time'])
            obs_spec['retarded_time'].append(d['retarded_time'])
            obs_spec_dBA['source_time'].append(d['source_time'])
            obs_spec_dBA['retarded_time'].append(d['retarded_time'])

            for key in obs_spec:
                if key not in ['freq', 'source_time', 'retarded_time'] and key in d:
                    obs_spec[key].append(d[key][:, 1])
            for key in obs_spec_dBA:
                if key not in ['freq', 'source_time', 'retarded_time'] and f"{key}_dBA" in d:
                    obs_spec_dBA[key].append(d[f"{key}_dBA"][:, 1])

        # Convert lists of arrays into 2D arrays: [nFreq x nTime]
        for key in obs_spec:
            if key not in ['freq', 'source_time', 'retarded_time'] and obs_spec[key]:
                obs_spec[key] = np.stack(obs_spec[key], axis=1)
            elif key not in ['freq', 'source_time', 'retarded_time']:
                obs_spec[key] = np.empty((len(obs_spec['freq']), 0))  # Empty array if missing

        for key in obs_spec_dBA:
            if key not in ['freq', 'source_time', 'retarded_time'] and obs_spec_dBA[key]:
                obs_spec_dBA[key] = np.stack(obs_spec_dBA[key], axis=1)
            elif key not in ['freq', 'source_time', 'retarded_time']:
                obs_spec_dBA[key] = np.empty((len(obs_spec_dBA['freq']), 0))

        SPECTROGRAM.append(obs_spec)
        SPECTROGRAM_dBA.append(obs_spec_dBA)

    return SPECTROGRAM, SPECTROGRAM_dBA


def PANAM_SQAT_data_conversion(PATH):
    PATH = Path(PATH)
    HEADER, DATA = mhdrload(PATH)

    toc = np.array([
        16, 20, 25, 31.5, 40, 50, 63, 80, 100, 125, 160, 200,
        250, 315, 400, 500, 630, 800, 1000, 1250, 1600, 2000,
        2500, 3150, 4000, 5000, 6300, 8000, 10000, 12500, 16000, 20000, 25000
    ])
    a_weights = A_weighting()
    data_flat = []

    # Step 1: Parse headers
    for i in range(0, HEADER.shape[2], 4):
        hdr = HEADER[:, :, i]
        info = load_header_first(hdr) if i == 0 else load_header(hdr)
        data_flat.append(info)

    # Step 2: Group data into observers
    source_times = [d["source_time"] for d in data_flat]
    first_time = source_times[0]
    observer_indices = [i for i, t in enumerate(source_times) if t == first_time]
    n_observer = len(observer_indices)
    n_time = len(data_flat) // n_observer

    data = [[data_flat[j * n_time + i] for j in range(n_observer)] for i in range(n_time)]

    # Step 3: Parse DATA for each timestep and observer
    for i_time in range(n_time):
        for j_obs in range(n_observer):
            idx = j_obs * n_time + i_time

            def clean(matrix):
                matrix = np.nan_to_num(matrix, nan=0.0, posinf=0.0, neginf=0.0)
                matrix[matrix < 0] = 0
                return matrix

            d = data[i_time][j_obs]
            d["airframe"] = clean(DATA[:, :, idx * 4 + 0])
            d["engine_broadband"] = clean(DATA[:, :, idx * 4 + 1])
            d["engine_buzzsaw"] = clean(DATA[:, :, idx * 4 + 2])
            d["fan_harmonics"] = clean(DATA[:28, :, idx * 4 + 3])

            d["airframe_toc"] = correct_to_toc_band(d["airframe"], toc)
            d["engine_broadband_toc"] = correct_to_toc_band(d["engine_broadband"], toc)
            d["engine_buzzsaw_toc"] = correct_to_toc_band(d["engine_buzzsaw"], toc)

            d["airframe_dBA"] = apply_a_weighting(d["airframe_toc"], a_weights)
            d["engine_broadband_dBA"] = apply_a_weighting(d["engine_broadband_toc"], a_weights)
            d["engine_buzzsaw_dBA"] = apply_a_weighting(d["engine_buzzsaw_toc"], a_weights)

            # Initialize the fan harmonics mapped to the 1/3 octave bands
            d["fan_harmonics_toc"] = np.zeros_like(d["airframe_toc"])
            d["fan_harmonics_toc"][:, 0] = d["airframe_toc"][:, 0]  # Copy frequency values from reference

            # Loop over each harmonic and assign its SPL to the nearest 1/3-octave band
            # NOTE: If multiple harmonics map to the same band, only the LAST one is retained.
            for f, spl in d["fan_harmonics"]:
                idx_closest = np.argmin(np.abs(d["fan_harmonics_toc"][:, 0] - f))
                d["fan_harmonics_toc"][idx_closest, 1] = spl  # Overwrite existing value

            d["fan_harmonics_dBA"] = apply_a_weighting(d["fan_harmonics_toc"], a_weights)

            d["engine"] = np.column_stack((
                d["airframe_toc"][:, 0],
                log_sum(
                    d["fan_harmonics_toc"][:, 1],
                    d["engine_broadband_toc"][:, 1],
                    d["engine_buzzsaw_toc"][:, 1]
                )
            ))

            d["engine_dBA"] = np.column_stack((
                d["airframe_dBA"][:, 0],
                log_sum(
                    d["fan_harmonics_dBA"][:, 1],
                    d["engine_broadband_dBA"][:, 1],
                    d["engine_buzzsaw_dBA"][:, 1]
                )
            ))

            d["overall"] = np.column_stack((
                d["airframe_toc"][:, 0],
                log_sum(
                    d["engine"][:, 1],
                    d["airframe_toc"][:, 1]
                )
            ))

            d["overall_dBA"] = np.column_stack((
                d["airframe_dBA"][:, 0],
                log_sum(
                    d["engine_dBA"][:, 1],
                    d["airframe_dBA"][:, 1]
                )
            ))
            
            d["overall_broadband"] = np.column_stack((
                d["airframe_toc"][:, 0],
                log_sum(
                    d["engine_broadband_toc"][:, 1],
                    d["airframe_toc"][:, 1]
                )
            ))

            d["engine_without_fan_harmonics"] = np.column_stack((
                d["airframe_toc"][:, 0],
                log_sum(
                    d["engine_broadband_toc"][:, 1],
                    d["engine_buzzsaw_toc"][:, 1]
                )
            ))

            d["overall_broadband_dBA"] = np.column_stack((
                d["airframe_dBA"][:, 0],
                log_sum(
                    d["engine_broadband_dBA"][:, 1],
                    d["airframe_dBA"][:, 1]
                )
            ))

            d["engine_without_fan_harmonics_dBA"] = np.column_stack((
                d["airframe_dBA"][:, 0],
                log_sum(
                    d["engine_broadband_dBA"][:, 1],
                    d["engine_buzzsaw_dBA"][:, 1]
                )
            ))


    # Step 4: Compute OASPL and Spectrograms
    OASPL, OASPL_dBA = compute_OASPL(data)
    SPECTROGRAM, SPECTROGRAM_dBA = compute_SPECTROGRAM(data)

    # Step 5: Check for repeated time steps
    doubled_time = []
    for j in range(n_observer):
        times = [data[i][j]['source_time'] for i in range(n_time)]
        unique_times = np.unique(times)
        doubled_time.append(len(unique_times) != len(times))

    # Step 6: Log results
    print("\n*--------------------------------------------------------------------------*")
    print("Log from <PANAM_SQAT_data_conversion> function")
    print(f"\n- Input file path: {str(PATH)}")

    if any(doubled_time):
        dup_obs = [i + 1 for i, v in enumerate(doubled_time) if v]
        print(f"\n- WARNING: Repeated time values were found for observer(s): {dup_obs}")
    else:
        print("\n- Repeated values on the time vector were not found for any receiver.")

    print(f"\n- Number of receiver(s) found: {n_observer}\n")
    for i in range(n_observer):
        x, y, z = data[0][i]['xobs'], data[0][i]['yobs'], data[0][i]['zobs']
        print(f"Receiver position {i + 1}: x = {x:.5g}\t| y = {y:.5g} \t| z = {z:.5g}")
    print("*--------------------------------------------------------------------------*")

    return data, OASPL, OASPL_dBA, SPECTROGRAM, SPECTROGRAM_dBA
    
def export_header_data_summary(PATH, HEADER, DATA, output_txt='mhdrload_output_summary.txt'):
    output_path = Path(PATH).with_name(output_txt)
    
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(f"=== MHDRLOAD OUTPUT SUMMARY ===\n")
        f.write(f"Input File: {PATH}\n\n")
        
        # Shapes
        f.write(f"HEADER shape: {HEADER.shape}\n")
        f.write(f"DATA shape: {DATA.shape}\n\n")

        # All header blocks
        f.write("=== HEADER CONTENT ===\n")
        for k in range(HEADER.shape[2]):
            f.write(f"--- HEADER BLOCK #{k + 1} ---\n")
            for i in range(HEADER.shape[0]):
                line = ''.join(HEADER[i, :, k]).rstrip()
                if line.strip():  # skip empty lines
                    f.write(f"{line}\n")
            f.write("\n")

        # All data blocks
        f.write("=== DATA CONTENT ===\n")
        for k in range(DATA.shape[2]):
            f.write(f"--- DATA BLOCK #{k + 1} ---\n")
            for i in range(DATA.shape[0]):
                row = DATA[i, :, k]
                if np.any(row):  # skip completely empty rows
                    row_str = " ".join(f"{x:.6f}" for x in row)
                    f.write(f"{row_str}\n")
            f.write("\n")

    print(f"Summary exported to: {output_path}")

if __name__ == "__main__":
    path = 'verification/PANAM_SQAT_data_conversion/auralization_input.dat'
    HEADER, DATA = mhdrload(path)
    export_header_data_summary(path, HEADER, DATA)