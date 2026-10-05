# patches/ita/dependency-lock.cmake
#
# Pins the ITA dependencies that are requested from a MOVING upstream branch.
#
# Why this exists
# ---------------
# ITACoreLibs, IHTAUtilityLibs, ViSTA, DSPFilters, openDAFF and pocketFFT are
# fetched with GIT_TAG set to a branch name (develop / master / feature/ita /
# cpp). Whatever those branches contain on the day you build is what you get,
# so a rebuild later can differ from the build this toolbox was developed
# against. This file pins them to the exact commits of the working build.
#
# How it works
# ------------
# CPM: once a package has been declared with CPMDeclarePackage, every later
# CPMAddPackage(NAME <same name> ...) uses the DECLARED arguments INSTEAD of
# its own. So each declaration below must repeat every argument the original
# call used (repository, DOWNLOAD_ONLY, PATCHES, ...), with only the tag
# replaced by a commit.
#
# Each declaration also needs an explicit NAME. CPM replays a declaration as
# CPMAddPackage(<declared arguments>), without the package name, and can only
# infer a name from GITHUB_REPOSITORY-style arguments - a plain GIT_REPOSITORY
# URL fails with "'NAME' was not provided and couldn't be automatically
# inferred".
#
# It is loaded through CMAKE_PROJECT_TOP_LEVEL_INCLUDES, which the ITA presets
# set (see patches/ita/ITAGeometricalAcoustics.patch). That runs after the
# top-level project() call, which is after CPM is loaded and before any
# dependency is requested. CMake >= 3.24 is required for that variable.
#
# Not covered here (pinned elsewhere)
#   * IHTACMakeCommon  - fetched before project(); pinned by editing the
#                        top-level CMakeLists.txt (ITAGeometricalAcoustics.patch)
#   * ITACoreLibs      - pinned by editing ITAGeo/external_libs/CMakeLists.txt
#                        (ITAGeo.patch)
#   * dependencies requested by tag - left as tags, see dependency-lock.json
#   * archive downloads (asio, fftw, pcre, NatNetSDK) - fixed URLs, not git
#
# GIT_SHALLOW is forced OFF: a shallow clone cannot reliably check out an
# arbitrary commit, and not every server allows fetching one by hash.
#
# To refresh the pins (e.g. after deliberately bumping ITA) rebuild once, then
# regenerate dependency-lock.json and the SHAs below from the new _deps tree.
# tools/verify_dependency_lock.py reports any drift.

if (NOT COMMAND CPMDeclarePackage)
	message (FATAL_ERROR
		"dependency-lock.cmake was loaded before CPM was available. "
		"It must be included through CMAKE_PROJECT_TOP_LEVEL_INCLUDES (set by the ITA presets)."
	)
endif ()

# The ViSTA patch ships inside ITACoreLibs. Resolve it where FetchContent will
# have put ITACoreLibs, so the correct line endings for this platform's checkout
# are used.
if (DEFINED FETCHCONTENT_BASEDIR)
	set (_ita_lock_deps_dir "${FETCHCONTENT_BASEDIR}")
else ()
	set (_ita_lock_deps_dir "${CMAKE_BINARY_DIR}/_deps")
endif ()

CPMDeclarePackage (
	IHTAUtilityLibs
	NAME IHTAUtilityLibs
	GIT_REPOSITORY https://git.rwth-aachen.de/ita/ihtautilitylibs
	GIT_TAG 773df1451ac5bd10349f833eec6413dc7f402eef
	GIT_SHALLOW FALSE
)

CPMDeclarePackage (
	vista
	NAME vista
	GIT_REPOSITORY https://git.rwth-aachen.de/ita/ViSTA
	GIT_TAG 29d83c51841d146fd68e8661b929dee07cf52016
	GIT_SHALLOW FALSE
	DOWNLOAD_ONLY YES
	PATCHES "${_ita_lock_deps_dir}/itacorelibs-src/ITABase/external_libs/patches/vista.patch"
)

CPMDeclarePackage (
	DSPFilters
	NAME DSPFilters
	GITHUB_REPOSITORY vinniefalco/DSPFilters
	GIT_TAG acc49170e79a94fcb9c04b8a2116e9f8dffd1c7d
	GIT_SHALLOW FALSE
	DOWNLOAD_ONLY ON
)

CPMDeclarePackage (
	openDAFF
	NAME openDAFF
	GIT_REPOSITORY https://git.code.sf.net/p/opendaff/git
	GIT_TAG cda7126ccdc55a544701b3daa06ee70b15975ce9
	GIT_SHALLOW FALSE
	DOWNLOAD_ONLY ON
)

CPMDeclarePackage (
	pocketFFT
	NAME pocketFFT
	GIT_REPOSITORY https://gitlab.mpcdf.mpg.de/mtr/pocketfft
	GIT_TAG 32424d2067c2e8043dc646a4e49754b2b40cc549
	GIT_SHALLOW FALSE
	DOWNLOAD_ONLY TRUE
)

message (STATUS "ITA dependency lock: pinned IHTAUtilityLibs, vista, DSPFilters, openDAFF, pocketFFT")
