# generates a WCET library for libc functions by running libc's test cases and measuring WCET
LIB=../wcet_fplib.lib.generated
SELECTED_FUNCTIONS_FILE=../../libcfuncs.txt

DEVICE=atmega128
CFLAGS=-O0 -g -mmcu=$(DEVICE)
SIMULATOR=~/async/WCET_gitlab/scripts/simulavr2times.py

TESTS=$(wildcard *.c)
SIMS=$(TESTS:.c=.sim)

all: $(LIB)

$(LIB): $(SIMS)
	../../generate_library.py -f $(SELECTED_FUNCTIONS_FILE) -o $(LIB) $(SIMS)

%.elf: %.c
	avr-gcc $(CFLAGS) $< -o $@

%.sim: %.elf
	echo "Running test case $< ..."
	python -u $(SIMULATOR) -e $< -s "-l0 -datmega128 -Texit" | tee $@

clean:
	rm -f *.elf *.sim
