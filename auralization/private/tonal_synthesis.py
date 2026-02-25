#auralization/private/tonal_synthesis.py

import numpy as np
import matplotlib.pyplot as plt
from utilities.plot_utils import plot_spectrogram
from utilities.plot_utils import export_figures
import globals

def tonal_synthesis(input, time_panam, time, show, tag_auralization, tag_source, input_type):
    """
    Synthesize tonal components from time-varying frequency and SPL.
    """
    tones = input['tones']
    tones_freq_time = np.array(input['tonesFreqTime'])
    tones_spl_time = np.array(input['tonesSPLTime'])

    # Optional input data check
    if show:
        fig, axs = plt.subplots(2, 1, figsize=(10, 6))
        for n in range(tones):
            axs[0].plot(time_panam, tones_spl_time[n, :], label=f'Tone {n + 1}')
            axs[1].plot(time_panam, tones_freq_time[n, :] / 1000)
        axs[0].set_ylabel('SPL, $L_{p,Z}$ (dB)')
        axs[1].set_ylabel('Frequency, $f$ (kHz)')
        axs[1].set_xlabel('PANAM receiver time (trimmed), $t^*_{P,i}$ (s)')
        axs[0].legend(loc='upper right')
        fig.suptitle(f"INPUT - Tonal content from PANAM - {input_type} - {tag_source}")
        fig.tight_layout()

        if tag_auralization:
            filename = f"{tag_auralization}_tonalContent_PANAM_{tag_source}"
            export_figures(filename, globals.save_mat_fig, save_png=True, save_pdf=True)
        plt.close()

    # Interpolate from PANAM time to auralization time
    envelope_spl = np.zeros((tones, len(time)))
    envelope_freq = np.zeros((tones, len(time)))
    envelope_amp = np.zeros((tones, len(time)))

    for n in range(tones):
        envelope_spl[n, :] = np.interp(time, time_panam, tones_spl_time[n, :])
        if np.any(np.isnan(envelope_spl[n, :])) or np.any(np.isinf(envelope_spl[n, :])):
            print(f"[WARN] NaN or Inf in envelope_spl for tone {n}")
        envelope_amp[n, :] = np.sqrt(2) * np.sqrt(globals.pref**2 * 10 ** (envelope_spl[n, :] / 10))
        envelope_freq[n, :] = np.interp(time, time_panam, tones_freq_time[n, :])

    # Synthesize signal
    kf = 2 * np.pi / globals.fs
    n_samples = len(time)
    #phase = np.random.uniform(-np.pi, np.pi, size=tones)
    phase = np.zeros(tones)  # Python
    tonal_signal = np.zeros(n_samples)

    for n in range(tones):
        tone = envelope_amp[n, :] * np.cos(kf * np.cumsum(envelope_freq[n, :]) + phase[n])
        tonal_signal += tone
        # === DEBUG: Look for 24 kHz tones ===
        if np.any((envelope_freq[n, :] > 23000) & (envelope_freq[n, :] < 25000)):
            max_freq = np.max(envelope_freq[n, :]) / 1000
            max_spl = np.max(envelope_spl[n, :])
            max_amp = np.max(envelope_amp[n, :])
            print(f"[DEBUG] Tone {n}: max freq = {max_freq:.2f} kHz, max SPL = {max_spl:.2f} dB, max amp = {max_amp:.2e} Pa")



    tonal_signal = tonal_signal.reshape(-1, 1)  # Column vector convention

    print("\n*--------------------------------------------------------------------------*")
    print(f"Log from <SQAT_auralization_master> function ({input_type}-based)")
    print(f"- TonalSynthesis ({tag_source}): Synthesis time completed.")

    if show:
        tag_title = f"OUTPUT - Spectrogram of auralized tonal noise - {input_type} - {tag_source}"
        tag_save = f"_tonalSignal_Spectrogram_{tag_source}"
        plot_spectrogram(tonal_signal, globals.fs, tag_title, tag_auralization, tag_save)

    return tonal_signal