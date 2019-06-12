# tools
CC=avr-gcc
OBJDUMP=avr-objdump
ELF2FLOW=../../build/bin/elf2flow

# files
ELF=test
SRC=main.c
ASM=$(ELF).asm
FLOW=$(ELF).json
FLOW_PRETTY=$(ELF).pretty.json
DBG=$(ELF).debug.json

# flags
CFLAGS=-mmcu=atmega128 -O0 -g -gdwarf-3

all: $(ELF) $(FLOW)

$(ELF): $(SRC)
	$(CC) $(CFLAGS) $< -o $@

$(ASM): $(ELF)
	$(OBJDUMP) -dl $< > $@

$(FLOW): $(ELF) $(ASM)
	$(ELF2FLOW) --arch=Avr -i -s -f $(ASM) -e $(ELF) -d $(DBG) -o $@

#$(FLOW_PRETTY): $(FLOW)
#	python -m json.tool $< > $@

clean:
	rm -f $(ELF) $(ASM) $(FLOW) $(DBG)
