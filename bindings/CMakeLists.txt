cmake_minimum_required (VERSION 3.20 FATAL_ERROR)
project (ARTPython LANGUAGES CXX)

# --------------------------------------------------------------------------
# Standalone build for the _art_core nanobind module.
# Links against the pre-built ITAGeometricalAcoustics libraries.
#
# Usage:
#   cd bindings
#   cmake -B build -DCMAKE_BUILD_TYPE=Release
#   cmake --build build --config Release
#
# The resulting module is _art_core.pyd on Windows (in build/Release/) and
# _art_core*.so on macOS / Linux (in build/). Copy it, together with the ITA
# runtime libraries, into the repository's bin/ directory, which is the first
# place the Python loader looks. tools/build_art.ps1 (Windows) and
# tools/build_art.sh (macOS / Linux) do that for you.
#
# Platform note: only the Windows build is tested. The macOS / Linux paths
# below are written to be correct but have not been exercised - upstream
# ITAGeometricalAcoustics is CI-tested on Windows only.
# --------------------------------------------------------------------------

# --- Paths to the pre-built ITAGeometricalAcoustics ---
set (ITA_ROOT "${CMAKE_CURRENT_SOURCE_DIR}/../ITAGeometricalAcoustics"
     CACHE PATH "Root of the ITAGeometricalAcoustics source tree")

if (WIN32)
	set (_ita_default_preset "full-win-vs-msvc")
elseif (APPLE)
	set (_ita_default_preset "full-mac-ninja-clang")
else ()
	set (_ita_default_preset "full-linux-ninja-gcc")
endif ()
set (ITA_BUILD_DIR "${ITA_ROOT}/out/build/${_ita_default_preset}"
     CACHE PATH "Build directory of ITAGeometricalAcoustics")

# --- Find Python + nanobind ---
find_package (Python 3.8 REQUIRED COMPONENTS Interpreter Development.Module)

execute_process (
	COMMAND "${Python_EXECUTABLE}" -m nanobind --cmake_dir
	OUTPUT_STRIP_TRAILING_WHITESPACE
	OUTPUT_VARIABLE NB_DIR
	RESULT_VARIABLE NB_DIR_RC
)
if (NB_DIR_RC)
	message (FATAL_ERROR "nanobind not found. Install it with:  pip install nanobind")
endif ()
list (APPEND CMAKE_PREFIX_PATH "${NB_DIR}")
find_package (nanobind CONFIG REQUIRED)

# --- Create the extension module ---
nanobind_add_module (_art_core src/ARTPythonBindings.cpp)

# --- Include directories (public headers from the source tree + deps) ---
target_include_directories (_art_core PRIVATE
	# ITAGeo and ITAPropagationPathSim public headers
	"${ITA_ROOT}/ITAGeo/include"
	"${ITA_ROOT}/ITAPropagationPathSim/include"

	# ITABase (fetched dependency)
	"${ITA_BUILD_DIR}/_deps/itacorelibs-src/ITABase/include"

	# Vista (VistaBase/VistaVector3D.h, VistaMath/VistaGeometries.h)
	"${ITA_BUILD_DIR}/_deps/vista-src/VistaCoreLibs"
)

# --- Link against the pre-built ITA libraries ---------------------------
# Resolved by name rather than hardcoded, so the correct platform suffix is
# picked up: .lib (Windows import library), .dylib (macOS), .so (Linux).
# ITA uses the "Ninja Multi-Config" generator, so Release/ appears in the
# path on every platform; the plain lib/ hints cover a single-config build.
set (_ita_lib_hints
	"${ITA_BUILD_DIR}/Release/lib"
	"${ITA_BUILD_DIR}/lib/Release"
	"${ITA_BUILD_DIR}/lib"
	"${ITA_BUILD_DIR}/Release/bin"
	"${ITA_BUILD_DIR}/Release"
	"${ITA_BUILD_DIR}"
)

set (_ita_libs "")
foreach (_name IN ITEMS ITAGeo ITAPropagationPathSim ITABase)
	find_library (ITA_${_name}_LIBRARY
		NAMES ${_name} lib${_name}
		HINTS ${_ita_lib_hints}
		NO_DEFAULT_PATH
	)
	if (NOT ITA_${_name}_LIBRARY)
		message (FATAL_ERROR
			"Could not find the ${_name} library under ${ITA_BUILD_DIR}.\n"
			"Build ITAGeometricalAcoustics first, or pass -DITA_BUILD_DIR=<its build dir>.\n"
			"Searched: ${_ita_lib_hints}")
	endif ()
	list (APPEND _ita_libs "${ITA_${_name}_LIBRARY}")
	message (STATUS "Found ${_name}: ${ITA_${_name}_LIBRARY}")
endforeach ()

target_link_libraries (_art_core PRIVATE ${_ita_libs})

# --- Runtime library lookup ----------------------------------------------
# On Windows the loader is told where the DLLs are at import time (Python's
# os.add_dll_directory). macOS and Linux resolve shared libraries through a
# path baked into the module at link time instead, so point it at its own
# directory: dropping _art_core.so next to the ITA .dylib/.so files in bin/
# is then enough, with no DYLD_LIBRARY_PATH (which macOS SIP strips anyway).
if (APPLE)
	set_target_properties (_art_core PROPERTIES
		BUILD_WITH_INSTALL_RPATH TRUE
		INSTALL_RPATH "@loader_path;@loader_path/../lib"
	)
elseif (UNIX)
	set_target_properties (_art_core PROPERTIES
		BUILD_WITH_INSTALL_RPATH TRUE
		INSTALL_RPATH "$ORIGIN:$ORIGIN/../lib"
	)
endif ()

# _USE_MATH_DEFINES is a no-op outside MSVC but harmless.
#
# Deliberately NOT defined here: Vista's DARWIN macro. VistaCoreLibs guards
# its Mach-native code paths on `defined DARWIN`, which its own CMake never
# sets, so the ITA libraries are compiled against Vista's generic POSIX
# fallback. Defining DARWIN only for this module would change the layout of
# VistaDefaultTimerImp and give an ABI mismatch against those libraries.
target_compile_definitions (_art_core PRIVATE _USE_MATH_DEFINES)
