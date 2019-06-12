#!/bin/bash

PROFILE=1  # comment for performance, uncomment for performance debugging

#BENCH_NAME=adpcm-encode
#SRC_FLOWS=adpcm
BENCH_NAME=ud
SRC_FLOWS=ud
BENCH=../test/benchmarks/$BENCH_NAME/O0

ELF2FLOW=../build/bin/elf2flow
TEMP=$BENCH/temp

OPTIMES=avr-spec.csv

echo ""
echo "Building benchmark..."
echo ""
(
	cd $BENCH
	make build
)

echo ""
echo "Analyzing binary..."
echo ""

rm -f $BENCH/*.json

$ELF2FLOW -f $BENCH/main.asm -e $BENCH/main.elf -a Avr -d $BENCH/debug.json -o $BENCH/main.json --inc-insn --inc-symb

echo ""
echo "Running mapping script for the following benchmark: $BENCH_NAME"
echo "Temp=$TEMP"
echo ""

if [ ! -d $TEMP ]; then
	mkdir -p $TEMP
fi

# mapping
if [ ! -z "$PROFILE" ]; then
	PROF=(-m cProfile -o profile.txt)
fi
python ${PROF[@]} main.py $@ \
    --bin-json   $BENCH/main.json \
    --dwarf-json $BENCH/debug.json \
    --src-csv    $BENCH/${SRC_FLOWS}_allflows.csv \
    --optime-csv $OPTIMES \
    --temp-dir   $TEMP \
    --render-graphs

if [ ! -z "$PROFILE" ]; then
	python print_profile.py profile.txt
fi
