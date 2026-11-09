#auralization/private/tonal_synthesis.py

import numpy as np
import matplotlib.pyplot as plt
from utilities.plot_utils import plot_spectrogram
from utilities.plot_utils import export_figures
import globals

def interp1_extrap(x, xp, fp):
    """MATLAB interp1(xp, fp, x, 'linear', 'extrap'): linear interpolation, and linear extrapolation beyond
    the ends using the first / last segment (np.interp would clamp to the end values)."""
    x = np.asarray(x, dtype=float)
    xp = np.asarray(xp, dtype=float)
    fp = np.asarray(fp, dtype=float)
    y = np.interp(x, xp, fp)
    if len(xp) > 1:
        lo = x < xp[0]
        hi = x > xp[-1]
        if np.any(lo):
            y[lo] = fp[0] + (fp[1] - fp[0]) / (xp[1] - xp[0]) * (x[lo] - xp[0])
        if np.any(hi):
            y[hi] = fp[-1] + (fp[-1] - fp[-2]) / (xp[-1] - xp[-2]) * (x[hi] - xp[-1])
    return y


def tonal_synthesis(input, time_panam, time, show, tag_auralization, tag_source, input_type):
    """
    Synthesize tonal components from time-varying frequency and SPL.
    """
    tones = input['tones']
    tones_freq_time = np.array(input['tonesFreqTime'])
    tones_spl_time = np.array(input['tonesSPLTime'])

    # Optional input data check
    if show:
        from utilities.plot_style import latex_legend  # noqa: F401  (MATLAB legend is plain text here)
        fig, axs = plt.subplots(2, 1, figsize=(10, 6), layout="constrained")
        fig.canvas.manager.set_window_title(f"INPUT - Tonal content from PANAM - {input_type} - {tag_source}")
        handles = []
        for n in range(tones):
            h, = axs[0].plot(time_panam, tones_spl_time[n, :])
            handles.append(h)
            axs[1].plot(time_panam, tones_freq_time[n, :] / 1000)
        axs[0].set_ylabel(r'SPL, $L_{\mathrm{p,Z}}$ (dB)')
        axs[1].set_ylabel('Frequency, $f$ (kHz)')
        axs[1].set_xlabel(r'PANAM receiver time (trimmed), $t^*_{\mathrm{P,i}}$ (s)')
        if tag_source == "fan_harmonics":
            labels = [f'Tone {k}' for k in range(1, tones + 1)]
        else:
            labels = [f'Buzzsaw tones - K = {tones:g}']
            handles = handles[:1]
        # MATLAB: legend(...) with Orientation 'horizontal', Location 'northoutside', legend box off
        fig.legend(handles, labels, loc="outside upper center", ncol=len(labels), frameon=False)

        if tag_auralization:
            filename = f"{tag_auralization}_tonalContent_PANAM_{tag_source}"
            export_figures(filename, globals.save_mat_fig, save_png=True, save_pdf=True)
        plt.close()

    # Interpolate from PANAM time to auralization time
    envelope_spl = np.zeros((tones, len(time)))
    envelope_freq = np.zeros((tones, len(time)))
    envelope_amp = np.zeros((tones, len(time)))

    # `time` may extend one sample beyond time_panam (even-length rule); like MATLAB this is extrapolated linearly.
    for n in range(tones):
        envelope_spl[n, :] = interp1_extrap(time, time_panam, tones_spl_time[n, :])
        if np.any(np.isnan(envelope_spl[n, :])) or np.any(np.isinf(envelope_spl[n, :])):
            print(f"[WARN] NaN or Inf in envelope_spl for tone {n}")
        envelope_amp[n, :] = np.sqrt(2) * np.sqrt(globals.pref**2 * 10 ** (envelope_spl[n, :] / 10))
        envelope_freq[n, :] = interp1_extrap(time, time_panam, tones_freq_time[n, :])

    # Synthesize signal
    kf = 2 * np.pi / globals.fs
    n_samples = len(time)
    phase = np.random.uniform(-np.pi, np.pi, size=tones)
    #phase = np.zeros(tones)  # Python
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