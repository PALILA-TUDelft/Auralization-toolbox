message(STATUS "Patching netcdf-cxx4 CMakeLists.txt at: ${NETCDF_CXX4_SOURCE_DIR}/cxx4/CMakeLists.txt")

set(file_path "${NETCDF_CXX4_SOURCE_DIR}/cxx4/CMakeLists.txt")

if(NOT EXISTS "${file_path}")
  message(FATAL_ERROR "File not found: ${file_path}")
endif()

file(READ "${file_path}" content)

# Remove INCLUDE_DIRECTORIES(".")
string(REGEX REPLACE "INCLUDE_DIRECTORIES\\(\"\\.\"\\)\n\n" "" content "${content}")

# Fix TARGET_INCLUDE_DIRECTORIES - replace the single line with multi-line version
string(REGEX REPLACE 
  "TARGET_INCLUDE_DIRECTORIES\\(netcdf-cxx4 PUBLIC \"\\$\\{CMAKE_CURRENT_SOURCE_DIR\\}\"\\)"
  "TARGET_INCLUDE_DIRECTORIES(netcdf-cxx4 PUBLIC\n  \$<BUILD_INTERFACE:\${CMAKE_CURRENT_SOURCE_DIR}>\n  \$<INSTALL_INTERFACE:include>)"
  content "${content}")

file(WRITE "${file_path}" "${content}")
message(STATUS "Successfully patched netcdf-cxx4 CMakeLists.txt")