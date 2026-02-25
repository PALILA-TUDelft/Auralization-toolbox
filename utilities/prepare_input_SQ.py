#utilities/prepare_input_SQ.py

import numpy as np
from utilities.trim_data_time_distance_based import trim_data_time_distance_based

def prepare_input_SQ(source_data, spectrogram, spectrogram_dBA, flight_profile, trim_time, tag=""):
    """
    Trims repeated timestamps and restricts data to a centered time window around min distance.

    Args:
        source_data (list of dict): Single observer time-series data (one column of PANAM output).
        spectrogram (dict): Spectrogram data from PANAM (e.g., overall, engine, etc.)
        spectrogram_dBA (dict): Same as above, A-weighted.
        flight_profile (dict): Flight profile from get_flight_profile().
        trim_time (float): Time in seconds to trim before and after.
        tag (str): Optional tag for output.

    Returns:
        source_data_trimmed, spectrogram_trimmed, spectrogram_dBA_trimmed, flight_profile_trimmed
    """
    time_vector = [d["source_time"] for d in source_data]
    _, unique_indices = np.unique(time_vector, return_index=True)
    unique_indices = sorted(unique_indices)

    # Remove duplicated time steps
    source_data_unique = [source_data[i] for i in unique_indices]

    def trim_dict_fields(d, indices, fields):
        result = {}
        for k, v in d.items():
            if k in fields:
                v = np.array(v)
                if v.ndim == 2:
                    result[k] = v[:, indices]
                elif v.ndim == 1:
                    result[k] = v[indices]
                else:
                    raise ValueError(f"Unexpected shape for field '{k}': {v.shape}")
            else:
                result[k] = v
        return result


    idx_lower, idx_upper = trim_data_time_distance_based(source_data_unique, trim_time, flight_profile, tag)
    time_slice = slice(idx_lower, idx_upper + 1)

    # Trim source_data
    source_data_trimmed = source_data_unique[idx_lower:idx_upper + 1]
    print(f"[DEBUG] Trimmed source_data length: {len(source_data_trimmed)}")


    # Fields to slice on time axis
    spec_fields = [
        "source_time", "retarded_time", "overall", "overall_broadband", "airframe_toc",
        "engine", "engine_without_fan_harmonics", "engine_broadband_toc", "engine_buzzsaw_toc", "fan_harmonics_toc"
    ]
    spec_dba_fields = [
        "source_time", "retarded_time", "overall", "overall_broadband", "airframe",
        "engine", "engine_without_fan_harmonics", "engine_broadband", "engine_buzzsaw", "fan_harmonics"
    ]

    # Trim spectrogram and spectrogram_dBA
    spectrogram_trimmed = trim_dict_fields(spectrogram, time_slice, spec_fields)
    spectrogram_dBA_trimmed = trim_dict_fields(spectrogram_dBA, time_slice, spec_dba_fields)

    # Trim flight profile
    flight_profile_trimmed = {
        k: np.array(v)[unique_indices][time_slice]
        for k, v in flight_profile.items()
    }

    return (
        source_data_trimmed,
        spectrogram_trimmed,
        spectrogram_dBA_trimmed,
        flight_profile_trimmed
    )