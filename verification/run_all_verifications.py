"""
Master verification runner.

Runs every Python-vs-MATLAB comparison in the `verification/` folder
headlessly (no plots, no windows) and prints a PASS/FAIL/SKIP report.

Usage:
    python verification/run_all_verifications.py

A check is SKIPPED if either the Python .npz or the MATLAB .mat file it
needs is missing (or the expected key isn't inside it). Everything else is
graded against the tolerances defined in the check calls below -- tune them
if your setup legitimately differs from these defaults.

Tolerance philosophy:
  - Deterministic vectors (time axes, angles, distances, band edges, HRIR
    lookups, dB(SPL) envelopes before synthesis) are checked with tight
    absolute tolerances, since both implementations should agree almost
    exactly -- there is no randomness upstream of these values.
  - Synthesized audio waveforms (broadband noise, tonal signals, and
    anything built from them: engine/overall signal, propagated output,
    binaural output, the final .wav) use *independent* random phase draws
    in Python and MATLAB. Sample-by-sample comparison is meaningless for
    these, so they are graded on SPL spectrogram Mean-Absolute-Error
    instead (same method the individual compare_*.py scripts already use),
    which is insensitive to phase.
  - Impulse responses / HRIRs (deterministic, no random phase) are graded
    on relative peak error instead of SPL, since they aren't stationary
    signals a spectrogram suits well.

Exit code is 0 if there are no FAILs (SKIPs don't affect it), 1 otherwise.
"""
import os
import sys

import numpy as np

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

try:
    from scipy.io import loadmat
except ImportError:
    loadmat = None

from utilities.plot_utils import myspecgram

def _parse_root():
    """--root <dir>: folder holding the <step>/ sub-folders (default: this folder, legacy layout).
    Use verification/scenarios/<scenario> to grade one scenario."""
    import argparse
    ap = argparse.ArgumentParser(add_help=True)
    ap.add_argument("--root", default=None, help="folder with the <step>/ sub-folders to grade")
    return ap.parse_known_args()[0].root


ROOT = os.path.abspath(_parse_root() or os.path.dirname(__file__))

FS = 48000
PREF = 20e-6
WINDOW_SIZE = 1024
OVERLAP = 0.75

results = []  # list of {"name", "status", "detail"}; status: PASS | FAIL | SKIP (data missing) | N/A (not applicable)


def _load_params():
    """Parsed ini of the scenario being graded (written by main.py --verification); {} for the legacy layout."""
    path = os.path.join(ROOT, "scenario_params_python.json")
    if not os.path.isfile(path):
        return {}
    import json
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


PARAMS = _load_params()


def _param(key, default):
    try:
        return float(PARAMS.get(key, default))
    except (TypeError, ValueError):
        return float(default)


def record(name, status, detail=""):
    results.append({"name": name, "status": status, "detail": detail})


def sq(x):
    return np.asarray(x).squeeze()


def _npz(path, key):
    return sq(np.load(path, allow_pickle=True)[key])


def _mat(path, key):
    return sq(loadmat(path)[key])


def check_files(py_path, mat_path):
    if not os.path.isfile(py_path):
        return f"missing Python file: {os.path.relpath(py_path, ROOT)}"
    if not os.path.isfile(mat_path):
        return f"missing MATLAB file: {os.path.relpath(mat_path, ROOT)}"
    if loadmat is None:
        return "scipy not installed -- cannot read .mat files"
    return None


def load_pair(name, py_path, mat_path, py_key, mat_key):
    err = check_files(py_path, mat_path)
    if err:
        record(name, "SKIP", err)
        return None
    try:
        py_val = _npz(py_path, py_key)
        mat_val = _mat(mat_path, mat_key)
    except KeyError as e:
        record(name, "SKIP", f"missing key {e}")
        return None
    return py_val, mat_val


def _shape_note(py_val, mat_val):
    py_arr = np.asarray(py_val)
    mat_arr = np.asarray(mat_val)
    if py_arr.shape != mat_arr.shape:
        return f"  [length mismatch: Python={py_arr.shape}, MATLAB={mat_arr.shape}, compared overlap only]"
    return ""


def max_abs(py_arr, mat_arr):
    # atleast_2d normalizes a bare 1D vector (e.g. a single surviving tone
    # row that squeezed from (1, N) to (N,)) to the same (rows, cols)
    # convention as a genuine 2D array, so row/col-count mismatches between
    # Python and MATLAB (different number of tones, etc.) are handled by
    # comparing only the overlapping rows/cols instead of raising.
    py_arr = np.atleast_2d(np.asarray(py_arr, dtype=float))
    mat_arr = np.atleast_2d(np.asarray(mat_arr, dtype=float))
    r = min(py_arr.shape[0], mat_arr.shape[0])
    c = min(py_arr.shape[1], mat_arr.shape[1])
    with np.errstate(invalid="ignore"):          # -inf - -inf = nan is expected here and handled below
        diff = np.abs(py_arr[:r, :c] - mat_arr[:r, :c])
    # Some vectors (e.g. bbn_narrowband SPL) legitimately contain -inf for
    # unassigned bins on both sides (matches MATLAB's p2spl with no epsilon).
    # -inf - -inf = nan, which would silently corrupt max(); compare only
    # where both sides are finite instead.
    finite = np.isfinite(diff)
    if not np.any(finite):
        return 0.0
    return float(np.max(diff[finite]))


def oaspl(sig):
    sig = np.asarray(sig, dtype=float).ravel()
    return 20 * np.log10(np.sqrt(np.mean(sig ** 2)) / PREF + 1e-30)


def avg_power_spectrum(sig, nfft=4800):
    """Block-averaged (Hann) power spectrum — phase-insensitive."""
    sig = np.asarray(sig, dtype=float).ravel()
    nblocks = len(sig) // nfft
    if nblocks == 0:
        return None
    win = np.hanning(nfft)
    wcorr = np.mean(win ** 2)
    P = np.zeros(nfft // 2 + 1)
    for b in range(nblocks):
        seg = sig[b * nfft:(b + 1) * nfft] * win
        P += np.abs(np.fft.rfft(seg)) ** 2
    return P / (nblocks * nfft * wcorr)


def level_metrics(py_sig, mat_sig):
    """Return (dOASPL, spectrum_offset_dB) — both phase-insensitive.

    Random-phase synthesized signals cannot be compared sample-by-sample,
    so we compare overall level (OASPL) and the mean in-band offset of the
    time-averaged power spectrum. Correct signals agree to <0.1 dB on both.
    """
    py_sig = np.asarray(py_sig, dtype=float).ravel()
    mat_sig = np.asarray(mat_sig, dtype=float).ravel()
    n = min(len(py_sig), len(mat_sig))
    py_sig, mat_sig = py_sig[:n], mat_sig[:n]
    d_oaspl = oaspl(py_sig) - oaspl(mat_sig)
    Ppy = avg_power_spectrum(py_sig)
    Pmat = avg_power_spectrum(mat_sig)
    if Ppy is None or Pmat is None:
        return d_oaspl, 0.0
    sp_py = 10 * np.log10(Ppy + 1e-30)
    sp_mat = 10 * np.log10(Pmat + 1e-30)
    mask = Pmat > np.max(Pmat) * 1e-4  # in-band, above noise floor
    spec_off = float(np.mean(sp_py[mask] - sp_mat[mask])) if np.any(mask) else 0.0
    return float(d_oaspl), spec_off


# --------------------------------------------------------------------- #
# check_* helpers -- each records exactly one PASS/FAIL/SKIP row
# --------------------------------------------------------------------- #
def check_max_abs(name, py_path, mat_path, py_key, mat_key, threshold, unit=""):
    pair = load_pair(name, py_path, mat_path, py_key, mat_key)
    if pair is None:
        return
    py_val, mat_val = pair
    m = max_abs(py_val, mat_val)
    status = "PASS" if m <= threshold else "FAIL"
    record(name, status, f"max|delta| = {m:.4g} {unit} (threshold {threshold:.4g} {unit})" + _shape_note(py_val, mat_val))


def check_spl_floored(name, py_path, mat_path, py_key, mat_key, threshold, floor_db=-60.0):
    """Max |delta| of two dB spectra where empty bins (-inf) are clamped to floor_db instead of being ignored,
    so a bin that is empty on one side only counts as a large error."""
    pair = load_pair(name, py_path, mat_path, py_key, mat_key)
    if pair is None:
        return
    py_arr = np.nan_to_num(np.asarray(pair[0], dtype=float).ravel(), nan=floor_db, neginf=floor_db)
    ml_arr = np.nan_to_num(np.asarray(pair[1], dtype=float).ravel(), nan=floor_db, neginf=floor_db)
    if py_arr.shape != ml_arr.shape:
        record(name, "FAIL", f"length mismatch: Python={py_arr.shape}, MATLAB={ml_arr.shape}")
        return
    py_arr, ml_arr = np.maximum(py_arr, floor_db), np.maximum(ml_arr, floor_db)
    d = np.abs(py_arr - ml_arr)
    m = float(np.max(d))
    status = "PASS" if m <= threshold else "FAIL"
    record(name, status, f"max|delta| = {m:.4g} dB over {d.size} bins, {int(np.sum(d > threshold))} above threshold "
                         f"{threshold:.4g} dB (empty bins clamped to {floor_db:g} dB)")


def check_db_magnitude(name, py_path, mat_path, py_key, mat_key, threshold_db, floor_db=-60.0, pct=99):
    """Compare two already-in-dB magnitude arrays (e.g. 10*log10(|X|^2)),
    ignoring bins where the reference is deep in the numerical noise floor.

    Near a spectral null the true linear magnitude is ~0, so tiny floating
    point differences (or differing epsilon conventions between Python and
    MATLAB) blow up into huge, meaningless dB deltas even though both sides
    agree the bin is silent. `floor_db` (relative to the reference's peak)
    excludes those bins; `pct` grades on a percentile instead of the strict
    max so a handful of remaining edge bins near the floor don't dominate.
    """
    pair = load_pair(name, py_path, mat_path, py_key, mat_key)
    if pair is None:
        return
    py_val, mat_val = np.asarray(pair[0], dtype=float).ravel(), np.asarray(pair[1], dtype=float).ravel()
    n = min(len(py_val), len(mat_val))
    py_val, mat_val = py_val[:n], mat_val[:n]
    in_band = mat_val > (np.max(mat_val) + floor_db)
    if not np.any(in_band):
        record(name, "SKIP", "no bins above the noise-floor threshold")
        return
    diff = np.abs(py_val[in_band] - mat_val[in_band])
    m = float(np.percentile(diff, pct))
    status = "PASS" if m <= threshold_db else "FAIL"
    record(name, status,
           f"p{pct:g}|delta| = {m:.3f} dB over in-band bins (threshold {threshold_db:.1f} dB, "
           f"{in_band.sum()}/{n} bins > peak{floor_db:+.0f} dB)" + _shape_note(py_val, mat_val))


def check_columns_max_abs(name, py_path, mat_path, py_key, mat_key, labels, threshold, unit="", pct=100):
    """Per-column error check. `pct` selects the error percentile to grade on
    (100 = strict max). Use pct<100 to tolerate a handful of isolated
    single-sample geometry glitches (e.g. one reflection point landing on a
    different ray sample) while still catching systematic drift."""
    pair = load_pair(name, py_path, mat_path, py_key, mat_key)
    if pair is None:
        return
    py_val, mat_val = pair
    n = min(py_val.shape[0], mat_val.shape[0])
    parts, worst = [], 0.0
    for i, label in enumerate(labels):
        err = np.abs(py_val[:n, i] - mat_val[:n, i])
        d = float(np.percentile(err, pct))
        worst = max(worst, d)
        extra = f" (max {float(np.max(err)):.3g})" if pct < 100 else ""
        parts.append(f"{label}: {d:.3g}{extra}")
    metric = "max" if pct >= 100 else f"p{pct:g}"
    status = "PASS" if worst <= threshold else "FAIL"
    record(name, status, f"[{metric}] " + ", ".join(parts) + f" {unit} (threshold {threshold:.3g} {unit})" + _shape_note(py_val, mat_val))


def check_ir_magnitude(name, py_path, mat_path, py_key, mat_key, threshold_db):
    """Compare per-block FIR magnitude response in dB (phase-insensitive).

    FIR filters are deterministic, but Python and MATLAB reconstruct them
    with different phase conventions (causal-shift heuristic vs min/linear
    phase). Only the magnitude response affects the filtering, so we grade
    on |FFT(ir)| per block, not the raw time-domain samples.
    """
    pair = load_pair(name, py_path, mat_path, py_key, mat_key)
    if pair is None:
        return
    py_val, mat_val = np.atleast_2d(pair[0]), np.atleast_2d(pair[1])
    r = min(py_val.shape[0], mat_val.shape[0])
    c = min(py_val.shape[1], mat_val.shape[1])
    worst = 0.0
    for j in range(c):
        A = 20 * np.log10(np.abs(np.fft.rfft(py_val[:r, j])) + 1e-30)
        B = 20 * np.log10(np.abs(np.fft.rfft(mat_val[:r, j])) + 1e-30)
        # restrict to bins with real energy (ignore deep nulls in dB)
        ref = np.abs(np.fft.rfft(mat_val[:r, j]))
        mask = ref > np.max(ref) * 1e-3
        if np.any(mask):
            worst = max(worst, float(np.mean(np.abs(A[mask] - B[mask]))))
    status = "PASS" if worst <= threshold_db else "FAIL"
    record(name, status, f"max mean|delta dB| across blocks = {worst:.3f} dB (threshold {threshold_db:.1f} dB)")


def check_relative(name, py_path, mat_path, py_key, mat_key, threshold_pct):
    pair = load_pair(name, py_path, mat_path, py_key, mat_key)
    if pair is None:
        return
    py_val, mat_val = pair
    m = max_abs(py_val, mat_val)
    denom = max(float(np.max(np.abs(np.asarray(mat_val, dtype=float)))), 1e-12)
    rel = m / denom
    status = "PASS" if rel <= threshold_pct / 100.0 else "FAIL"
    record(name, status, f"max|delta|/max|ref| = {rel:.2%} (threshold {threshold_pct:.0f}%)" + _shape_note(py_val, mat_val))


def check_spl_mae(name, py_path, mat_path, py_key, mat_key, threshold_db):
    """Phase-insensitive level check for random-phase synthesized signals.

    Compares OASPL and the mean in-band offset of the time-averaged power
    spectrum. `threshold_db` bounds both. (Named check_spl_mae for call-site
    compatibility, but no longer uses per-bin spectrogram MAE, which is
    dominated by random-phase scatter and near-silent bins.)
    """
    pair = load_pair(name, py_path, mat_path, py_key, mat_key)
    if pair is None:
        return
    py_val, mat_val = pair
    d_oaspl, spec_off = level_metrics(py_val, mat_val)
    worst = max(abs(d_oaspl), abs(spec_off))
    status = "PASS" if worst <= threshold_db else "FAIL"
    record(name, status,
           f"dOASPL={d_oaspl:+.3f} dB, spec_offset={spec_off:+.3f} dB (threshold {threshold_db:.1f} dB)")


def check_scalar(name, py_path, mat_path, py_key, mat_key, threshold, unit=""):
    pair = load_pair(name, py_path, mat_path, py_key, mat_key)
    if pair is None:
        return
    py_val, mat_val = pair
    m = abs(float(py_val) - float(mat_val))
    status = "PASS" if m <= threshold else "FAIL"
    record(name, status, f"|delta| = {m:.4g} {unit} (Python={float(py_val):.4g}, MATLAB={float(mat_val):.4g})")


def check_complex_db(name, py_path, mat_path, py_key, mat_key, col_py=None, col_mat=None, threshold_db=3.0):
    pair = load_pair(name, py_path, mat_path, py_key, mat_key)
    if pair is None:
        return
    py_val, mat_val = pair
    if col_py is not None:
        py_val = py_val[:, col_py]
    if col_mat is not None:
        mat_val = mat_val[:, col_mat]
    n = min(len(py_val), len(mat_val))
    db_py = 10 * np.log10(np.abs(py_val[:n]) ** 2 + 1e-30)
    db_mat = 10 * np.log10(np.abs(mat_val[:n]) ** 2 + 1e-30)
    m = float(np.mean(np.abs(db_py - db_mat)))
    status = "PASS" if m <= threshold_db else "FAIL"
    record(name, status, f"mean|delta dB| = {m:.3f} dB (threshold {threshold_db:.1f} dB)")


# ===================================================================== #
# 1. Flight profile
# ===================================================================== #
folder = os.path.join(ROOT, "flight_profile")
for key, unit, tol in [("z", "m", 1.0), ("TAS", "m/s", 0.5), ("thrust", "kN", 0.5)]:
    check_max_abs(f"flight_profile: {key}",
                  os.path.join(folder, "flight_profile_python.npz"),
                  os.path.join(folder, "flight_profile_matlab.mat"),
                  key, key, tol, unit)

# ===================================================================== #
# 2. Trim data
# ===================================================================== #
folder = os.path.join(ROOT, "trim_data")
check_max_abs("trim_data: SPL_vs_time",
              os.path.join(folder, "trim_data_python.npz"),
              os.path.join(folder, "trim_data_matlab.mat"),
              "SPL_vs_time", "SPL_vs_time", 0.5, "dB")

# ===================================================================== #
# 3. Time vectors
# ===================================================================== #
folder = os.path.join(ROOT, "time_vector")
for key in ["time_PANAM_auralization", "time"]:
    check_max_abs(f"time_vector: {key}",
                  os.path.join(folder, "time_vectors_python.npz"),
                  os.path.join(folder, "time_vectors_matlab.mat"),
                  key, key, 1e-6, "s")

# ===================================================================== #
# 4/5. Tonal input (fan / buzzsaw) -- deterministic SPL(dB) vs time
# ===================================================================== #
folder = os.path.join(ROOT, "get_tonal_input")
check_max_abs("get_tonal_input: fan tonesSPLTime",
              os.path.join(folder, "tones_spl_debug_fan.npz"),
              os.path.join(folder, "tones_spl_debug_matlab_f.mat"),
              "signal", "tonesSPLTime", 0.5, "dB")
check_max_abs("get_tonal_input: buzzsaw tonesSPLTime",
              os.path.join(folder, "tones_spl_debug_buzzsaw.npz"),
              os.path.join(folder, "tones_spl_debug_matlab_b.mat"),
              "signal", "tonesSPLTime", 0.5, "dB")

# ===================================================================== #
# 6. Doppler / theta (buzzsaw) -- deterministic
# ===================================================================== #
folder = os.path.join(ROOT, "doppler_theta_buzzsaw")
check_max_abs("doppler_theta_buzzsaw: theta_deg",
              os.path.join(folder, "doppler_theta_buzzsaw_python.npz"),
              os.path.join(folder, "doppler_theta_buzzsaw_matlab.mat"),
              "theta_deg", "theta_deg", 0.1, "deg")
check_max_abs("doppler_theta_buzzsaw: doppler_ratio",
              os.path.join(folder, "doppler_theta_buzzsaw_python.npz"),
              os.path.join(folder, "doppler_theta_buzzsaw_matlab.mat"),
              "doppler_ratio", "doppler_ratio", 1e-3, "-")

# ===================================================================== #
# 7/8. Tonal signals (fan / buzzsaw) -- random phase -> level metrics
# ===================================================================== #
check_spl_mae("tonal_fan_signal: level",
              os.path.join(ROOT, "tonal_fan_signal", "tonal_fan_signal_python.npz"),
              os.path.join(ROOT, "tonal_fan_signal", "tonal_fan_signal_matlab.mat"),
              "signal", "TonalSignal_FanHarmonics", 0.5)
check_spl_mae("tonal_buzz_signal: level",
              os.path.join(ROOT, "tonal_buzz_signal", "tonal_buzz_signal_python.npz"),
              os.path.join(ROOT, "tonal_buzz_signal", "tonal_buzz_signal_matlab.mat"),
              "signal", "TonalSignal_Buzzsaw", 0.5)

# ===================================================================== #
# 9. BBN TOC -> narrowband (engine / airframe) -- deterministic
# ===================================================================== #
folder = os.path.join(ROOT, "bbn_narrowband")
for source in ["engine", "airframe"]:
    check_max_abs(f"bbn_narrowband ({source}): SPL_narrowband",
                  os.path.join(folder, f"bbn_narrowband_{source}_python.npz"),
                  os.path.join(folder, f"bbn_narrowband_{source}_matlab.mat"),
                  "SPL_narrowband", "SPL_narrowband", 1.0, "dB")
    if _param("smoothings_emission_based", 0) > 0:
        # the spectrum above is the one BEFORE smoothing; this one is after the smoothing iterations
        check_spl_floored(f"bbn_narrowband ({source}): SPL_narrowband_smoothed",
                          os.path.join(folder, f"bbn_narrowband_{source}_python.npz"),
                          os.path.join(folder, f"bbn_narrowband_{source}_matlab.mat"),
                          "SPL_narrowband_smoothed", "SPL_narrowband_smoothed", 0.5)

# ===================================================================== #
# 10/11. Broadband signals (engine / airframe) -- random phase -> level metrics
# ===================================================================== #
check_spl_mae("specrogram_engine_bbn: level",
              os.path.join(ROOT, "specrogram_engine_bbn", "BroadbandSignal_engine_python.npz"),
              os.path.join(ROOT, "specrogram_engine_bbn", "BroadbandSignal_engine_matlab.mat"),
              "signal", "BroadbandSignal_engine", 0.5)
check_spl_mae("airframe: level",
              os.path.join(ROOT, "airframe", "airframe_signal_python.npz"),
              os.path.join(ROOT, "airframe", "auralizedAirframeSignal_MATLAB.mat"),
              "signal", "auralizedAirframeSignal", 0.5)

# ===================================================================== #
# 12/13. Engine / overall signal -- level metrics
# ===================================================================== #
check_spl_mae("engine_signal_auralized: level",
              os.path.join(ROOT, "engine_signal_auralized", "engine_signal_python.npz"),
              os.path.join(ROOT, "engine_signal_auralized", "engine_signal_matlab.mat"),
              "signal", "auralizedEngineSignal", 0.5)
check_spl_mae("spectrogram_overall_signal: level",
              os.path.join(ROOT, "spectrogram_overall_signal", "overall_signal_python.npz"),
              os.path.join(ROOT, "spectrogram_overall_signal", "overall_signal_matlab.mat"),
              "signal", "auralizedOverallSignal", 0.5)

# ===================================================================== #
# 14. Propagation -- many deterministic sub-checks
# ===================================================================== #
folder = os.path.join(ROOT, "propagation")
py_path = os.path.join(folder, "propagation_python.npz")
mat_path = os.path.join(folder, "propagation_matlab.mat")

check_max_abs("propagation: thetaReflectedRay", py_path, mat_path,
              "thetaReflectedRay", "thetaReflectedRay", np.deg2rad(0.5), "rad")
check_max_abs("propagation: propDistanceReflectedRay", py_path, mat_path,
              "propDistanceReflectedRay", "propDistanceReflectedRay", 1.0, "m")
check_max_abs("propagation: launchAngle_direct", py_path, mat_path,
              "launchAngle_direct", "launchAngle_direct", 0.5, "deg")
check_max_abs("propagation: launchAngle_reflected", py_path, mat_path,
              "launchAngle_reflected", "launchAngle_reflected", 0.5, "deg")

# NOTE: Python rescales ray.t to pathLength/soundSpeed before storing
# propagation_time (see get_propagation.py); MATLAB uses eigenray.t(end)
# directly. If this check fails, that rescale is the first place to look.
check_columns_max_abs("propagation: propagation_time", py_path, mat_path,
                       "propagation_time", "propagation_time", ["direct", "reflected"], 1e-3, "s")

check_columns_max_abs("propagation: spherical_direct", py_path, mat_path,
                       "spherical_direct", "spherical_direct", ["azimuth", "elevation"], 1.0, "deg")
# p99: tolerate isolated single-sample reflection-geometry glitches (MATLAB uses
# the exact r.z==0 crossing; Python uses argmin(|z|)). The smoothed angle below
# is what actually feeds the HRTF, and it is graded strictly.
check_columns_max_abs("propagation: spherical_reflected", py_path, mat_path,
                       "spherical_reflected", "spherical_reflected", ["azimuth", "elevation"], 1.0, "deg", pct=99)
check_columns_max_abs("propagation: spherical_reflected_smooth", py_path, mat_path,
                       "spherical_reflected_smooth", "spherical_reflected_smooth", ["azimuth", "elevation"], 1.0, "deg")

check_complex_db("propagation: |TF| direct (overhead)", py_path, mat_path,
                  "tf_overhead_individual", "tf_overhead_individual", col_py=0, col_mat=0, threshold_db=3.0)
check_complex_db("propagation: |TF| reflected (overhead)", py_path, mat_path,
                  "tf_overhead_individual", "tf_overhead_individual", col_py=1, col_mat=1, threshold_db=3.0)
check_complex_db("propagation: |TF| combined (overhead)", py_path, mat_path,
                  "tf_overhead_combined", "tf_overhead_combined", threshold_db=3.0)

# ===================================================================== #
# 15. Apply propagation
# ===================================================================== #
folder = os.path.join(ROOT, "apply_propagation")
py_path = os.path.join(folder, "apply_propagation_python.npz")
mat_path = os.path.join(folder, "apply_propagation_matlab.mat")

check_ir_magnitude("apply_propagation: ir (magnitude)", py_path, mat_path, "ir", "ir", 3.0)
check_spl_mae("apply_propagation: output level", py_path, mat_path,
              "output_signal", "output_signal", 0.75)

# ===================================================================== #
# 15b. FIR transfer function (ART vs FIR at a fixed time block)
# ===================================================================== #
folder = os.path.join(ROOT, "fir_transfer_function")
# file suffix is "_combined" (ground reflection on) or "_direct" (off): use whichever Python wrote
_fir_tag = "direct" if os.path.isfile(os.path.join(folder, "fir_transfer_function_direct_python.npz")) else "combined"
py_path = os.path.join(folder, f"fir_transfer_function_{_fir_tag}_python.npz")
mat_path = os.path.join(folder, f"fir_transfer_function_{_fir_tag}_matlab.mat")
check_db_magnitude("fir_transfer_function: ART magnitude", py_path, mat_path, "mag_art", "mag_art", 1.0)
check_db_magnitude("fir_transfer_function: FIR magnitude", py_path, mat_path, "mag_fir", "mag_fir", 1.0)

# Both sides must compare the SAME time block. MATLAB stores tBlock 1-based, Python t_block 0-based.
name = "fir_transfer_function: t_block (same block compared)"
err = check_files(py_path, mat_path)
if err:
    record(name, "SKIP", err)
else:
    try:
        py_tb = int(_npz(py_path, "t_block"))
        ml_tb = int(_mat(mat_path, "t_block")) - 1
        if py_tb == ml_tb:
            record(name, "PASS", f"block {py_tb} (0-based) on both sides")
        else:
            record(name, "FAIL", f"Python block {py_tb} vs MATLAB block {ml_tb} (0-based): the FIR/ART magnitudes "
                                 f"above compare different time blocks")
    except KeyError as e:
        record(name, "SKIP", f"missing key {e}")

# ===================================================================== #
# 16. Binaural
# ===================================================================== #
folder = os.path.join(ROOT, "binaural")
py_path = os.path.join(folder, "binaural_python.npz")
mat_path = os.path.join(folder, "binaural_matlab.mat")

binaural_off = bool(PARAMS) and _param("binaural_signal", 0) == 0
reflection_off = bool(PARAMS) and _param("consider_ground_reflection", 1) == 0

_binaural_checks = [
    ("binaural: HRIR direct left", lambda n: check_relative(n, py_path, mat_path, "hrir_direct_left", "hrir_direct_left", 5.0), False),
    ("binaural: HRIR direct right", lambda n: check_relative(n, py_path, mat_path, "hrir_direct_right", "hrir_direct_right", 5.0), False),
    ("binaural: HRIR reflected left", lambda n: check_relative(n, py_path, mat_path, "hrir_reflected_left", "hrir_reflected_left", 5.0), True),
    ("binaural: HRIR reflected right", lambda n: check_relative(n, py_path, mat_path, "hrir_reflected_right", "hrir_reflected_right", 5.0), True),
    ("binaural: output left level", lambda n: check_spl_mae(n, py_path, mat_path, "output_binaural_left", "output_binaural_left", 1.0), False),
    ("binaural: output right level", lambda n: check_spl_mae(n, py_path, mat_path, "output_binaural_right", "output_binaural_right", 1.0), False),
]
for _name, _run, _needs_reflection in _binaural_checks:
    if binaural_off:
        record(_name, "N/A", "binaural_signal = 0 in this scenario")
    elif _needs_reflection and reflection_off:
        record(_name, "N/A", "consider_ground_reflection = 0 in this scenario (no reflected path)")
    else:
        _run(_name)

# ===================================================================== #
# 17. Wav output
# ===================================================================== #
folder = os.path.join(ROOT, "wav_output")
py_path = os.path.join(folder, "wav_output_python.npz")
mat_path = os.path.join(folder, "wav_output_matlab.mat")

check_scalar("wav_output: attenuation_db", py_path, mat_path, "attenuation_db", "AttenuationdB", 1e-9, "dB")
check_spl_mae("wav_output: output level", py_path, mat_path, "output_signal", "outputSignal", 0.75)

# ===================================================================== #
# 18. Prepare_input_SQ (trimmed data) -- informational summary check
# ===================================================================== #
folder = os.path.join(ROOT, "Prepare_input_SQ")
py_path = os.path.join(folder, "python_trimmed_output.npz")
mat_path = os.path.join(folder, "MATLAB_trimmed_output.mat")
name = "Prepare_input_SQ: trimmed overall SPL"
err = check_files(py_path, mat_path)
if err:
    record(name, "SKIP", err)
else:
    try:
        npz = np.load(py_path, allow_pickle=True)
        mat = loadmat(mat_path, simplify_cells=True)
        source_data_py = npz["source_data_trimmed"].tolist()
        mat_data = mat["source_data_trimmed"]
        spl_py = np.array([10 * np.log10(np.sum(10 ** (d["overall"][:, 1] / 10))) for d in source_data_py])
        spl_mat = np.array([10 * np.log10(np.sum(10 ** (d["overall"][:, 1] / 10))) for d in mat_data])
        m = max_abs(spl_py, spl_mat)
        status = "PASS" if m <= 0.5 else "FAIL"
        record(name, status, f"max|delta| = {m:.3f} dB (threshold 0.5 dB)")
    except Exception as e:
        record(name, "SKIP", f"error while comparing: {e}")


# ===================================================================== #
# Report
# ===================================================================== #
def print_report():
    name_w = max(len(r["name"]) for r in results) + 2
    print("\n" + "=" * 100)
    print("VERIFICATION REPORT")
    print("=" * 100)

    for r in results:
        symbol = {"PASS": "[PASS]", "FAIL": "[FAIL]", "SKIP": "[SKIP]", "N/A": "[N/A ]"}[r["status"]]
        print(f"{symbol}  {r['name']:<{name_w}} {r['detail']}")

    n_pass = sum(1 for r in results if r["status"] == "PASS")
    n_fail = sum(1 for r in results if r["status"] == "FAIL")
    n_skip = sum(1 for r in results if r["status"] == "SKIP")
    n_na = sum(1 for r in results if r["status"] == "N/A")

    print("-" * 100)
    print(f"TOTAL: {len(results)}   PASS: {n_pass}   FAIL: {n_fail}   SKIP: {n_skip}   N/A: {n_na}")
    print("=" * 100)

    if n_fail:
        print("\nFAILED CHECKS:")
        for r in results:
            if r["status"] == "FAIL":
                print(f"  - {r['name']}: {r['detail']}")

    if n_skip:
        print("\nSKIPPED CHECKS (missing files/keys -- generate them and re-run):")
        for r in results:
            if r["status"] == "SKIP":
                print(f"  - {r['name']}: {r['detail']}")

    return n_fail == 0


if __name__ == "__main__":
    all_ok = print_report()
    sys.exit(0 if all_ok else 1)
