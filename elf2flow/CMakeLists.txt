# --------------------------------------------------------------------------- #
# CMakeLists.txt for elf2flow
# --------------------------------------------------------------------------- #
set(_TARGET_NAME elf2flow)

# Populate the list with source files
set(_TARGET_SRCS main.cpp)

add_executable(${_TARGET_NAME} ${_TARGET_SRCS})

target_include_directories(${_TARGET_NAME} PRIVATE
    ${PROJECT_SOURCE_DIR}/libbincfg/inc
    ${COMMON_INC_DIR}
    ${BOOST_INCLUDEDIR}
    ${LIBDWARF_INC})

target_link_libraries(${_TARGET_NAME}
    $<TARGET_OBJECTS:common>
    bincfg
    ${LIBBOOST_LOG}
    ${LIBBOOST_SYSTEM}
    ${LIBBOOST_THREAD}
    ${LIBBOOST_PRGOPT}
    ${LIBBOOST_FILESYS}
    pthread
    )

# Enable profiling if flag set
if (FLAG_ENABLE_PROFILING)
    target_link_libraries(${_TARGET_NAME} -pg)
endif()

# Install executable
install (TARGETS ${_TARGET_NAME}
    RUNTIME DESTINATION bin)
