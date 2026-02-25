# auralization/private/propagation/ground_reflection.py
import numpy as np

try:
    from scipy.special import wofz as faddeeva_w
except Exception as e:
    faddeeva_w = None


def get_ground_reflection_coefficient(freq_hz: np.ndarray,
                                  sigma_e: float,
                                  theta_rad: float,
                                  r2_m: float,
                                  sound_speed: float) -> np.ndarray:
    """
    Direct port of MATLAB get_ground_reflection_coefficient(freq, sigma_e, theta, r2, soundSpeed).

    Parameters
    ----------
    freq_hz : array_like
        Frequency vector [Hz], shape (nFreq,) or (nFreq,1)
    sigma_e : float
        Effective flow resistance (same units you use in MATLAB; we do not reinterpret)
    theta_rad : float
        Angle between ground plane and reflected path [rad]
    r2_m : float
        Total propagation distance of reflected ray [m]
    sound_speed : float
        Sound speed [m/s]

    Returns
    -------
    Q : np.ndarray (complex), shape (nFreq,)
        Frequency-dependent ground reflection coefficient
    """
    f = np.asarray(freq_hz, dtype=float).reshape(-1)

    # MATLAB: model = 'miki'
    Zn = _ground_impedance_normalized(f, sigma_e, model="miki")  # complex

    # Zn( isnan )=0 ; Zn( isinf )=0
    Zn = np.where(np.isfinite(Zn), Zn, 0.0 + 0.0j)

    # Rp = ( Zn*sin(theta) - 1 ) / ( Zn*sin(theta) + 1 )
    sin_theta = np.sin(theta_rad)
    Rp = (Zn * sin_theta - 1.0) / (Zn * sin_theta + 1.0)

    # mu = (1+1j)/2 * sqrt((2*pi*f*r2)/c) * ( sin(theta) + 1/Zn )
    # (Pieren eq 3.31)
    mu = (1.0 + 1.0j) / 2.0 * np.sqrt((2.0 * np.pi * f * r2_m) / sound_speed) * (sin_theta + 1.0 / Zn)
    mu = np.where(np.isfinite(mu), mu, 0.0 + 0.0j)

    # F = 1 + 1j * mu * sqrt(pi) * Faddeeva_w(mu)
    if faddeeva_w is None:
        raise ImportError(
            "scipy is required for the Faddeeva w-function (scipy.special.wofz). "
            "Install scipy or ask me for a pure-Python fallback."
        )

    F = 1.0 + 1.0j * mu * np.sqrt(np.pi) * faddeeva_w(mu)
    F = np.where(np.isfinite(F), F, 0.0 + 0.0j)

    # Q = Rp + (1 - Rp)*F
    Q = Rp + (1.0 - Rp) * F
    return Q


def _ground_impedance_normalized(freq_hz: np.ndarray, sigma_e: float, model: str = "miki") -> np.ndarray:
    """
    MATLAB get_ground_impedance(freq, sigma_e, model).
    Returns Zn normalized by rho*c (dimensionless complex).
    """
    f = np.asarray(freq_hz, dtype=float).reshape(-1)

    if model == "Delany_Bazley":
        a, b, c, d = 0.0497, -0.754, 0.0758, -0.732
    elif model == "miki":
        a, b, c, d = 0.07, -0.632, 0.107, -0.632
    else:
        raise ValueError(f"Unsupported ground impedance model: {model}")

    # MATLAB: X = (freq ./ sigma_e);
    X = f / float(sigma_e)

    # Zn = 1 + (a*X^b) - 1j*(c*X^d)
    Zn = 1.0 + (a * (X ** b)) - 1.0j * (c * (X ** d))
    return Zn.astype(np.complex128)
