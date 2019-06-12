# --------------------------------------------------------------------------- #
# CMakeLists.txt for MP-MA
# --------------------------------------------------------------------------- #
cmake_minimum_required(VERSION 3.10)

# --------------------------------------------------------------------------- #
# Define project
project(MP-MA)

# Set default build type if none specified
if (NOT CMAKE_BUILD_TYPE)
    message("Debug build set as default.")
    set(CMAKE_BUILD_TYPE "Debug")
endif (NOT CMAKE_BUILD_TYPE)

# Use C++11 standard
add_compile_options(-std=c++11)

# Enable profiling if flag set
if (FLAG_ENABLE_PROFILING)
    add_compile_options(-pg)
    message("Profiling is enabled.")
endif()

if (CMAKE_BUILD_TYPE STREQUAL "Debug")
    # Use readelf -p .GCC.command.line ./libbincfg.a for reading switches
    add_compile_options(-Wall -gdwarf-4 -g -O0 -frecord-gcc-switches)
endif (CMAKE_BUILD_TYPE STREQUAL "Debug")

if (CMAKE_BUILD_TYPE STREQUAL "Release")
    add_compile_options(-Wall -O1)
endif (CMAKE_BUILD_TYPE STREQUAL "Release")
# --------------------------------------------------------------------------- #

# Define a variable for the common include folder
set(COMMON_INC_DIR ${PROJECT_SOURCE_DIR}/common/inc)
# --------------------------------------------------------------------------- #


# --------------------------------------------------------------------------- #
# Boost - Not using FindBoost.cmake (contains bugs)
#
# NOTE: This will only find static boost libraries with no versioned filename 
#       layout (--layout=versioned). 
#
# NOTE: _BOOST_INC and _BOOST_LIB definitions serve as optional hints which
#       have a priority over other (default) paths when searching boost include
#       and lib directories.
# --------------------------------------------------------------------------- #

# Boost headers
find_path(LIBBOOST_INC
    NAMES boost/version.hpp
    HINTS ${_BOOST_INC} ${_LOCAL_INC_DIR}
)
if (NOT LIBBOOST_INC)
    message(WARNING "Could not locate Boost headers")
endif()

MESSAGE(STATUS "Boost headers:  ${LIBBOOST_INC}")

# Version check
SET(BOOST_VERSION_MINIMUM "105500")
file(STRINGS ${LIBBOOST_INC}/boost/version.hpp BOOST_VERSION_STRING
        REGEX "^#define BOOST_VERSION ")
string(REGEX MATCH "([0-9]+)" BOOST_VERSION ${BOOST_VERSION_STRING})

if (${BOOST_VERSION} VERSION_LESS ${BOOST_VERSION_MINIMUM})
    message(WARNING "Boost version " ${BOOST_VERSION} " not supported.")
endif()

# Boost libs
find_library(LIBBOOST_FILESYS NAMES libboost_filesystem.a      HINTS ${_BOOST_LIB} ${_LOCAL_LIB_DIR})
find_library(LIBBOOST_LOG     NAMES libboost_log.a             HINTS ${_BOOST_LIB} ${_LOCAL_LIB_DIR})
find_library(LIBBOOST_PRGOPT  NAMES libboost_program_options.a HINTS ${_BOOST_LIB} ${_LOCAL_LIB_DIR})
find_library(LIBBOOST_SYSTEM  NAMES libboost_system.a          HINTS ${_BOOST_LIB} ${_LOCAL_LIB_DIR})
find_library(LIBBOOST_THREAD  NAMES libboost_thread.a          HINTS ${_BOOST_LIB} ${_LOCAL_LIB_DIR})

set(LIBBOOST_LIBS
    ${LIBBOOST_FILESYS}
    ${LIBBOOST_LOG}
    ${LIBBOOST_PRGOPT}
    ${LIBBOOST_SYSTEM}
    ${LIBBOOST_THREAD}
)

if (NOT LIBBOOST_LIBS)
    message(WARNING "Could not locate boost libs.")
endif()

MESSAGE(STATUS "Boost libaries  ${LIBBOOST_LIBS}")

# --------------------------------------------------------------------------- #
# JSON lib
#
# --------------------------------------------------------------------------- #
find_path(LIBJSON_INC
    NAMES nlohmann/json.hpp
    HINTS ${_LOCAL_INC_DIR}
)
if (NOT LIBJSON_INC)
    message(WARNING "Could not locate JSON lib headers")
endif()

# --------------------------------------------------------------------------- #
# Libdwarf
#
# --------------------------------------------------------------------------- #
find_path(LIBDWARF_INC
    NAMES dwarf.h libdwarf.h
    HINTS ${_LOCAL_INC_DIR}
)
if (NOT LIBDWARF_INC)
    message(WARNING "Could not locate libdwarf headers.")
endif()
MESSAGE(STATUS "libdwarf includes: ${LIBDWARF_INC}")

find_library(LIBDWARF
    NAMES dwarf
    HINTS ${_LOCAL_LIB_DIR}
)
if (NOT LIBDWARF)
    message(WARNING "Could not locate libdwarf.")
endif()


find_library(LIBELF NAMES elf)
if (NOT LIBELF)
    message(WARNING "Could not find libelf.")
endif()

find_library(ZLIB NAMES z)
if (NOT ZLIB)
    message(WARNING "Could not find zlib.")
endif()

# --------------------------------------------------------------------------- #
# Add subdirectories to scan
add_subdirectory(common)
add_subdirectory(libbincfg)
#add_subdirectory(libmapping)
add_subdirectory(elf2flow)
add_subdirectory(test)
# --------------------------------------------------------------------------- #
