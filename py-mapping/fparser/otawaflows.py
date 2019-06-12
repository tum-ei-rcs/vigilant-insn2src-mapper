# Parser for OTAWA's dumpcfg tool, xml output.
#
# One trick we play here, is that we rename all IDs.
# OTAWA uses string IDs in its XML, but we want integers.

import xml.etree.ElementTree as XET
import os
import logging
import networkx as nx


log = logging.getLogger(__name__)
log.addHandler(logging.NullHandler())  # Python 2.7


class BinaryFlow(object):
    
    def __init__(self, name, filename, ident=None):
        self.name = name
        self.file = filename
        self.ident = ident
        self.digraph = nx.DiGraph()
        self.address = None

    def add_bbs(self, bblist):
        for bb in bblist:
            nid = bb['ID']
            self.digraph.add_node(nid)
            # noinspection PyUnresolvedReferences
            self.digraph.node[nid].update(bb['attributes'])

    def make_bb(self, attrs):
        newid = max(self.digraph.nodes) + 1
        self.add_bbs([dict(ID=newid, attributes=attrs)])
        return newid

    def add_edge(self, tup):
        self.digraph.add_edge(tup[0], tup[1])

    def del_edge(self, tup):
        self.digraph.remove_edge(tup[0], tup[1])

    def set_edge_data(self, tup, edata):
        # noinspection PyUnresolvedReferences
        self.digraph.edges[tup[0], tup[1]].update(edata)


class CFGReader(object):

    def __init__(self, filename=None, fromString=None):
        """
        Create a new parser object from either file or string input
        """
        self._calls = {}  # dict: tuple(Flow id,bbid) -> Flow id
        self._origid2flow = {}  # dict: OTAWA id -> Flow
        self._origid2bb = {}  # dict: OTAWA id -> BasicBlock
        self._xml_root = None

        if filename is not None:
            self._open_from_file(filename)
        else:
            self._open_from_string(fromString)
        if self._xml_root is None:
            raise ValueError

        self._parse_xml(self._xml_root)
        if not self._origid2flow:
            log.warning("No flows found in XML")
            return
        self._resolve_calls()

    def __len__(self):
        return len(self._origid2flow)

    def _open_from_file(self, fname):
        if os.stat(fname).st_size > 0:
            self._xml_root = XET.parse(fname).getroot()
            log.debug("XML file '{}' open".format(fname))
        else:
            raise IOError("file {} not found.format(fname)")

    def _open_from_string(self, fromString):
        self._xml_root = XET.fromstring(fromString)

    def getFlows(self):
        return [f for num, f in self._origid2flow.iteritems()]

    def _resolve_calls(self):
        """re-assign all IDs to be numbers, instead of strings"""
        log.info("Resolving calls...")
        for tup, cid in self._calls.iteritems():
            fid = tup[0]
            bbid = tup[1]
            if cid not in self._origid2flow:
                log.error("Callee '{}' is unknown".format(cid))
                raise ValueError
            # attribute call to given BB
            callsite = self._origid2flow[fid]
            callee = self._origid2flow[cid]
            bbcall = self._origid2bb[bbid]
            callsite.digraph.nodes[bbcall['ID']]['calls'] = [callee.name]
            log.info("Subprogram {} calls {} @BB{}".format
                     (callsite.name, callee.name, bbcall['ID']))

    def _parse_edge(self, node):
        """handle one 'edge' entry in XML. returns dict"""
        dst = None
        src_orig = node.get('source')
        dst_orig = node.get('target', None)
        callee = node.get('called', None)
        typ = node.get('kind')
        props = {p.get('identifier'): p.text for p in node.iterfind('property')}

        # remap src/dst to actual ID
        src = self._origid2bb[src_orig]['ID']
        if dst_orig is not None:
            dst = self._origid2bb[dst_orig]['ID']
        # --
        e = {'s': src, 'd': dst, 'so': src_orig, 'do': dst_orig, 'type': typ, 'calls': callee,
             'otawa-properties': props}
        log.debug('{}'.format(e))
        return e

    def _parse_bb(self, node):
        """handle one 'bb' entry in XML. returns BasicBlock()"""
        sid = node.get('id')  # string
        num = int(node.get('number'))
        siz = int(node.get('size'))
        addrbb = int(node.get('address', 0), 16)  # BB begin

        props = {p.get('identifier'): p.text for p in node.iterfind('property')}

        numInsn = 0
        BL = None
        EL = None
        addr1 = None
        addrs = []
        asm = []
        for insn in node.iterfind('inst'):
            addr = int(insn.get('address'), 16)
            addrs.append(addr)
            raw = insn.find('asm')
            if raw is not None:
                asm.append(raw.text)
            line = int(insn.get('line', 0))
            if numInsn == 0:
                BL = line
                EL = line
                addr1 = addr
            else:
                if line < BL:
                    BL = line
                if line > EL:
                    EL = line
                if addr > addr1:
                    addr1 = addr
            numInsn += 1

        attrs = {'size': siz,
                 'asm': asm,
                 'addr': addrbb,  # BB begin
                 'addrs': addrs,  # all
                 'addr0': int(node.get('address'), 16), 'addr1': addr1,  # low and high
                 'strID': sid, 'BeginLine': BL, 'EndLine': EL, 'numInsn': numInsn,
                 'otawa-properties': props}
        b = dict(attributes=attrs, ID=num, _type='')
        self._origid2bb[sid] = b
        # --
        log.debug('{}'.format(b))
        return b

    def _parse_cfg(self, node_cfg):
        """handle one 'cfg' entry in XML. Returns Flow()"""

        def guess_filename():
            # get filename from first BB (cfg carries none)
            bb = node_cfg.find("bb")
            inst = bb.find("inst")
            return inst.get("file")

        def get_exitblock():
            ne = node_cfg.find('exit')
            sid = ne.get('id')  # string
            attrs = {'BB.type': 'exit'}
            bb = dict(label='exit', ID=-2, attributes=attrs, _type='exit')
            self._origid2bb[sid] = bb
            return bb

        def get_entryblock():
            ne = node_cfg.find('entry')
            sid = ne.get('id')  # string
            attrs = {'BB.type': 'entry'}
            bb = dict(label='entry', ID=-1, attributes=attrs, _type='entry')
            self._origid2bb[sid] = bb
            return bb

        fid = node_cfg.get("id")
        fname = guess_filename()
        f = BinaryFlow(node_cfg.get("label"), fname, ident=fid)
        log.info("Found CFG: {}".format(f.name))

        # read BBs
        bbs = [self._parse_bb(b) for b in node_cfg.iterfind("bb")]
        log.debug("{} basic blocks".format(len(bbs)))
        # set entry/exit
        bb_entry = get_entryblock()
        bbs.append(bb_entry)
        bbs.append(get_exitblock())
        # store all BBs
        f.add_bbs(bbs)

        # read edges
        edges = [self._parse_edge(e) for e in node_cfg.iterfind("edge")]
        log.debug("{} edges".format(len(edges)))
        for e in edges:
            if e['type'] != 'call':
                tup = (e['s'], e['d'])
                f.add_edge(tup)
                f.set_edge_data(tup, e)
            else:
                # attribute call to BB later on (not now, since calle might be unparsed)
                self._calls[fid, e['so']] = e['calls']
        log.debug("Edges: {}".format(edges))

        # set flow entry address
        bb_first = next(iter(f.digraph.successors(bb_entry['ID'])))
        # noinspection PyUnresolvedReferences
        f.address = f.digraph.node[bb_first]['addr']

        if not f.name:
            f.name = "0x{:x}".format(f.address)
        self._origid2flow[fid] = f
        # --
        return f, f.name

    def _parse_xml(self, root):
        """handle XML file"""
        if root.tag == "cfg-collection":
            for cfg in root.iterfind("cfg"):
                flow, func = self._parse_cfg(cfg)
                log.debug("Completed flow {}".format(func))
        else:
            log.error("Expected 'cfg-collection' as root element, found '{}'".format(root.tag))
