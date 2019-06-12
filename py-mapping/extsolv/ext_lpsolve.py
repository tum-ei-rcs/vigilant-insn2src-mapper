#
# Little wrapper for lp_solve 5.5 binary via file I/O. Lpsolve's own python wrapper crashes.
# Quick and dirty. Use with care.
#
import re
import os
import subprocess


class LinTerm(object):
    """a*x or a x or a or x, where a is numeric and x an identifier"""
    def __init__(self, fromstring):
        parts = re.split(r'\*|\s+', fromstring)
        self.var = None
        self.mult = 1
        for p in parts:
            if p == '':
                continue
            try:
                self.mult = float(p)
            except ValueError:
                self.var = p

    def __str__(self):
        ss = "{}".format(self.mult)
        if self.var is not None:
            ss += "*{}".format(self.var)
        return ss

    def get_variable(self):
        return self.var

    def write_lp(self):
        ss = ""
        if self.mult != 1 or self.var is None:
            ss += "{}".format(self.mult)
        if self.var is not None:
            if ss:
                ss += " "
            ss += "{}".format(self.var)
        return ss


class LinClause(object):
    """ax + bc + ..."""
    def __init__(self, fromstring=None, termlist=None):
        assert termlist or fromstring
        # --
        if termlist:
            assert isinstance(next(iter(termlist)), LinTerm)
        else:
            parts = fromstring.split('+')  # FIXME: allow minus
            termlist = [LinTerm(fromstring=s) for s in parts]
        # --
        self.terms = termlist

    def get_variables(self):
        return (t.get_variable() for t in self.terms)

    def __str__(self):
        return " + ".join([str(t) for t in self.terms])

    def write_lp(self):
        return " ".join([lt.write_lp() for lt in self.terms])


class LinCon(object):
    """<LinClause> <op> <LinClause>"""
    def __init__(self, lhs, rhs, op):
        assert isinstance(lhs, LinClause)
        assert isinstance(rhs, LinClause)
        # --
        self.lhs = lhs
        self.rhs = rhs
        self.op = op

    def __str__(self):
        return self.write_lp()

    def write_lp(self):
        return "{} {} {}".format(self.lhs.write_lp(), self.op, self.rhs.write_lp())


class LinProg(object):
    """Defines a linear problem to be solved"""

    def __init__(self, name, keep_files=False):
        self.keep_files = keep_files
        self.binary = '/usr/bin/lp_solve'
        self.opts = ''
        self.name = name
        # --
        self.obj = None
        self.cons = list()  # list(LinCon)
        # --
        self.objval = None
        self.vars = dict()  # dict(str->value)
        self.state = 'invalid'

    def _write_lpfile(self, infile, mode):
        """encode to lp format"""

        def declare_vartypes():
            intsection = []
            binsection = []
            for v, vd in self.vars.iteritems():
                if vd['type'] == 'int':
                    intsection.append(v)
            for v, vd in self.vars.iteritems():
                if vd['type'] == 'bin':
                    binsection.append(v)
            if intsection:
                f.write("int " + ",".join(intsection) + ";\n\n")
            if binsection:
                f.write("int " + ",".join(binsection) + ";\n\n")

        with open(infile, 'w') as f:
            f.write("{}: {};\n\n".format(mode, self.obj.write_lp()))
            for c in self.cons:
                f.write("{};\n".format(c.write_lp()))
            f.write("\n")
            declare_vartypes()

    def _parse_result(self, outs):
        """Parse results from lp_solve 5.5

        Expected ouput (example):
            Value of objective function: 1e+30

            Actual values of the variables:
            x                               0
            y                             2.5
            z                           1e+30
        """
        mode = None
        for line in outs.split("\n"):
            if mode is None:
                m = re.search(r"Value of objective function: (.*)", line)
                if m:
                    self.objval = m.group(1)
                    continue
                m = re.search(r"Actual values of the variables:", line)
                if m:
                    mode = "vars"
                    continue
            elif mode == "vars":
                m = re.search(r"(\w+)[\s\t]+(.*)", line)
                if m:
                    var = m.group(1).strip()
                    val = float(m.group(2).strip())
                    if var not in self.vars:
                        self.add_variables([var])
                    self.vars[var]['value'] = val

    def _run_lpsolve(self, infile):
        cmd = [self.binary]
        if self.opts:
            cmd.append(self.opts)
        cmd.append('<' + infile)
        return subprocess.check_output(cmd)

    def set_objective(self, fromstring):
        # --
        self.obj = LinClause(fromstring=fromstring)
        self.add_variables(self.obj.get_variables())

    def add_variables(self, varlist):
        for v in varlist:
            if v is not None:
                if v not in self.vars:
                    self.vars[v] = dict(value=None, type='int')

    def set_variable_type(self, varname, typ):
        """By default variables are integer. Override here"""
        assert type in ('float', 'int', 'bin'), "Unsupported variable type"
        # --
        if varname not in self.vars:
            self.add_variables([varname])
        self.vars[varname]['type'] = typ

    def add_constraint(self, fromstring):
        m = re.match(r"(.*?)(<=|>=|=|<|>)(.*)", fromstring)
        assert m, "cannot parse"
        lhs = LinClause(m.group(1))
        self.add_variables(lhs.get_variables())
        op = m.group(2).strip()
        rhs = LinClause(m.group(3))
        self.add_variables(rhs.get_variables())
        self.cons.append(LinCon(lhs, rhs, op))

    def get_objective(self):
        return self.obj, self.objval

    def get_variables(self):
        return self.vars

    def get_constraints(self):
        return self.cons

    def solve(self, mode='max'):
        assert self.obj, "Objective function not set"
        assert self.cons, "Constraints missing"
        assert mode in ('min', 'max')
        # --
        infile = "{}.lp.in".format(self.name)
        self._write_lpfile(infile, mode)

        try:
            outs = self._run_lpsolve(infile)
            self.state = 'solved'
            self._parse_result(outs)
        except subprocess.CalledProcessError:
            self.state = 'failed'

        if not self.keep_files:
            os.remove(infile)
