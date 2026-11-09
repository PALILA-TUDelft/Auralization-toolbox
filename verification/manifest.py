"""Manifest of every file/variable that must exist for a Python<->MATLAB comparison.

Single source of truth used by check_scenario_complete.py and run_scenarios.py.
File names and keys mirror what run_all_verifications.py reads, so if a name is
changed there it must be changed here too.

Layout per scenario:
    verification/scenarios/<scenario>/<step>/<py_file>   (written by main.py --verification)
    verification/scenarios/<scenario>/<step>/<mat_file>  (written by the MATLAB toolbox)
    verification/scenarios/<scenario>/scenario_params_python.json  (parsed ini, written by Python)

`when` is an optional predicate on the parsed ini dict (strings) -- if it returns
False the entry is not required for that scenario.
"""


def _f(ini, key, default=0.0):
    try:
        return float(ini.get(key, default))
    except (TypeError, ValueError):
        return float(default)


def binaural_on(ini):
    return _f(ini, "binaural_signal") == 1


def reflection_on(ini):
    return _f(ini, "consider_ground_reflection") == 1


def fir_tag(ini):
    return "combined" if reflection_on(ini) else "direct"


# step, python file, python keys, matlab file, matlab vars, when
# (fir_transfer_function file names depend on the scenario -> handled in required_entries)
_STEPS = [
    ("flight_profile", "flight_profile_python.npz", ["x", "y", "z", "TAS", "thrust"],
     "flight_profile_matlab.mat", ["x", "z", "TAS", "thrust"], None),
    ("trim_data", "trim_data_python.npz", ["time", "SPL_vs_time"],
     "trim_data_matlab.mat", ["time", "SPL_vs_time"], None),
    ("Prepare_input_SQ", "python_trimmed_output.npz", ["source_data_trimmed"],
     "MATLAB_trimmed_output.mat", ["source_data_trimmed"], None),
    ("time_vector", "time_vectors_python.npz", ["time_PANAM_auralization", "time"],
     "time_vectors_matlab.mat", ["time_PANAM_auralization", "time"], None),
    ("get_tonal_input", "tones_spl_debug_fan.npz", ["signal"],
     "tones_spl_debug_matlab_f.mat", ["tonesSPLTime"], None),
    ("get_tonal_input", "tones_spl_debug_buzzsaw.npz", ["signal"],
     "tones_spl_debug_matlab_b.mat", ["tonesSPLTime"], None),
    ("doppler_theta_buzzsaw", "doppler_theta_buzzsaw_python.npz", ["theta_deg", "doppler_ratio"],
     "doppler_theta_buzzsaw_matlab.mat", ["theta_deg", "doppler_ratio"], None),
    ("tonal_fan_signal", "tonal_fan_signal_python.npz", ["signal"],
     "tonal_fan_signal_matlab.mat", ["TonalSignal_FanHarmonics"], None),
    ("tonal_buzz_signal", "tonal_buzz_signal_python.npz", ["signal"],
     "tonal_buzz_signal_matlab.mat", ["TonalSignal_Buzzsaw"], None),
    ("bbn_narrowband", "bbn_narrowband_engine_python.npz", ["freq_narrowband", "SPL_narrowband"],
     "bbn_narrowband_engine_matlab.mat", ["freq_narrowband", "SPL_narrowband"], None),
    ("bbn_narrowband", "bbn_narrowband_airframe_python.npz", ["freq_narrowband", "SPL_narrowband"],
     "bbn_narrowband_airframe_matlab.mat", ["freq_narrowband", "SPL_narrowband"], None),
    ("specrogram_engine_bbn", "BroadbandSignal_engine_python.npz", ["signal"],
     "BroadbandSignal_engine_matlab.mat", ["BroadbandSignal_engine"], None),
    ("airframe", "airframe_signal_python.npz", ["signal"],
     "auralizedAirframeSignal_MATLAB.mat", ["auralizedAirframeSignal"], None),
    ("engine_signal_auralized", "engine_signal_python.npz", ["signal"],
     "engine_signal_matlab.mat", ["auralizedEngineSignal"], None),
    ("spectrogram_overall_signal", "overall_signal_python.npz", ["signal"],
     "overall_signal_matlab.mat", ["auralizedOverallSignal"], None),
    ("propagation", "propagation_python.npz",
     ["time", "freq", "thetaReflectedRay", "propDistanceReflectedRay", "propagation_time",
      "launchAngle_direct", "launchAngle_reflected", "spherical_direct", "spherical_reflected",
      "spherical_reflected_smooth", "overhead_idx", "tf_overhead_individual", "tf_overhead_combined"],
     "propagation_matlab.mat",
     ["time", "freq", "thetaReflectedRay", "propDistanceReflectedRay", "propagation_time",
      "launchAngle_direct", "launchAngle_reflected", "spherical_direct", "spherical_reflected",
      "spherical_reflected_smooth", "overhead_idx", "tf_overhead_individual", "tf_overhead_combined"], None),
    ("apply_propagation", "apply_propagation_python.npz", ["ir", "output_signal"],
     "apply_propagation_matlab.mat", ["ir", "output_signal"], None),
    ("fir_transfer_function", "fir_transfer_function_{fir}_python.npz", ["mag_fir", "mag_art"],
     "fir_transfer_function_{fir}_matlab.mat", ["mag_fir", "mag_art"], None),
    ("binaural", "binaural_python.npz",
     ["hrir_direct_left", "hrir_direct_right", "output_binaural_left", "output_binaural_right"],
     "binaural_matlab.mat",
     ["hrir_direct_left", "hrir_direct_right", "output_binaural_left", "output_binaural_right"], binaural_on),
    ("wav_output", "wav_output_python.npz", ["output_signal", "attenuation_db"],
     "wav_output_matlab.mat", ["outputSignal", "AttenuationdB"], None),
]

# Extra keys only needed for binaural + ground reflection
_BINAURAL_REFLECTED_EXTRA = ("binaural", "binaural_python.npz", ["hrir_reflected_left", "hrir_reflected_right"],
                             "binaural_matlab.mat", ["hrir_reflected_left", "hrir_reflected_right"])


def required_entries(ini):
    """Return a list of dicts {step, py_file, py_keys, mat_file, mat_keys} for a scenario ini dict."""
    out = []
    for step, py_file, py_keys, mat_file, mat_keys, when in _STEPS:
        if when is not None and not when(ini):
            continue
        fmt = {"fir": fir_tag(ini)}
        entry = dict(step=step, py_file=py_file.format(**fmt), py_keys=list(py_keys),
                     mat_file=mat_file.format(**fmt), mat_keys=list(mat_keys))
        if step == "bbn_narrowband" and _f(ini, "smoothings_emission_based") > 0:
            entry["py_keys"].append("SPL_narrowband_smoothed")
            entry["mat_keys"].append("SPL_narrowband_smoothed")
        if step == "binaural" and reflection_on(ini):
            entry["py_keys"] += _BINAURAL_REFLECTED_EXTRA[2]
            entry["mat_keys"] += _BINAURAL_REFLECTED_EXTRA[4]
        out.append(entry)
    return out
