#!/usr/bin/env bash
#
# Build the ART native module (_art_core) on macOS or Linux and stage it, with
# the ITA shared libraries, into bin/ where the toolbox looks for it.
#
# POSIX counterpart of build_art.ps1. Steps:
#   1. check for git / cmake / ninja / python3 / nanobind
#   2. git submodule update --init --recursive
#   3. apply the local ITA patches
#   4. configure ITAGeometricalAcoustics, verify the dependency lock, build (Release)
#   5. configure + build the nanobind module in bindings/
#   6. copy _art_core*.so and the ITA .dylib/.so files into bin/, and make
#      them relocatable so they find each other from that directory
#
# Step 4 is long (it fetches and compiles assimp, OpenMesh, netcdf, HDF5,
# Vista and more) and needs several GB of disk.
#
# IMPORTANT: upstream ITAGeometricalAcoustics is CI-tested on Windows only.
# This script encodes the intended macOS / Linux build but has not been run on
# either platform. Expect to debug the ITA dependency chain; see the README
# section "Building ART on macOS and Linux".
#
# Usage:
#   ./tools/build_art.sh              # full build
#   ./tools/build_art.sh --skip-ita   # rebuild only the bindings
#   ./tools/build_art.sh --clean      # wipe the bindings build tree first
#   ./tools/build_art.sh --clean-ita  # configure ITA from scratch (after an interrupted configure)
#
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ITA_ROOT="$REPO_ROOT/ITAGeometricalAcoustics"
BINDINGS_DIR="$REPO_ROOT/bindings"
BIN_DIR="$REPO_ROOT/bin"

SKIP_ITA=0
CLEAN=0
CLEAN_ITA=0
PRESET=""

while [ $# -gt 0 ]; do
    case "$1" in
        --skip-ita) SKIP_ITA=1 ;;
        --clean)    CLEAN=1 ;;
        --clean-ita) CLEAN_ITA=1 ;;
        --preset)   shift; PRESET="${1:-}" ;;
        -h|--help)  sed -n '2,30p' "${BASH_SOURCE[0]}"; exit 0 ;;
        *) echo "Unknown option: $1" >&2; exit 2 ;;
    esac
    shift
done

case "$(uname -s)" in
    Darwin) DEFAULT_PRESET="full-mac-ninja-clang"; PLATFORM="macOS"; LIB_EXT="dylib" ;;
    Linux)  DEFAULT_PRESET="full-linux-ninja-gcc"; PLATFORM="Linux";  LIB_EXT="so" ;;
    *)      echo "This script is for macOS and Linux. On Windows use tools/build_art.ps1." >&2
            exit 1 ;;
esac
PRESET="${PRESET:-$DEFAULT_PRESET}"
ITA_BUILD="$ITA_ROOT/out/build/$PRESET"

step() { echo; echo "=== $*"; }

# --- 1. Prerequisites -----------------------------------------------------
echo "=== Checking prerequisites ($PLATFORM, preset $PRESET)"
for exe in git cmake ninja; do
    if ! command -v "$exe" >/dev/null 2>&1; then
        echo "'$exe' not found on PATH." >&2
        if [ "$exe" = "ninja" ]; then
            echo "  macOS:  brew install ninja" >&2
            echo "  Linux:  apt install ninja-build" >&2
        fi
        exit 1
    fi
    echo "  $exe : $(command -v "$exe")"
done

PYTHON="${PYTHON:-python3}"
if ! command -v "$PYTHON" >/dev/null 2>&1; then
    echo "'$PYTHON' not found. Activate your virtual environment, or set PYTHON=..." >&2
    exit 1
fi
PY_VER="$("$PYTHON" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')"
echo "  python : $(command -v "$PYTHON") (Python $PY_VER)"

if ! "$PYTHON" -c 'import nanobind' >/dev/null 2>&1; then
    echo "nanobind is not installed for this interpreter." >&2
    echo "Run: $PYTHON -m pip install -r requirements-build.txt" >&2
    exit 1
fi
echo "  nanobind : ok"

if [ "$PLATFORM" = "macOS" ] && ! xcode-select -p >/dev/null 2>&1; then
    echo "Xcode command line tools not found. Run: xcode-select --install" >&2
    exit 1
fi

if [ "$SKIP_ITA" -eq 0 ]; then
    # --- 2. Submodules ----------------------------------------------------
    step "Updating submodules"
    git -C "$REPO_ROOT" submodule update --init --recursive

    # --- 3. Patches -------------------------------------------------------
    step "Applying ITA patches"
    bash "$REPO_ROOT/tools/apply_ita_patches.sh"

    # --- 4. Build ITA -----------------------------------------------------
    if [ "$CLEAN_ITA" -eq 1 ] && [ -d "$ITA_BUILD" ]; then
        echo "Removing $ITA_BUILD"
        rm -rf "$ITA_BUILD"
    fi

    # CMake re-runs the PATCH step of every patched dependency (vista, nanoflann,
    # netcdf-c, netcdf-cxx4, reflect-cpp) each time it configures, and a patch
    # cannot be applied twice, so re-configuring a tree whose dependencies are
    # already downloaded fails with "Reversed (or previously applied) patch
    # detected". For a tree that was configured before, run in local-only mode
    # instead: nothing is fetched or patched again. A tree counts as configured if
    # an earlier run finished configuring it (the stamp file) or if it already
    # produced the ITA libraries.
    ITA_STAMP="$ITA_BUILD/.configured-ok"
    LOCAL_ONLY=""
    if [ -f "$ITA_STAMP" ] || ls "$ITA_BUILD"/Release/lib/libITAGeo.* >/dev/null 2>&1; then
        echo "  ITA was configured before: re-configuring in local-only mode"
        LOCAL_ONLY="-DFETCHCONTENT_FULLY_DISCONNECTED=ON"
    fi

    # WITH_IHTA_TRACKING=OFF: IHTAUtilityLibs builds an optional tracking library
    # that needs the OptiTrack NatNet SDK, which only exists for Windows. Without
    # this switch CMake stops with 'Could not find ... "NatNetSDK"'. ART does not
    # use the tracking library (its DLL is not among the files in bin/).
    step "Configuring ITAGeometricalAcoustics (preset $PRESET)"
    if ! ( cd "$ITA_ROOT" && cmake --preset "$PRESET" $LOCAL_ONLY -DWITH_IHTA_TRACKING=OFF ); then
        echo >&2
        echo "ITA configuration failed." >&2
        echo "If an EARLIER configure was interrupted (network error, Ctrl+C) and the message above" >&2
        echo "mentions \"previously applied\" patches, the half-finished tree cannot be reused:" >&2
        echo "  rerun with --clean-ita to configure ITA from scratch." >&2
        exit 1
    fi

    step "Verifying the dependency lock"
    if ! "$PYTHON" "$REPO_ROOT/tools/verify_dependency_lock.py" "$ITA_BUILD"; then
        echo "Fetched dependencies differ from patches/ita/dependency-lock.json." >&2
        echo "See BUILD.md, section \"Reproducibility\"." >&2
        exit 1
    fi
    # Configure + lock verified: later runs may re-configure in local-only mode.
    date +%Y-%m-%dT%H:%M:%S > "$ITA_STAMP"

    step "Building the ITA libraries ART needs (Release) - this takes a while"
    # Only the two libraries the bindings link against; their dependencies come
    # with them. Building all of ITA also builds apps and netcdf-cxx4, which ART
    # does not use and which does not compile in this configuration.
    cmake --build "$ITA_BUILD" --config Release --target ITAGeo ITAPropagationPathSim
fi

if [ ! -d "$ITA_BUILD" ]; then
    echo "ITA build directory not found: $ITA_BUILD" >&2
    echo "Build ITA first (drop --skip-ita)." >&2
    exit 1
fi

# --- 5. Build the bindings ------------------------------------------------
if [ "$CLEAN" -eq 1 ] && [ -d "$BINDINGS_DIR/build" ]; then
    echo "Removing $BINDINGS_DIR/build"
    rm -rf "$BINDINGS_DIR/build"
fi

step "Configuring _art_core bindings"
( cd "$BINDINGS_DIR" && cmake -B build -DCMAKE_BUILD_TYPE=Release \
    -DITA_ROOT="$ITA_ROOT" -DITA_BUILD_DIR="$ITA_BUILD" \
    -DPython_EXECUTABLE="$(command -v "$PYTHON")" )

step "Building _art_core"
( cd "$BINDINGS_DIR" && cmake --build build --config Release )

# --- 6. Stage into bin/ ---------------------------------------------------
step "Staging into bin/"
mkdir -p "$BIN_DIR"

# Newest match wins. Written without mapfile / negative array indices so this
# runs on the bash 3.2 that macOS still ships as /bin/bash.
pyd=""
while IFS= read -r candidate; do
    if [ -z "$pyd" ] || [ "$candidate" -nt "$pyd" ]; then
        pyd="$candidate"
    fi
done < <(find "$BINDINGS_DIR/build" -name '_art_core*.so' -type f)

if [ -z "$pyd" ]; then
    echo "No _art_core*.so was produced under $BINDINGS_DIR/build." >&2
    exit 1
fi
cp -f "$pyd" "$BIN_DIR/"
echo "  $(basename "$pyd")"

shopt -s nullglob
libs=()
for d in "$ITA_BUILD/Release/lib" "$ITA_BUILD/Release/bin" "$ITA_BUILD/lib" "$ITA_BUILD/bin"; do
    [ -d "$d" ] || continue
    for f in "$d"/*."$LIB_EXT" "$d"/*."$LIB_EXT".*; do
        [ -f "$f" ] && libs+=("$f")
    done
done
shopt -u nullglob

if [ ${#libs[@]} -eq 0 ]; then
    echo "No .$LIB_EXT files found under $ITA_BUILD." >&2
    echo "Was ITA built as shared libraries? Check BUILD_SHARED_LIBS." >&2
    exit 1
fi
for f in "${libs[@]}"; do
    cp -f "$f" "$BIN_DIR/"
    echo "  $(basename "$f")"
done

# Make the staged libraries relocatable: each needs to resolve its siblings
# from whatever directory it ends up in, not from the build tree it was
# linked in. Without this, moving bin/ (or zipping it for a Release) breaks
# the @rpath / $ORIGIN lookups.
step "Making staged libraries relocatable"
if [ "$PLATFORM" = "macOS" ]; then
    for f in "$BIN_DIR"/*.dylib "$BIN_DIR"/_art_core*.so; do
        [ -f "$f" ] || continue
        # Already present? install_name_tool fails loudly; that is fine.
        if otool -l "$f" 2>/dev/null | grep -q '@loader_path'; then
            echo "  rpath ok   $(basename "$f")"
        elif install_name_tool -add_rpath "@loader_path" "$f" 2>/dev/null; then
            echo "  rpath set  $(basename "$f")"
        else
            echo "  rpath SKIP $(basename "$f") (could not add @loader_path)"
        fi
    done
else
    if command -v patchelf >/dev/null 2>&1; then
        for f in "$BIN_DIR"/*.so "$BIN_DIR"/*.so.*; do
            [ -f "$f" ] || continue
            patchelf --set-rpath '$ORIGIN' "$f" 2>/dev/null \
                && echo "  rpath set  $(basename "$f")" \
                || echo "  rpath SKIP $(basename "$f")"
        done
    else
        echo "  patchelf not installed; skipping (set LD_LIBRARY_PATH=$BIN_DIR instead)"
        echo "  install with: apt install patchelf"
    fi
fi

# --- Verify ---------------------------------------------------------------
step "Verifying"
( cd "$REPO_ROOT" && "$PYTHON" -c "
from auralization.private.propagation.art_bindings import art_core_available
import sys
ok = art_core_available()
print('  _art_core importable:', ok)
sys.exit(0 if ok else 1)
" ) || {
    echo "Built, but _art_core could not be imported." >&2
    if [ "$PLATFORM" = "macOS" ]; then
        echo "Inspect the library dependencies with:  otool -L $BIN_DIR/_art_core*.so" >&2
    else
        echo "Inspect the library dependencies with:  ldd $BIN_DIR/_art_core*.so" >&2
    fi
    exit 1
}

echo
echo "Done. ART staged in $BIN_DIR (Python $PY_VER, $PLATFORM $(uname -m))."
echo "bin/ is gitignored. To share it, attach a zip of it to a GitHub Release."
