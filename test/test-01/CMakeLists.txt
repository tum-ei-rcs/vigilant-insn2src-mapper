# --------------------------------------------------------------------------- #
# CMakeLists.txt for test-01
#
# NOTE: Log might need the following libs (log;log_setup;date_time;filesystem;
#       system;thread) in this order for static libs as well as pthread.
# --------------------------------------------------------------------------- #
set(_TARGET_NAME test-01)

# Populate the list with source files
set(_TARGET_SRCS main.cpp)

add_executable(${_TARGET_NAME} ${_TARGET_SRCS})

target_include_directories(${_TARGET_NAME} PRIVATE
    ${PROJECT_SOURCE_DIR}/libbincfg/inc
    ${COMMON_INC_DIR}
    ${LIBBOOST_INC})

target_link_libraries(${_TARGET_NAME}
    $<TARGET_OBJECTS:common>
    bincfg
    ${LIBBOOST_LOG}
    ${LIBBOOST_SYSTEM}
    ${LIBBOOST_THREAD}
    pthread
)

# Install executable
install (TARGETS ${_TARGET_NAME}
    RUNTIME DESTINATION bin)
