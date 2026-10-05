# auralization/master_auralization_engine_airframe.py

import os
import numpy as np
from utilities.verification_paths import verif_path
import globals
from utilities.plot_utils import plot_spectrogram
from auralization.private.get_auralization_time import get_auralization_time
from auralization.private.get_tonal_input import get_tonal_input
from auralization.private.tonal_synthesis import tonal_synthesis
from auralization.private.broadband_synthesis_smooth import broadband_synthesis_smooth
from auralization.private.get_emission_angle import get_emission_angle
from auralization.private.propagation.get_propagation import get_propagation
from auralization.private.propagation.apply_propagation import apply_propagation
from auralization.private.save_wav import save_wav
from utilities.ini_parser import ini_int

def master_auralization_engine_airframe(input_data, flight_profile, smoothing, input_type, tag_auralization, show, wav_path=None):

    # `show` is either a bool (all figures on/off) or a dict mapping figure keys
    # (see main.FIGURE_KEYS) to booleans
    if isinstance(show, dict):
        _show = lambda key: bool(show.get(key, False))
    else:
        _show = lambda key: bool(show)

    globals.dt_panam = input_data[1]['source_time'] - input_data[0]['source_time']

    # Step 1: Time vectors
    _, time_PANAM_auralization, time = get_auralization_time(input_data, input_type)

    if globals.verification:
        verif_dir = verif_path("time_vector")
        np.savez(os.path.join(verif_dir, "time_vectors_python.npz"),
                 time_PANAM_auralization=time_PANAM_auralization,
                 time=time)
        print(f"[VERIFICATION] Saved time vectors to {verif_dir}/time_vectors_python.npz")

    # Step 2: Tonal synthesis - fan harmonics
    tag_source = "fan_harmonics"
    input_fan = get_tonal_input(input_data, time_PANAM_auralization, tag_source, tag_auralization)
    tonal_fan = tonal_synthesis(input_fan, time_PANAM_auralization, time, _show("tonal_fan"), tag_auralization, tag_source, input_type)

    # Step 3: Tonal synthesis - buzzsaw
    tag_source = "buzzsaw"
    input_buzz = get_tonal_input(input_data, time_PANAM_auralization, tag_source, tag_auralization,
                                 show=_show("tonal_buzzsaw"))
    tonal_buzz = tonal_synthesis(input_buzz, time_PANAM_auralization, time, _show("tonal_buzzsaw"), tag_auralization, tag_source, input_type)

    # Step 4: Broadband synthesis - engine
    tag_source = "engine"
    broadband_engine = broadband_synthesis_smooth(input_data, tag_source, time_PANAM_auralization, time, smoothing, _show("broadband_engine"), tag_auralization, input_type)

    # Step 5: Combine engine signals
    tonal_fan = tonal_fan.squeeze()
    tonal_buzz = tonal_buzz.squeeze()
    broadband_engine = broadband_engine.squeeze()

    if globals.verification:
        verif_dir = verif_path("tonal_fan_signal")
        np.savez(os.path.join(verif_dir, "tonal_fan_signal_python.npz"), signal=tonal_fan)

        verif_dir = verif_path("tonal_buzz_signal")
        np.savez(os.path.join(verif_dir, "tonal_buzz_signal_python.npz"), signal=tonal_buzz)

        verif_dir = verif_path("specrogram_engine_bbn")
        np.savez(os.path.join(verif_dir, "BroadbandSignal_engine_python.npz"), signal=broadband_engine)
        print("[VERIFICATION] Saved tonal-fan/tonal-buzz/broadband-engine signals")

    engine_signal = tonal_fan + tonal_buzz + broadband_engine

    if globals.verification:
        verif_dir = verif_path("engine_signal_auralized")
        np.savez(os.path.join(verif_dir, "engine_signal_python.npz"), signal=engine_signal)
        print(f"[VERIFICATION] Saved engine signal to {verif_dir}/engine_signal_python.npz")

    if _show("engine_spectrogram"):
        plot_spectrogram(engine_signal, globals.fs, f"Spectrogram: Engine - {input_type}", tag_auralization, "_engineSignal_Spectrogram")

    # Step 6: Broadband synthesis - airframe
    tag_source = "airframe"
    airframe_signal = broadband_synthesis_smooth(input_data, tag_source, time_PANAM_auralization, time, smoothing, _show("broadband_airframe"), tag_auralization, input_type)

    if globals.verification:
        verif_dir = verif_path("airframe")
        np.savez(os.path.join(verif_dir, "airframe_signal_python.npz"), signal=airframe_signal.squeeze())
        print(f"[VERIFICATION] Saved airframe signal to {verif_dir}/airframe_signal_python.npz")

    # Step 7: Combine overall signal
    overall_signal = engine_signal + airframe_signal

    if globals.verification:
        verif_dir = verif_path("spectrogram_overall_signal")
        np.savez(os.path.join(verif_dir, "overall_signal_python.npz"), signal=overall_signal.squeeze())
        print(f"[VERIFICATION] Saved overall signal to {verif_dir}/overall_signal_python.npz")

    if _show("overall_spectrogram"):
        plot_spectrogram(overall_signal, globals.fs, f"Spectrogram: Overall - {input_type}", tag_auralization, "_overallSignal_spectrogram")

    # Step 8: Ray-tracing propagation
    receiver = [input_data[0]['xobs'], input_data[0]['yobs'], input_data[0]['zobs']]
    nfft = int(globals.fs)  # df = 1 Hz

    emission_angle_panam = get_emission_angle(input_data)

    input_file = globals.input_file

    propagation_result = get_propagation(
        input_file=input_file,
        flight_profile=flight_profile,
        receiver=receiver,
        nfft=nfft,
        time=time_PANAM_auralization,
        emission_angle_panam=emission_angle_panam,
        show={key: _show(key) for key in ("propagation_rays", "propagation_tf")},
        tag_auralization=tag_auralization,
    )

    # Step 9: Apply propagation
    consider_reflection = ini_int(input_file, "consider_ground_reflection", 1)
    binaural_signal = ini_int(input_file, "binaural_signal", 0)

    tag_source = "overallSignal"
    overall_result = apply_propagation(
        overall_signal, propagation_result, binaural_signal,
        {key: _show(key) for key in ("propagation_tf", "propagated_spectrogram", "binaural")},
        tag_auralization, tag_source, consider_reflection
    )

    # Step 10: Save output .wav file (saved even when figure saving is disabled)
    if wav_path is None:
        wav_path = tag_auralization
    attenuation_db = float(input_file.get("attenuation_db", 0))
    save_wav(overall_result["outputSignal"], int(globals.fs), attenuation_db, "_overallSignal", wav_path)

    # Build output struct
    output_auralization = {
        "emission": {
            "overallSignal": overall_signal,
            "engineSignal": engine_signal,
            "tonalSignalFanHarmonics": tonal_fan,
            "tonalSignalBuzzsaw": tonal_buzz,
            "broadbandSignal_engine": broadband_engine,
            "auralizedAirframeSignal": airframe_signal,
        },
        "overallSignal": overall_result["outputSignal"],
    }

    # ---- save vectors for wav verification ----
    if globals.verification:
        verif_dir = verif_path("wav_output")
        np.savez(os.path.join(verif_dir, "wav_output_python.npz"),
                 output_signal=overall_result["outputSignal"],
                 attenuation_db=attenuation_db)
        print(f"[VERIFICATION] Saved wav output to {verif_dir}/wav_output_python.npz")

    # Step 11: Binaural signal
    if binaural_signal == 1:
        output_auralization["overallSignal_binaural"] = overall_result["outputSignal_binaural"]
        save_wav(overall_result["outputSignal_binaural"], int(globals.fs), attenuation_db, "_overallSignal_binaural", wav_path)

    print("*--------------------------------------------------------------------------*")

    return output_auralization
