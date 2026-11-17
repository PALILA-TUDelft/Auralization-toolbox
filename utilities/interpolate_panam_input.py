#utilities/interpolate_panam_input.py

import numbers
import numpy as np

# Tone tables list (frequency, level) rows; a frequency of 0 marks a tone that is absent at that time step
TONAL_FIELDS = {"fan_harmonics", "engine_buzzsaw"}


def _midpoint(entry_a, entry_b):
    """Average two consecutive PANAM samples field by field (levels are averaged in dB)."""
    midpoint = {}
    for key, value_a in entry_a.items():
        value_b = entry_b[key]
        if (isinstance(value_a, np.ndarray) and isinstance(value_b, np.ndarray)
                and value_a.shape == value_b.shape and np.issubdtype(value_a.dtype, np.number)):
            value = 0.5 * (value_a + value_b)
            if key in TONAL_FIELDS and value_a.ndim == 2:
                # Averaging with an absent tone would invent a tone at half its frequency
                absent = (value_a[:, 0] == 0) | (value_b[:, 0] == 0)
                value[absent] = value_a[absent]
            midpoint[key] = value
        elif (isinstance(value_a, numbers.Number) and isinstance(value_b, numbers.Number)
              and not isinstance(value_a, bool)):
            midpoint[key] = 0.5 * (value_a + value_b)
        else:
            midpoint[key] = value_a
    return midpoint


def interpolate_panam_input(source_data, flight_profile):
    """
    Insert one interpolated sample halfway between each pair of consecutive PANAM samples.

    Args:
        source_data (list of dict): Trimmed PANAM data for one observer (N samples).
        flight_profile (dict): Trimmed flight profile with N-element trajectories.

    Returns:
        tuple: (source_data, flight_profile), each with 2*N - 1 samples.
    """
    n_samples = len(source_data)

    source_data_interpolated = [source_data[0]]
    for entry_a, entry_b in zip(source_data[:-1], source_data[1:]):
        source_data_interpolated += [_midpoint(entry_a, entry_b), entry_b]

    index = np.arange(n_samples)
    index_interpolated = np.arange(2 * n_samples - 1) / 2
    flight_profile_interpolated = {
        key: np.interp(index_interpolated, index, np.asarray(value, dtype=float))
        if np.ndim(value) == 1 and len(value) == n_samples else value
        for key, value in flight_profile.items()
    }

    return source_data_interpolated, flight_profile_interpolated
