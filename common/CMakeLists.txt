# --------------------------------------------------------------------------- #
# CMakeLists.txt for common
# --------------------------------------------------------------------------- #
set(_TARGET_NAME common)

# Populate the list with source files
set(_SRCS ILogger.cpp
    Logger.cpp
    LogManager.cpp)

# Prepend path prefix to each source file
set(_SRC_PATH src)

set(_TARGET_SRCS "")
foreach(source ${_SRCS})
    list(APPEND _TARGET_SRCS ${_SRC_PATH}/${source})
endforeach()

# Object collection
add_library(${_TARGET_NAME} OBJECT ${_TARGET_SRCS})

# Include paths
target_include_directories(${_TARGET_NAME} PRIVATE 
    inc
    ${LIBBOOST_INC})

# Install
#install(TARGETS ${_TARGET_NAME}
#    OBJECTS DESTINATION obj)
