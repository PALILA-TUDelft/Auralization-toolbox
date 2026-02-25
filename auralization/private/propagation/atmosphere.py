# auralization/private/propagation/atmosphere.py
from __future__ import annotations
from dataclasses import dataclass
import numpy as np


import numpy as np

class StratifiedAtmospherePy:
    """
    Minimal Python equivalent of the MATLAB StratifiedAtmosphere for propagation.
    Supports the profiles actually used in get_propagation.m:
      - temperatureProfile: 'constant' or 'isa'
      - humidityProfile: 'constant'
      - windProfile is NOT needed for the TF model (only for eigenray tracing in C++).
    """

    def __init__(self, cfg=None):
        # Defaults (MATLAB-like)
        self.temperatureProfile = "isa"     # 'constant' or 'isa'
        self.humidityProfile = "constant"   # only constant implemented here
        self.windProfile = "zero"           # placeholder for later; not used in TF

        self.constTemperature = 293.15      # K
        self.constStaticPressure = 101325.0 # Pa
        self.constRelHumidity = 50.0        # %

        # Optional config injection
        if cfg is not None:
            # temperature profile
            if hasattr(cfg, "temperature_profile"):
                self.temperatureProfile = str(cfg.temperature_profile).lower()

            # convert Celsius -> Kelvin
            if hasattr(cfg, "temperature_celsius"):
                self.constTemperature = float(cfg.temperature_celsius) + 273.15

            if hasattr(cfg, "const_static_pressure"):
                self.constStaticPressure = float(cfg.const_static_pressure)

            if hasattr(cfg, "rel_humidity_percent"):
                self.constRelHumidity = float(cfg.rel_humidity_percent)

    # --- Thermodynamics / profiles ---
    def T(self, altitude_m: float) -> float:
        """Temperature [K]"""
        z = float(altitude_m)
        if self.temperatureProfile == "constant":
            return float(self.constTemperature)
        if self.temperatureProfile == "isa":
            # MATLAB T_ISA: 288.15 - 0.0065*z for z>0
            T0 = 288.15
            return float(T0 - 0.0065 * z) if z > 0 else float(T0)
        raise ValueError(f"Unsupported temperatureProfile: {self.temperatureProfile}")

    def staticPressure(self, altitude_m: float) -> float:
        """Static pressure [Pa]"""
        z = float(altitude_m)
        if self.temperatureProfile == "constant":
            return float(self.constStaticPressure)
        if self.temperatureProfile == "isa":
            # MATLAB p0_ISA:
            # p0 = 101325*(1 - 0.0065*z/T0)^5.2561 for z>0
            p0 = 101325.0
            if z > 0:
                T0 = 288.15
                return float(p0 * (1.0 - 0.0065 * z / T0) ** 5.2561)
            return float(p0)
        raise ValueError(f"Unsupported temperatureProfile: {self.temperatureProfile}")

    def humidity(self, altitude_m: float) -> float:
        """Relative humidity [%]"""
        if self.humidityProfile == "constant":
            return float(self.constRelHumidity)
        raise ValueError(f"Unsupported humidityProfile: {self.humidityProfile}")

    def attenuation(self, altitude_m: float, f_hz: np.ndarray) -> np.ndarray:
        """Attenuation coefficient [dB/m] at altitude and frequencies"""
        return air_attenuation_iso_9613_1(self, altitude_m, f_hz)


def air_attenuation_iso_9613_1(atmos: StratifiedAtmospherePy, altitude_m: float, f_hz: np.ndarray) -> np.ndarray:
    """
    Direct port of MATLAB airAttenuationISO(atmos, altitude, f).
    Output: alpha [dB/m] with same shape as f_hz.
    """
    f = np.asarray(f_hz, dtype=float)

    T = atmos.T(altitude_m)
    hr = atmos.humidity(altitude_m)         # [%]
    pa = atmos.staticPressure(altitude_m)   # [Pa]

    pr = 101325.0
    T0 = 293.15
    T01 = 273.16

    # psat = pr * 10^(-6.8346 * (T01 / T)^1.261 + 4.6151);
    psat = pr * 10.0 ** (-6.8346 * (T01 / T) ** 1.261 + 4.6151)

    # h = hr * (psat / pa);
    h = hr * (psat / pa)

    frO = _f_relax_o(pa, pr, h)
    frN = _f_relax_n(pa, pr, h, T, T0)

    alpha = _attenuation_coeff(f, pa, pr, T, T0, frN, frO)  # [dB/m]
    return alpha


def _f_relax_o(pa: float, pr: float, h: float) -> float:
    # frO = pa/pr*( 24 + 4.04*(10^4)*h * (0.02+h)/(0.391+h) );
    return (pa / pr) * (24.0 + 4.04e4 * h * (0.02 + h) / (0.391 + h))


def _f_relax_n(pa: float, pr: float, h: float, T: float, T0: float) -> float:
    # frN = pa/pr*(T/T0)^(-1/2) * ( 9 + 280*h*exp( -4.17*((T/T0)^(-1/3) - 1) ) );
    return (pa / pr) * (T / T0) ** (-0.5) * (9.0 + 280.0 * h * np.exp(-4.17 * ((T / T0) ** (-1.0 / 3.0) - 1.0)))


def _attenuation_coeff(f: np.ndarray, pa: float, pr: float, T: float, T0: float, frN: float, frO: float) -> np.ndarray:
    # A = 8.686*f^2 * ( 1.84e-11*pr/pa*(T/T0)^(1/2) + (T/T0)^(-5/2) * (
    #      0.01275*exp(-2239.1/T)/(frO + f^2/frO) + 0.1068*exp(-3352/T)/(frN + f^2/frN) ) )
    term1 = 1.84e-11 * (pr / pa) * (T / T0) ** 0.5
    term2 = (T / T0) ** (-2.5)
    termO = 0.01275 * np.exp(-2239.1 / T) / (frO + (f * f) / frO)
    termN = 0.1068 * np.exp(-3352.0 / T) / (frN + (f * f) / frN)
    return 8.686 * (f * f) * (term1 + term2 * (termO + termN))

@dataclass
class AtmosphereConfig:
    temperature_profile: str
    temperature_celsius: float
    const_static_pressure: float
    rel_humidity_percent: float
