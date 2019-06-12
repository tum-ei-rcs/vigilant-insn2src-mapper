#!/bin/bash
# convenience wrapper for mapping workflow. Calls tools in required order.
#

# Opts
BENCH_DIR=/home/marius/workspaces/rp-workspace/benchmarks/b-o0
PYSCRIPT_DIR=/home/marius/workspaces/ma-workspace/MP-MA/py-mapping
PYSCRIPT=$PYSCRIPT_DIR/main.py
MAP_DIR=$(pwd)
MAP_MERGE_SCRIPT=$MAP_DIR/merge_mapping.py


process_bench() {
    # Remove previous files
    rm -f $MAP_DIR/$BENCH/elf2flow.dbg
    rm -f $MAP_DIR/$BENCH/main.json

    # Generate binary flows
    elf2flow -a Avr --inc-symb --inc-insn \
        -f $BENCH_DIR/$BENCH/main.asm \
        -e $BENCH_DIR/$BENCH/main.elf \
        -o $MAP_DIR/$BENCH/main.json \
        -d $MAP_DIR/$BENCH/elf2flow.dbg

    # Find the source csv
    SRC_CSV=$(find $BENCH_DIR/$BENCH -iname "*_allflows.csv")

    python $PYSCRIPT \
        --bin-json $MAP_DIR/$BENCH/main.json \
        --dwarf-json $MAP_DIR/$BENCH/elf2flow.dbg \
        --src-csv $SRC_CSV \
        --temp-dir $MAP_DIR/$BENCH/$HOM_ORDER \
        --optime-csv $PYSCRIPT_DIR/avr-spec.csv \
        --hom-order $HOM_ORDER \
        --annot-file $BENCH_DIR/$BENCH/loop_annot.json \
        $SUPPRESS_LOG

    # Merge individual mapping outputs
    python $MAP_MERGE_SCRIPT \
        --mapping-dir $MAP_DIR/$BENCH/$HOM_ORDER \
        --bench-dir $BENCH_DIR/$BENCH \
        --out-file $MAP_DIR/$BENCH/$HOM_ORDER/merged_mapping.map
}


print_usage() {
    echo "Following arguments are valid:"
    echo ""
    echo "--benchmark      Benchmark name."
    echo "--suppress-log   Supresses logging."
    echo "--hom-order      Specify the dominator tree order used by the dominator homomorphism arlgorithm."
    echo "                 Either 'pre' or 'post'"
    echo ""
}


########
# MAIN #
#######


if [ $# -eq 0 ]; then
    echo "No arguments given."
    echo ""
    print_usage
    exit 1
fi


for i in "$@"; do
case $i in
    --suppress-log)
    SUPPRESS_LOG='--suppress-log'
    shift
    ;;

    --hom-order=*)
    HOM_ORDER="${i#*=}"
    shift
    ;;

    --benchmark=*)
    BENCH="${i#*=}"
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


process_bench
