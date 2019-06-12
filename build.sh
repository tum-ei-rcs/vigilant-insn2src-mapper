#!/usr/bin/env bash

# --------------------------------------------------------------------------- #
# CONSTANTS (options)
# --------------------------------------------------------------------------- #
SCRIPT_PATH="$( cd "$(dirname "$0")" ; pwd -P )"

BUILD_DIR="build"
CMAKE_DIR="CMake"

CMAKE="cmake"

C_COMP=gcc
CXX_COMP=g++

#CMAKE_VERBOSE="ON"
CMAKE_VERBOSE="OFF"

#ENABLE_PROFILING="ON"
ENABLE_PROFILING="OFF"

# Local directories
LOCAL_INC="$HOME/local/include"
LOCAL_LIB="$HOME/local/lib"

# Qt install directory path (must contain lib/cmake)
QT_PATH="$HOME/local/qt/lib/cmake"

# Optional hint for locating boost inc folder (e.g. ~/local/include/boost-1_66)
BOOST_INC="$HOME/local/include/boost-1_65_1"

# --------------------------------------------------------------------------- #

cmake_func()
{
    check_dirs

    $CMAKE $SCRIPT_PATH \
        -DCMAKE_BUILD_TYPE:STRING=Debug \
        -DCMAKE_INSTALL_PREFIX=$SCRIPT_PATH/$BUILD_DIR \
        -DCMAKE_C_COMPILER=$C_COMP \
        -DCMAKE_CXX_COMPILER=$CXX_COMP \
        -DCMAKE_VERBOSE_MAKEFILE:BOOL=$CMAKE_VERBOSE \
        -DFLAG_ENABLE_PROFILING:BOOL=$ENABLE_PROFILING \
        -DCMAKE_PREFIX_PATH:STRING=$QT_PATH \
        -D_LOCAL_INC_DIR:STRING=$LOCAL_INC \
        -D_LOCAL_LIB_DIR:STRING=$LOCAL_LIB \
        -D_BOOST_INC:STRING=$BOOST_INC

    make_func
}

make_func()
{
    if ! [ -d "$SCRIPT_PATH/$BUILD_DIR/$CMAKE_DIR" ]; then
        echo "CMake build directory not found."
    else
        cd "$SCRIPT_PATH/$BUILD_DIR/$CMAKE_DIR"
        make && make install
    fi
}

check_dirs()
{
    if [ -d "$SCRIPT_PATH/$BUILD_DIR/$CMAKE_DIR" ]; then
        echo "Found CMake build directory."
    else
        if ! [ -d "$SCRIPT_PATH/$BUILD_DIR" ]; then
            mkdir "$SCRIPT_PATH/$BUILD_DIR"
        fi
        mkdir "$SCRIPT_PATH/$BUILD_DIR/$CMAKE_DIR"
    fi

    cd "$SCRIPT_PATH/$BUILD_DIR/$CMAKE_DIR"
}

remove_dirs()
{
    if [ -d "$SCRIPT_PATH/$BUILD_DIR" ]; then
        echo "Removing $SCRIPT_PATH/$BUILD_DIR"
        rm -r "$SCRIPT_PATH/$BUILD_DIR"
    else
        echo "Build directory not found, nothing to remove."
    fi
}

print_usage()
{
    echo "Use one of the following:"
    echo "  -cmake  | -c : Invoke cmake"
    echo "  -make   | -m : Execute make and make install"
    echo "  -remove | -r : Remove the created build directory completely"
    echo ""
}

# --------------------------------------------------------------------------- #
# MAIN
# --------------------------------------------------------------------------- #


if [ "$1" != "" ]; then
    case $1 in
    "-cmake"  | "-c")
        cmake_func
        ;;
    "-make"   | "-m")
        make_func
        ;;
    "-remove" | "-r")
        remove_dirs
        ;;
    *)
        echo "Invalid argument specified."
        echo ""
        print_usage
        ;;
    esac
else
    echo "No argument specified."
    echo ""
    print_usage
fi
# --------------------------------------------------------------------------- #
