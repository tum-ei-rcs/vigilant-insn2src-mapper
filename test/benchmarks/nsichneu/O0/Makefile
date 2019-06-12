# Hey Emacs, this is a -*- makefile -*-
########################## Makefile Options ##############################

# Target file name (without extension).
TARGET = main

# Define programs and commands.
SHELL = sh
CC = avr-gcc
OBJCOPY = avr-objcopy
OBJDUMP = avr-objdump
NM = avr-nm
AVRDUDE = avrdude
REMOVE = rm -f
COPY = cp
MAPPER=../../../../py-mapping/main.py
MERGEMAPS=../../../../py-mapping/merge_mapping.py
ELF2FLOW=../../../../build/bin/elf2flow
WCET_TOOL=boundt_avr
WCET_TOOL_OPTS=-device=ATmega128 -form=elf -elf_sym -v -no_stack -no_arithmetic -no_const
WCET_TOOL_OPTS+=-assert loopinfo.txt

# artifacts
SRC_ALL=nsichneu.c
WCET_FUN=main
#ANNOTS=--annot-file loop_annot.json
ASM=main.asm
ELF=main.elf
BFLOWS=main.json
SFLOWS=$(wildcard *_allflows.csv)
DWARF=debug.json
OPTIMES=../../avr-spec.csv
MAPDIR=temp

############# PLEASE DO NOT CHANGE ANYTHING BELOW THIS LINE ##############
MCU = atmega128
F_OSC = 16000000

SRC_DIR   	= ./src/
INCLUDE_GLOBAL = /usr/lib/avr/include/

# search for c files here

DEBUG = dwarf-2

EXTRAINCDIRS = $(INCLUDE_GLOBAL) $(INCLUDE_LOCAL) $(SRC_DIR)
CSTANDARD = -std=gnu99

CFLAGS = -g$(DEBUG)
CFLAGS += $(CDEFS) $(CINCS)
CFLAGS += -O0 -g -gcolumn-info
CFLAGS += -funsigned-char -funsigned-bitfields -fpack-struct -fshort-enums
CFLAGS += -Wall #-Wstrict-prototypes
CFLAGS += -Wa,-adhlns=$(<:.c=.lst)
CFLAGS += $(patsubst %,-I%,$(EXTRAINCDIRS))
CFLAGS += $(CSTANDARD)
CFLAGS += -DF_OSC=$(F_OSC) -D__AVR__
ASFLAGS = -Wa,-adhlns=$(<:.S=.lst),-gstabs 
ASFLAGS += -DF_OSC=$(F_OSC)

PRINTF_LIB_MIN = -Wl,-u,vfprintf -lprintf_min
PRINTF_LIB_FLOAT = -Wl,-u,vfprintf -lprintf_flt
SCANF_LIB_MIN = -Wl,-u,vfscanf -lscanf_min
SCANF_LIB_FLOAT = -Wl,-u,vfscanf -lscanf_flt
MATH_LIB = -lm

LDFLAGS = -Wl,-Map=$(TARGET).map,--cref
LDFLAGS += $(EXTMEMOPTS)
#LDFLAGS += -gc-sections 
LDFLAGS+=-lm

OBJ_ALL = $(SRC_ALL:.c=.o) $(ASRC:.S=.o)

ALL_CFLAGS = -mmcu=$(MCU) -I. $(CFLAGS) $(GENDEPFLAGS)
ALL_ASFLAGS = -mmcu=$(MCU) -I. -x assembler-with-cpp $(ASFLAGS)

.PHONY: build flow mapping

all: build flow mapping

build: $(ELF) $(ASM)

flow: $(BFLOWS)

$(BFLOWS): $(ELF) 
	$(ELF2FLOW) -f $(ASM) -e $(ELF) -a Avr -d $(DWARF) -o $(BFLOWS) --inc-insn --inc-symb

mapping: $(BFLOWS)
	mkdir -p $(MAPDIR)
	python $(MAPPER) --bin-json $(BFLOWS) --dwarf-json $(DWARF) --src-csv $(SFLOWS) --optime-csv $(OPTIMES) --temp-dir $(MAPDIR) $(ANNOTS) --render-graphs
	#python -m cProfile -o profile.txt $(MAPPER) --bin-json $(BFLOWS) --dwarf-json $(DWARF) --src-csv $(SFLOWS) --optime-csv $(OPTIMES) --temp-dir $(MAPDIR) $(ANNOTS) # --render-graphs
	python $(MERGEMAPS) -m $(MAPDIR) -b`pwd` -o mapping.map
	#python ../../../../py-mapping/print_profile.py profile.txt

$(ASM): $(ELF)
	$(OBJDUMP) -Dl $< > $@

.SECONDARY : /$(TARGET).elf
.PRECIOUS : $(OBJ_ALL)
%.elf: $(OBJ_ALL)
	$(CC) $(ALL_CFLAGS) $(OBJ_ALL) --output $@ $(LDFLAGS)

%.o : %.c
	@$(CMD_PREFIX) echo
	@$(CMD_PREFIX) echo $(MSG_COMPILING) $<
	rm -f $<.opt  # because GCC does not delete it when there is no output
	$(CMD_PREFIX) $(CC) -c $(ALL_CFLAGS) -fopt-info-optimized=$<.opt $< -o $@ 

wcet: $(ELF)
	@echo "WCET analysis..."
	$(WCET_TOOL) $(WCET_TOOL_OPTS) $< $(WCET_FUN) > wcet.log 2> stderr.log

clean: 
	rm -f $(OBJ_ALL) $(TARGET).elf $(TARGET).hex *.lst *.asm *.map $(BFLOWS) $(DWARF)
	rm -rf $(MAPDIR)


