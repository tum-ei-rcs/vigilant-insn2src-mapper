#!/bin/sh

# arg0: benchmark folder path, function assumes that the passed folder exists
#
#
# NOTE: - json files are hardcoded.
#       - if FLAG_ANALYZE_ONLY is set, function exits after invoking elf2flow.
#
process_bench() {
    # Check number of arguments passed
    if [ ! $# -eq 1 ]; then
        echo "$ERR Invalid number of arguments passed in process_bench()."
        exit 1
    fi
    
    # Assign local variables
    local b_folder=$1
    local b_src_csv=$(find $b_folder -maxdepth 1 -type f -iname '*_allflows.csv' -print -quit)
    local b_bin_json=$b_folder/main.json
    local b_bin_debug=$b_folder/debug.json
    local b_temp_folder=$TEMP_FOLDER/$b_folder
    
    mkdir -p $b_temp_folder

    # Analyze binary (skips analysis if files already present)
    analyze_bin $b_folder
    status=$?
    if [ "$FLAG_ANALYZE_ONLY" = "TRUE" ]; then
        return $status
    fi
    
    # Return if analysis failed
    if [ ! $status -eq 0 ]; then
        return $status
    fi

    # Run the python script
    local suppress_log=""
    if [ "$FLAG_ANL_NO_LOG" = "TRUE" ]; then
        suppress_log="--suppress-log"
        redirect=/dev/null
    fi

    python $PYSCRIPT \
        --bin-json    $b_bin_json \
        --dwarf-json  $b_bin_debug \
        --src-csv     $b_src_csv \
        --optime-csv  $OPCSV \
        --temp-dir    $b_temp_folder \
        $suppress_log
    return $?
}


analyze_bin() {
    # Check number of arguments passed
    if [ ! $# -eq 1 ]; then
        echo "$ERR Invalid number of arguments passed in analyze_bin()."
        exit 1
    fi

    local b_folder=$1
    local suppress_log=""
    local redirect=/dev/tty

    if [ "$FLAG_ANL_NO_LOG" = "TRUE" ]; then
        suppress_log="--suppress-log"
        redirect=/dev/null
    fi

    if [ -f "$b_folder/main.json" ] && [ -f "$b_folder/debug.json" ]; then
        return 0
    fi

    # Remove all json files
    rm -f $b_folder/*.json

    # Invoke elf2flow
    $ELF2FLOW -f $b_folder/main.asm -e $b_folder/main.elf -a Avr -d $b_folder/debug.json -o $b_folder/main.json --inc-insn --inc-symb $suppress_log > $redirect
  
    if [ ! $? -eq 0 ]; then
        echo "$ERR Could not analyze binary."
        rm -f $b_folder/*.json
        return 1
    fi

    return 0
}   


search_benchs() {
    SRC_FLOWS=$(find $BENCH_ROOT -maxdepth 2 -type f -iname '*_allflows.csv' -print | sort -u)

    if [ -z "$SRC_FLOWS" ]; then
        echo "$ERR Could not find benchmark(s)."
        exit 1
    fi
}


print_usage() {
    echo "Following arguments are valid:"
    echo ""
    echo "-b=*  | --bench=*         process specific benchmark"
    echo "-a    | --all-benchs      process all benchmarks"
    echo "-ab   | --analyze-bin     only analyze binary during processing"
    echo "-anl  | --analyze-no-log  suppress logging during binary analysis"
    echo "-r=*  | --root=*          path of root folder of benchmarks"
    echo "-t=*  | --temp=*          path of temporary folder"
    echo "-e=*  | --elf2flow=*      path of elf2flow executable"
    echo "-py=* | --pyscript-dir=*  path of py script dir"
    echo "-op=* | --opcode-csv=*    path of opcode csv file"
    echo ""
}


check_paths() {
    if [ ! -d "$BENCH_ROOT" ]; then
        echo "$ERR Root folder \"$BENCH_ROOT\" does not exist."
        exit 1
    fi

    if [ ! -z "$TEMP_ROOT" ] && [ ! -d "$TEMP_ROOT" ]; then
        echo "$ERR Temp folder \"$TEMP_ROOT\" does not exist."
        exit 1
    fi

    if [ ! -f "$ELF2FLOW" ]; then
        echo "$ERR Incorrect path given for elf2flow executable."
        exit 1
    fi

    if [ ! -f "$PYSCRIPT" ]; then
        echo "$ERR Incorrect path given for python script."
        exit 1
    fi

    if [ ! -f "$OPCSV" ]; then
        echo "$ERR Incorrect path given for opcode csv file."
        exit 1
    fi
}


########
# MAIN #
########

############################
# Colored text and logging
E="\033"
C_RST="$E[0m"
C_INV="$E[7m"
ERR="$E[0;41m ERROR  $C_RST"
ERR_2="[ $E[91mERRO$C_RST ]"
INF="[ $E[92mINFO$C_RST ]"
############################

# Default values
TEMP_FOLDER=test/temp
ELF2FLOW=$HOME/workspaces/ma-workspace/MP-MA/build/bin/elf2flow
BENCH_ROOT=.
PYSCRIPT=./main.py


if [ $# -eq 0 ]; then
    echo "No arguments given."
    echo ""
    print_usage
    exit 1
fi

# Parse arguments
for i in "$@"; do
case $i in
    -b=*|--bench=*)
    BENCH="${i#*=}"
    shift
    ;;

    -r=*|--root=*)
    BENCH_ROOT="${i#*=}"
    shift    
    ;;

    -ab|--analyze-bin)
    FLAG_ANALYZE_ONLY=TRUE
    shift
    ;;

    -anl | --analyze-no-log)
    FLAG_ANL_NO_LOG=TRUE
    shift
    ;;

    -a|--all-benchs)
    FLAG_ALL_BENCHS=TRUE
    shift
    ;;

    -t=*|--temp=*)
    TEMP_FOLDER="${i#*=}"
    shift
    ;;

    -e=*|--elf2flow=*)
    ELF2FLOW="${i#*=}"
    shift
    ;;

    -py=*|--pyscript-path=*)
    PYSCRIPT="${i#*=}"
    shift
    ;;

    -op=*|--opcode-csv=*)
    OPCSV="${i#*=}"
    shift
    ;;

    -h|--help)
    print_usage
    exit 0
    ;;

    *)
    echo "Invalid argument given: $i"
    echo ""
    print_usage
    exit 1
    ;;
esac
done

# Check if paths are valid
check_paths

# Process all benchmarks if "-a|--all-benchs" specified
if [ "$FLAG_ALL_BENCHS" = "TRUE" ]; then
    echo "$INF Processing all benchmarks in \"$BENCH_ROOT\"..."
    echo ""
    search_benchs

    for f in $SRC_FLOWS; do
        echo "$INF Processing benchmark $C_INV ${f%/*} $C_RST..."
        process_bench ${f%/*}
        if [ ! $? -eq 0 ]; then
            echo "$ERR_2 An error occurred while processing benchmark ${f%/*}.\n"
            continue
        fi
        echo "$INF All OK.\n"
    done

    exit 0
fi

# Process specific benchmark (we land here if FLAG_ALL_BENCHS is not set)
if [ ! -z "$BENCH" ]; then
    echo "$INF Processing benchmark \"$C_INV $BENCH $C_RST\"..."
    echo ""

    # Find benchmark folder
    if [ ! -d "$BENCH_ROOT/$BENCH" ]; then
        echo "$ERR Could not find benchmark $BENCH."
        exit 1
    fi

    # Process benchmark
    process_bench $BENCH_ROOT/$BENCH
else
    echo "No benchmark specified."
    exit 1
fi

exit 0





