CC=arm-none-eabi-gcc
OBJDUMP=arm-none-eabi-objdump

OTAWA=owcet
OTAWA2JSON=~/async/graph-mapping/py-mapping/fparser/otawa2json.py
SIM=ogensim
SIM2TIME=/home/becker/async/WCET_gitlab/scripts/ogensim2times.py
MAPPER=../../../../py-mapping/main.py
MERGEMAPS=../../../../py-mapping/merge_mapping.py
ELF2FLOW=../../../../build/bin/elf2flow

GRAPH_DIR=graphs/
MAPDIR=maps

SRCS=fdct.c
EXE=main.elf
ASM=$(EXE:.elf=.asm)
OBJS=$(SRCS:.c=.o)
FFX=$(EXE).ffx
FF=$(EXE:.elf=.ff)
CFG=cfg.xml
JSON=$(CFG:.xml=.json)
FUNC=fdct
DWARF=debug.json
OPTIMES=../../../../py-mapping/arm-trivial-spec.csv
BFLOWS=main.json
SFLOWS=$(wildcard *_allflows.csv)

CFLAGS=-O0 -g --std=gnu99
CFLAGS+=--specs=nosys.specs -march=armv5

LDFLAGS=-gdwarf-4
LDFLAGS+=-lm

OWCET_SCRIPT=owcet-script.osx
OTAWA_PATH=$(shell otawa-config --data)
#OTAWA_FLAGS=-s $(OTAWA_PATH)/share/Otawa/scripts/generic.osx
OTAWA_FLAGS=-s $(OWCET_SCRIPT)
OTAWA_FLAGS+=--log=bb -v
OTAWA_FLAGS+=-p pipeline=otawa-pipelineconfig.xml
OTAWA_FLAGS+=-p cache=otawa-cacheconfig.xml
OTAWA_FLAGS+=-p graphdir=$(GRAPH_DIR)
#OTAWA_FLAGS+=-i ccg # cache modeling method
#OTAWA_FLAGS+=-t exegraph # pipeline modeling method
#SIM_FLAGS+=-c otawa-cacheconfig.xml 
#SIM_FLAGS+=--traceCache
SIM_FLAGS+=-p otawa-pipelineconfig.xml 
SIM_FLAGS+=-m otawa-memoryconfig.xml 
SIM_FLAGS+=-vl 0
SIM_FLAGS+=--dumpCfg sim.cfg 
SIM_FLAGS+=--inlineCalls  # so that WCET output and sim concur

all: $(EXE) dwarf flow

dwarf: $(DWARF)

flow: $(BFLOWS)

$(EXE): $(OBJS)
	$(CC) $(CFLAGS) $^ $(LDFLAGS) -o $@

$(ASM): $(EXE)
	$(OBJDUMP) -Dl $< > $@

%.o: %.c
	$(CC) $(CFLAGS) -c $< -o $@

$(DWARF): $(ASM) $(EXE)
	$(ELF2FLOW) -f $(ASM) -e $(EXE) -a ArmV5 -d $(DWARF) --inc-insn --inc-symb --ignore-errors

$(BFLOWS): $(CFG)
	$(OTAWA2JSON) --xml $(CFG) --out $@ --asm $(ASM)

mapping: $(BFLOWS)
	mkdir -p $(MAPDIR)
	python $(MAPPER) --mapper=homomorphism --bin-json $(BFLOWS) --dwarf-json $(DWARF) --src-csv $(SFLOWS) --optime-csv $(OPTIMES) --temp-dir $(MAPDIR) --render-graphs $(ANNOTS) 2>&1 | tee mapping.log
	python $(MERGEMAPS) -m $(MAPDIR) -b`pwd` -o mapping.map

$(FF): $(EXE)
	mkff $(EXE) > $@
	echo "Please edit file $@ manually"

$(FFX): $(SRCS)
	orange $^ -- $(FUNC) -o $@

$(CFG): $(EXE)
	dumpcfg --all -x $^ > $@

$(JSON): $(CFG)
	$(OTAWA2JSON) --xml $< --out $@

wcet.log: $(EXE) $(FFX) $(OWCET_SCRIPT)
	mkdir -p $(GRAPH_DIR)
	$(OTAWA) $(OTAWA_FLAGS) $(EXE) $(FUNC) -f $(FFX) 2>&1 | tee $@

sim.log: $(EXE)
	$(SIM) $(SIM_FLAGS) $< 2>&1 | tee sim1.log
	mv sim1.log $@

times.log: sim.log $(EXE)
	$(SIM2TIME) -e $(EXE) -t sim.log --pretty --coverage | tee $@

clean:
	rm -f *.o $(EXE) $(FFX) $(FF) wcet.log
	rm -f $(BFLOWS) $(DWARF)
	rm -rf $(MAPDIR) mapping.log mapping.map
	rm -f sim.log times.log
