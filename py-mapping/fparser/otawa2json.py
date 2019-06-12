#!/usr/bin/python
from __future__ import print_function
import logging
import coloredlogs
import argparse
import os.path
import sys
import otawaflows
import json
import copy


# Set up logging
lvl = 'DEBUG'
coloredlogs.install(level=lvl, fmt='[ %(levelname)s ] <%(name)s> %(message)s')
log = logging.getLogger(__file__)

# globals
outfile = sys.stdout
INSN_LENGTH = 4


def create_insnmap(flows):
    """Get instructions of function"""

    # if we parse ASM: targets must be computed

    # if we go by flow graph: missing mnemonics, missing ops, missing insn (non-user code)

    def process_flow(flow):
        """create insnmap of a single function

        We either use the assembly, but then we have to parse a lot,
        or we use OTAWA's flow info, which however lacks mnemonics
        """

        def get_mnemo(assembly):
            return assembly.split(' ')[0].upper()

        def targets_of(bbb, this_addr):
            """returns addresses of instructions after given BB"""
            succs = list(flow.digraph.successors(bbb))
            tnext_addrs = [flow.digraph.node[v].get('addr', None)
                           for v in succs]
            next_addrs = [t for t in tnext_addrs if t is not None]

            # omit aways closest ones (that's what the mapping wants)
            default_addr = []
            if len(next_addrs) > 1:
                diff = [abs(na - this_addr) for na in next_addrs]
                idx_min = diff.index(min(diff))
                default_addr.append(next_addrs.pop(idx_min))
            return next_addrs, default_addr

        fimap = []  # {"Addr":0,"Mnem":"JMP","Op":["0x8c"],"Target":[140]}, ...
        for n in flow.digraph.nodes:
            bbd = flow.digraph.nodes[n]
            addrs = bbd.get('addrs', [])
            asms = bbd.get('asm', [])
            if not addrs:
                continue
            assert len(addrs) == len(asms)

            # by default we assume that insns appear in execution sequence
            prev_addr = prev_asm = None
            for addr, asm in zip(addrs, asms):
                if addr != addrs[0]:
                    insn = dict(Addr=prev_addr, Mnem=get_mnemo(prev_asm),
                                Op=[], Target=[addr])
                    fimap.append(insn)
                prev_addr = addr
                prev_asm = asm

            # handle last insn in BB: targets addresses given by CFG edges
            targets = targets_of(n, prev_addr)
            insn = dict(Addr=addrs[-1], Mnem=get_mnemo(asms[-1]), Op=[],
                        Target=targets[0], DefaultTarget=targets[1])
            fimap.append(insn)
        return fimap

    imap = []
    for f in flows:
        imap.extend(process_flow(f))
    # --
    return imap


def correct_calls(flow):
    """Each function call must have an additional BB"""
    for u in list(flow.digraph.nodes):
        bbd = flow.digraph.node[u]
        callees = bbd.get('calls', None)
        if callees is not None:
            newattr = copy.deepcopy(bbd)
            newattr['asm'] = [newattr['asm'][-1]]
            newattr['addrs'] = [newattr['addrs'][-1]]
            newattr['numInsn'] = 1
            newattr['size'] = INSN_LENGTH
            dummy = flow.make_bb(newattr)
            # add edges
            for v in list(flow.digraph.successors(u)):
                flow.add_edge([dummy, v])
                flow.del_edge([u, v])
            flow.add_edge([u, dummy])
            # finally, make actual call BB a normal one
            del bbd['calls']


def write_flow(flow):
    """Flow graph to JSON"""
    global outfile

    def list_bb():
        li = [{'ID': bb} for bb in flow.digraph.nodes]
        for bb in li:
            nid = bb['ID']
            addrs = flow.digraph.nodes[nid].get('addrs', None)
            if addrs is not None:
                arange = [min(addrs), max(addrs)]
                bb['AddrRanges'] = [arange]
                # sanity check: contiguous?
                len_addr = arange[1] - arange[0] + INSN_LENGTH
                len_bb = flow.digraph.nodes[nid]['size']
                assert len_bb >= len_addr, "Address range of BB not contiguous"
            callees = flow.digraph.node[nid].get('calls', None)
            if callees is not None:
                bb['BlockType'] = 'FunctionCall'
                bb['calls'] = callees
            else:
                bb['BlockType'] = flow.digraph.node[nid].get('BB.type', 'Normal')
            bb['BlockType'] = bb['BlockType'][0].upper() + bb['BlockType'][1:]
        return li

    def list_ed():
        return [[e[0], e[1]] for e in flow.digraph.edges]

    di = dict(BasicBlocks=list_bb(), Edges=list_ed(), Name=flow.name, Type="Flow")
    print(json.dumps(di), file=outfile)
    print('\n\n', file=outfile)


def write_symtab(stab):
    """Symbol table to JSON"""
    global outfile
    di = dict(Section=".text", Type="SymbolMap", Symbols=stab)
    print(json.dumps(di, indent=4), file=outfile)
    print('\n\n', file=outfile)


def write_insnmap(imap):
    """Instruction map to JSON
    We additionally need to consult the assembly, since we need mnemonics and operands
    """
    global outfile
    di = dict(Instructions=imap, Section=".text", Type="InsnMap")
    print(json.dumps(di, indent=4), file=outfile)
    print('\n\n', file=outfile)


def main(args):
    global outfile
    if args.out is not None:
        outfile = open(args.out, 'w')

    ocfg = otawaflows.CFGReader(filename=args.xml)
    flows = ocfg.getFlows()
    for f in flows:
        log.info("Flow {} @0x{:x}".format(f.name, f.address))

    # create symtab
    symtab = [dict(Symbol=f.name, Addr=f.address) for f in flows]

    # creates instruction info
    insnmap = create_insnmap(flows)

    # export as JSON
    for f in flows:
        correct_calls(f)  # TODO: each call has one additional BB
        write_flow(f)
    write_insnmap(insnmap)
    write_symtab(symtab)

    if args.out is not None:
        outfile.close()
    # --
    return 0


def check_file(fpath):
    if not os.path.isfile(fpath):
        raise argparse.ArgumentTypeError('Invalid file path given.')
    return fpath


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="OTAWA to JSON flow converter")
    parser.add_argument('--out', default=None,
                        help='path of output file (JSON)')
    required = parser.add_argument_group('required arguments')
    required.add_argument('--asm', type=check_file, default=None,
                          help='optional: path to ASM (of ELF) file')
    required.add_argument('--xml', type=check_file, required=True,
                          help="path to XML file from OTAWA's dumpcfg")

    pargs = parser.parse_args()
    sys.exit(main(pargs))
