#!/bin/bash
EXE=main.elf
XML=cfg.xml
JSON=cfg.json

# TODO: iterate over nm's output; otherwise OTAWA doesn't give all symbols
# FIXME: can we modify dumpcfg: 1. also give mnemonic, 2. all symbols

#dumpcfg --all -x $ELF > $XML
ASM=/home/becker/async/WCET_gitlab/benchmarks/otawa/otawa/main.asm
XML=/home/becker/async/WCET_gitlab/benchmarks/otawa/otawa/cfg.xml

python otawa2json.py --asm $ASM --xml $XML --out $JSON
