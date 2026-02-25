#auralization/private/broadband_synthesis_smooth.py

import numpy as np
import os
from scipy.signal.windows import hann
from numpy.fft import ifft
from utilities.plot_utils import plot_spectrogram
from auralization.private.convert_freq_bands import convert_freq_bands
import globals

def broadband_synthesis_smooth(input_data, source, time_panam, time, smoothing, show, tag_auralization, input_type):
    fs = globals.fs
    pref = globals.pref
    dt_panam = globals.dt_panam

    WinFlag = True
    WinCorr = True
    OvlpCorr = True

    block_len = round(fs * dt_panam)
    hop_size_factor = 5
    hop_size = block_len // hop_size_factor
    n_blocks = int(fs * time[-1] / hop_size)
    L = hop_size * n_blocks + block_len - hop_size
    df = fs / block_len

    freq_panam = []
    bands_vs_time = []

    for i in range(len(input_data)):
        entry = input_data[i]
        if source == 'engine':
            freq_panam.append(entry['engine_broadband'][:, 0])
            bands_vs_time.append(entry['engine_broadband'][:, 1])
        elif source == 'airframe':
            freq_panam.append(entry['airframe'][:, 0])
            bands_vs_time.append(entry['airframe'][:, 1])
        elif source == 'overall':
            freq_panam.append(entry['overall_broadband'][:, 0])
            bands_vs_time.append(entry['overall_broadband'][:, 1])

    freq_panam = np.array(freq_panam).T
    bands_vs_time = np.array(bands_vs_time)

    if hop_size_factor == 1:
        bins_vs_time = convert_freq_bands(bands_vs_time, freq_panam, df, time_panam, block_len, smoothing)
    else:
        rep_bands_vs_time = np.zeros((n_blocks, freq_panam.shape[0]))
        freq_panam_rep = np.zeros_like(rep_bands_vs_time)

        j = 0
        for i in range(0, n_blocks, hop_size_factor):
            rep_bands_vs_time[i] = bands_vs_time[j]
            freq_panam_rep[i] = freq_panam[:, j]
            if j != n_blocks // hop_size_factor - 1:
                for k in range(1, hop_size_factor):
                    rep_bands_vs_time[i + k] = 0.5 * (bands_vs_time[j] + bands_vs_time[j + 1])
                    freq_panam_rep[i + k] = freq_panam[:, j]
            else:
                for k in range(1, hop_size_factor):
                    rep_bands_vs_time[i + k] = bands_vs_time[j]
                    freq_panam_rep[i + k] = freq_panam[:, j]
            j += 1
            if i + hop_size_factor >= n_blocks:
                rep_bands_vs_time[i+1:] = bands_vs_time[j]
                freq_panam_rep[i+1:] = freq_panam[:, j]
                break


        input_time = np.linspace(0, time_panam[-1], rep_bands_vs_time.shape[0])
        bins_vs_time = convert_freq_bands(rep_bands_vs_time, freq_panam_rep.T, df, input_time, block_len, smoothing)

    bins_vs_time = bins_vs_time.T
    broadband_signal = np.zeros(L)
    win = hann(block_len, sym=False)
    n_ovlp = block_len / hop_size
    win_energy = np.sum(win ** 2) / block_len

    for i_block in range(n_blocks):
        start = i_block * hop_size
        end = start + block_len

        filt_ampl = bins_vs_time[i_block]
        np.random.seed(i_block)
        filt_phase = 2 * np.pi * np.random.rand(len(filt_ampl))
        filt_phase[0] = 0
        filt_phase[-1] = 0

        filter_one_side = filt_ampl * np.exp(1j * filt_phase)
        filter_one_side[1:] *= block_len
        filter_one_side[1:] /= 2


        filter_total = np.concatenate([filter_one_side, np.conj(filter_one_side[-2:0:-1])])
        block_out = np.real(ifft(filter_total))

        grain = block_out * win if WinFlag else block_out

        if WinCorr:
            grain /= np.sqrt(win_energy)
        if OvlpCorr:
            grain /= np.sqrt(n_ovlp)

        grain_rms = np.sqrt(np.mean(grain**2))


        broadband_signal[start:end] += grain

    if L < len(time):
        broadband_signal = np.concatenate([broadband_signal, np.ones(len(time) - L) * broadband_signal[-1]])
    elif L > len(time):
        broadband_signal = broadband_signal[:len(time)]

    if show:
        title = f"OUTPUT - Spectrogram of auralized BBN - {input_type} - {source}"
        tag_save = f"_broadbandSignal_spectrogram_{source}"
        plot_spectrogram(broadband_signal, fs, title, tag_auralization, tag_save)
        
    return broadband_signal