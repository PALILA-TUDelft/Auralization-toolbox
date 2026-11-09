# auralization/private/propagation/apply_propagation.py
#
# Port of MATLAB apply_propagation.m, get_FIR.m and overlapp_add_convolution.m
from __future__ import annotations
import os
import numpy as np
from utilities.verification_paths import verif_path
from scipy.signal import fftconvolve
import globals
from utilities.plot_utils import (plot_spectrogram, plot_spectrogram_binaural,
                                  plot_hrir_spectrogram, plot_spectrogram_difference,
                                  plot_fir_comparison, plot_fir_spectrogram)
from auralization.private.propagation.hrtf import hrir_interpolation


def apply_propagation(input_signal, propagation_result, binaural_signal,
                      show, tag_auralization, tag_source, consider_ground_reflection):
    """
    Apply atmospheric transfer functions (from get_propagation) to the
    synthesised source signal using time-varying FIR filters and
    overlap-add convolution.

    Port of MATLAB apply_propagation.m
    """
    fs = int(globals.fs)

    # `show` is either a bool (all plots on/off) or a dict with keys
    # "propagation_tf" (FIR plots), "propagated_spectrogram" and "binaural"
    if not isinstance(show, dict):
        show = {key: bool(show) for key in ("propagation_tf", "propagated_spectrogram", "binaural")}

    # Step 1: get FIR filters from transfer functions
    fir_result = _get_fir(propagation_result, fs, consider_ground_reflection,
                          binaural_signal, tag_auralization, show.get("propagation_tf", False))

    # Step 2: overlap-add convolution (mono)
    block_len = round(fs * globals.dt_panam)
    output_signal = _overlap_add_convolution(input_signal, block_len,
                                             fir_result["impulseResponse"], "mono")

    # Step 3: plot mono spectrogram
    if show.get("propagated_spectrogram", False):
        tag_title = f"OUTPUT - Spectrogram after propagation - {tag_source}"
        tag_save = f"_{tag_source}_spectrogram_emission_propagated"
        plot_spectrogram(output_signal, fs, tag_title, tag_auralization, tag_save)

    # ---- save vectors for verification ----
    if globals.verification:
        verif_dir = verif_path("apply_propagation")
        np.savez(
            os.path.join(verif_dir, "apply_propagation_python.npz"),
            ir=fir_result["impulseResponse"],
            output_signal=output_signal,
            input_signal=np.asarray(input_signal, dtype=float).ravel(),
            block_len=block_len,
        )
        print(f"[VERIFICATION] Saved apply_propagation vectors to {verif_dir}/apply_propagation_python.npz")

    result = {"outputSignal": output_signal}

    # Step 4: binaural overlap-add convolution
    if binaural_signal == 1:
        output_binaural = _overlap_add_convolution(
            input_signal, block_len,
            fir_result["impulseResponse_binaural"], "stereo")
        result["outputSignal_binaural"] = output_binaural

        # ---- save binaural vectors for verification ----
        if globals.verification:
            verif_dir_bin = verif_path("binaural")
            save_dict = {
                "ir_binaural_left": fir_result["impulseResponse_binaural"]["left_ear"],
                "ir_binaural_right": fir_result["impulseResponse_binaural"]["right_ear"],
                "output_binaural_left": output_binaural[:, 0],
                "output_binaural_right": output_binaural[:, 1],
                "hrir_direct_left": fir_result["HRIR_direct"]["l_a"],
                "hrir_direct_right": fir_result["HRIR_direct"]["r_a"],
            }
            if "HRIR_reflected" in fir_result:
                save_dict["hrir_reflected_left"] = fir_result["HRIR_reflected"]["l_a"]
                save_dict["hrir_reflected_right"] = fir_result["HRIR_reflected"]["r_a"]
            np.savez(os.path.join(verif_dir_bin, "binaural_python.npz"), **save_dict)
            print(f"[VERIFICATION] Saved binaural vectors to {verif_dir_bin}/binaural_python.npz")

        if show.get("propagated_spectrogram", False):
            tag_title = f"OUTPUT - Spectrogram after propagation (binaural) - {tag_source}"
            tag_save = f"_{tag_source}_spectrogram_emission_propagated_binaural"
            plot_spectrogram_binaural(output_binaural, fs, tag_title, tag_auralization, tag_save)

        if show.get("binaural", False) and tag_source == "overallSignal":
            if "HRIR_reflected" in fir_result:
                plot_hrir_spectrogram(
                    fir_result["HRIR_direct"], fir_result["HRIR_reflected"],
                    globals.dt_panam, tag_auralization,
                    f"_{tag_source}_spectrogram_HRIR")

            plot_spectrogram_difference(
                output_signal, output_binaural, fs,
                tag_auralization, f"_{tag_source}_spectrogram_binaural_mono")

    return result


# -----------------------------------------------------------------------
# get_FIR  (port of MATLAB get_FIR.m)
# -----------------------------------------------------------------------
def _single_to_double_sided(spec):
    """
    Convert single-sided spectrum (N/2+1 bins) to double-sided (N bins).
    Port of MATLAB AKsingle2bothSidedSpectrum.
    """
    return np.concatenate([spec, np.conj(spec[-2:0:-1])], axis=0)


def _get_fir(propagation_result, fs, consider_ground_reflection,
             binaural_signal, tag_auralization, show=False):
    """
    Convert single-sided transfer functions to truncated FIR filters.
    When binaural_signal=1, also produces HRTF-convolved binaural FIRs.

    Port of MATLAB get_FIR.m
    """
    input_file = globals.input_file

    if binaural_signal == 1:
        head_orientation = float(input_file.get("head_orientation", 0))
        sofa_path = input_file.get("hrtf_sofa_path", os.path.join("input_data", "FABIAN_HRIR_measured_HATO_0.mat"))

    TF_list = propagation_result["TF"]
    num_time_steps = len(TF_list)
    num_freq_bins = TF_list[0]["individual_tf"].shape[0]       # single-sided
    num_freq_bins_double = 2 * (num_freq_bins - 1)              # double-sided

    # --- direct path ---
    TF_direct = np.zeros((num_freq_bins, num_time_steps), dtype=np.complex128)
    for i in range(num_time_steps):
        TF_direct[:, i] = TF_list[i]["individual_tf"][:, 0]

    ir_direct = np.fft.irfft(TF_direct, n=num_freq_bins_double, axis=0)
    ir_direct = _make_causal(ir_direct)

    # --- reflected path ---
    if consider_ground_reflection:
        TF_reflected = np.zeros((num_freq_bins, num_time_steps), dtype=np.complex128)
        for i in range(num_time_steps):
            TF_reflected[:, i] = TF_list[i]["individual_tf"][:, 1]

        ir_reflected = np.fft.irfft(TF_reflected, n=num_freq_bins_double, axis=0)
        ir_reflected = _make_causal(ir_reflected)

    # --- binaural: apply HRTFs to atmospheric TFs in frequency domain ---
    if binaural_signal == 1:
        TF_direct_double = _single_to_double_sided(TF_direct)

        # direct path HRIRs
        az_direct = propagation_result["spherical_angles_HRTF"]["direct_path"][:, 0]
        el_direct = propagation_result["spherical_angles_HRTF"]["direct_path"][:, 1]
        HATO = 0  # head-above-torso orientation (degrees)

        hrir_direct_left, hrir_direct_right = hrir_interpolation(
            az_direct + head_orientation, el_direct, HATO, sofa_path)
        n_hrir = hrir_direct_left.shape[0]

        # zero-pad HRIRs to match double-sided TF length
        hrir_direct_left_padded = np.zeros((num_freq_bins_double, num_time_steps))
        hrir_direct_left_padded[:n_hrir, :] = hrir_direct_left
        hrir_direct_right_padded = np.zeros((num_freq_bins_double, num_time_steps))
        hrir_direct_right_padded[:n_hrir, :] = hrir_direct_right

        # binaural IR = IFFT( atmospheric_TF * FFT(HRIR) )
        ir_binaural_left_d = np.fft.ifft(
            TF_direct_double * np.fft.fft(hrir_direct_left_padded, axis=0), axis=0).real
        ir_binaural_right_d = np.fft.ifft(
            TF_direct_double * np.fft.fft(hrir_direct_right_padded, axis=0), axis=0).real

        ir_binaural_left_d = _make_causal(ir_binaural_left_d)
        ir_binaural_right_d = _make_causal(ir_binaural_right_d)

        # reflected path HRIRs
        if consider_ground_reflection:
            TF_reflected_double = _single_to_double_sided(TF_reflected)

            az_reflected = propagation_result["spherical_angles_HRTF"]["reflected_path"][:, 0]
            el_reflected = propagation_result["spherical_angles_HRTF"]["reflected_path"][:, 1]

            hrir_reflected_left, hrir_reflected_right = hrir_interpolation(
                az_reflected + head_orientation, el_reflected, HATO, sofa_path)

            hrir_reflected_left_padded = np.zeros((num_freq_bins_double, num_time_steps))
            hrir_reflected_left_padded[:n_hrir, :] = hrir_reflected_left
            hrir_reflected_right_padded = np.zeros((num_freq_bins_double, num_time_steps))
            hrir_reflected_right_padded[:n_hrir, :] = hrir_reflected_right

            ir_binaural_left_r = np.fft.ifft(
                TF_reflected_double * np.fft.fft(hrir_reflected_left_padded, axis=0), axis=0).real
            ir_binaural_right_r = np.fft.ifft(
                TF_reflected_double * np.fft.fft(hrir_reflected_right_padded, axis=0), axis=0).real

            ir_binaural_left_r = _make_causal(ir_binaural_left_r)
            ir_binaural_right_r = _make_causal(ir_binaural_right_r)

    # --- truncate FIR to nTaps ---
    n_taps = fs
    out = {}

    if consider_ground_reflection:
        out["impulseResponse"] = _truncate_fir(ir_direct + ir_reflected, n_taps)

        if binaural_signal == 1:
            out["impulseResponse_binaural"] = {
                "left_ear": _truncate_fir(ir_binaural_left_d + ir_binaural_left_r, n_taps),
                "right_ear": _truncate_fir(ir_binaural_right_d + ir_binaural_right_r, n_taps),
            }
            out["HRIR_direct"] = {"l_a": hrir_direct_left, "r_a": hrir_direct_right}
            out["HRIR_reflected"] = {"l_a": hrir_reflected_left, "r_a": hrir_reflected_right}
    else:
        out["impulseResponse"] = _truncate_fir(ir_direct, n_taps)

        if binaural_signal == 1:
            out["impulseResponse_binaural"] = {
                "left_ear": _truncate_fir(ir_binaural_left_d, n_taps),
                "right_ear": _truncate_fir(ir_binaural_right_d, n_taps),
            }
            out["HRIR_direct"] = {"l_a": hrir_direct_left, "r_a": hrir_direct_right}

    # --- FIR plots / verification export ---
    # tf_ref/t_block are computed unconditionally (cheap) so the verification
    # export below works even when show=False.
    # MATLAB: tBlock = round(numTimeSteps/2) (1-based, halves round up) -> 0-based index (N+1)//2 - 1.
    # (N // 2 is the same for odd N but one block too late for even N.)
    t_block = (num_time_steps + 1) // 2 - 1

    if consider_ground_reflection:
        TF_combined = np.zeros((num_freq_bins, num_time_steps), dtype=np.complex128)
        for i in range(num_time_steps):
            TF_combined[:, i] = TF_list[i]["combined_tf"]
        tf_ref = TF_combined
        tag_suffix = "_combined"
    else:
        tf_ref = TF_direct
        tag_suffix = "_direct"

    if globals.verification:
        verif_dir = verif_path("fir_transfer_function")

        n_taps = out["impulseResponse"].shape[0]
        n_bins_fir = int(np.ceil((n_taps + 1) / 2))
        freq_fir = np.linspace(0, fs / 2, n_bins_fir)
        fft_fir = np.fft.fft(out["impulseResponse"][:, t_block])
        mag_fir = 10 * np.log10(np.abs(fft_fir[:n_bins_fir]) ** 2 + 1e-30)

        freq_art = np.linspace(0, fs / 2, tf_ref.shape[0])
        mag_art = 10 * np.log10(np.abs(tf_ref[:, t_block]) ** 2 + 1e-30)

        out_path = os.path.join(verif_dir, f"fir_transfer_function{tag_suffix}_python.npz")
        np.savez(out_path,
                 freq_fir=freq_fir, mag_fir=mag_fir,
                 freq_art=freq_art, mag_art=mag_art,
                 t_block=t_block, n_taps=n_taps)
        print(f"[VERIFICATION] Saved FIR transfer function vectors to {out_path}")

    if show:
        plot_fir_comparison(out["impulseResponse"], tf_ref, t_block, fs,
                            tag_auralization + tag_suffix if tag_auralization else "")
        plot_fir_spectrogram(out["impulseResponse"], tf_ref, fs,
                             tag_auralization + tag_suffix if tag_auralization else "")

        if binaural_signal == 1:
            plot_fir_comparison(out["impulseResponse_binaural"]["left_ear"], tf_ref, t_block, fs,
                                tag_auralization + tag_suffix + "_binaural_left" if tag_auralization else "")
            plot_fir_spectrogram(out["impulseResponse_binaural"]["left_ear"], tf_ref, fs,
                                 tag_auralization + tag_suffix + "_binaural_left" if tag_auralization else "")

    return out


# -----------------------------------------------------------------------
# overlap-add convolution  (port of MATLAB overlapp_add_convolution.m)
# -----------------------------------------------------------------------
def _overlap_add_convolution(input_signal, block_len, ir, mode="mono"):
    """
    FFT-based block convolution using overlap-add.

    Parameters
    ----------
    input_signal : (N,) array
    block_len : int — synthesis block length in samples
    ir : mono mode — (nTaps, nBlocks) array
         stereo mode — dict with "left_ear" and "right_ear", each (nTaps, nBlocks)
    mode : "mono" or "stereo"

    Returns
    -------
    mono: (N + nTaps - 1,) array
    stereo: (N + nTaps - 1, 2) array — column 0 = left, column 1 = right
    """
    input_signal = np.asarray(input_signal, dtype=float).ravel()

    if mode == "mono":
        L = len(input_signal) // block_len
        input_signal = input_signal[:block_len * L]

        n_taps = ir.shape[0]
        output_signal = np.zeros(block_len * L + n_taps - 1)

        for ll in range(L):
            block = input_signal[ll * block_len:(ll + 1) * block_len]
            h = ir[:, ll]
            conv_result = fftconvolve(block, h, mode="full")
            output_signal[ll * block_len:ll * block_len + len(conv_result)] += conv_result

        return output_signal

    elif mode == "stereo":
        ir_left = ir["left_ear"]
        ir_right = ir["right_ear"]

        L = len(input_signal) // block_len
        input_signal = input_signal[:block_len * L]

        n_taps = ir_left.shape[0]
        out_len = block_len * L + n_taps - 1
        output_left = np.zeros(out_len)
        output_right = np.zeros(out_len)

        for ll in range(L):
            block = input_signal[ll * block_len:(ll + 1) * block_len]

            conv_l = fftconvolve(block, ir_left[:, ll], mode="full")
            output_left[ll * block_len:ll * block_len + len(conv_l)] += conv_l

            conv_r = fftconvolve(block, ir_right[:, ll], mode="full")
            output_right[ll * block_len:ll * block_len + len(conv_r)] += conv_r

        return np.column_stack([output_left, output_right])


# -----------------------------------------------------------------------
# helpers
# -----------------------------------------------------------------------
def _make_causal(ir):
    """
    Shift impulse response to make it causal (port of MATLAB il_makeCausal).
    """
    n_samples = ir.shape[0]
    out = ir.copy()
    for i in range(ir.shape[1]):
        if ir[-1, i] > 1e-8:  # MATLAB: signed test (input(end,i) > 1e-8), not abs()
            out[:, i] = np.roll(ir[:, i], n_samples // 2)
    return out


def _truncate_fir(ir, n_taps):
    """
    Truncate impulse response to nTaps around its peak (port of MATLAB il_truncate_FIR).
    """
    num_cols = ir.shape[1]
    # zero-pad to avoid boundary issues
    pad = np.zeros((n_taps, num_cols))
    ir_padded = np.vstack([pad, ir, pad])

    out = np.zeros((n_taps, num_cols))
    for i in range(num_cols):
        idx_max = int(np.argmax(ir_padded[:, i]))
        start = idx_max - n_taps // 2
        end_ = start + n_taps
        out[:, i] = ir_padded[start:end_, i]

    return out
