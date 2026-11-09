# Maintaining the ITA dependency

What this toolbox takes from ITAGeometricalAcoustics (ITA), at which versions,
what is changed locally, and how to move to a newer ITA. For building and
installing, see [BUILD.md](BUILD.md).

Versions recorded on **2026-11-09**. If this page and a pin disagree, the pin is
correct: the submodule commits, [dependency-lock.json](patches/ita/dependency-lock.json)
and [dependency-lock.cmake](patches/ita/dependency-lock.cmake) are what the build
uses.

**Contents**:
[Where versions are set](#where-versions-are-set) ·
[ITA packages](#ita-packages) ·
[Third-party libraries](#third-party-libraries) ·
[Toolchain and Python](#toolchain-and-python) ·
[Local patches](#local-patches) ·
[Patches ITA applies itself](#patches-ita-applies-itself) ·
[Moving to a newer ITA](#moving-to-a-newer-ita) ·
[Known gaps](#known-gaps)

---

## Where versions are set

| What | Set in | Checked by |
|---|---|---|
| ITA and its three nested repositories | git submodule commits | `git submodule status --recursive` |
| `IHTACMakeCommon` | `ITAGeometricalAcoustics.patch` | `verify_dependency_lock.py` |
| `ITACoreLibs` | `ITAGeo.patch` | `verify_dependency_lock.py` |
| `IHTAUtilityLibs`, `ViSTA`, `DSPFilters`, `openDAFF`, `pocketFFT` | `dependency-lock.cmake` | `verify_dependency_lock.py` |
| Libraries requested by tag | ITA's own CMake files | `verify_dependency_lock.py` |
| Plain archive downloads | ITA's own CMake files | nothing |
| nanobind | `requirements-build.txt` | nothing |
| Python runtime packages | `requirements.txt` (minimum versions only) | nothing |

---

## ITA packages

| Package | Version | Commit | Upstream `master` on 2026-11-09 | Used by ART |
|---|---|---|---|---|
| [ITAGeometricalAcoustics](https://git.rwth-aachen.de/ita/ITAGeometricalAcoustics) | `v2025a-1-g59dbdda` | `59dbdda81794` | **differs**: `655adb691ec1` | superproject |
| [ITAGeo](https://git.rwth-aachen.de/ita/ITAGeo) | `ITAGeo_v1.0.0` | `2e7ba6940589` | same | yes, built and linked |
| [ITAPropagationPathSim](https://git.rwth-aachen.de/ita/ITAPropagationPathSim) | `ITAPropagationPathSim_v1.0.0` | `8a4a3c337045` | same | yes, built and linked (contains the ray tracer) |
| [ITAPropagationModels](https://git.rwth-aachen.de/ita/ITAPropagationModels) | `ITAPropagationModels_v1.0.0` | `2b2dd664ecd9` | **differs**: `5193ea572a97` | configured only, not built |
| [ITACoreLibs](https://git.rwth-aachen.de/ita/ITACoreLibs) | branch `develop` | `b82d1daaf206` | **differs**: `bb1cdbeeb6fd` (the pin is still the tip of `develop`) | `ITABase` is linked |

All four submodule commits are dated 2025-09-17.

`_art_core` ([ARTPythonBindings.cpp](bindings/src/ARTPythonBindings.cpp)) links
`ITAGeo`, `ITAPropagationPathSim` and `ITABase`. It is the code most likely to
need changes after an ITA update, because it compiles directly against these:

- `ITAGeo::Utils::JSON` `Encode` / `Decode`, `CStratifiedAtmosphere`, the
  temperature, wind and humidity profile classes
- `EigenraySearch::CEngine`, `EigenraySearch::Settings` (`rayTracing`,
  `rayAdaptation.accuracy`, `rayAdaptation.advancedRayZooming`,
  `rayAdaptation.abort`)
- `Simulation::CEngine`, `Simulation::Settings` (`solverMethod`,
  `dIntegrationTimeStep`, `bMultiThreading`, `adaptiveIntegration`),
  `Simulation::CAbortAtMaxTime`
- `CRay`: `NumPoints`, `InitialDirection`, `SpreadingLoss`, `ReflectionOrder`,
  `ReceiverHit`, `IsEigenray`, `ReflectionIndices`
- `VistaVector3D`, which stores **single-precision** coordinates

[bindings/CMakeLists.txt](bindings/CMakeLists.txt) also hard-codes the include
paths `_deps/itacorelibs-src/ITABase/include` and `_deps/vista-src/VistaCoreLibs`.

---

## Third-party libraries

ITA downloads these during CMake configure. URLs and full commits are in
[dependency-lock.json](patches/ita/dependency-lock.json).

### Requested from a moving branch, pinned here

These change without notice if the pin is removed.

| Library | Upstream branch | Pinned commit |
|---|---|---|
| IHTACMakeCommon | `main` | `4e05d29dd759` |
| ITACoreLibs | `develop` in a submodule checkout | `b82d1daaf206` |
| IHTAUtilityLibs | `develop` | `773df1451ac5` |
| ViSTA | `feature/ita` | `29d83c51841d` |
| DSPFilters | `master` | `acc49170e79a` |
| openDAFF | `master` | `cda7126ccdc5` |
| pocketFFT | `cpp` | `32424d2067c2` |

### Requested by tag or fixed commit

| Library | Version | Commit | | Library | Version | Commit |
|---|---|---|---|---|---|---|
| assimp | `v5.2.5` | `9519a62dd207` | | nlohmann_json | `v3.10.1` | `7194245a314d` |
| cli11 | `v2.1.2` | `70f8072f9dd2` | | openmesh | `OpenMesh-8.1` | `db8c0608830a` |
| date | `v3.0.1` | `6e921e1b1d21` | | pkgproj | `v1.10.0` | `48db48207f16` |
| dtracksdk | `v2.7.0` | `8250c3356979` | | poly-scribe | `v1.0.0` | `352ef53047d0` |
| easy_profiler | `v2.1.0` | `046d9bd40cfd` | | portaudio | `v19.7.0-RC2` | `147dd7225483` |
| eigen | `3.4.0` | `3147391d946b` | | ppl_format | `v1.0.0` | `d75b6a6d0633` |
| format.cmake | `v1.7.2` | `282c3cb6be89` | | reflect-cpp | commit, set by poly-scribe | `c5f0a241c7ec` |
| glm | `1.0.1` | `0af55ccecd98` | | samplerate | `0.2.1` | `a147b6dc4046` |
| grpsrcbydir | `v1.0` | `784628b837d0` | | sndfile | `1.0.31` | `d60deb5d8691` |
| hdf5 | `hdf5-1.14.6` | `7bf340440909` | | spdlog | `v1.11.0` | `ad0e89cbfb4d` |
| jsoncons | `v1.3.0` | `68fafa1a6936` | | tbb | `v2021.3.0` | `261fe22630bd` |
| nanoflann | `v1.7.1` | `9a653cb243db` | | yaml-cpp | `0.8.0` | `f7320141120f` |
| netcdf-c | `v4.9.3` | `3a6b1debf155` | | zlib | `v1.2.13` | `04f42ceca40f` |
| netcdf-cxx4 | `v4.3.1` | `f88821882674` | | | | |

### Plain archive downloads

No commit and no checksum. Requested by ITACoreLibs or IHTAUtilityLibs.

| Library | Version | Source |
|---|---|---|
| fftw | 3.3.9 | `http://fftw.org/fftw-3.3.9.tar.gz` |
| pcre | 8.45 | `sourceforge.net/projects/pcre/files/pcre/8.45/` |
| NatNet SDK | 2.10 | `s3.amazonaws.com/naturalpoint/software/NatNetSDK/NatNet_SDK_2.10.zip` |
| oscpkt | 1.2 | `http://gruntthepeon.free.fr/oscpkt/oscpkt-1.2.tar.gz` |
| Steinberg ASIO SDK | 2.3.4 when last fetched | `https://www.steinberg.net/asiosdk`, an **unversioned** URL |

---

## Toolchain and Python

| Component | Version |
|---|---|
| Compiler | Visual Studio 2019 Build Tools, MSVC v142 (19.29). Only VS 2019 is supported. |
| CMake | 3.27.9 (3.24 or newer required; newer than 3.27 untested) |
| Python | 3.13.2. The compiled module works on this minor version only. |
| nanobind | 2.13.0 (3.x untested) |

The current `bin/` module was built with the system Python 3.13.2, which has
nanobind 2.13.0. The repository's `.venv` does not have nanobind installed.

Python runtime packages. `requirements.txt` sets the minimum; the last column is
what the repository's `.venv` had installed on 2026-11-09.

| Package | Minimum | Installed |
|---|---|---|
| numpy | 1.24 | 2.4.6 |
| scipy | 1.15 (`sph_harm_y` is needed for HRTF interpolation) | 1.18.0 |
| matplotlib | 3.7 | 3.11.0 |
| sofar | 1.1 | 1.2.3 |
| customtkinter | 5.2 | 6.0.0 |

---

## Local patches

ITA is a git submodule, so changes to it live in [patches/ita/](patches/ita/) and
are replayed by `tools/apply_ita_patches.ps1`.
`ITAPropagationPathSim` has no local changes, so the **ray-tracing code is
unmodified upstream code**. Every local change is to build configuration.

All patches below were confirmed applied, and the checkout has no other edits
(line endings aside; on Windows `git status` shows many files as modified because
of them).

### `ITAGeometricalAcoustics.patch` (applied to the superproject)

| File | Change | Why | If upstream changes it |
|---|---|---|---|
| `CMakePresets.json`, `conf-common` | sets `CMAKE_PROJECT_TOP_LEVEL_INCLUDES` to `${sourceDir}/../patches/ita/dependency-lock.cmake` | Loads the lock. The path requires ITA to be at the repository root. | **Required.** Without it the five libraries in the lock float. |
| `CMakePresets.json`, `conf-full` | turns off `ITA_GEOMETRICAL_ACOUSTICS_WITH_APPS`, `_APPS_QT`, `_APPS_MATLAB`, `ITA_PROPAGATION_MODELS_WITH_APPS` | The apps need Qt and MATLAB. | Required unless Qt and MATLAB are available. |
| `CMakePresets.json` | adds `conf-minimal`, `minimal-win-vs-msvc`, `minimal-release-vs` | Core-engine-only configuration. | Optional; the default build does not use it. |
| `CMakeLists.txt` | pins `IHTACMakeCommon` (was `main`) | Reproducibility. Fetched before `project()`, so the lock file cannot reach it. | **Required.** Update the commit. |

### `ITAGeo.patch` (applied to `ITAGeo/`)

| File | Change | Why | If upstream changes it |
|---|---|---|---|
| `CMakeLists.txt` | `if (WIN32)` becomes `if (WIN32 AND SketchUpAPI_FOUND)` | Without SketchUp, CMake stops on a property set on a target that does not exist. | Drop if upstream adds the guard. |
| `external_libs/CMakeLists.txt` | adds `netcdf-cxx4` v4.3.1 with the local `netcdf-cxx4.patch`, at the top of the file | ITAGeo is added first, and the first CPM request for a package wins, so this patched version replaces the unpatched request that remains in `ITAPropagationModels`. | Required while upstream's target publishes an absolute include path. |
| `external_libs/CMakeLists.txt` | pins `ITACoreLibs` (was `${CORE_LIBS_BRANCH}`), `GIT_SHALLOW FALSE` | Reproducibility. | **Required.** Update the commit. |

### `ITAPropagationModels.patch` (applied to `ITAPropagationModels/`)

| File | Change | Why | If upstream changes it |
|---|---|---|---|
| `apps/pelican/CMakeLists.txt` | removes `netcdf-cxx4` from `target_link_libraries` | Keeps the configure step working with the single patched `netcdf-cxx4`. | Check that it is still needed. |
| `external_libs/CMakeLists.txt` | removes the `if (netcdf-cxx4_ADDED)` block | The same. | Check that it is still needed. |

### Files copied into ITA, from `patches/ita/files/`

| File | Status | Purpose |
|---|---|---|
| `ITAGeo/external_libs/patches/netcdf-cxx4.patch` | **used** | Removes `INCLUDE_DIRECTORIES(".")` and wraps the include directory in `$<BUILD_INTERFACE:>` / `$<INSTALL_INTERFACE:include>`, because CMake rejects an absolute source-tree include path in an installable target. |
| `ITAGeo/external_libs/fix-netcdf-cxx4.cmake` | unused | An earlier script version of the same fix. |
| `ITAPropagationModels/external_libs/patches/netcdf-cxx4.patch` | unused | An earlier copy of the same fix, with paths relative to `cxx4/`. |

`netcdf-cxx4` is configured but never compiled for ART, so its changes only need
to keep CMake's configure and generate steps working.

### `dependency-lock.cmake`

It declares `IHTAUtilityLibs`, `vista`, `DSPFilters`, `openDAFF` and `pocketFFT`
with `CPMDeclarePackage`. CPM then uses the declared arguments **instead of** the
ones in the original request, so each declaration must repeat everything upstream
passes (`DOWNLOAD_ONLY`, `PATCHES`, ...) with only the tag changed. The `vista`
entry also hard-codes the location of `vista.patch` inside ITACoreLibs.

---

## Patches ITA applies itself

These are not in this repository. They ship with ITA or its libraries and are
applied automatically, but a pin change can break them: each must still match the
pinned source of the library it patches.

| Patch | Shipped in | Applied to | What it does |
|---|---|---|---|
| `vista.patch` | ITACoreLibs, `ITABase/external_libs/patches/` | ViSTA | Removes `std::unary_function` and similar for newer C++ |
| `namspace_alias.patch` | ITACoreLibs, `ITADSP/external_libs/patches/` | DSPFilters | Removes the `std::tr1` namespace alias |
| `nanoflann.patch` | IHTAUtilityLibs, `IHTADirectivity/external_libs/patches/` | nanoflann | Fixes the `uninstall` target clash |
| `netcdf.patch` | IHTAUtilityLibs, `IHTADirectivity/external_libs/patches/`; a variant in `ITAPropagationModels/external_libs/patches/` | netcdf-c | Build fixes when netcdf-c is a sub-project |
| `reflect-cpp.patch` | poly-scribe, `external-patches/` | reflect-cpp | Fixes YAML null handling |

---

## Moving to a newer ITA

**Work in a fresh clone.** Never configure or build in an existing working
`ITAGeometricalAcoustics/out` tree: re-configuring it re-runs patch steps that
cannot run twice, and `-CleanIta` deletes it.

1. **Move the submodules** in the fresh clone.

   ```powershell
   git -C ITAGeometricalAcoustics fetch --tags
   git -C ITAGeometricalAcoustics checkout <new-commit>
   git submodule update --init --recursive
   ```

2. **Re-apply the patches** with `tools/apply_ita_patches.ps1`. On `[FAIL]`, make
   the change by hand using the tables [above](#local-patches), then regenerate
   the patch (see "Regenerating a patch" in [BUILD.md](BUILD.md#regenerating-a-patch)).
3. **Compare upstream's requests with the lock.** Read the `CPMAddPackage` calls
   for the five libraries in `dependency-lock.cmake` in the new ITACoreLibs and
   IHTAUtilityLibs. Copy any changed or new arguments. If a library was renamed,
   update its `NAME`.
4. **Choose the new commits for the seven moving libraries** and update them in
   `ITAGeometricalAcoustics.patch`, `ITAGeo.patch` and `dependency-lock.cmake`.
5. **Configure and update the lock file.** Run `tools/build_art.ps1`. It stops at
   the verifier if anything differs. Review each `DRIFT` line, then update
   `dependency-lock.json`.
   - Expect `0 not fetched`. A rename shows up there, and the verifier still
     passes.
   - Compare `_deps/*-src` with the lock by hand. The verifier only reads the
     lock, so a **new** dependency is not reported.
   - If a re-run fails with `Reversed (or previously applied) patch`, use
     `-CleanIta` (in the fresh clone only).
6. **Fix the bindings** if the [ITA API](#ita-packages) changed, then finish the
   build.
7. **Check the results, not just the build.** Compare eigenrays against the
   previous build across geometries, atmospheres and wind profiles; the current
   build was bit-for-bit identical on 72 rays. Then run
   `python verification/run_all_verifications.py`. Any numerical difference needs
   an explanation before the update is accepted.
8. **Record the update**: commit the new submodule pointer and patches, update this
   page and the tables in `BUILD.md`, and republish `art-win-amd64-py313.zip`.

---

## Known gaps

- **Archives are not checksummed** and could change or disappear. fftw and oscpkt
  use plain HTTP, and oscpkt is on a personal host.
- **The ASIO SDK URL has no version**, so a fresh build may get a different one.
- **Tags are trusted at fetch time.** The verifier catches a moved tag only by
  comparing commits after a configure.
- **Python runtime packages have no upper bounds**, so a new install can get newer
  versions than those listed here.
- **Only tested on Windows.**
