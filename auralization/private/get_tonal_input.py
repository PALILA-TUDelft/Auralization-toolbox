#auralization/private/get_tonal_input.py

import numpy as np
from utilities.verification_paths import verif_path
from math import radians
import globals
import os
from utilities.plot_utils import plot_doppler_theta_buzzsaw, plot_buzzsaw_panamsynthesis
from utilities.ini_parser import ini_int

def get_octave_bands(b):
    G = 10 ** (3 / 10)
    fr = 1000
    x = np.arange(-18, 15)
    f_center = fr * G ** (x / b)
    f1 = f_center * G ** (-1 / (2 * b))
    f2 = f_center * G ** (1 / (2 * b))
    return f1, f_center, f2

def get_tonal_input(input_data, time_panam, source, tag_auralization="", show=False):
    if source == "buzzsaw":
        max_rpm = float(globals.input_file["max_rotations_per_minute"])
        n_harmonics = ini_int(globals.input_file, "n_harmonics", None)
        b = 3  # 1/3-octave
        f1, _, f2 = get_octave_bands(b)
        n_times = len(time_panam)

        tones_spl_time = np.zeros((n_harmonics, n_times))
        tones_freq_time = np.zeros((n_harmonics, n_times))
        prev_match_idx = np.zeros((n_harmonics,), dtype=int)
        theta_deg_time = np.zeros(n_times)
        doppler_ratio_time = np.zeros(n_times)
        #idx_map = np.zeros((n_harmonics, n_times), dtype=int)
        #prev_match_idx = np.ones((n_harmonics,), dtype=int)

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

            theta_deg_time[i] = phix
            doppler_ratio_time[i] = 1.0 / doppler  # f'/f0

            tones_freq_time[:, i] = shifted_freqs

            idx_synth = (shifted_freqs[:, None] >= f1) & (shifted_freqs[:, None] <= f2)
            tones_per_band = np.sum(idx_synth, axis=0)

            idx_panam = (tones[:, 0][:, None] >= f1) & (tones[:, 0][:, None] <= f2)

            for b in range(n_harmonics):
                if not np.any(idx_synth[b]):
                    tones_spl_time[b, i] = 0
                    # MATLAB (idx_synthesised2panam(B,i) stays 0 in this step) forgets the previous match, so the next
                    # step with no PANAM value falls back to tone 1 instead of an older match.
                    prev_match_idx[b] = 0
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

        if show:
            plot_doppler_theta_buzzsaw(theta_deg_time, doppler_ratio_time, tag_auralization)

            # Check-plot at the overhead position (closest source-receiver distance)
            dists = np.array([entry["dist"] for entry in input_data])
            overhead_idx = int(np.argmin(dists))

            tones_overhead = input_data[overhead_idx]["engine_buzzsaw"]
            tones_overhead = tones_overhead[tones_overhead[:, 0] != 0]

            freq_synthesis = tones_freq_time[:, overhead_idx]
            SPL_synthesis = tones_spl_time[:, overhead_idx]
            audible = SPL_synthesis > 0

            if len(tones_overhead) > 0 and np.any(audible):
                plot_buzzsaw_panamsynthesis(
                    tones_overhead[:, 0], tones_overhead[:, 1],
                    freq_synthesis[audible], SPL_synthesis[audible],
                    f1, f2, "buzzsaw", tag_auralization
                )

        # Optional: save debug/verification outputs
        if globals.verification:
            out_dir = verif_path("get_tonal_input")
            np.savez(os.path.join(out_dir, "tones_spl_debug_buzzsaw.npz"), signal=tones_spl_time)

            # Doppler / emission-angle vectors that feed the buzzsaw doppler figure
            dopp_dir = verif_path("doppler_theta_buzzsaw")
            np.savez(os.path.join(dopp_dir, "doppler_theta_buzzsaw_python.npz"),
                     theta_deg=theta_deg_time,
                     doppler_ratio=doppler_ratio_time)
            print("[VERIFICATION] Saved buzzsaw tones + doppler/theta vectors")

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

        if globals.verification:
            out_dir = verif_path("get_tonal_input")
            np.savez(os.path.join(out_dir, "tones_spl_debug_fan.npz"), signal=tones_spl_time)
            print(f"[VERIFICATION] Saved fan-harmonics tones to {out_dir}/tones_spl_debug_fan.npz")

        return {
            "tones": tones_freq_time.shape[0],
            "tonesFreqTime": tones_freq_time,
            "tonesSPLTime": tones_spl_time
        }

    
    else:
        raise ValueError(f"Unsupported source type: {source}")