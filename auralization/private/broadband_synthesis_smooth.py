#auralization/private/broadband_synthesis_smooth.py

import numpy as np
from utilities.verification_paths import verif_path
import os
from scipy.signal.windows import hann
from numpy.fft import ifft
from utilities.plot_utils import plot_spectrogram, plot_bbn_toc_to_narrowband
from auralization.private.convert_freq_bands import convert_freq_bands
import globals

def build_hop_band_matrices(bands_vs_time, freq_panam, n_blocks, hop_size_factor):
    """Spread the PANAM time steps over the synthesis hop blocks (MATLAB: RepBandsVsTime / freq_PANAM_rep).

    Each PANAM step j fills ``hop_size_factor`` consecutive blocks: the first with the values of step j, the
    following ones with the mean of steps j and j+1 (and the band frequencies of step j). In the last interval
    (j == n_blocks/hop_size_factor) all blocks keep the values of step j. Direct translation of
    broadbandSynthesis_smooth.m, including its behaviour when n_blocks is not a multiple of
    hop_size_factor: MATLAB then grows the matrices beyond n_blocks rows, and so does this function.

    bands_vs_time : (n_steps, n_bands)   freq_panam : (n_bands, n_steps)
    returns (rep_bands_vs_time, freq_panam_rep), both (n_rows, n_bands), n_rows >= n_blocks
    """
    H = hop_size_factor
    n_steps, n_bands = bands_vs_time.shape
    last_i = ((n_blocks - 1) // H) * H
    n_rows = last_i + H
    rep = np.zeros((n_rows, n_bands))
    frep = np.zeros((n_rows, n_bands))

    j = 0
    for i in range(0, n_blocks, H):
        rep[i] = bands_vs_time[j]
        frep[i] = freq_panam[:, j]
        if (j + 1) != n_blocks / H:                       # MATLAB (1-based): j ~= nBlocks/HopSizeFactor
            if j + 1 >= n_steps:
                raise ValueError("n_blocks is not a multiple of the hop size factor and the PANAM data runs out; "
                                 "the MATLAB implementation fails for this input as well.")
            rep[i + 1:i + H] = 0.5 * (bands_vs_time[j] + bands_vs_time[j + 1])
        else:
            rep[i + 1:i + H] = bands_vs_time[j]
        frep[i + 1:i + H] = freq_panam[:, j]
        j += 1
        if i == n_blocks - 1:                             # MATLAB: if i == nBlocks, return  (aborts the function)
            raise ValueError("n_blocks % hop_size_factor == 1: the MATLAB implementation aborts here as well.")
    return rep, frep


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
    # MATLAB: floor(fs*time(end)/HopSize). The tolerance guards against x.9999999999 due to round-off.
    n_blocks = int(np.floor(fs * time[-1] / hop_size + 1e-6))
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
        input_time = time_panam
        plot_bands_vs_time = bands_vs_time     # (n_orig_times, n_bands)
        plot_freq_panam = freq_panam           # (n_bands, n_orig_times)
        bins_vs_time, bins_vs_time_equal = convert_freq_bands(bands_vs_time, freq_panam, df, time_panam, block_len, smoothing)
    else:
        rep_bands_vs_time, freq_panam_rep = build_hop_band_matrices(bands_vs_time, freq_panam, n_blocks, hop_size_factor)

        input_time = np.linspace(0, time_panam[-1], rep_bands_vs_time.shape[0])
        plot_bands_vs_time = rep_bands_vs_time     # (n_blocks, n_bands)
        plot_freq_panam = freq_panam_rep.T         # (n_bands, n_blocks)
        bins_vs_time, bins_vs_time_equal = convert_freq_bands(rep_bands_vs_time, freq_panam_rep.T, df, input_time, block_len, smoothing)

    bins_vs_time = bins_vs_time.T
    bins_vs_time_equal = bins_vs_time_equal.T

    if show:
        # Check-plot (port of MATLAB ConvertFreqBands plot block): PANAM 1/3-octave
        # band input at the middle time block vs. the (pre-smoothing) equal-distribution
        # narrowband spectrum at the first time block.
        idx_t = int(np.floor(plot_bands_vs_time.shape[0] / 2 + 0.5)) - 1  # MATLAB round(N/2), 1-based

        freq_narrowband = np.linspace(0, fs / 2, block_len // 2 + 1)
        # Matches MATLAB's p2spl(x) = 20*log10(x/2e-5) exactly: no epsilon, no
        # /sqrt(2). Bins with zero assigned pressure (see note below) correctly
        # come out as -inf here, same as MATLAB; plot_bbn_toc_to_narrowband
        # masks non-finite values before drawing instead of clipping them to
        # a finite floor.
        with np.errstate(divide="ignore"):
            SPL_narrowband = 20 * np.log10(np.abs(bins_vs_time_equal[0, :]) / pref)

        plot_bbn_toc_to_narrowband(
            plot_freq_panam[:, idx_t], plot_bands_vs_time[idx_t, :],
            freq_narrowband, SPL_narrowband, source, df, tag_auralization
        )

    if globals.verification:
        # Vectors behind the "TOC to Narrowband" check-plot (computed independently of `show`)
        idx_t = int(np.floor(plot_bands_vs_time.shape[0] / 2 + 0.5)) - 1
        freq_narrowband_v = np.linspace(0, fs / 2, block_len // 2 + 1)
        # Same formula as above (matches MATLAB's p2spl exactly) so the saved
        # verification vectors are bit-comparable to what the real MATLAB
        # plot displays, not a separately-invented approximation.
        with np.errstate(divide="ignore"):
            SPL_narrowband_v = 20 * np.log10(np.abs(bins_vs_time_equal[0, :]) / pref)
            # after the smoothing iterations, mid time-block (MATLAB: p2spl(p(:, idx_t)))
            SPL_narrowband_smoothed_v = 20 * np.log10(np.abs(bins_vs_time[idx_t, :]) / pref)
        verif_dir = verif_path("bbn_narrowband")
        np.savez(os.path.join(verif_dir, f"bbn_narrowband_{source}_python.npz"),
                 freq_bands=plot_freq_panam[:, idx_t],
                 SPL_bands=plot_bands_vs_time[idx_t, :],
                 freq_narrowband=freq_narrowband_v,
                 SPL_narrowband=SPL_narrowband_v,
                 SPL_narrowband_smoothed=SPL_narrowband_smoothed_v,
                 df=df)
        print(f"[VERIFICATION] Saved BBN TOC->narrowband vectors ({source}) to {verif_dir}/bbn_narrowband_{source}_python.npz")

    broadband_signal = np.zeros(L)
    win = hann(block_len) #, sym=False)
    n_ovlp = block_len / hop_size
    win_energy = np.sum(win ** 2) / block_len

    for i_block in range(n_blocks):
        start = i_block * hop_size
        end = start + block_len

        filt_ampl = bins_vs_time[i_block]
        # NOTE: do NOT reseed per block here. Seeding with i_block made every
        # source (engine, airframe, ...) draw the identical phase sequence, so
        # the broadband sources became phase-correlated and added partially
        # coherently (~+1.3 dB on the overall signal). MATLAB draws phases from
        # an un-reseeded RNG stream, giving independent phases per source; we
        # match that by leaving the global RNG stream to flow.
        filt_phase = 2 * np.pi * np.random.rand(len(filt_ampl))
        #filt_phase = np.zeros(len(filt_ampl))

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