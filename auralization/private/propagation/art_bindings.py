# auralization/private/propagation/art_bindings.py
from __future__ import annotations
from dataclasses import dataclass
import numpy as np


@dataclass
class Eigenray:
    t: np.ndarray                  # (M,) seconds
    r: np.ndarray                  # (M,3) meters
    phi_deg: float                 # ART convention
    theta_deg: float               # ART convention
    alpha_deg: float               # launch angle used in MATLAB comparisons
    spreading_loss: float          # scalar gain at receiver
    num_reflections: int           # 0 direct, 1 first-order
    receiver_sphere_hit: bool = True


def find_eigenrays(atmosphere_json: str,
                   source_xyz: np.ndarray,
                   receiver_xyz: np.ndarray,
                   settings: dict) -> list[Eigenray]:
    """
    TO BE REPLACED with a real binding call (pybind11 / ctypes).
    Must return [direct_ray, reflected_ray] (2 rays).
    """
    raise NotImplementedError(
        "find_eigenrays() is not implemented yet. "
        "Next step is to bind the C++ ART engine and return Eigenray objects."
    )
