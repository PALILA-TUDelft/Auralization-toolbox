# auralization/private/propagation/art_bindings.py
from __future__ import annotations

import json
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path

import numpy as np

# ---------------------------------------------------------------------------
# Locate and load the compiled _art_core extension module.
# The shared libraries from the ITAGeometricalAcoustics build must be findable
# (.dll on Windows, .dylib on macOS, .so on Linux).
#
# Loading is deferred until the first eigenray call, so that the rest of the
# toolbox (and the pure-Python helpers in this module, such as
# create_atmosphere_json and wind_profile_from_ini) remains importable on a
# machine where ART has not been built or downloaded yet.
#
# Search order, first existing directory wins:
#   1. $ART_DLL_DIR / $ART_PYD_DIR     (explicit override)
#   2. <project root>/bin              (build_art.ps1/.sh output, or an unpacked archive)
#   3. <project root>/prebuilt/<tag>   (binaries committed to the repository, when
#                                       the platform and Python version match)
#   4. the in-tree CMake build output  (local developer build)
#
# Windows resolves dependent DLLs through os.add_dll_directory at import time.
# macOS and Linux instead resolve them through an rpath baked into the module
# when it is linked (@loader_path / $ORIGIN, set in bindings/CMakeLists.txt),
# so placing _art_core next to the ITA libraries in bin/ is sufficient there;
# DYLD_LIBRARY_PATH is not used, because macOS SIP strips it.
# ---------------------------------------------------------------------------
_PROJECT_ROOT = Path(__file__).resolve().parents[3]  # Auralization-toolbox/

if sys.platform == "win32":
    _ITA_PRESET = "full-win-vs-msvc"
elif sys.platform == "darwin":
    _ITA_PRESET = "full-mac-ninja-clang"
else:
    _ITA_PRESET = "full-linux-ninja-gcc"

_ITA_BUILD_RELEASE = (
    _PROJECT_ROOT / "ITAGeometricalAcoustics" / "out" / "build" / _ITA_PRESET / "Release"
)
# Windows puts the runtime DLLs in Release/bin; the Unix builds put the
# shared libraries in Release/lib. Search both, on every platform.
_ITA_BUILD_LIB_DIRS = [_ITA_BUILD_RELEASE / "bin", _ITA_BUILD_RELEASE / "lib"]


# Binaries committed to the repository live in prebuilt/<platform>-py<major><minor>,
# e.g. prebuilt/win-x64-py313. The module is tied to one Python minor version, so
# the folder is only a candidate for the interpreter it was built for.
if sys.platform == "win32":
    _PREBUILT_TAG = f"win-x64-py{sys.version_info.major}{sys.version_info.minor}"
else:
    _PREBUILT_TAG = f"{sys.platform}-py{sys.version_info.major}{sys.version_info.minor}"
_PREBUILT_DIR = _PROJECT_ROOT / "prebuilt" / _PREBUILT_TAG


def _candidates(env_var: str) -> list[Path]:
    """Directories to search for the ART binaries, highest priority first."""
    dirs = []
    override = os.environ.get(env_var)
    if override:
        dirs.extend(Path(p).expanduser() for p in override.split(os.pathsep) if p)
    dirs.append(_PROJECT_ROOT / "bin")
    dirs.append(_PREBUILT_DIR)
    return dirs


_ART_DLL_DIRS = _candidates("ART_DLL_DIR") + _ITA_BUILD_LIB_DIRS
_ART_PYD_DIRS = _candidates("ART_PYD_DIR") + [
    _PROJECT_ROOT / "bindings" / "build" / "Release",  # MSVC multi-config
    _PROJECT_ROOT / "bindings" / "build",              # single-config (Unix)
]

# Platform-specific wording for the error below.
if sys.platform == "win32":
    _MODULE_GLOB = "_art_core*.pyd"
    _LIB_MARKER = "ITAGeo.dll"  # present in the directory that holds the ITA DLLs
    _LIB_WORD = "DLLs"
    _BUILD_CMD = "powershell -ExecutionPolicy Bypass -File tools/build_art.ps1"
    _PREBUILT_NOTE = "The prebuilt binaries are Windows x64 only and are"
else:
    _MODULE_GLOB = "_art_core*.so"
    _LIB_MARKER = ""  # unused: macOS / Linux find libraries through the rpath
    _LIB_WORD = ".dylib files" if sys.platform == "darwin" else ".so files"
    _BUILD_CMD = "./tools/build_art.sh"
    _PREBUILT_NOTE = (
        "No prebuilt binaries are published for this platform yet, so it has "
        "to be\nbuilt from source. The result is"
    )

_INSTALL_HINT = """\
The compiled ART extension module '_art_core' could not be imported, so
eigenray tracing is unavailable. The rest of the toolbox does not need it.

To enable it, either:
  * build it from source:  {build_cmd}
  * use the binaries committed to the repository (Windows x64 + Python 3.13 only):
      {prebuilt_dir}
    (a git clone has them; check that the folder exists and is complete), or
  * put {module_glob} and the ITA {lib_word} into
      {bin_dir}, or
  * point ART_DLL_DIR / ART_PYD_DIR at the directories holding the ITA
    {lib_word} and {module_glob} respectively.

See the "ART (Atmospheric Ray Tracing) native module" section of the README.
{prebuilt_note} tied to one Python minor version
(this interpreter is {py} on {platform}).

Searched for the ITA {lib_word} in:
{dll_dirs}
Searched for _art_core in:
{pyd_dirs}

Underlying import error: {err}"""

_art_core = None


def _load_art_core():
    """Import and cache the native _art_core module, with an actionable error."""
    global _art_core
    if _art_core is not None:
        return _art_core

    # Use exactly ONE directory for the module and ONE for the ITA libraries: the
    # first candidate, in priority order, that really contains them. Adding every
    # existing candidate would let two different builds mix: Windows searches
    # directories added with os.add_dll_directory in no guaranteed order, and
    # sys.path.insert(0, ...) in a loop would reverse the priority.
    if hasattr(os, "add_dll_directory"):  # Windows only
        existing = [d for d in _ART_DLL_DIRS if d.is_dir()]
        chosen = next((d for d in existing if (d / _LIB_MARKER).is_file()), None)
        # No directory has the marker (unusual layout): fall back to all of them.
        for d in [chosen] if chosen else existing:
            os.add_dll_directory(str(d))
    pyd_dir = next((d for d in _ART_PYD_DIRS if d.is_dir() and any(d.glob(_MODULE_GLOB))), None)
    if pyd_dir is not None:
        entry = str(pyd_dir)
        if entry in sys.path:
            sys.path.remove(entry)
        sys.path.insert(0, entry)

    try:
        import _art_core as _mod  # noqa: PLC0415
    except ImportError as err:
        raise ImportError(
            _INSTALL_HINT.format(
                bin_dir=_PROJECT_ROOT / "bin",
                prebuilt_dir=_PREBUILT_DIR,
                py=f"{sys.version_info.major}.{sys.version_info.minor}",
                platform=sys.platform,
                build_cmd=_BUILD_CMD,
                module_glob=_MODULE_GLOB,
                lib_word=_LIB_WORD,
                prebuilt_note=_PREBUILT_NOTE,
                dll_dirs="\n".join(f"  - {d}" for d in _ART_DLL_DIRS),
                pyd_dirs="\n".join(f"  - {d}" for d in _ART_PYD_DIRS),
                err=err,
            )
        ) from err

    _art_core = _mod
    return _art_core


def art_core_available() -> bool:
    """True if the native ART module can be loaded (useful for skipping tests)."""
    try:
        _load_art_core()
    except ImportError:
        return False
    return True


# ---------------------------------------------------------------------------
# Public data types
# Attribute names follow the MATLAB AtmosphericRay convention so that
# tf_model.py and angles.py can consume them without translation.
# ---------------------------------------------------------------------------
@dataclass
class Eigenray:
    t: np.ndarray               # (M,) seconds
    r: np.ndarray               # (M,3) meters
    phi: float                  # azimuth angle [deg] (ART convention)
    theta: float                # elevation angle [deg] (ART convention)
    alpha_deg: float            # launch angle = 90 - theta
    spreadingLoss: float        # scalar gain at receiver
    numReflections: int         # 0 = direct, 1 = first-order reflection
    receiverSphereHit: bool = True

    @property
    def numPoints(self) -> int:
        return self.r.shape[0]

    @property
    def r_cart(self) -> np.ndarray:
        return self.r

    @property
    def r_z(self) -> np.ndarray:
        return self.r[:, 2]

    def pathLength(self) -> float:
        return float(np.sum(np.linalg.norm(np.diff(self.r, axis=0), axis=1)))


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------
def _dict_to_eigenray(d: dict) -> Eigenray:
    r = np.asarray(d["r"], dtype=float)
    # Determine reflections from geometry: z <= 0 means ground bounce.
    # This mirrors the C++ ToPropagationPath conversion that the MATLAB
    # pipeline uses (RayToPropagationPath.cpp, line 19).
    num_refl = 1 if np.any(r[:, 2] <= 0.0) else 0
    # alpha_deg: 2D vertical-plane angle matching MATLAB n0.alpha_deg.
    # The C++ binding exports 90-theta (elevation), but MATLAB uses the full
    # atan2(nz, nx) which distinguishes approaching vs departing rays.
    theta_r = np.radians(float(d["theta_deg"]))
    phi_r = np.radians(float(d["phi_deg"]))
    nx = np.sin(theta_r) * np.cos(phi_r)
    nz = np.cos(theta_r)
    alpha = np.degrees(np.arctan2(nz, nx)) % 360.0
    return Eigenray(
        t=np.asarray(d["t"], dtype=float),
        r=r,
        phi=float(d["phi_deg"]),
        theta=float(d["theta_deg"]),
        alpha_deg=alpha,
        spreadingLoss=float(d["spreading_loss"]),
        numReflections=num_refl,
        receiverSphereHit=bool(d["receiver_sphere_hit"]),
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def create_atmosphere_json(
    temp_profile: str = "constant",
    temperature_celsius: float = 15.0,
    humidity_percent: float = 50.0,
    static_pressure_pa: float = 101325.0,
    wind: dict | None = None,
) -> str:
    """Build an atmosphere JSON string accepted by find_eigenrays / trace_rays.

    Parameters
    ----------
    temp_profile : 'constant' or 'isa'
    temperature_celsius : ground-level temperature (only used for 'constant')
    humidity_percent : relative humidity [%]
    static_pressure_pa : static pressure [Pa] (only used for 'constant')

    The JSON is assembled here, with the same structure and values as MATLAB's
    ``StratifiedAtmosphere.toJSON`` (ARTMatlab), and NOT through the C++
    ``create_atmosphere_json`` binding. The C++ encoder copies a constant
    temperature profile through ``TemperatureProfiles::CConstant``'s copy
    constructor, which swaps temperature and static pressure (ITAGeo
    Utils/JSON/Atmosphere.cpp:141 + TemperatureProfiles.cpp:23-27). The ray
    tracer would then see T = 101325 K and p = 278 Pa, making every ray travel
    time ~19x too short. MATLAB never goes through that encoder.

    wind : dict, optional
        Wind profile as returned by ``wind_profile_from_ini`` (default: zero wind).

    Like MATLAB, an unknown temperature profile raises an error instead of
    silently falling back to 'constant'.
    """
    profile = str(temp_profile).strip().lower()
    if profile == "constant":
        temperature = {
            "type": "temperature_profile",
            "class": "constant",
            "static_pressure": float(static_pressure_pa),
            "temperature": float(temperature_celsius) + 273.15,  # [K]
        }
    elif profile == "isa":
        temperature = {"type": "temperature_profile", "class": "isa"}
    else:
        raise ValueError(
            f"Unsupported temperature profile '{temp_profile}'. Valid values: 'constant', 'isa'."
        )

    atmosphere = {
        "humidity_profile": {
            "type": "humidity_profile",
            "class": "constant",
            "relative_humidity": float(humidity_percent),
        },
        "temperature_profile": temperature,
        "wind_profile": wind if wind is not None else {"type": "wind_profile", "class": "zero"},
    }
    return json.dumps(atmosphere)


# Defaults of ARTMatlab's StratifiedAtmosphere (used by MATLAB when the ini does not set them)
_WIND_DEFAULTS = {
    "const_wind_velocity": 20.0,          # [m/s]   constant wind profile
    "const_wind_direction": (1.0, 0.0, 0.0),  # horizontal direction of the wind
    "friction_velocity": 0.6,             # [m/s]   logarithmic wind profile
    "surface_roughness": 0.1,             # [m]     logarithmic wind profile
}


def _parse_number(value, name):
    try:
        x = float(value)
    except (TypeError, ValueError):
        raise ValueError(f"Wind parameter '{name}' must be a number, got {value!r}.") from None
    if not np.isfinite(x):
        raise ValueError(f"Wind parameter '{name}' must be finite, got {value!r}.")
    return x


def _parse_direction(value):
    """Parse '[1 0 0]', '1 0 0', '1,0,0' (or a sequence) like MATLAB's set.constWindDirection."""
    if isinstance(value, str):
        parts = [p for p in re.split(r"[\s,;\[\]]+", value.strip()) if p]
        comps = [_parse_number(p, "const_wind_direction") for p in parts]
    else:
        comps = [_parse_number(p, "const_wind_direction") for p in value]
    if len(comps) == 2:
        comps.append(0.0)
    if len(comps) != 3:
        raise ValueError("const_wind_direction must have two or three components.")
    if comps[2] != 0:
        raise ValueError("Wind direction must be purely horizontal (z component = 0).")
    v = np.asarray(comps, dtype=float)
    n = float(np.linalg.norm(v))
    if n == 0:
        raise ValueError("const_wind_direction must not be the zero vector.")
    if n != 1.0:
        print("[WARN] Wind direction must be a normalized vector. Normalizing...")  # same as MATLAB
        v = v / n
    return v


def wind_profile_from_ini(input_file: dict) -> dict:
    """Wind profile JSON node, built the way MATLAB's get_propagation.m + toJSON.m do.

    ini keys: wind_profile ('zero' | 'constant' | 'log'), and optionally
    const_wind_velocity, const_wind_direction, surface_roughness, friction_velocity.
    Missing parameters take the ARTMatlab defaults (see ``_WIND_DEFAULTS``). Every
    parameter that is present is validated like MATLAB's property setters do,
    whichever profile is selected.
    """
    profile = str(input_file.get("wind_profile", "zero")).strip().lower()
    if profile not in ("zero", "constant", "log"):
        raise ValueError(
            f"Unsupported wind_profile '{profile}'. Valid values: 'zero', 'constant', 'log' "
            "('import' is not supported)."
        )

    velocity = _parse_number(input_file.get("const_wind_velocity", _WIND_DEFAULTS["const_wind_velocity"]),
                             "const_wind_velocity")
    direction = _parse_direction(input_file.get("const_wind_direction", _WIND_DEFAULTS["const_wind_direction"]))
    friction = _parse_number(input_file.get("friction_velocity", _WIND_DEFAULTS["friction_velocity"]),
                             "friction_velocity")
    roughness = _parse_number(input_file.get("surface_roughness", _WIND_DEFAULTS["surface_roughness"]),
                              "surface_roughness")
    if roughness <= 0:
        raise ValueError("surface_roughness must be > 0.")

    if profile == "zero":
        return {"type": "wind_profile", "class": "zero"}
    if profile == "constant":
        return {"type": "wind_profile", "class": "constant",
                "wind_vector": [float(c) for c in velocity * direction]}
    return {"type": "wind_profile", "class": "log",
            "friction_velocity": friction, "surface_roughness": roughness,
            "wind_direction": [float(c) for c in direction]}


def find_eigenrays(
    atmosphere_json: str,
    source_xyz: np.ndarray,
    receiver_xyz: np.ndarray,
    settings: dict,
) -> list[Eigenray]:
    """Find eigenrays between source and receiver through the given atmosphere.

    Parameters
    ----------
    atmosphere_json : str
        JSON string from create_atmosphere_json().
    source_xyz : array-like, shape (3,)
        Source position [x, y, z] in metres.
    receiver_xyz : array-like, shape (3,)
        Receiver position [x, y, z] in metres.
    settings : dict
        Eigenray search settings.  Recognised keys (all optional):
          maxReceiverRadius, maxReflectionOrder, maxPropagationTime,
          abortOnReceiverDistIncrease, maxSourceReceiverAngle,
          maxAngleForGeomSpreading, advancedRayZoomingActive,
          advancedRayZoomingThreshold, abortMaxNAdaptations,
          abortMinAngleResolution.

    Returns
    -------
    list[Eigenray]
        Typically [direct_ray, reflected_ray] for maxReflectionOrder=1.
    """
    src = list(np.asarray(source_xyz, dtype=float).ravel())
    rcv = list(np.asarray(receiver_xyz, dtype=float).ravel())

    ray_dicts, _num_traced = _load_art_core().find_eigenrays(
        atmosphere_json=atmosphere_json,
        source=src,
        receiver=rcv,
        eigenray_settings=settings,
    )

    return [_dict_to_eigenray(d) for d in ray_dicts]
