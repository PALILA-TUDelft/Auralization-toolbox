# auralization/private/propagation/angles.py
from __future__ import annotations
import numpy as np

def fabian_angles_from_eigenrays(eigenrays_direct, eigenrays_reflected, receiver_xyz, reflected_reflection_point_xyz=None):
    """
    Convert ART spherical angles to FABIAN receiver-based convention

    Parameters
    ----------
    eigenrays_direct : list
        Each element must provide .phi (deg) and .theta (deg) for direct ray.
    eigenrays_reflected : list
        Each element must provide .phi (deg) for reflected ray and access to reflection point
        if reflected_reflection_point_xyz is not provided.
    receiver_xyz : array_like shape (3,)
    reflected_reflection_point_xyz : list[np.ndarray] or None
        If provided, each element is the (3,) xyz reflection point for the reflected ray
        used to compute thetaReflected (receiver-side elevation).

    Returns
    -------
    dict:
      - direct_path: (N,2) [phi,theta] in FABIAN convention
      - reflected_path: (N,2) [phi,theta] in FABIAN convention (unsmoothed)
    """
    receiver = np.asarray(receiver_xyz, dtype=float).reshape(3)
    N = len(eigenrays_direct)

    direct = np.zeros((N, 2), dtype=float)
    refl = np.zeros((N, 2), dtype=float)

    for i in range(N):
        # Direct: if phi>=180 -> phi-180 else phi+180; thetaFab = theta-90
        phi_d = float(eigenrays_direct[i].phi)
        theta_d = float(eigenrays_direct[i].theta)
        if phi_d >= 180.0:
            direct[i, :] = [phi_d - 180.0, theta_d - 90.0]
        else:
            direct[i, :] = [phi_d + 180.0, theta_d - 90.0]

        # Reflected azimuth same wrap rule, elevation computed from receiver/reflection point geometry
        phi_r = float(eigenrays_reflected[i].phi)

        if reflected_reflection_point_xyz is None:
            raise ValueError("Provide reflected_reflection_point_xyz for reflected elevation calculation.")
        refl_pt = np.asarray(reflected_reflection_point_xyz[i], dtype=float).reshape(3)

        hyp = np.linalg.norm(receiver - refl_pt)
        # MATLAB: thetaReflected = rad2deg(asin(receiver(3)/hyp))
        theta_reflected_deg = np.degrees(np.arcsin(receiver[2] / hyp)) if hyp > 0 else 0.0

        if phi_r >= 180.0:
            refl[i, :] = [phi_r - 180.0, -theta_reflected_deg]
        else:
            refl[i, :] = [phi_r + 180.0, -theta_reflected_deg]

    return {"direct_path": direct, "reflected_path": refl}

def moving_average(x: np.ndarray, window: int = 10) -> np.ndarray:
    """
    Applies along axis 0.
    """
    if window <= 1:
        return x.copy()
    if x.shape[0] < window:
        return x.copy()

    kernel = np.ones(window, dtype=float) / float(window)
    out = np.zeros_like(x, dtype=float)
    for col in range(x.shape[1]):
        out[:, col] = np.convolve(x[:, col], kernel, mode="same")
    return out
