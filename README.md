# Vigilant Instruction-to-Source Mapper
This tool was developed for timing analysis of source code. 
Its main purpose is to establish a safe mapping between machine code 
and source-level constructs, such that the timing of the machine
instructions can be back-annotated to the source code.

The algorithms are described in detail in the publication


> Martin Becker, Marius Pazaj, and Samarjit Chakraborty. 2019. WCET Analy-
> sis meets Virtual Prototyping: Improving Source-Level Timing Annotations.
> In 22nd International Workshop on Software and Compilers for Embedded
> Systems (SCOPES ’19), May 27–28, 2019, Sankt Goar, Germany. ACM, New
> York, NY, USA, 10 pages. https://doi.org/10.1145/3323439.3323978

Please cite this work when using our tool.

**Sources are coming soon. We are currently in a refactoring process 
to make the tool architecture-independent**

## Overview
This tool establishes a mapping from the machine instructions of a program
to its source code ("what instructions belong to this source block?"). Unlike
debugging information, which partially addresses the same problem, this tool
computes a *complete* mapping, such that no instruction remains unmapped.
This property is important when the mapping is used to annotate the source
code with instruction timing, ensuring that no time "is lost". We use this
mapping for worst-case timing analysis, as we have demonstrated here
https://doi.org/10.1007/s10009-018-0497-2.

The tool consists of an architecture-specific frontend (C++),
a C++ code analyzer (not part of this repository), and
the mapper itself (Python). The frontend parses executables (ELF) and 
produces two JSON files (binary control flow graph and debug info). The code analyzer
computes source control flow graphs from the sources of a program.


## Building
### Frontend
Prerequisites:
 1. Boost Library version >= 1.55 (tested up to 1.66)
 2. gcc/g++ >= 4.9
 3. cmake >=3.10.1
 4. libelf-dev
 5. libdwarf-dev >= 2011
 6. zlib-dev
 7. nlohmann/json >= 3.1.1

Compiling:
 1. set correct paths in build.sh
  BUILD_DIR is the installation path relative to build.sh
  C_COMP is the C compiler to be used
  CXX_COMP is the C++ compiler to be used
  LOCAL_INC is TBD
  LOCAL_LIB is TBD
  BOOST_LIB is the installation path of the Boost libraries
  BOOST_INC is the include path of Boost
 2. run 'build.sh -c' (executes cmake to generate Makefiles and then runs step 3 automatically)
 3. run 'build.sh -m' (runs make and make install)

### Mapper
This part does not require any compilation, but the following
Python following modules must be installed:
 * networkx >= 2.0

## Usage
TODO
 
