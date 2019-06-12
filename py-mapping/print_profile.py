#!/usr/bin/python
import sys
import pstats

if len(sys.argv) < 2:
    print "need to provide file name"
    sys.exit(1)

f = sys.argv[1]
print "Profile={}".format(f)
p = pstats.Stats(f)
p.strip_dirs().sort_stats('cumtime').print_stats(20)  # cumtime, tottime
