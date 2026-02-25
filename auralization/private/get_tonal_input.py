#auralization/private/get_tonal_input.py

import numpy as np
from math import radians
import globals
import os

def get_octave_bands(b):
    f_center = np.array([
        16, 20, 25, 31.5, 40, 50, 63, 80, 100, 125, 160, 200, 250, 315, 400,
        500, 630, 800, 1000, 1250, 1600, 2000, 2500, 3150, 4000, 5000,
        6300, 8000, 10000, 12500, 16000, 20000, 25000
    ])
    f1 = f_center / 2**(1 / (2 * b))
    f2 = f_center * 2**(1 / (2 * b))
    return f1, f_center, f2

def get_tonal_input(input_data, time_panam, source, tag_auralization=""):
    if source == "buzzsaw":
        max_rpm = float(globals.input_file["max_rotations_per_minute"])
        n_harmonics = int(globals.input_file["n_harmonics"])
        b = 3  # 1/3-octave
        f1, _, f2 = get_octave_bands(b)
        n_times = len(time_panam)

        tones_spl_time = np.zeros((n_harmonics, n_times))
        tones_freq_time = np.zeros((n_harmonics, n_times))
        idx_map = np.zeros((n_harmonics, n_times), dtype=int)
        prev_match_idx = np.ones((n_harmonics,), dtype=int)

        for i in range(n_times):
            entry = input_data[i]
            n1 = entry["n1"]
            vel = entry["vel"]
            cs = entry["sound_speed"]
            phix = entry["phix"]
            tones = entry["engine_buzzsaw"]
            tones = tones[tones[:, 0] != 0]

            f0 = (n1 / 100.0) * (max_rpm / 60.0)
            base_freqs = f0 * np.arange(1, n_harmonics + 1)

            theta = radians(phix)
            doppler = 1 - (vel / cs) * np.cos(theta)
            shifted_freqs = base_freqs / doppler

            tones_freq_time[:, i] = shifted_freqs

            idx_synth = (shifted_freqs[:, None] >= f1) & (shifted_freqs[:, None] <= f2)
            tones_per_band = np.sum(idx_synth, axis=0)

            idx_panam = (tones[:, 0][:, None] >= f1) & (tones[:, 0][:, None] <= f2)

            for b in range(n_harmonics):
                if not np.any(idx_synth[b]):
                    tones_spl_time[b, i] = 0
                    continue

                band_idx = np.where(idx_synth[b])[0][0]
                panam_matches = np.where(idx_panam[:, band_idx])[0]

                if len(panam_matches) == 0:
                    match_idx = prev_match_idx[b] if i > 0 else 0
                    match_idx = min(match_idx, tones.shape[0] - 1)
                    spl_band = tones[match_idx, 1]
                elif len(panam_matches) == 1:
                    match_idx = panam_matches[0]
                    spl_band = tones[match_idx, 1]
                else:
                    match_idx = panam_matches[0]
                    spl_band = 10 * np.log10(np.sum(10 ** (tones[panam_matches, 1] / 10)))

                prev_match_idx[b] = match_idx
                pressure = globals.pref**2 * 10**(spl_band / 10)
                n_tones = max(tones_per_band[band_idx], 1)
                tone_pressure = np.sqrt(pressure / n_tones)

                if pressure <= 0 or not np.isfinite(tone_pressure) or tone_pressure < 1e-12:
                    tones_spl_time[b, i] = 0  # clamp to silence
                else:
                    tones_spl_time[b, i] = 20 * np.log10(tone_pressure / globals.pref)



        # Handle the tone threshold cutoff just like MATLAB
        if np.max(tones_spl_time[0, :]) < 20:
            tones_spl_time = tones_spl_time[0:1, :]
            tones_freq_time = tones_freq_time[0:1, :]

        # Optional: save debug outputs
        out_dir = "verification/get_tonal_input"
        os.makedirs(out_dir, exist_ok=True)
        np.savez(os.path.join(out_dir, "tones_spl_debug_buzzsaw.npz"), signal=tones_spl_time)

        return {
            "tones": tones_spl_time.shape[0],
            "tonesFreqTime": tones_freq_time,
            "tonesSPLTime": tones_spl_time
        }

    elif source == "fan_harmonics":
        tones_freq_time = []
        tones_spl_time = []
        for entry in input_data:
            tones = entry["fan_harmonics"]
            tones = tones[tones[:, 0] != 0]
            tones_freq_time.append(tones[:, 0])         
            tones_spl_time.append(tones[:, 1])

        max_len = max(len(f) for f in tones_freq_time)
        tones_freq_time = np.stack([np.pad(f, (0, max_len - len(f))) for f in tones_freq_time], axis=1)
        tones_spl_time = np.stack([np.pad(s, (0, max_len - len(s))) for s in tones_spl_time], axis=1)

        # In master_auralization_engine_airframe.py
        out_dir = "verification/get_tonal_input"
        os.makedirs(out_dir, exist_ok=True)
        np.savez(os.path.join(out_dir, "tones_spl_debug_fan.npz"), signal=tones_spl_time)

        return {
            "tones": tones_freq_time.shape[0],
            "tonesFreqTime": tones_freq_time,
            "tonesSPLTime": tones_spl_time
        }

    
    else:
        raise ValueError(f"Unsupported source type: {source}")