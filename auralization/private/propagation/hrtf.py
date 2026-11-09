# auralization/private/propagation/hrtf.py
#
# Open-source replacement for MATLAB AKhrirInterpolation (AKtools, TU Berlin).
# Supports two FABIAN HRTF formats:
#   .mat — pre-computed complex SH coefficients (from AKtools, fastest, exact match)
#   .sofa — raw measured HRIRs (DOI: 10.14279/depositonce-5718.5, SH decomposition on load)
#
# Both end in the same complex SH expansion, equivalent to the 'measured_sh' mode in
# AKhrirInterpolation: the .mat file ships the coefficients, the .sofa file is decomposed with an
# unweighted least-squares fit in the same basis. The AKtools coefficients are exactly that fit
# (HRIRs from both files agree to ~1e-13, see verification/test_python_port_fixes.py).
# Head-above-torso interpolation across HATO data sets is not implemented (HATO 0 data only).
#
# ATTRIBUTION: the FABIAN HRTF database must be cited in any publication that
# uses the binaural output of this toolbox. See "Third-party data and
# attribution" in the README for the two required references.

import os
import numpy as np
from scipy.io import loadmat


_hrtf_cache: dict = {}


# -----------------------------------------------------------------------
# Complex SH basis (AKtools / Williams convention, used by both the .mat and .sofa paths)
# -----------------------------------------------------------------------
def _sh_indices(order):
    """(n, m) of every SH coefficient, ordered like the AKtools coefficient files (n ascending, m = -n..n)."""
    n_arr = np.concatenate([np.full(2 * n + 1, n) for n in range(order + 1)])
    m_arr = np.concatenate([np.arange(-n, n + 1) for n in range(order + 1)])
    return n_arr, m_arr


def _sh_matrix_complex(n_arr, m_arr, az_deg, el_deg):
    """
    Build the complex SH basis matrix (N_dirs, N_coeffs) in the convention of the FABIAN .mat coefficients.
    Uses associated Legendre functions (lpmv) directly, replacing deprecated sph_harm.
    """
    from scipy.special import lpmv
    from math import factorial

    az_rad = np.radians(np.asarray(az_deg, dtype=float))
    colat_rad = np.pi / 2 - np.radians(np.asarray(el_deg, dtype=float))
    cos_colat = np.cos(colat_rad)

    N_dirs = len(az_rad)
    N_coeffs = len(n_arr)
    Y = np.zeros((N_dirs, N_coeffs), dtype=complex)

    for idx in range(N_coeffs):
        n = int(n_arr[idx])
        m = int(m_arr[idx])
        abs_m = abs(m)

        norm = np.sqrt((2 * n + 1) / (4 * np.pi)
                       * factorial(n - abs_m) / factorial(n + abs_m))
        P = lpmv(abs_m, n, cos_colat)
        sign = 1 if m >= 0 else (-1)**abs_m
        Y[:, idx] = sign * norm * P * np.exp(1j * m * az_rad)

    return Y


# -----------------------------------------------------------------------
# Loaders
# -----------------------------------------------------------------------
def _load_mat(mat_path):
    """Load pre-computed complex SH coefficients from AKtools .mat file."""
    mat = loadmat(mat_path, simplify_cells=False)
    sh = mat['SH'][0, 0]
    n_freq = sh['coeffLeft'].squeeze().shape[1]
    fs = int(mat['SamplingRate'].squeeze())
    n_fft = 2 * (n_freq - 1)

    return {
        "source": "mat",
        "sh_left": sh['coeffLeft'].squeeze(),    # (n_coeffs, n_freq) complex
        "sh_right": sh['coeffRight'].squeeze(),
        "n_arr": sh['n'].squeeze().astype(int),
        "m_arr": sh['m'].squeeze().astype(int),
        "order": int(sh['order'].squeeze()),
        "n_fft": n_fft,
    }


def _load_sofa(sofa_path, sh_order):
    """Load a SOFA file and decompose the HRTFs into complex SH coefficients (same layout as _load_mat)."""
    import sofar
    sofa_obj = sofar.read_sofa(sofa_path)
    ir = sofa_obj.Data_IR                    # (M, 2, n_samples)
    src_pos = sofa_obj.SourcePosition        # (M, 3): [az, el, dist]

    if str(sofa_obj.SourcePosition_Type).lower() != "spherical":
        raise ValueError(f"{sofa_path}: SourcePosition_Type must be 'spherical', got {sofa_obj.SourcePosition_Type!r}")
    n_dirs, _, n_samples = ir.shape
    n_arr, m_arr = _sh_indices(sh_order)
    if n_dirs < len(n_arr):
        raise ValueError(f"SH order {sh_order} needs at least {len(n_arr)} directions, the SOFA file has {n_dirs}")

    hrtf = np.concatenate([np.fft.rfft(ir[:, 0, :], axis=1),
                           np.fft.rfft(ir[:, 1, :], axis=1)], axis=1)       # (M, 2 * n_freq)

    # Unweighted least squares: reproduces the AKtools coefficients of the FABIAN .mat file to ~1e-13
    # (area-weighting the fit does not).
    Y = _sh_matrix_complex(n_arr, m_arr, src_pos[:, 0], src_pos[:, 1])
    coeffs = np.linalg.lstsq(Y, hrtf, rcond=None)[0]
    n_freq = n_samples // 2 + 1

    return {
        "source": "sofa",
        "sh_left": coeffs[:, :n_freq],
        "sh_right": coeffs[:, n_freq:],
        "n_arr": n_arr,
        "m_arr": m_arr,
        "order": sh_order,
        "n_fft": n_samples,
    }


# -----------------------------------------------------------------------
# Main entry point
# -----------------------------------------------------------------------
def hrir_interpolation(azimuth, elevation, head_orientation, hrtf_path, sh_order=35):
    """
    SH-interpolated HRIR from a SOFA or .mat file.

    Equivalent to MATLAB:
        [l_a, r_a] = AKhrirInterpolation(azimuth, elevation, HATO, 'measured_sh')

    Parameters
    ----------
    azimuth : (N,) — azimuth angles in degrees (head_orientation already applied by caller)
    elevation : (N,) — elevation angles in degrees
    head_orientation : float — rotation in degrees added to the azimuth (the whole head rotates; AKtools'
        interpolation between the HATO data sets is not implemented, so callers pass 0)
    hrtf_path : str — path to FABIAN .sofa or .mat file
    sh_order : int — SH order (default 35; ignored for .mat files which embed their own order)

    Returns
    -------
    hrir_left : (n_samples, N) — left ear HRIRs
    hrir_right : (n_samples, N) — right ear HRIRs
    """
    ext = os.path.splitext(hrtf_path)[1].lower()
    cache_key = (hrtf_path, sh_order if ext == ".sofa" else "mat")

    if cache_key not in _hrtf_cache:
        if ext == ".mat":
            print(f"[HRTF] Loading pre-computed SH coefficients from {hrtf_path}...")
            _hrtf_cache[cache_key] = _load_mat(hrtf_path)
        else:
            print(f"[HRTF] Loading SOFA and computing SH coefficients (order {sh_order})...")
            _hrtf_cache[cache_key] = _load_sofa(hrtf_path, sh_order)
        print("[HRTF] Ready.")

    data = _hrtf_cache[cache_key]

    az = np.mod(np.asarray(azimuth, dtype=float) + head_orientation, 360.0)
    el = np.asarray(elevation, dtype=float)

    Y_query = _sh_matrix_complex(data["n_arr"], data["m_arr"], az, el)

    hrtf_left = Y_query @ data["sh_left"]
    hrtf_right = Y_query @ data["sh_right"]

    # MATLAB AKhrirInterpolation: l(end,:) = 0; r(end,:) = 0 (the Nyquist bin is discarded)
    if data["n_fft"] % 2 == 0:
        hrtf_left[:, -1] = 0
        hrtf_right[:, -1] = 0

    hrir_left = np.fft.irfft(hrtf_left, n=data["n_fft"], axis=1).T    # (n_samples, N)
    hrir_right = np.fft.irfft(hrtf_right, n=data["n_fft"], axis=1).T

    # MATLAB (spherical-harmonics domain): if the energy of the first HRIR is mostly in the second half,
    # the HRIRs are flipped in time: sum(abs(l(1:Nsamp/2,1))) < sum(abs(l(Nsamp/2:end,1))) -> flipud
    half = data["n_fft"] // 2
    if np.sum(np.abs(hrir_left[:half, 0])) < np.sum(np.abs(hrir_left[half - 1:, 0])):
        hrir_left = hrir_left[::-1]
        hrir_right = hrir_right[::-1]

    return hrir_left, hrir_right
