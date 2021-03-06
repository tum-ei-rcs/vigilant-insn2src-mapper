# Vigilant Instruction-to-Source Mapper
This tool was developed for timing analysis of source code.
Its main purpose is to establish a safe mapping between machine code
and source-level constructs, such that the timing of the machine
instructions can be back-annotated to the source code.

The algorithms are described in detail in the publication


> Martin Becker, Marius Pazaj, and Samarjit Chakraborty. 2019. WCET Analysis
> meets Virtual Prototyping: Improving Source-Level Timing Annotations.
> In 22nd International Workshop on Software and Compilers for Embedded
> Systems (SCOPES ’19), May 27–28, 2019, Sankt Goar, Germany. ACM, New
> York, NY, USA, 10 pages. https://doi.org/10.1145/3323439.3323978 
> (free access: http://mediatum.ub.tum.de/doc/1484949/23817226017.pdf)

Please cite this work when using our tool.

## News
Support for caches coming soon!

## Overview
This tool establishes a mapping from the machine instructions of a program
to its source code ("which instructions belong to this source block?"). Unlike
debugging information, which partially address the same problem, this tool
computes a *complete* mapping, such that no instruction remains unmapped.
This is important when the mapping is used to annotate the source
code with instruction timing, ensuring that no time "is lost". We use this
mapping for worst-case execution timing analysis, as we have demonstrated here
https://doi.org/10.1007/s10009-018-0497-2 (free access to preprint: 
https://arxiv.org/pdf/1802.09239).

The tool consists of an architecture-specific frontend (for AVR and ARMv5, written in C++),
a C++ code analyzer (not part of this repository), and
the mapper itself (written in Python). The frontend parses executables (ELF) and
produces two JSON files (binary control flow graph and debug info). The code analyzer
computes source control flow graphs from the sources of a program.

**This version supports AVR and ARMv5 binaries**. In principle it should also work for
other architectures. In particular, ARM support needs OTAWA installed, since we use it
to compute the control flow graph (CFG) from the ARM binaries. OTAWA also supports
other architectures, hence this workflow should also work for those (e.g., ARMv7, PowerPC, Sparc, etc.).
The mapping for AVR and ARMv5 has been verified against cycle-accurate simulations.

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

For ARM support, you also need to install OTAWA v1 (www.otawa.fr).

### Mapper
This part does not require any compilation, but the following
Python following modules must be installed:
 * networkx >= 2.0

## Usage
Examples are in the subdirectory `test/benchmarks`. For example, to compute a mapping
for the program 'adpcm', do the following (assumes Linux):

### Example "adpcm" for AVR

```sh
cd test/benchmarks/adpcm-encode/O0
make build  # compiles the program for AVR (*.elf). Requires avr-gcc installed.
make flow  # computes CFG from ELF/binary (*.json)
make mapping  # invokes the Python mapper
```
For parameters see Makefile. The mapping process generates several files:
 1. The file with a instruction-to-source mapping for all functions: `mapping.map`
   * this is a CSV file, capturing this mapping from the source's point of view
   * e.g., `6; l768c9; 17108,17130,-10; 49,__adddi3_s8` indicates that source basic block number 6 (line 768 column 9) caused the binary basic blocks numbers 17108 and 17130 (and a virtual binary block -10), their total time is 49 clock cycles, and additionally a call to `__adddi3_s8` happens, whose timing is not included in the 49 cycles (see WCET library). If this field mentions a source function, then the time is also not included, but the callee has its own mapping. It is therefore the responsibility of the annotation tool to decide whether such calls have a mapping (and thus their timing is considered), or whether they are library functions.
 2. The directory `temp` within the benchmark contains various graphs (control flows, dominator trees, etc.). Perhaps the most interesting is the visualization of the maps. To inspect those, use a browser, e.g., `firefox temp/map_quantl.svg` (image is interactive; loops can be collapsed by clicking on their headers).

The file `mapping.map` can be read by our tool `cbbanalyzer` (separate repository), which annotates the C source with the timing. This tool also creates one input file that is necessary for the mapper, which is `adpcm_allflows.csv`. It is generated with clang's CFGGenerator, and gives a listing of source blocks.

### Example "cnt" for ARM
This requires the OTAWA toolbox to be installed.
```sh
cd test/benchmarks/cnt/O0-arm
make main.elf  # requires arm-none-eabi-gcc. E.g., GNU Arm Embedded 2018-Q4
make main.asm
make dwarf  # generates input (debug info) for mapper
make cfg.json  # generates input (binary flows) for mapper
make mapping  # generates mapping.map
```
Other outputs from the mapper are stored in the subfolder `maps`. For the documentation of `mapping.map`, see description above (AVR usage).

### WCET Library
The mapping contains the timing of all binary blocks that map to each source block. However, this timing excludes calls to all functions for which no source code is available. For such functions, we rely on a WCET library. One such library for avr-libc in version 1.8.0 is included in the file `data/wcet-lib/avr/libc-1.8.0/atmega128/wcet.lib`.

### Instruction Time Specification
An file with mnemomic and time specification is required to compute the clock cycles that are shown in `mapping.map`. If you don't need this, then you can omit the command line parameter `--optime-csv`. Otherwise, thr parameter must point to a CSV file that specifies how much time (min, max) each instruction takes. We have included two such specifications here:
 * `py-mapping/avr-spec.csv`: for AVR Atmega
 * `py-mapping/arm-trivial-spec.csv`: for a hypothetical ARM processor where every instruction takes one clock cycle
 
