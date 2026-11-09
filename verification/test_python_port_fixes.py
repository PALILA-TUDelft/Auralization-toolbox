"""Regression tests for the places where the Python port had to mimic MATLAB semantics exactly.

Fast (no ART / no audio); run with:
    python verification/test_python_port_fixes.py

Each test compares the Python code with an independent, line-by-line translation of the MATLAB behaviour
(1-based indexing written out explicitly), or with exact rational arithmetic.
Exit code 0 if everything passes.
"""
import math
import os
import sys
from fractions import Fraction

import numpy as np

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import globals  # noqa: E402
from auralization.private.broadband_synthesis_smooth import build_hop_band_matrices  # noqa: E402
from auralization.private.convert_freq_bands import convert_freq_bands  # noqa: E402
from auralization.private.get_auralization_time import _colon_length, get_auralization_time  # noqa: E402
from auralization.private.tonal_synthesis import interp1_extrap  # noqa: E402
from utilities.ini_parser import ini_int  # noqa: E402
from utilities.trim_data_time_distance_based import trim_data_time_distance_based  # noqa: E402
from auralization.private.propagation.angles import moving_average  # noqa: E402
from auralization.private.propagation.apply_propagation import _make_causal  # noqa: E402
from auralization.private.propagation.hrtf import hrir_interpolation  # noqa: E402

results = []


def test(name):
    def deco(fn):
        try:
            detail = fn() or ""
            results.append((name, True, detail))
        except AssertionError as e:
            results.append((name, False, str(e)))
        except Exception as e:  # noqa: BLE001
            results.append((name, False, f"{type(e).__name__}: {e}"))
        return fn
    return deco


# --------------------------------------------------------------------------------------------- time vectors
def _old_arange_impl(N, dt, fs):
    tpa = np.arange(0, N * dt, dt)
    d = 1 / fs
    t = np.arange(tpa[0], tpa[-1] + d, d)
    if len(t) % 2:
        t = np.append(t, t[-1] + d)
    return tpa, t


@test("time vectors: exact length for any dt_panam / fs (np.arange used to be off by one for 0.1, 0.2, 0.05 ...)")
def _():
    bad = 0
    total = 0
    for dt_s in ("0.5", "0.25", "0.2", "0.1", "0.05", "0.4"):
        for fs in (48000, 44100):
            for N in range(40, 400, 3):
                dtF = Fraction(dt_s)
                globals.dt_panam, globals.fs = float(dtF), fs
                data = [{"source_time": i * float(dtF)} for i in range(N)]
                _, tpa, t = get_auralization_time(data, "emission")
                n_true = math.floor((N - 1) * dtF * fs) + 1
                n_true += n_true % 2                      # even number of samples
                total += 1
                bad += (len(tpa) != N) or (len(t) != n_true)
    assert bad == 0, f"{bad} of {total} cases have the wrong length"
    return f"{total} cases"


@test("time vectors: identical to the previous implementation where that was correct (dt = 0.5, 0.25)")
def _():
    for dt in (0.5, 0.25):
        for fs in (48000, 44100):
            for N in range(40, 300, 7):
                globals.dt_panam, globals.fs = dt, fs
                data = [{"source_time": i * dt} for i in range(N)]
                _, tpa, t = get_auralization_time(data, "emission")
                otpa, ot = _old_arange_impl(N, dt, fs)
                assert len(otpa) == len(tpa) and len(ot) == len(t)
                assert np.allclose(otpa, tpa, rtol=0, atol=1e-12) and np.allclose(ot, t, rtol=0, atol=1e-9)


@test("time vectors: n_blocks = floor(fs*time[-1]/hop + 1e-6) is exactly 5*(N-1)")
def _():
    for dt in (0.5, 0.25, 0.2, 0.1, 0.05):
        for fs in (48000, 44100):
            for N in range(40, 400, 5):
                globals.dt_panam, globals.fs = dt, fs
                data = [{"source_time": i * dt} for i in range(N)]
                _, _, t = get_auralization_time(data, "emission")
                hop = round(fs * dt) // 5
                assert int(np.floor(fs * t[-1] / hop + 1e-6)) == 5 * (N - 1), (dt, fs, N)


@test("_colon_length matches MATLAB colon on simple cases")
def _():
    assert _colon_length(0, 1, 0.25) == 5
    assert _colon_length(0, 0.3, 0.1) == 4          # np.arange(0, 0.3 + 0.1, 0.1) style pitfalls
    assert _colon_length(0, 149.9, 0.1) == 1500
    assert _colon_length(0, 0.99, 0.25) == 4


# --------------------------------------------------------------------------------------------- hop blocks
def _matlab_rep(B, F, n_blocks, H=5):
    """Line-by-line translation of the RepBandsVsTime loop in broadbandSynthesis_smooth.m (1-based)."""
    n_bands = B.shape[1]
    rep = np.zeros((n_blocks, n_bands))
    frep = np.zeros((n_blocks, n_bands))

    def ensure(rows):                                  # MATLAB grows the matrix when indexing beyond its end
        nonlocal rep, frep
        if rows > rep.shape[0]:
            pad = np.zeros((rows - rep.shape[0], n_bands))
            rep, frep = np.vstack([rep, pad]), np.vstack([frep, pad])

    j = 1
    for i in range(1, n_blocks + 1, H):
        ensure(i + H - 1)
        rep[i - 1] = B[j - 1]
        frep[i - 1] = F[:, j - 1]
        if j != n_blocks / H:
            rep[i:i + H - 1] = 0.5 * (B[j - 1] + B[j])
            frep[i:i + H - 1] = F[:, j - 1]
        else:
            rep[i:i + H - 1] = B[j - 1]
            frep[i:i + H - 1] = F[:, j - 1]
        j += 1
        if i == n_blocks:
            raise ValueError("return")
    return rep, frep


@test("hop blocks: Python equals the MATLAB loop, incl. the last 4 blocks (used to take the last PANAM row)")
def _():
    rng = np.random.default_rng(1)
    for N in (8, 40, 61, 301):
        B = rng.normal(60, 10, (N, 24))
        F = np.sort(rng.uniform(50, 10000, (24, N)), axis=0)
        n_blocks = 5 * (N - 1)
        rep, frep = build_hop_band_matrices(B, F, n_blocks, 5)
        mrep, mfrep = _matlab_rep(B, F, n_blocks)
        assert rep.shape == mrep.shape == (n_blocks, 24), (rep.shape, mrep.shape)
        assert np.array_equal(rep, mrep) and np.array_equal(frep, mfrep), f"N={N}: differs"
        # explicit statement of the fixed behaviour
        assert np.array_equal(rep[-4:], np.tile(B[N - 2], (4, 1)))


@test("hop blocks: n_blocks not a multiple of 5 -> matrices grow like MATLAB; n_blocks % 5 == 1 -> error like MATLAB")
def _():
    rng = np.random.default_rng(2)
    B = rng.normal(60, 10, (10, 24))
    F = np.sort(rng.uniform(50, 10000, (24, 10)), axis=0)
    rep, frep = build_hop_band_matrices(B, F, 23, 5)
    mrep, mfrep = _matlab_rep(B, F, 23)
    assert rep.shape == mrep.shape == (25, 24)
    assert np.array_equal(rep, mrep) and np.array_equal(frep, mfrep)
    try:
        build_hop_band_matrices(B, F, 21, 5)
        raise AssertionError("expected ValueError for n_blocks % 5 == 1")
    except ValueError:
        pass


# --------------------------------------------------------------------------------------------- ConvertFreqBands
def _matlab_convert(pMspl, fM_time_band, df, fs, block_len, smoothing, pref=20e-6, index_shift=0):
    """Line-by-line translation of ConvertFreqBands in broadbandSynthesis_smooth.m.
    pMspl, fM_time_band: (n_times, n_bands); returns p, pEqual as (n_freq, n_times)."""
    n_t, _ = pMspl.shape
    pM = pref ** 2 * 10 ** (pMspl.T / 10)             # (n_bands, n_times)
    fM = fM_time_band.T                                # MATLAB: fM = fM'
    f = fs / 2 * np.linspace(0, 1, block_len // 2 + 1)
    p = np.zeros((len(f), n_t))
    p_equal = np.zeros_like(p)
    b = 3
    G = 10 ** (3 / 10)
    n_b = fM.shape[0]
    for tt in range(n_t):
        fL = np.concatenate([fM[:, tt] / G ** (1 / (2 * b)), [fM[-1, tt] * G ** (1 / (2 * b))]])   # fL(tt, 1:nB+1)
        n = np.diff(fL) / df
        for i in range(1, n_b + 1):                    # i = 1:size(fM,1)
            idx = (f >= fL[i - 1]) & (f <= fL[i])
            p[idx, tt] = np.sqrt(pM[i - 1, tt] / n[i - 1]) * np.sqrt(2)
        p_equal[:, tt] = p[:, tt]
        fMs = 1.0 * fM[:, tt]
        for j in range(1, smoothing + 1):
            for i in range(1, len(fMs)):               # i = 1:length(fMs)-1
                idx = (f > fMs[i - 1] * G ** (1 / (4 ** j * b))) & (f < fMs[i] / G ** (1 / (4 ** j * b)))
                if np.any(idx):
                    p[idx, tt] = np.mean(p[idx, tt])
            tmp = []
            for i in range(1, len(fMs) + 1):           # i = 1:length(fMs)
                if fMs[i - 1] > fL[5 * j - 1 + index_shift]:   # fL(tt, 5*j)  (1-based); index_shift=1 = the old wrong index
                    tmp += [fMs[i - 1] / G ** (3 / (2 * 4 ** j * b)), fMs[i - 1] / G ** (1 / (2 * 4 ** j * b)),
                            fMs[i - 1] * G ** (1 / (2 * 4 ** j * b)), fMs[i - 1] * G ** (3 / (2 * 4 ** j * b))]
            fMs = np.array(tmp)
    return p, p_equal


def _bands():
    G = 10 ** (3 / 10)
    return 1000.0 * G ** (np.arange(-14, 10) / 3)      # 24 third-octave centres, ~ 40 Hz .. 8 kHz


@test("ConvertFreqBands: smoothing = 0, 1, 2, 3 equal the MATLAB translation (index 5*j used to be off by one)")
def _():
    globals.fs, globals.pref = 48000, 20e-6
    rng = np.random.default_rng(3)
    n_t, block_len = 6, 4800
    centres = _bands()
    pMspl = rng.normal(55, 8, (n_t, len(centres)))
    fM_tb = np.tile(centres, (n_t, 1))
    for smoothing in (0, 1, 2, 3):
        p_ref, pe_ref = _matlab_convert(pMspl, fM_tb, 48000 / block_len, 48000, block_len, smoothing)
        t = np.arange(n_t) * 0.1
        p, pe = convert_freq_bands(pMspl, fM_tb.T, 48000 / block_len, t, block_len, smoothing)
        assert p.shape == p_ref.shape or p.shape[0] >= p_ref.shape[0]
        assert np.allclose(p[:p_ref.shape[0]], p_ref, rtol=1e-12, atol=1e-18), f"smoothing={smoothing}: p differs"
        assert np.allclose(pe[:pe_ref.shape[0]], pe_ref, rtol=1e-12, atol=1e-18), f"smoothing={smoothing}: pEqual differs"


@test("ConvertFreqBands: the fL(5*j) index is only visible at fine resolution (0.5 Hz) -> Python == MATLAB there, old index differs")
def _():
    globals.fs, globals.pref = 48000, 20e-6
    rng = np.random.default_rng(5)
    n_t, block_len = 2, 96000                          # df = 0.5 Hz
    centres = _bands()
    pMspl = rng.normal(55, 8, (n_t, len(centres)))
    fM_tb = np.tile(centres, (n_t, 1))
    df = 48000 / block_len
    p_ref, _ = _matlab_convert(pMspl, fM_tb, df, 48000, block_len, 2)
    p_old, _ = _matlab_convert(pMspl, fM_tb, df, 48000, block_len, 2, index_shift=1)
    p, _ = convert_freq_bands(pMspl, fM_tb.T, df, np.arange(n_t) * 0.1, block_len, 2)
    assert np.allclose(p[:p_ref.shape[0]], p_ref, rtol=1e-12, atol=1e-18), "Python differs from the MATLAB translation"
    n_old = int(np.sum(~np.isclose(p_old, p_ref, rtol=1e-9, atol=1e-18)))
    assert n_old > 0, "test has no power: the old index gives the same result"
    assert not np.allclose(p[:p_old.shape[0]], p_old, rtol=1e-9, atol=1e-18), "Python still uses the old index"
    return f"old index would change {n_old} values"


@test("ConvertFreqBands: fewer time blocks than bands works (the old shape heuristic transposed the wrong way)")
def _():
    globals.fs, globals.pref = 48000, 20e-6
    centres = _bands()
    n_t = 3                                            # < 24 bands
    rng = np.random.default_rng(4)
    pMspl = rng.normal(55, 8, (n_t, len(centres)))
    fM_tb = np.tile(centres, (n_t, 1))
    p_ref, _ = _matlab_convert(pMspl, fM_tb, 10.0, 48000, 4800, 0)
    p, _ = convert_freq_bands(pMspl, fM_tb.T, 10.0, np.arange(n_t) * 0.1, 4800, 0)
    assert np.allclose(p[:p_ref.shape[0]], p_ref, rtol=1e-12, atol=1e-18)
    try:
        convert_freq_bands(pMspl, fM_tb, 10.0, np.arange(n_t) * 0.1, 4800, 0)   # wrong orientation
        raise AssertionError("expected ValueError for a wrongly oriented fM")
    except ValueError:
        pass


# --------------------------------------------------------------------------------------------- misc
@test("interp1_extrap equals MATLAB interp1(...,'linear','extrap') (np.interp clamps)")
def _():
    from scipy.interpolate import interp1d
    xp = np.array([0.0, 0.5, 1.0, 1.5])
    fp = np.array([10.0, 14.0, 13.0, 20.0])
    x = np.array([-0.2, 0.0, 0.3, 1.5, 1.7])
    ref = interp1d(xp, fp, kind="linear", fill_value="extrapolate")(x)
    assert np.allclose(interp1_extrap(x, xp, fp), ref, rtol=0, atol=1e-12)
    assert not np.allclose(np.interp(x, xp, fp), ref)


@test("ini_int accepts '1', '1.0', '4.8e4' and rejects '1.5' / text")
def _():
    assert ini_int({"a": "1"}, "a", 0) == 1 and ini_int({"a": "1.0"}, "a", 0) == 1
    assert ini_int({"a": "4.8e4"}, "a", 0) == 48000 and ini_int({}, "a", 7) == 7
    for bad in ("1.5", "abc"):
        try:
            ini_int({"a": bad}, "a", 0)
            raise AssertionError(f"expected ValueError for {bad!r}")
        except ValueError:
            pass


@test("t_block: (N+1)//2 - 1 equals MATLAB round(N/2) - 1 (halves round up), odd AND even N")
def _():
    for N in range(2, 500):
        matlab_1_based = int(math.floor(N / 2 + 0.5))   # MATLAB round(N/2)
        assert (N + 1) // 2 - 1 == matlab_1_based - 1, N


def _trim_input(n, i_min, dt=0.1):
    dist = 100.0 + np.abs(np.arange(n) - i_min)
    return [{"source_time": k * dt, "dist": dist[k], "overall": np.array([[1000.0, 60.0]])} for k in range(n)]


@test("trim: window leaving the data on ONE side keeps the whole signal (MATLAB), fractional trim bins round like MATLAB")
def _():
    # idx_min = 30 (0-based), N = 100, dt = 0.1: trim 5 s -> 50 bins -> lower overflows, upper does not
    assert trim_data_time_distance_based(_trim_input(100, 30), 5.0, None, tag="") == (0, 99)
    assert trim_data_time_distance_based(_trim_input(100, 50), 2.0, None, tag="") == (30, 70)
    # trim / dt = 2.5 bins: MATLAB round(31 - 2.5) = round(28.5) = 29 (1-based) -> 28; round(33.5) = 34 -> 33
    assert trim_data_time_distance_based(_trim_input(100, 30, dt=0.2), 0.5, None, tag="") == (28, 33)


@test("_make_causal: signed test last > 1e-8 (a negative last sample does not trigger the shift)")
def _():
    ir = np.zeros((8, 3))
    ir[-1, 0], ir[-1, 1], ir[-1, 2] = 1e-3, -1e-3, 1e-9
    ir[3, :] = 1.0
    out = _make_causal(ir)
    assert np.array_equal(out[:, 0], np.roll(ir[:, 0], 4))
    assert np.array_equal(out[:, 1], ir[:, 1]) and np.array_equal(out[:, 2], ir[:, 2])


@test("moving_average == MATLAB smoothdata(x,'movmean',10) incl. fewer than 10 samples (shrinking window)")
def _():
    rng = np.random.default_rng(0)
    for n in (3, 9, 10, 25):
        x = rng.standard_normal((n, 2))
        ref = np.zeros_like(x)
        for i in range(n):   # window [i-5, i+4], truncated at the ends
            lo, hi = max(0, i - 5), min(n - 1, i + 4)
            ref[i] = x[lo:hi + 1].mean(axis=0)
        assert np.allclose(moving_average(x, 10), ref), n


@test("HRIR: Nyquist bin discarded, HRIRs causal (first half carries the energy) for the FABIAN .mat")
def _():
    path = os.path.join(os.path.dirname(__file__), "..", "input_data", "FABIAN_HRIR_measured_HATO_0.mat")
    if not os.path.exists(path):
        return "skipped (FABIAN .mat not found)"
    l, r = hrir_interpolation(np.array([90.0, 10.0]), np.array([30.0, -20.0]), 0, path)
    assert l.shape == (256, 2)
    assert np.abs(l[:128, 0]).sum() > np.abs(l[127:, 0]).sum()
    assert abs(np.fft.rfft(l, axis=0)[-1]).max() < 1e-12     # Nyquist bin is exactly 0


@test("HRIR: the FABIAN .sofa (SH decomposition on load) gives the same HRIRs as the AKtools .mat coefficients")
def _():
    root = os.path.join(os.path.dirname(__file__), "..", "input_data")
    mat, sofa = (os.path.join(root, f"FABIAN_HRIR_measured_HATO_0.{e}") for e in ("mat", "sofa"))
    if not (os.path.exists(mat) and os.path.exists(sofa)):
        return "skipped (FABIAN .mat/.sofa not found)"
    rng = np.random.default_rng(0)
    az, el = rng.uniform(0, 360, 300), rng.uniform(-90, 90, 300)
    az[:4], el[:4] = [0, 90, 180, 270], [0, 0, 0, 0]
    ref = hrir_interpolation(az, el, 0, mat)
    out = hrir_interpolation(az, el, 0, sofa)
    for ear, (a, b) in zip("LR", zip(ref, out)):
        err = np.abs(a - b).max() / np.abs(a).max()
        assert err < 1e-9, f"{ear} ear: max|delta|/max|ref| = {err:.2e}"
    return f"max|delta|/max|ref| = {max(np.abs(a - b).max() / np.abs(a).max() for a, b in zip(ref, out)):.1e}"


if __name__ == "__main__":
    width = max(len(n) for n, _, _ in results)
    n_fail = 0
    for name, ok, detail in results:
        print(f"[{'PASS' if ok else 'FAIL'}]  {name:<{width}}  {detail}")
        n_fail += (not ok)
    print(f"\n{len(results) - n_fail}/{len(results)} passed")
    sys.exit(1 if n_fail else 0)
