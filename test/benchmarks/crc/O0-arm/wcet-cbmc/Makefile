# hey emacs, this is a -*- Makefile -*-   
#
# This Makefile can be used with find_wcet2.py to employ MAKE for WCET search.
# It is a template and should be copied in a separate folder, together with
# the file to be analyzed. That file must have extension *.in and contain ANSI
# C source code, and additionally a marker "###WCET_TEST###". This marker is
# replaced with assertions on the variable "timeElapsed", and repeatedly given
# to a model checker to find the lowest upper bound for timeElapsed.
#
# (C) 2016 Martin Becker <becker@rcs.ei.tum.de>, TU Muenchen, RCS.

# source code instrumented with "timeElapsed"
TMPL=$(wildcard *.in)

########################################
#  PATHS, IF NECESSARY
#########################################
PY=python
CBMC=cbmc
LOGFILE=wcet.log
TIMER=timeout -s INT 10m /usr/bin/time -v
CBMCINTERMED=modelcheck
FIND_WCET=~/async/WCET_gitlab/scripts/find_wcet.py
FUNC=CBMCDriver

########################################
#  VERIFICATION SETTINGS
#########################################
CFLAGS=-DIS_ANALYSIS -DCBMC -DNEWCODE
CBMCLOOPS= #--unwindset fir_filter_int.0:34,fir_filter_int.1:700
CBMCDRIVER=--function main
CBMCFLAGS+=$(CFLAGS) $(CBMCLOOPS) $(CBMCDRIVER) --all-properties --slice-formula --yices

# how precise (clock cycles) do we need WCET?
WCET_PREC=1

#########################################
#  BUILD RULES
#########################################
.PHONY: clean

all: $(LOGFILE)

$(LOGFILE): $(TMPL)
	GOTOINSFLAGS="--remove-calls-no-body;--function-inline $(FUNC);--constant-propagator" CBMC="$(CBMC)" CBMCFLAGS="$(CBMCFLAGS)" TIMEOUT="$(TIMER)" CBMCINTERMED="$(CBMCINTERMED)" $(PY) -u $(FIND_WCET) -p $(WCET_PREC) $^ | tee $(LOGFILE)
	#CBMC="$(CBMC)" CBMCFLAGS="$(CBMCFLAGS)" TIMEOUT="$(TIMER)" CBMCINTERMED="$(CBMCINTERMED)" $(PY) -u $(FIND_WCET) -p $(WCET_PREC) $^ | tee $(LOGFILE)

clean:
	rm -f $(LOGFILE)

