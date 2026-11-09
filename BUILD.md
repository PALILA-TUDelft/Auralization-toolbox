# Building and installing ART

The propagation stage needs **ART** (Atmospheric Ray Tracing), a C++ eigenray
solver from [ITAGeometricalAcoustics](https://git.rwth-aachen.de/ita/ITAGeometricalAcoustics)
(ITA, RWTH Aachen University, Apache-2.0). This toolbox reaches it through a
small [nanobind](https://nanobind.readthedocs.io/) module, `_art_core`
([bindings/src/ARTPythonBindings.cpp](bindings/src/ARTPythonBindings.cpp)).

Everything else in the toolbox runs without ART. The native module is loaded
the first time a ray is traced, so a machine without it imports and runs fine
up to that point.

This page is the complete reference. The README has a short version.

**Contents**:
[Choosing an option](#choosing-an-option) ·
[Tested environment](#tested-environment) ·
[Option A: prebuilt binaries](#option-a-prebuilt-binaries-windows-python-313) ·
[Option B: build on Windows](#option-b-build-from-source-on-windows) ·
[Option C: macOS and Linux](#option-c-build-from-source-on-macos-and-linux) ·
[Check the installation](#check-the-installation) ·
[Reproducibility](#reproducibility) ·
[Local changes to ITA](#local-changes-to-ita) ·
[Troubleshooting](#troubleshooting) ·
[For maintainers](#for-maintainers)

---

## Choosing an option

| You have | Use | Effort |
|---|---|---|
| Windows x64 and **Python 3.13** | [Option A](#option-a-prebuilt-binaries-windows-python-313) (the binaries are in the repository) | none: `git clone` is enough |
| Windows x64 and another Python version | [Option B](#option-b-build-from-source-on-windows) | long build, about 25 minutes |
| macOS or Linux | [Option C](#option-c-build-from-source-on-macos-and-linux) | long build, **not yet verified** |
| no need for propagation | nothing to install | none |

The compiled module is tied to the Python minor version it was built with:
`_art_core.cp313-win_amd64.pyd` loads on Python 3.13 and on nothing else.

## Tested environment

Everything below was verified by cloning the repository from scratch into a new
folder, creating a new virtual environment and running `tools/build_art.ps1`, on
the machine described under [Option B](#option-b-build-from-source-on-windows).
It has not been tried on a different computer.

| Component | Version |
|---|---|
| OS | Windows 11 x64 |
| Compiler | **Visual Studio 2019** Build Tools, MSVC v142 (19.29) |
| CMake | 3.27.9 (3.24 or newer is required; see [Troubleshooting](#troubleshooting)) |
| git | 2.39 |
| Python | 3.13.2 |
| nanobind | 2.13.0 (pinned in `requirements-build.txt`) |
| ITAGeometricalAcoustics | `ITAGeometricalAcoustics_v2025a-1-g59dbdda` (git submodule) |
| Build | Release, shared libraries |

**Only Visual Studio 2019 is supported.** ITA's CMake preset hard-codes the
`Visual Studio 16 2019` generator, and `tools/build_art.ps1` checks for it
before doing anything else.

### What was verified

| Check | Result |
|---|---|
| Fresh `git clone --recurse-submodules`, new virtual environment, `build_art.ps1` | succeeds, about 25 minutes |
| Every fetched dependency against the lock | 34 of 34 at the locked commit |
| Eigenrays from this build against the original development build, 36 cases (4 geometries, 3 atmospheres, no/constant/logarithmic wind) | 72 of 72 rays bit-for-bit identical |
| `bin/` against the original build | the same 15 files, the same sizes |
| Running `build_art.ps1` a second time | succeeds in about a minute |
| `apply_ita_patches.ps1` and `apply_ita_patches.sh` on a pristine checkout, then again | both patch it, then skip |
| Option A: a copy of the repository with no `bin/` and no build tree, only `prebuilt/win-x64-py313/` | ART becomes available and traces rays (`2 [0, 1]`) |
| macOS and Linux (Option C) | **not tested** |

---

## Option A: prebuilt binaries (Windows, Python 3.13)

> **Python 3.13 only.** The folder contains `_art_core.cp313-win_amd64.pyd`,
> which Python 3.13 on 64-bit Windows can load and no other version can. For any
> other Python version use [Option B](#option-b-build-from-source-on-windows).

The compiled binaries are stored in the repository, in
[prebuilt/win-x64-py313/](prebuilt/win-x64-py313/) (15 files, about 13 MB). Nothing
is downloaded and nothing is compiled:

1. `git clone` the repository. The `--recurse-submodules` flag is **not** needed
   for this option, because ITA itself is only needed to build.
2. Install the **Microsoft Visual C++ Redistributable (x64), version 14.29 or
   newer**, if it is not already on the machine. The binaries need `vcruntime140.dll`,
   `vcruntime140_1.dll`, `msvcp140.dll` and `vcomp140.dll`, which it provides.
   (Python itself usually installs it.)
3. [Check the installation](#check-the-installation).

The toolbox finds `prebuilt/win-x64-py313/` automatically, as long as the Python
that runs it is 3.13 on 64-bit Windows. Where the files came from, their SHA-256
sums and their licenses are in [prebuilt/README.md](prebuilt/README.md) and
[prebuilt/THIRD_PARTY_LICENSES.txt](prebuilt/THIRD_PARTY_LICENSES.txt).

A build you make yourself goes into `bin/`, which is searched first, so it
overrides the committed files without touching them.

## Option B: build from source on Windows

### 1. Prerequisites

| Tool | Notes |
|---|---|
| **Build Tools for Visual Studio 2019** | Install the workload **Desktop development with C++** (it includes MSVC v142). Nothing else is needed. |
| CMake | **3.27.9** was used. 3.24 or newer is required; versions newer than 3.27 are untested. |
| git | Long path support is recommended (`git config --system core.longpaths true`). |
| Python | The module only runs on the Python version it was built with, so build it with the interpreter you will run the toolbox with. 3.13.2 was tested. |
| Disk | About 5 GB free. The ITA build directory alone is 3.6 GB. |
| Network | Outbound HTTPS to: `fftw.org`, `git.code.sf.net`, `git.rwth-aachen.de`, `github.com`, `gitlab.com`, `gitlab.mpcdf.mpg.de`, `gitlab.vci.rwth-aachen.de:9000`, `s3.amazonaws.com`, `sourceforge.net`, `steinberg.net`, `www.graphics.rwth-aachen.de:9000`. See [Troubleshooting](#troubleshooting) for the port-9000 host. |

### 2. Build

Use a PowerShell prompt, with the virtual environment you will run the toolbox
from **activated** (the build uses the `python` that is first on `PATH`):

```powershell
git clone --recurse-submodules https://github.com/<owner>/Auralization-toolbox
cd Auralization-toolbox
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt -r requirements-build.txt
powershell -ExecutionPolicy Bypass -File tools\build_art.ps1
```

If you cloned without `--recurse-submodules`, run
`git submodule update --init --recursive` first (the script does this too).

`tools/build_art.ps1` does, in order:

1. checks for Visual Studio 2019, git, CMake, Python and nanobind, and stops
   with an explanation if one is missing;
2. initialises the submodules;
3. applies the [local ITA changes](#local-changes-to-ita)
   (`tools/apply_ita_patches.ps1`);
4. configures ITA with the `full-win-vs-msvc` preset, then **verifies that every
   fetched dependency is the locked commit** ([Reproducibility](#reproducibility))
   and stops if not;
5. builds the two ITA libraries ART needs, `ITAGeo` and `ITAPropagationPathSim`,
   together with everything they depend on, in Release. **It does not build all
   of ITA** (see the note below);
6. builds `_art_core` against it, with the same Visual Studio 2019 generator and
   the Python from your `PATH`;
7. copies the module and the ITA DLLs into `bin/`;
8. imports the module to confirm it works.

> **Build only those two targets.** Building the whole ITA tree also builds its
> applications and `netcdf-cxx4`, which ART does not use and which does not
> compile in this configuration (`Cannot open include file: 'netcdf.h'`). If you
> drive CMake yourself, use
> `cmake --build <dir> --config Release --target ITAGeo ITAPropagationPathSim`.

Options: `-SkipIta` rebuilds only `_art_core` against an existing ITA build;
`-Clean` deletes the bindings build tree first; `-CleanIta` deletes the ITA build
tree so ITA is configured from scratch; `-Preset <name>` picks another ITA preset.

The script can be run again at any time. Once ITA has been configured it
re-configures in *local-only* mode (see
[Re-running the build](#re-running-the-build)) and only rebuilds what changed.

Afterwards, [check the installation](#check-the-installation).

### Re-running the build

CMake re-runs the **patch step** of every patched dependency (`vista`,
`nanoflann`, `netcdf-c`, `netcdf-cxx4`, `reflect-cpp`) each time it configures,
and a patch cannot be applied twice. Re-configuring a tree whose dependencies
are already downloaded therefore fails with:

```text
Reversed (or previously applied) patch detected!  Assume -R? [n]
Skipping patch.
```

The build scripts avoid this: once ITA has been configured (the script writes
`.configured-ok` into the build directory, and a tree that already contains
`ITAGeo.lib` counts too), they re-configure with
`-DFETCHCONTENT_FULLY_DISCONNECTED=ON`, which fetches and patches nothing. A
configure then takes under a minute. If you run CMake yourself on an existing
tree, pass the same option.

The one case this cannot cover is a **first configure that was interrupted**
(network error, Ctrl+C): the half-populated tree has some dependencies patched
and others not. Run the script again with `-CleanIta` (`--clean-ita` for
`build_art.sh`) to configure ITA from scratch.

## Option C: build from source on macOS and Linux

> **Not verified.** ITA is tested upstream on Windows only (every job in its CI
> runs on a Windows runner). The path below is written out in full and was
> reviewed against the dependency sources, but it has **not been run on macOS or
> Linux**. Treat the first build as a porting exercise, and please report what
> you find.

```bash
# macOS:   xcode-select --install && brew install cmake ninja gpatch libomp
# Debian:  sudo apt install build-essential cmake ninja-build patchelf

git clone --recurse-submodules https://github.com/<owner>/Auralization-toolbox
cd Auralization-toolbox
python3 -m venv .venv && source .venv/bin/activate
python -m pip install -r requirements.txt -r requirements-build.txt
bash tools/build_art.sh      # or ./tools/build_art.sh once the file is executable
```

`build_art.sh` mirrors the PowerShell script. It uses the ITA presets
`full-mac-ninja-clang` / `full-linux-ninja-gcc` (added by the local changes),
and takes `--skip-ita`, `--clean` and `--preset <name>`. It runs under the
bash 3.2 that macOS ships.

Differences from Windows that the build accounts for:

- **OpenMP.** `ITAPropagationPathSim` needs OpenMP, which Apple's clang does not
  include. `build_art.sh` uses Homebrew's `libomp` (`brew install libomp`) and tells
  CMake where it is. The built libraries then depend on that `libomp.dylib`, so
  a Mac that runs them needs `libomp` installed too.
- **GNU patch.** CMake applies the dependency patches with the first `patch` on
  the machine. On macOS that is Apple's BSD patch, which rejects this
  repository's patches with `2 out of 2 hunks failed` (the patch files have CRLF
  line endings, the sources they change have LF). `build_art.sh` therefore needs
  GNU patch (`brew install gpatch`) and passes it to CMake as `PATCH_EXECUTABLE`.
  Linux and Git for Windows already ship GNU patch.
- **Profiler library.** IHTAUtilityLibs asks for a folder `IHTAPROFILER` that is
  really named `IHTAProfiler`: fine on Windows and on a default macOS file system,
  an error on Linux. `build_art.sh` configures with `-DWITH_IHTA_PROFILER=OFF`; ART
  does not use it.
- **Tracking library.** ITA's IHTAUtilityLibs also builds a motion-tracking
  library that needs the OptiTrack NatNet SDK, which exists for Windows only.
  `build_art.sh` configures with `-DWITH_IHTA_TRACKING=OFF`; ART does not use it
  (it is not among the files in `bin/`). Without the switch, configuring stops
  with `Could not find a package configuration file provided by "NatNetSDK"`.
  If you run CMake by hand, pass the same switch.
- **Library lookup.** Windows is told where the DLLs are when the module is
  imported. macOS and Linux resolve shared libraries through a path stored in the
  module when it is linked, so the module is linked with `@loader_path` (macOS) /
  `$ORIGIN` (Linux), and `build_art.sh` makes the staged libraries relocatable
  with `install_name_tool` / `patchelf`. `DYLD_LIBRARY_PATH` is deliberately not
  used: macOS strips it for protected processes.
- **Library names.** `bindings/CMakeLists.txt` finds the ITA libraries by name
  with `find_library`, so `.dylib` and `.so` are picked up as well as `.lib`.
- **Vista.** ITA's Vista library has native macOS timer code that its own CMake
  never enables, so it compiles the generic POSIX branch (`clock_gettime`),
  which macOS 10.12+ has. **Do not define Vista's `DARWIN` macro** for the
  bindings alone: that changes the layout of one of Vista's classes and gives an
  ABI mismatch against the ITA libraries.

If importing fails after a successful build, look at the library paths:

```bash
otool -L bin/_art_core*.so      # macOS
ldd      bin/_art_core*.so      # Linux
```

Anything that still points into a build directory, or a missing `@loader_path` /
`$ORIGIN` entry, means the relocation step did not take.

## Check the installation

```python
from auralization.private.propagation.art_bindings import art_core_available
print(art_core_available())          # True if ART was found
```

A real ray trace, which should print `2 [0, 1]` (the direct ray and one ground
reflection):

```python
from auralization.private.propagation.art_bindings import create_atmosphere_json, find_eigenrays
rays = find_eigenrays(create_atmosphere_json(), [0, 0, 300], [500, 0, 2], {"maxReflectionOrder": 1})
print(len(rays), [r.numReflections for r in rays])
```

The toolbox looks for the binaries in this order, and uses the first that works:

1. the directories in the environment variables `ART_DLL_DIR` (the ITA libraries)
   and `ART_PYD_DIR` (`_art_core`);
2. `bin/` in the repository root (what `build_art.ps1` / `build_art.sh` write);
3. `prebuilt/<platform>-py<version>/`, the binaries committed to the repository
   (`prebuilt/win-x64-py313/` on Windows x64 with Python 3.13);
4. the in-tree build output (`ITAGeometricalAcoustics/out/build/<preset>/Release`
   and `bindings/build`).

---

## Reproducibility

Building ITA downloads about 40 libraries (34 from git and 4 plain archives). Left alone, **the result depends on
the day you build**, because several of them are requested from a *branch*, not
a version: whatever the branch contains at that moment is what you get. This
repository pins them, and checks that the pins held.

### What is pinned and how

ITA fetches its dependencies with CPM/FetchContent from three kinds of source:

- **Git, by tag.** Left as the tag. The full list with the resolved commits is
  [below](#locked-dependencies).
- **Git, by branch. These are the ones that move.** Seven of them:
  `IHTACMakeCommon` (`main`), `ITACoreLibs` (`develop`, chosen because a
  submodule checkout is normally detached, not on `master`), `IHTAUtilityLibs` (`develop`),
  `ViSTA` (`feature/ita`), `DSPFilters` (`master`), `openDAFF` (`master`) and
  `pocketFFT` (`cpp`). All seven are pinned to the commit of the working build:
  - `IHTACMakeCommon` is fetched before CMake's `project()` call, so it is pinned
    by editing ITA's top-level `CMakeLists.txt`.
  - `ITACoreLibs` is pinned by editing `ITAGeo/external_libs/CMakeLists.txt`.
  - The other five are requested from *inside* ITACoreLibs and IHTAUtilityLibs,
    which cannot be edited, so [patches/ita/dependency-lock.cmake](patches/ita/dependency-lock.cmake)
    declares them with `CPMDeclarePackage`. CPM then uses the declared arguments
    instead of the library's own. The file is loaded through
    `CMAKE_PROJECT_TOP_LEVEL_INCLUDES`, which the ITA presets set (CMake 3.24+).
- **Plain downloads (not git).** `fftw` 3.3.9 (`fftw.org`), `pcre` 8.45
  (`sourceforge.net`), the Steinberg ASIO SDK (`steinberg.net`) and NatNet SDK
  2.10 (`s3.amazonaws.com`). These are fixed versions but are **not
  checksummed**: if one of those hosts changes or removes a file, the build will
  fail or change. This is the one remaining gap.

**Use the presets.** The lock is wired into ITA's CMake presets. If you
configure ITA by hand without `--preset`, nothing is pinned.

### Verifying

`build_art.ps1` and `build_art.sh` run this right after configuring ITA and
stop if anything differs. You can run it yourself at any time:

```bash
python tools/verify_dependency_lock.py                # default build directory
python tools/verify_dependency_lock.py <ita-build-dir>
```

It compares every fetched dependency with
[patches/ita/dependency-lock.json](patches/ita/dependency-lock.json) and prints
`34 match, 0 drifted, 0 not fetched in this configuration.` when all is well.

### Locked dependencies

| Dependency | Source | Pinned to | Commit |
|---|---|---|---|
| assimp | github.com/assimp/assimp | tag `v5.2.5` | `9519a62dd207` |
| cli11 | github.com/CLIUtils/CLI11 | tag `v2.1.2` | `70f8072f9dd2` |
| date | github.com/HowardHinnant/date | tag `v3.0.1` | `6e921e1b1d21` |
| dspfilters | github.com/vinniefalco/DSPFilters | commit pinned in `dependency-lock.cmake` | `acc49170e79a` |
| dtracksdk | github.com/ar-tracking/DTrackSDK | tag `v2.7.0` | `8250c3356979` |
| easy_profiler | github.com/yse/easy_profiler | tag `v2.1.0` | `046d9bd40cfd` |
| eigen | gitlab.com/libeigen/eigen | tag `3.4.0` | `3147391d946b` |
| format.cmake | github.com/TheLartians/Format.cmake | tag `v1.7.2` | `282c3cb6be89` |
| glm | github.com/g-truc/glm | tag `1.0.1` | `0af55ccecd98` |
| grpsrcbydir | github.com/TheLartians/GroupSourcesByFolder.cmake | tag `v1.0` | `784628b837d0` |
| hdf5 | github.com/HDFGroup/hdf5 | tag `hdf5-1.14.6` | `7bf340440909` |
| ihtacmakecommon | git.rwth-aachen.de/ihta/cmake/ihtacmakecommon | commit pinned by `ITAGeo.patch` / `ITAGeometricalAcoustics.patch` | `4e05d29dd759` |
| ihtautilitylibs | git.rwth-aachen.de/ita/ihtautilitylibs | commit pinned in `dependency-lock.cmake` | `773df1451ac5` |
| itacorelibs | git.rwth-aachen.de/ita/ITACoreLibs | commit pinned by `ITAGeo.patch` / `ITAGeometricalAcoustics.patch` | `b82d1daaf206` |
| jsoncons | github.com/danielaparker/jsoncons | tag `v1.3.0` | `68fafa1a6936` |
| nanoflann | github.com/jlblancoc/nanoflann | tag `v1.7.1` | `9a653cb243db` |
| netcdf-c | github.com/Unidata/netcdf-c | tag `v4.9.3` | `3a6b1debf155` |
| netcdf-cxx4 | github.com/Unidata/netcdf-cxx4 | tag `v4.3.1` | `f88821882674` |
| nlohmann_json | github.com/nlohmann/json | tag `v3.10.1` | `7194245a314d` |
| opendaff | git.code.sf.net/p/opendaff/git | commit pinned in `dependency-lock.cmake` | `cda7126ccdc5` |
| openmesh | www.graphics.rwth-aachen.de:9000/OpenMesh/OpenMesh | tag `OpenMesh-8.1` | `db8c0608830a` |
| pkgproj | github.com/TheLartians/PackageProject.cmake | tag `v1.10.0` | `48db48207f16` |
| pocketfft | gitlab.mpcdf.mpg.de/mtr/pocketfft | commit pinned in `dependency-lock.cmake` | `32424d2067c2` |
| poly-scribe | github.com/pingelit/poly-scribe | tag `v1.0.0` | `352ef53047d0` |
| portaudio | github.com/PortAudio/portaudio | tag `v19.7.0-RC2` | `147dd7225483` |
| ppl_format | git.rwth-aachen.de/ihta/simulation/propagation-path-list | tag `v1.0.0` | `d75b6a6d0633` |
| reflect-cpp | github.com/getml/reflect-cpp | commit (pinned by the requesting project) | `c5f0a241c7ec` |
| samplerate | github.com/libsndfile/libsamplerate | tag `0.2.1` | `a147b6dc4046` |
| sndfile | github.com/libsndfile/libsndfile | tag `1.0.31` | `d60deb5d8691` |
| spdlog | github.com/gabime/spdlog | tag `v1.11.0` | `ad0e89cbfb4d` |
| tbb | github.com/oneapi-src/oneTBB | tag `v2021.3.0` | `261fe22630bd` |
| vista | git.rwth-aachen.de/ita/ViSTA | commit pinned in `dependency-lock.cmake` | `29d83c51841d` |
| yaml-cpp | github.com/jbeder/yaml-cpp | tag `0.8.0` | `f7320141120f` |
| zlib | github.com/madler/zlib | tag `v1.2.13` | `04f42ceca40f` |

### Updating the lock

Only do this deliberately, for example when moving to a newer ITA release. Build
once without the lock, then regenerate `dependency-lock.json` and the commits in
`dependency-lock.cmake` from the new `_deps` tree, and re-run the verifier.

---

## Local changes to ITA

ITA is a git submodule, which records only an upstream commit, so changes to it
cannot be committed here. They are kept as patches in [patches/ita/](patches/ita/)
and applied by `tools/apply_ita_patches.ps1` (`.sh` on macOS/Linux). The scripts
are safe to run repeatedly: a patch that is already applied is skipped. They
apply with `--ignore-whitespace`, so they work whether the submodule was checked
out with LF or CRLF line endings.

| File | Change | Why |
|---|---|---|
| `ITAGeometricalAcoustics.patch` | `conf-full` turns off `ITA_GEOMETRICAL_ACOUSTICS_WITH_APPS`, `_APPS_QT`, `_APPS_MATLAB` and `ITA_PROPAGATION_MODELS_WITH_APPS` | The apps need Qt and MATLAB and are not needed for ART. |
| | adds the `minimal-win-vs-msvc` preset | A configuration for the core engine only. |
| | adds the `full-mac-ninja-clang` and `full-linux-ninja-gcc` presets | Used by `build_art.sh`. Untested. |
| | sets `CMAKE_PROJECT_TOP_LEVEL_INCLUDES` | Loads the dependency lock. |
| | pins `IHTACMakeCommon` in `CMakeLists.txt` | Reproducibility. |
| `ITAGeo.patch` | `if (WIN32)` becomes `if (WIN32 AND SketchUpAPI_FOUND)` | The SketchUp library is optional. Without this guard the build sets a property on a target that does not exist and CMake stops. |
| | adds `netcdf-cxx4` v4.3.1 with `netcdf-cxx4.patch` | netcdf-cxx4 is needed by ITA; the patch below is applied to it. |
| | pins `ITACoreLibs` | Reproducibility. |
| `ITAGeo-unix.patch` | downloads and uses `FindSketchUpAPI.cmake` only `if (WIN32)` | Its Find module stops with `SketchUpAPI is only available on Win/Mac` on Linux, and SketchUp is not used outside Windows. |
| | guards `set_property (TARGET UpdateAssimpLibsDebugSymbolsAndDLLs ...)` with `if (TARGET ...)` | assimp defines that target only in its MSVC build; elsewhere CMake stops with `set_property could not find TARGET`. No effect on Windows. |
| `ITAPropagationModels.patch` | removes the `netcdf-cxx4` link and target setup from `pelican` and `external_libs` | The dependency is now defined once, in ITAGeo. |
| `files/ITAGeometricalAcoustics/integration/pkg-config/tbb.pc.in` | copied into the ITA root (a copy of the file from oneTBB v2021.3.0) | Outside Windows, oneTBB reads `${CMAKE_SOURCE_DIR}/integration/pkg-config/tbb.pc.in`, which only exists when oneTBB is the top-level project. Without the copy CMake stops with `File ... tbb.pc.in does not exist`. |
| `files/.../netcdf-cxx4.patch` | removes `INCLUDE_DIRECTORIES(".")` and wraps the include directory in `$<BUILD_INTERFACE:>` / `$<INSTALL_INTERFACE:include>` | The upstream target publishes an absolute source-tree include path, which CMake does not allow in an installable target. |

`netcdf-cxx4` is configured but **never compiled** for ART: the build only
builds `ITAGeo` and `ITAPropagationPathSim`. The `netcdf-cxx4` changes therefore
exist to keep the CMake configure and generate steps working, not the compile.

Two files are installed but not used by the current build and are kept only for
reference: `files/ITAGeo/external_libs/fix-netcdf-cxx4.cmake` and
`files/ITAPropagationModels/external_libs/patches/netcdf-cxx4.patch`.

---

## Troubleshooting

Each entry is a problem that was met while developing this build, and its fix.

**`ART module not found` / `_art_core could not be imported`.** The message lists
every directory that was searched. The usual causes:

- *Wrong Python.* `_art_core.cp313-win_amd64.pyd` loads on Python 3.13 only. Check
  `python --version`; for another version, build with [Option B](#option-b-build-from-source-on-windows)
  using that interpreter.
- *`DLL load failed`.* Install the Microsoft Visual C++ Redistributable (x64),
  14.29 or newer (Option A, step 2).
- *Not 64-bit.* The binaries are x64 only.
- *A stale or mixed build.* Delete `bin/` and run the build again, or set
  `ART_DLL_DIR` and `ART_PYD_DIR` explicitly to one directory that has all the
  files. The toolbox uses one directory for the module and one for the DLLs, the
  first that contains them, in the order given under [Check the installation](#check-the-installation).

**`build_art.ps1` says Visual Studio 2019 was not found.** Install *Build Tools for
Visual Studio 2019* with the workload **Desktop development with C++**. Newer
Visual Studio versions are not a substitute: ITA's preset asks for the
`Visual Studio 16 2019` generator by name.

**`Reversed (or previously applied) patch detected`** while configuring ITA.
An earlier configure was interrupted (network error, Ctrl+C), which leaves a
half-finished tree that cannot be patched a second time. Run
`tools\build_art.ps1 -CleanIta` (`./tools/build_art.sh --clean-ita`) to configure
ITA from scratch. A tree that configured completely is re-used safely: the script
re-configures it in local-only mode, so nothing is fetched or patched again.

**`netcdf.h` not found.** This happens when everything in ITA is built, including
its apps and `netcdf-cxx4`, which ART does not use and which does not compile in
this configuration. `build_art.ps1` builds only the two libraries ART needs
(`ITAGeo`, `ITAPropagationPathSim`). If you build by hand, use
`cmake --build <dir> --config Release --target ITAGeo ITAPropagationPathSim`.

**A download fails during configure.** The build fetches from the hosts listed in
[Prerequisites](#1-prerequisites). Two of them, `gitlab.vci.rwth-aachen.de` and
`www.graphics.rwth-aachen.de` (OpenMesh), are on **port 9000**, which firewalls
and proxies commonly block, and the OpenMesh one answers with a redirect. If
that is where it stops, allow outbound HTTPS on port 9000, or build on another
network. Run the script again afterwards; use `-CleanIta` if the message
mentions "previously applied".

**`N drifted` in the dependency lock check.** A dependency was fetched at a
different commit than `patches/ita/dependency-lock.json` records. The build
stops there on purpose. See [Reproducibility](#reproducibility), in particular
"Updating the lock", before deciding whether the new version is acceptable.

**CMake picks the wrong Python.** Activate the virtual environment first: the
script passes the `python` that is first on `PATH` to CMake. Check with
`python -c "import sys; print(sys.executable)"`.

**A newer CMake.** 3.27.9 was used. 3.24 or newer is required (the lock is loaded
through `CMAKE_PROJECT_TOP_LEVEL_INCLUDES`). Versions newer than 3.27 have not
been tried; if one fails in a way that is not obviously about your setup, install
3.27.9.

**Paths too long on Windows.** The dependencies are unpacked into deep directories.
Enable long paths: `git config --system core.longpaths true` (administrator
prompt), and clone into a short folder such as `C:\dev\`.

**Disk space.** About 5 GB: the ITA build directory alone is 3.6 GB.

If something here does not match what you see, open an issue with the full output
of `tools\build_art.ps1` (or `.sh`).

---

## For maintainers

### Updating the committed binaries (Option A)

After a successful `build_art.ps1` run on **Python 3.13**:

```powershell
Copy-Item bin\* prebuilt\win-x64-py313\ -Force
Get-FileHash prebuilt\win-x64-py313\* -Algorithm SHA256   # refresh the table in prebuilt/README.md
```

Update the table in [prebuilt/README.md](prebuilt/README.md) (sizes and SHA-256
sums) and, if a dependency changed, the matching text in
`prebuilt/THIRD_PARTY_LICENSES.txt`. Git keeps every version of every binary for
good, so each update adds about 13 MB to the size of the repository: update the
folder when ART really changed, not on every commit. Then run the
"Option A check" workflow (Actions tab) to test the committed files on a clean
machine.

A zip of the same 15 files can still be attached to a GitHub Release for people
who do not clone the repository.

### Regenerating a patch

Edit the file inside the submodule, then write the difference against the
submodule's committed version, with line endings normalised to LF so the patch
applies on any platform, and re-apply it to a pristine checkout to confirm it
reproduces your edit. `git diff` alone is not enough: a Windows working tree may
contain CRLF endings that make every line look changed.
