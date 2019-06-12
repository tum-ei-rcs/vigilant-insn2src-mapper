#!/usr/bin/python
#
# check cache classification for superlong BBs (known bug in OTAWA)
import argparse
import re


def scan_log(args):
    bbinfo = dict()
    lblock2bb = dict()

    def register_bb(bbid):
        bbinfo[bbid] = dict(wraps=0, sets=set(), unsound=[])

    def read_log():
        with open(args.log, 'r') as f:
            lno = 0
            mode = None
            bb = None
            bb_entry_set = None
            catset = None
            for lno, line in enumerate(f):
                if mode is None:
                    if re.match(r"Starting otawa::util::LBlockBuilder", line):
                        mode = "lbb"
                    if re.match(r"Starting otawa::CAT2Builder", line):
                        mode = "cat"
                elif mode == "lbb":
                    if re.match(r"Ending otawa::util::LBlockBuilder", line):
                        mode = None
                        continue
                    m = re.search(r"process BB (\d+)", line)
                    if m:
                        bb = m.group(1)
                        register_bb(bb)
                        bb_entry_set = None
                        continue
                    m = re.search(r"block at ([0-9a-f]+) size \d+ \(cache block [0-9a-f]+, "
                                  r"set = (\d+)", line)
                    if m:
                        lblock2bb[m.group(1)] = bb
                        set_here = int(m.group(2))
                        if bbinfo[bb]['wraps'] >= args.assoc:
                            bbinfo[bb]['sets'].add(set_here)
                        if bb_entry_set is None:
                            bb_entry_set = set_here
                            # print "bb {}: entry set={}".format(bb, bb_entry_set)
                        else:
                            if set_here == bb_entry_set:
                                bbinfo[bb]['wraps'] += 1
                                bbinfo[bb]['sets'].add(set_here)
                elif mode == "cat":
                    if re.match(r"Ending otawa::CAT2Builder", line):
                        mode = None
                        continue
                    # now we know which sets are wrapping. Ensure they have no AH/FM classification
                    m = re.search(r"SET (\d+)", line)
                    if m:
                        catset = int(m.group(1))
                        continue
                    m = re.search(r"([0-9a-f]+): ([\w-]+)", line)
                    if m:
                        lb_here = m.group(1)
                        lb_cat = m.group(2)
                        if lb_here not in lblock2bb:
                            # print "WARN: l-block without BB: {}".format(lb_here)
                            continue
                        bb = lblock2bb[lb_here]
                        if catset in bbinfo[bb]['sets']:
                            # one of the affected
                            if lb_cat not in ('always-miss', 'pessimistically', 'not-classified'):
                                bbinfo[bb]['unsound'].append((lb_here, lb_cat))

        print "Processed {} lines".format(lno)

    def analyze():
        possibly_unsound = False
        for bb, data in bbinfo.iteritems():
            if data['unsound'] and data['wraps'] >= args.assoc:
                print "BB {} wraps in sets {}. Possibly unsound L-block classifications: {}".\
                      format(bb, data['sets'], data['unsound'])
                possibly_unsound = True
        if not possibly_unsound:
            print "INFO: Everything seems okay with associativity A={}".format(args.assoc)
        else:
            print "WARN: Analysis result is possibly unsound."

    print "Checking OTAWA log '{}' for PERS inconsistencies...".format(args.log)
    read_log()
    analyze()
    return 0


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Sanity-check OTAWA cache analysis")
    parser.add_argument("-a", "--assoc", default=2, help="cache associativity")
    parser.add_argument("log")
    args = parser.parse_args()
    scan_log(args)
    print "Done."
