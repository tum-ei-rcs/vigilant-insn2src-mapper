#!/usr/bin/python
#
# Test lp-solve driver
#
from ext_lpsolve import LinProg

lp = LinProg('test', keep_files=False)
lp.set_objective("x1+x2")
lp.add_constraint('x1 >= 1')
lp.add_constraint('x2 >= 1')

obj, _ = lp.get_objective()
print "objective: {}".format(obj)
print "constraints: {}".format(" /\\ ".join([str(c) for c in lp.get_constraints()]))

lp.solve(mode='min')
print "state: {}".format(lp.state)
print "vars: {}".format(["{}={}".format(k, v) for k,v in lp.get_variables().iteritems()])
lobj, lval = lp.get_objective()
print "oval: {}".format(lval)
