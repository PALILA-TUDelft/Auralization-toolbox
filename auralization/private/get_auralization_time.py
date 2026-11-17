# auralization/private/get_auralization_time.py
import numpy as np
import globals


def _colon_length(start, stop, step):
    """Number of elements of MATLAB's start:step:stop, including its tolerance for floating-point
    round-off (np.arange has none and can be off by one element)."""
    n = (stop - start) / step
    tol = 3 * np.finfo(float).eps * max(abs(start), abs(stop)) / abs(step)
    n_round = np.round(n)
    if abs(n - n_round) <= tol:
        n = n_round
    return int(np.floor(n)) + 1


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

    # Uniformly spaced time vector for auralization (same length, constant step).
    # MATLAB: 0:dt_panam:(N*dt_panam)-dt_panam  -> exactly N elements. Built as dt*arange(N) because
    # np.arange(0, N*dt, dt) can return N+1 elements when dt is not exactly representable in binary
    # (e.g. dt = 0.1, 0.2, 0.05), which later breaks the interpolation.
    n_panam = len(time_PANAM_retarded)
    time_PANAM_auralization = globals.dt_panam * np.arange(n_panam)

    # Time vector for synthesized signal (based on sampling rate fs)
    # MATLAB: time = t0:dt:tend, with an even number of samples (one more sample is added if odd).
    dt = 1 / globals.fs
    t0 = time_PANAM_auralization[0]
    n_samples = _colon_length(t0, time_PANAM_auralization[-1], dt)
    if n_samples % 2 != 0:
        n_samples += 1
    time = t0 + dt * np.arange(n_samples)

    return time_PANAM_retarded, time_PANAM_auralization, time