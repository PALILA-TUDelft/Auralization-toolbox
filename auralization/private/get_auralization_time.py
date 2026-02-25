# auralization/private/get_auralization_time.py
import numpy as np
import globals


def get_auralization_time(data, input_type):
    """
    Computes time vectors required for auralization:
    - time_PANAM_retarded: normalized cumulative time (retarded or source)
    - time_PANAM_auralization: evenly spaced time grid matching PANAM time resolution
    - time: time vector based on sampling frequency fs

    Args:
        data (list of dict): PANAM data for one observer.
        input_type (str): 'emission' or 'immission'

    Returns:
        tuple of np.ndarray: (time_PANAM_retarded, time_PANAM_auralization, time)
    """
    # Extract time vector from data
    if input_type == 'immission':
        time_PANAM = [entry['retarded_time'] for entry in data]
    elif input_type == 'emission':
        time_PANAM = [entry['source_time'] for entry in data]
    else:
        raise ValueError(f"Unsupported input_type: {input_type}")

    # Compute dt vector and cumulative time (retarded)
    dt_panam_retarded = [0]  # first element is zero
    for i in range(1, len(time_PANAM)):
        dt_panam_retarded.append(time_PANAM[i] - time_PANAM[i - 1])
    time_PANAM_retarded = np.cumsum(dt_panam_retarded)

    # Uniformly spaced time vector for auralization (same length, constant step)
    time_PANAM_auralization = np.arange(
        0,
        len(time_PANAM_retarded) * globals.dt_panam,
        globals.dt_panam
    )

    # Time vector for synthesized signal (based on sampling rate fs)
    dt = 1 / globals.fs
    time = np.arange(
        time_PANAM_auralization[0],
        time_PANAM_auralization[-1] + dt,
        dt
    )

    # Ensure even number of samples
    if len(time) % 2 != 0:
        time = np.append(time, time[-1] + dt)

    return time_PANAM_retarded, time_PANAM_auralization, time