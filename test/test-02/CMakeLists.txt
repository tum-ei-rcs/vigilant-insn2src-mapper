# --------------------------------------------------------------------------- #
# CMakeLists.txt for test-02
# --------------------------------------------------------------------------- #
set(_TARGET_NAME test-02)

# Populate the list with source files
set(_TARGET_SRCS main.cpp)

add_executable(${_TARGET_NAME} ${_TARGET_SRCS})

target_include_directories(${_TARGET_NAME} PRIVATE
    ${PROJECT_SOURCE_DIR}/libbincfg/inc
    ${LIBBOOST_INC})

target_link_libraries(${_TARGET_NAME}
    bincfg
    ${LIBBOOST_PRGOPT}
)

# Install executable
install (TARGETS ${_TARGET_NAME}
    RUNTIME DESTINATION bin)
