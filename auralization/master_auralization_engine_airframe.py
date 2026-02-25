# auralization/master_auralization_engine_airframe.py

import numpy as np
import os
import globals
from globals import input_file
from utilities.plot_utils import plot_spectrogram
from auralization.private.get_auralization_time import get_auralization_time
from auralization.private.get_tonal_input import get_tonal_input
from auralization.private.tonal_synthesis import tonal_synthesis
from auralization.private.broadband_synthesis_smooth import broadband_synthesis_smooth
# from auralization.private.get_emission_angle import get_emission_angle  
from auralization.private.propagation.get_propagation import get_propagation
# from auralization.private.apply_propagation import apply_propagation
# from auralization.private.save_wav import save_wav
# from auralization.private.plot_spectrogram import plot_spectrogram

def master_auralization_engine_airframe(input_data, flight_profile, smoothing, input_type, tag_auralization, show):

    globals.dt_panam = input_data[1]['source_time'] - input_data[0]['source_time']

    # Step 1: Time vectors
    _, time_PANAM_auralization, time = get_auralization_time(input_data, input_type)

    # Step 2: Tonal synthesis - fan harmonics
    tag_source = "fan_harmonics"
    input_fan = get_tonal_input(input_data, time_PANAM_auralization, tag_source, tag_auralization)
    tonal_fan = tonal_synthesis(input_fan, time_PANAM_auralization, time, show, tag_auralization, tag_source, input_type)

    # Step 3: Tonal synthesis - buzzsaw
    tag_source = "buzzsaw"
    input_buzz = get_tonal_input(input_data, time_PANAM_auralization, tag_source, tag_auralization)
    tonal_buzz = tonal_synthesis(input_buzz, time_PANAM_auralization, time, show, tag_auralization, tag_source, input_type)

    # Step 4: Broadband synthesis - engine
    tag_source = "engine"
    broadband_engine = broadband_synthesis_smooth(input_data, tag_source, time_PANAM_auralization, time, smoothing, show, tag_auralization, input_type)

    # Step 5: Combine engine signals
    tonal_fan = tonal_fan.squeeze()
    tonal_buzz = tonal_buzz.squeeze()
    broadband_engine = broadband_engine.squeeze()

    engine_signal = tonal_fan.copy()
    engine_signal += tonal_buzz
    engine_signal += broadband_engine

    if show:
        plot_spectrogram(engine_signal, globals.fs, f"Spectrogram: Engine - {input_type}", tag_auralization, "_engineSignal_Spectrogram")

    # Step 6: Broadband synthesis - airframe
    tag_source = "airframe"
    airframe_signal = broadband_synthesis_smooth(input_data, tag_source, time_PANAM_auralization, time, smoothing, show, tag_auralization, input_type)

    # Step 7: Combine overall signal
    overall_signal = engine_signal + airframe_signal
    if show:
        plot_spectrogram(overall_signal, globals.fs, f"Spectrogram: Overall - {input_type}", tag_auralization, "_overallSignal_spectrogram")

    # Step 8: Ray-tracing propagation (if emission-based)
    receiver = [input_data[0]['xobs'], input_data[0]['yobs'], input_data[0]['zobs']]
    show_propagation = bool(show)
    nfft = int(globals.fs)  # 1 Hz resolution if fs integer

    # emission_angle_panam needed only for plotting comparisons; you can pass None for now
    emission_angle = None

    propagation_result = get_propagation(
        flight_profile=flight_profile,
        receiver=receiver,
        nfft=nfft,
        time=time_PANAM_auralization,
        emission_angle_panam=emission_angle,
        show=show_propagation,
        tag_auralization=tag_auralization,
    )

    # # Step 9: Apply propagation
    # consider_reflection = int(input_file.get("consider_ground_reflection", 1))
    # output = apply_propagation(overall_signal, propagation_result, 0, show, tag_auralization, "overallSignal", consider_reflection)

    # # Step 10: Save output .wav file
    # attenuation_db = float(input_file.get("attenuation_db", 0))
    # save_wav(output["outputSignal"], globals.fs, attenuation_db, "_overallSignal", tag_auralization)

    # if int(input_file.get("binaural_signal", 0)) == 1:
    #     save_wav(output["outputSignal_binaural"], globals.fs, attenuation_db, "_overallSignal_binaural", tag_auralization)

    # print("*--------------------------------------------------------------------------*")

    # return {
    #     "overallSignal": output["outputSignal"],
    #     "binaural": output.get("outputSignal_binaural", None)
    # }