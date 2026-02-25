# auralization/private/propagation/tf_model.py
from __future__ import annotations
import numpy as np
import numpy as np


def transfer_function_from_eigenrays(atmos,
                                     eigenrays,
                                     freq_hz: np.ndarray,
                                     ground_reflection_factor: np.ndarray) -> dict:
    """
    Python equivalent of MATLAB AtmosphericPropagation.TransferFunction(eigenrays).

    Parameters
    ----------
    atmos : StratifiedAtmospherePy-like
        Must provide attenuation(z, f)->dB/m
    eigenrays : list
        List of eigenray objects (from C++ binding later), each must provide:
          - numPoints (int)
          - r_cart: np.ndarray shape (nPoints,3)
          - r_z: np.ndarray shape (nPoints,)
          - t: np.ndarray shape (nPoints,)
          - numReflections (int)
          - spreadingLoss (float)
    freq_hz : np.ndarray
        Frequency vector [Hz], shape (nFreq,)
    ground_reflection_factor : np.ndarray
        Complex reflection factor R(f) used for the ground reflection.
        In MATLAB this is propagationModel.groundReflectionFactor.
        Can be scalar or (nFreq,) complex.

    Returns
    -------
    dict with:
      - 'freq_hz'
      - 'individual_tf' : (nFreq, nRays) complex
      - 'combined_tf'   : (nFreq,) complex
      - 'spreading_loss': (nRays,) float
      - 'delay_s'       : (nRays,) float
    """
    f = np.asarray(freq_hz, dtype=float).reshape(-1)
    nFreq = f.size
    nRays = len(eigenrays)

    # Normalize ground_reflection_factor to (nFreq,)
    GR = np.asarray(ground_reflection_factor)
    if GR.size == 1:
        GR = np.full((nFreq,), complex(GR.item()), dtype=np.complex128)
    else:
        GR = GR.reshape(-1).astype(np.complex128)
        if GR.size != nFreq:
            raise ValueError("ground_reflection_factor must be scalar or same length as freq_hz")

    spreading = np.ones((nRays,), dtype=float)
    delay = np.zeros((nRays,), dtype=float)

    # alphaDB integral results are turned into a factor: 10^(-alphaDB/20)
    alpha_factor = np.ones((nFreq, nRays), dtype=float)

    # TotalReflectionFactor: GR ** numReflections
    refl_factor = np.ones((nFreq, nRays), dtype=np.complex128)

    for j, ray in enumerate(eigenrays):
        if ray.numPoints == 0:
            spreading[j] = 1.0
            delay[j] = 0.0
            continue

        spreading[j] = float(ray.spreadingLoss)
        delay[j] = float(ray.t[-1])

        # integrate attenuation coefficient (dB/m) along path segments
        r = ray.r_cart
        z = np.abs(ray.r_z)

        dr = np.linalg.norm(np.diff(r, axis=0), axis=1)  # (nPoints-1,)
        alpha_db = np.zeros((nFreq,), dtype=float)
        for k in range(ray.numPoints - 1):
            alpha_db += atmos.attenuation(z[k], f) * dr[k]  # (nFreq,)
        alpha_factor[:, j] = 10.0 ** (-alpha_db / 20.0)  # MATLAB: 10.^(-alphaDB/20)

        refl_factor[:, j] = GR ** int(ray.numReflections)

    # PropagationDelayFilter: exp(1j*2*pi*delay*f)
    linear_phase = np.exp(1j * 2.0 * np.pi * f[:, None] * delay[None, :])  # (nFreq,nRays)

    # spreading loss is scalar per ray, broadcast
    spreading_mat = spreading[None, :]

    individual_tf = alpha_factor * linear_phase * refl_factor * spreading_mat  # (nFreq,nRays) complex
    combined_tf = np.sum(individual_tf, axis=1)  # (nFreq,)

    return {
        "freq_hz": f,
        "individual_tf": individual_tf.astype(np.complex128),
        "combined_tf": combined_tf.astype(np.complex128),
        "spreading_loss": spreading,
        "delay_s": delay,
    }

def compute_tf_stack(atmos, rays, freq_hz, reflection_factor):
    return transfer_function_from_eigenrays(
        atmos=atmos,
        eigenrays=rays,
        freq_hz=freq_hz,
        ground_reflection_factor=reflection_factor
    )
