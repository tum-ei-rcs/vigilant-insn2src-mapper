import logging
import os.path
import copy
import datetime
import networkx as nx
from abc import ABCMeta, abstractmethod
from sortedcontainers import SortedDict, SortedSet
from flow import loop_analysis, dominator


log = logging.getLogger(__name__)


class ControlFlow(object):
    """Generic control flow"""
    __metaclass__ = ABCMeta

    def __init__(self, name, filename, simplify=False):
        self.name = name
        self.file = filename
        self.simplify = simplify

        self.digraph = nx.DiGraph()
        self.digraph.graph['name'] = "{}::{}".format(filename, name)
        self._tree_predom = None
        self._tree_postdom = None
        self._entryId = None
        self._exitId = None
        self._loopInfo = None
        self._maxId = None
        self._ctrldep = None

    def __len__(self):
        return len(self.digraph)

    def entryId(self):
        return self._entryId

    def exitId(self):
        return self._exitId

    def nodes(self):
        return self.digraph.nodes()

    def _graph_changed(self):
        self._tree_postdom = self._tree_predom = None
        self._ctrldep = None

    def _post_init(self):
        if self.simplify:
            log.info("Simplifying CFG of {}".format(self.name))
            self._contract_straight_paths()
        # binary: eternal loops. source: codes after 'return'. Remove them.
        self._prune_unreachable()
        assert self._validate_graph(), "ControlFlow validation failed."
        self._analyze_loops()

    # Private methods
    def _set_entry(self, entryId):
        self._entryId = entryId
        self._graph_changed()

    def _set_exit(self, exitId):
        self._exitId = exitId
        self._graph_changed()

    def _prune_unreachable(self):
        # reachable = nx.node_connected_component(self.digraph.to_undirected(), self._entryId)
        # unreach = set(self.digraph.nodes) - set(reachable)
        dt = nx.dfs_tree(self.digraph, self._entryId)
        unreach = set(self.digraph.nodes) - set(dt.nodes)
        if unreach:
            log.warning("Removing {} unreachable nodes in {}: {}".format
                        (len(unreach), self.name, unreach))
            if self._exitId in unreach:
                log.warning("Function '{}' never terminates".format(self.name))
                self._exitId = None
            self.digraph.remove_nodes_from(unreach)

    def _add_block(self, ident, _type, _attrs):
        """
        Adds a node in digraph. A node will have the following attributes:

          - attrs : dict containing attributes for a node
          - type  : in ['Entry', 'Exit', 'Normal', 'FunctionCall', 'Dummy']
        """
        assert _type in ('Entry', 'Exit', 'Normal', 'FunctionCall'), "Invalid block type given."
        assert self.digraph.has_node(ident) is not True, \
            "Graph already contains node with id: {}".format(ident)
        # --
        self._graph_changed()

        if _type == 'Entry':
            self._entryId = ident
        elif _type == 'Exit':
            self._exitId = ident

        # Validate attributes
        # validKeys = self._get_block_attr_keys()
        # assert isinstance(validKeys, set)
        # assert set(_attrs.keys()) <= validKeys

        self.digraph.add_node(ident, attrs=_attrs, type=_type)
        
        # Update max id
        if self._maxId is None:
            self._maxId = ident
        else:
            if ident > self._maxId:
                self._maxId = ident

    def _remove_block(self, ident):
        """
        Removes given node and returns adjacent edges (incoming, outgoing).

        Args:
            ident: Id of node to be removed.

        Return:
            Tuple (predecessors, successors) of node lists.
        """
        assert ident in self.digraph, "Invalid id."
        # --
        self._graph_changed()
        pre = list(self.digraph.predecessors(ident))
        suc = list(self.digraph.successors(ident))

        self.digraph.remove_node(ident)
        return pre, suc

    def _add_edge(self, e):
        assert self.digraph.has_node(e[0])
        assert self.digraph.has_node(e[1])
        # --
        self._graph_changed()
        self.digraph.add_edge(e[0], e[1])

    def _validate_graph(self):
        """Validates the given graph, returns False if validation failed."""
        status = False
        
        while True:
            if self._entryId is None:
                break
            # if self._exitId is None:
            #    break
            
            # DiGraph validation
            if not isinstance(self.digraph, nx.DiGraph):
                log.error("ControlFlow has an invalid graph.")
                break
            if len(self.digraph) < 2:
                log.error("ControlFlow's graph is emtpy.")
                break
    
            status = True
            break
        
        return status

    def _analyze_loops(self):
        """Perform loop analysis, save result."""
        self._loopInfo = loop_analysis.LoopInfo(self.digraph, self._entryId)

    ##################
    # Public methods #
    ##################

    def get_blocks(self):
        return self.digraph.nodes

    def get_block_type(self, blockId):
        return self.digraph.nodes[blockId]['type']
    
    def get_block_attrs(self, blockId):
        return self.digraph.nodes[blockId]['attrs']
    
    def get_loop_info(self):
        return self._loopInfo

    def get_max_id(self):
        return self._maxId

    def predom_tree(self):
        """Get dominator tree of CFG"""
        if self._tree_predom is None:
            self._tree_predom = dominator.PreDominatorTree(self.digraph,
                                                           entryId=self._entryId,
                                                           exitId=self._exitId)
        # --
        return self._tree_predom

    def postdom_tree(self):
        """Get post-dominator tree of CFG"""
        if self._tree_postdom is None:
            self._tree_postdom = dominator.PostDominatorTree(self.digraph,
                                                             entryId=self._entryId,
                                                             exitId=self._exitId)
        # --
        return self._tree_postdom

    def get_control_dependencies(self):
        """
        Calculate the control dependency
        :return: dict(edge -> controlled nodes)
        """
        if self._ctrldep is None:
            log.info("Computing ctrl dependencies of {}...".format(self.name))
            self._ctrldep = dict()
            tp = self.postdom_tree()
            g = tp.get_tree()
            for u, v in self.digraph.edges:
                if not tp.test_dominance(v, u):
                    log.debug("{}: {} is a ctrl edge".format(self.name, (u, v)))
                    lca = tp.nearest_common_dominator({v, u})
                    log.debug("{} ctrl edge {}: LCA={}".format(self.name, (u, v), lca))
                    controlled_nodes = set()
                    x = v
                    while x != lca:
                        controlled_nodes.add(x)
                        x = next(iter(g.predecessors(x)))
                    if lca == u:  # u pdom v <-> u is a loop header
                        controlled_nodes.add(lca)
                    self._ctrldep[(u, v)] = controlled_nodes
        # --
        return self._ctrldep

    def get_loc_string(self, blockId, fullpath=False):
        """Human-readable line info"""
        li = self.get_line_info(blockId)
        b = li.get('begin', dict())
        col_or_disc = b.get('c', '0') if b.get('c', '0') != 0 else b.get('d', 0)
        fname = self.file if fullpath else os.path.basename(self.file)
        return "{}::{}:{}".format(fname, b.get('l', 0), col_or_disc)

    def get_all_func_calls(self):
        """ Returns a list (control flow, calling node) from this function"""
        ret = []
        for n in self.digraph.nodes:
            calls = self.get_func_calls(n)
            ret.extend([(n, c) for c in calls])
        return ret

    ####################
    # Abstract methods #
    ####################

    @abstractmethod
    def _contract_straight_paths(self):
        """
        Contract edges (u,v) where u is the only predecessor of v,
        and v the only postdecessor of u.
        Simplifies analysis and mapping.
        """
        raise NotImplementedError

    @abstractmethod
    def _get_block_attr_keys(self):
        """ Returns a set of valid keys for block attributes """
        raise NotImplementedError

    @abstractmethod
    def get_var_accesses(self, blockId):
        """ Returns varReads, varWrites. """
        raise NotImplementedError

    @abstractmethod
    def get_func_calls(self, blockId):
        """ Returns a list of function calls for the given block """
        raise NotImplementedError

    @abstractmethod
    def get_line_info(self, blockId):
        """ Returns line info for the given block """
        raise NotImplementedError

    def set_line_info(self, which, blockId, line, col, discr):
        """ Overwrite line info for the given block """
        raise NotImplementedError


"""
TODO: - Collapse inlined functions (simple case), else raise an AssertionError
"""


class BinaryControlFlow(ControlFlow):
    """Parses a json object to generate a binary ControlFlow object."""

    attrKeys = {'AddrRanges'}  # keys guaranteed to be there in regular BBs

    def __init__(self, jsonObj, dwData, insns, symbs, dieOffset, opCodeTiming, simplify=False):
        # Hold a reference to dwarf data and instructions
        self._dwData = dwData
        self._insns = insns
        self._symbs = symbs
        self._dieOffset = dieOffset

        self._funcCalls = None
        self._varAccesses = None
        self._varNames = None
        self._opTimes = None
        self._inlSubs = {}
        self._colls = {}

        self._corrected_line_info = dict()  # overrides DWARF info when set_line_info was used

        # Check if the given json object is valid
        assert self._validate_json_obj(jsonObj), "Invalid json object."

        # Get comp dir, name
        comp_dir, name = self._dwData.get_subprogram_file(self._dieOffset)

        # Add blocks and edges here
        super(BinaryControlFlow, self).__init__(jsonObj['Name'],
                                                os.path.join(comp_dir, name),
                                                simplify)
        assert self._parse_json_obj(jsonObj), "Could not parse json object."

        # Finish initialization of base class
        super(BinaryControlFlow, self)._post_init()

        # warn about some insns that can defy static analysis
        self._check_unsupported_instructions()

        # Attribute timing info to all basic blocks
        self._opTimes = self._parse_op_time_csv(opCodeTiming)
        self._attr_block_time()

        # Locate function calls
        self._find_func_calls()

        # Locate variables
        self._find_variables()
        log.debug("VarAccesses: {}".format(self._varAccesses))

        # Collapse inlined subroutines
        self._collapse_inlined_subroutines()

    def _parse_op_time_csv(self, op_time_csv):
        """Read instruction/opcode timing CSV
        FIXME: sanitize/check input
        """
        opTimes = dict()

        with open(op_time_csv, 'r') as fp:
            for line in fp:
                if line[0] == '#':
                    continue
                lCols = line.split(';')
                assert len(lCols) == 3, "Invalid csv structure."
                opTimes[lCols[0]] = (int(lCols[1]), int(lCols[2]))

        return opTimes

    def _check_unsupported_instructions(self):
        BLACKLIST = list()
        BLACKLIST.append('spm')  # self-modifying code
        BLACKLIST.sort()
        for b in self.get_blocks():
            for addr, inst in self.instructions(b):
                mnem = inst['Mnem']
                assert mnem not in BLACKLIST, "Unsupported mnemonic: {}".format(mnem)

    def _attr_block_time(self):
        self._blockTimes = dict()

        timeMissing = set()
        for b in self.get_blocks():
            totalSum = 0
            for addr, inst in self.instructions(b):
                mnem = inst['Mnem']
                try:
                    # Add max time (second element in opTime tuple)
                    maxTime = self._opTimes[mnem][1]
                    totalSum += maxTime
                except KeyError:
                    timeMissing.add(mnem)

            self._blockTimes[b] = totalSum

        if timeMissing:
            file_missing = 'missing-times-opcodes.csv'
            with open(file_missing, 'a') as f:
                f.write("# {}:\n".format(datetime.datetime.now()))
                for missing_mnemo in timeMissing:
                    f.write("{};1;1\n".format(missing_mnemo))
            fullpath = os.path.join(os.getcwd(), file_missing)
            assert False, "Time missing for some mnemonics in {}. See file {}".format(self.name,
                                                                                      fullpath)

        log.debug("Block times = {}".format(self._blockTimes))

    def instructions(self, blockId):
        """iterates over instructions of basic block"""
        ranges = self.get_addr_ranges(blockId)
        for r in ranges:
            insns = self._insns.get_instructions(r)
            for addr, inst in insns:
                yield addr, inst

    def get_block_time(self, blockId):
        return self._blockTimes[blockId]

    def get_var_accesses(self, blockId):
        """
        Returns accessed variables in order for the given block id.

        Return:
            Tuple (r, w) of lists containing named variables.
        """
        offReads, offWrites = self._varAccesses[blockId]
        varReads = [self._varNames[k] for k in offReads]
        varWrites = [self._varNames[k] for k in offWrites]

        return varReads, varWrites

    def set_line_info(self, blockId, which, line=None, col=None, discr=None):
        assert which in ("min", "max", "begin", "end")
        # --
        oldinfo = copy.deepcopy(self.get_line_info(blockId))
        if line is not None:
            oldinfo[which]['l'] = line
        if col is not None:
            oldinfo[which]['c'] = col
        if discr is not None:
            oldinfo[which]['d'] = discr
        self._corrected_line_info[blockId] = oldinfo

    def get_line_info(self, blockId):
        """
        Returns line info for a given blockId

        Return
            Dict containing the following elements:
                - begin : Begin Line
                - end   : End Line
                - max   : Min Line
                - min   : Max Line
            
            where each element is a dict: {l, c, d} where:
                - l : line
                - c : column
                - d : discriminator

          * Returns None if blockId is entry or exit.
        """
        if blockId in self._corrected_line_info:
            return self._corrected_line_info[blockId]

        ranges = self.get_addr_ranges(blockId)
        if len(ranges) == 0:
            return None
        return self._dwData.get_line_info(ranges)

    def get_addr_ranges(self, blockId):
        """
        Helper function to get address ranges for a given block.
        
        Return:
            List of tuples (r_start, r_end).
        """
        return self.digraph.nodes[blockId]['attrs']['AddrRanges']

    def get_func_calls(self, blockId):
        """
        Function calls in binary flow are found in separate blocks.Returns 
        a list of function names (list max length is 1)."""
        f = self._funcCalls.get(blockId, None)
        if f is None:
            return []
        else:
            return [f]

    def get_unique_dw_lines(self, blockIds):
        """
        BBs can be subdivided into chunks, whereas each has an individual dbg info (dwarf line).
        Multiple BBs can map to the same dwarf line, i.e, to same dbg info.
        This function returns those dwarf lines for each given BB, which exclusively map to it.
        :returns dict(dw line -> BB)
        FIXME: not elegant.
        """
        dwLines_unq = dict()
        # 1. count how many BBs map to the same dwarf line
        for b in blockIds:
            dwLines = self._dwData.get_dw_lines(self.get_addr_ranges(b))
            for dw_i in dwLines.keys():
                if dw_i not in dwLines_unq:
                    dwLines_unq[dw_i] = (1, b)
                else:
                    dwLines_unq[dw_i] = (2, b)  # > 1
        # remove those where multiple BBs map to the same
        del_keys = [k for k, v in dwLines_unq.items() if v[0] != 1]
        for k in del_keys:
            del dwLines_unq[k]
        # unpack tuple
        for k, v in dwLines_unq.items():
            dwLines_unq[k] = v[1]
        return dwLines_unq

    def _collapse_inlined_subroutines(self):

        def test_inl_coll():
            dsc = {}
            iee = [(d['b_entry'], d['b_exit']) for d in self._inlSubs.values()]
            for b_entry, b_exit in iee:
                if b_entry == b_exit:
                    # Trivial case
                    dsc[b_entry] = 0
                    continue
                
                lh_entry = self._loopInfo.lookup_node(b_entry)
                lh_exit = self._loopInfo.lookup_node(b_exit)

                if lh_entry is not None:
                    assert lh_entry == lh_exit
                    log.warning("Inlined sub. in loop, check me.")
                else:
                    # Not in loop
                    dsc[b_entry] = 3
                    continue
                
                # b_entry is loop header
                ee = self._loopInfo.get_exit_edges(b_entry)
                be = self._loopInfo.get_back_edges(b_entry)
                assert len(ee) == 1
                assert len(be) == 1

                if lh_entry == b_entry:
                    assert ee[0][0] != b_entry, "Invalid case."
                    
                    if ee[0][0] == b_exit:
                        # If b_exit last in loop -> three disconnected components
                        if b_exit == be:
                            dsc[b_entry] = 3
                        else:
                            dsc[b_entry] = 4
                    else:
                        # b_exit not tail of exit edge
                        dsc[b_entry] = 3
                else:
                    # b_entry in loop body
                    assert b_exit != ee[0][0]
                    dsc[b_entry] = 2
            
            return dsc

        def cut_graph(bs, be, dcc):
            """
            Returns a disconnected component when the undirected graph
            is cut at bs and be. Also checks the number of components against
            the input dcc.

            Args:
                bs:  Start block of inl. sub.
                be:  End block of inl. sub.
                dcc: Count of disconnected components to test against.

            Return:
                Subgraph (undirected) corresponding to inl. sub.
            """
            d_g = nx.DiGraph()
            d_g.add_nodes_from(self.digraph.nodes())
            d_g.add_edges_from(self.digraph.edges())
            
            d_g.remove_edges_from(d_g.in_edges(bs))
            d_g.remove_edges_from(d_g.out_edges(be))
            
            u_g = d_g.to_undirected()
            cc = list(nx.connected_component_subgraphs(u_g))

            if dcc == 0:
                # Trivial case, check if in loop or not
                # FIXME: Move this check from here.
                lh = self._loopInfo.lookup_node(bs)
                if lh is None:
                    dcc = 3
                else:
                    # FIXME: Handle the case lh == bs
                    assert lh != bs, "Not implemented."
                    dcc = 2
            
            assert len(cc) == dcc, \
                "Cannot collapse inlined subroutines."
            
            for c in cc:
                if bs in c.nodes:
                    assert be in c.nodes
                    return cc

            assert False, "Should not land here..."

        def coll_cc(b_entry, b_exit, cc):
            """
            Collapses given subgraph into a virtual function call. Collapsed
            subgraph is saved in self._colls. 
            
            Note:
                - Note that the subgraph includes original b_entry and b_exit
                  basic blocks in control flow.
                - b_entry and b_exit are split at inl low and high pc respectively.

            Args:
                b_entry: Block containing low_pc
                b_exit:  Block containing high_pc
                cc:      Subgraph (undirected) containing nodes to be collapsed,
                         including, b_entry and b_exit.
            
            Return:
                Void.
            """
            # Split at low
            # Split at high
            pass

        def get_block_id(ar, address):
            """Returns the id of the block that contains given address."""
            assert isinstance(ar, SortedDict)

            bi = ar.bisect_right(address)
            assert bi != 0, "Invalid address."
            r = ar.peekitem(bi-1)
            # r = (r_start, (r_end, blockId))
            assert r[1][0] >= address >= r[0], "Invalid address"
            return r[1][1]

        # Get inlined subroutines for current subprogram, if any.
        self._inlSubs = {i['dieOffset']: i
                         for i in self._dwData.get_inlined_subroutines(self._dieOffset)}
        if len(self._inlSubs) == 0:
            return

        # Skip entry, exit, functionCall blocks
        blockIds = []
        for b in self.digraph:
            if b == self._entryId or b == self._exitId:
                continue
            if self.get_block_type(b) == 'FunctionCall':
                continue
            blockIds.append(b)

        # Get address ranges
        ar = self._get_address_ranges(blockIds)

        for key, inl in self._inlSubs.items():
            assert inl['low_pc'] < inl['high_pc']

            b_entry = get_block_id(ar, inl['low_pc'])
            b_exit = get_block_id(ar, inl['high_pc'])
            log.debug("Inlined sub: low_pc={}, block={}".format(inl['low_pc'], b_entry))
            log.debug("Inlined sub: high_pc={}, block={}".format(inl['high_pc'], b_exit))
            inl['b_entry'] = b_entry
            inl['b_exit'] = b_exit

        dsc = test_inl_coll()
        for key, d in self._inlSubs.items():
            b_entry = d['b_entry']
            b_exit = d['b_exit']
            self._inlSubs[key]['cc'] = cut_graph(b_entry, b_exit, dsc[b_entry])

        # Inlined subroutines must be collapsed in order, sorted by descending
        # high_pc.

    def _merge_blocks(self, blockId1, blockId2):
        """Given two adjacent blocks u -> v
        with u having no other successors and v no other predecessors,
        merge them into first one.

        :returns false if merging is not allowed or possible
        """
        # noinspection PyCallingNonCallable,PyCallingNonCallable
        assert self.digraph.out_degree(blockId1) == 1 and self.digraph.in_degree(blockId2) == 1
        # --

        def merge_ranges(r1, r2):
            return r1 + r2  # type: list

        HANDLERS = {'AddrRanges': merge_ranges}

        def merge_attrs():
            attr_dst = copy.deepcopy(self.get_block_attrs(blockId1))
            attr_src = self.get_block_attrs(blockId2)
            for a, v in attr_src.iteritems():
                try:
                    attr_dst[a] = HANDLERS[a](attr_dst[a], v)
                except KeyError:
                    log.error("Cannot merge BBs {} and {}: no merger for attr {} known".format
                              (blockId1, blockId1, a))
                    return None
            return attr_dst

        # first see if merging is supported
        if self._exitId == blockId2 and self._entryId == blockId1:
            return False  # must stay distinct, since all other algos downstream do fail

        if self._entryId == blockId1:
            return False

        new_attrs = merge_attrs()
        if new_attrs is None:
            return False
        self.digraph.nodes[blockId1]['attrs'] = new_attrs

        # then do it
        _, suc = self._remove_block(blockId2)
        for s in suc:
            self._add_edge((blockId1, s))

        # correct exit, if we deleted that one.
        if self._exitId == blockId2:
            self._exitId = blockId1
            self.digraph.nodes[blockId1]['type'] = 'Exit'
        # --
        return True

    def split_block(self, blockId, addr):
        """
        Splits the given block in two adjacent blocks at the given address.
        B --> (B1 -> B2). B1 includes input address.

        Args:
            blockId: Block to be split.
            addr:    Address where block will be split.

        Return:
            Void 
        """
        def split_ranges(ar, addr):
            """
            Splits given list of address ranges @ addr.
            FIXME: Move this function elsewhere.

            Args:
                ar:   List of address range tuples.
                addr: Instruction address where to split ranges.

            Return:
                Tuple (ar1, ar2) of lists of address ranges.

            Note:
                addr will be in ar1.
            """
            ar1 = []
            ar2 = []

            # Will also perform checks for addr
            na = self._insns.get_next_insn_address(addr)
            # This should not happen here, addr represents the very last address.
            assert na is not None, "Invalid addr."

            f_found = False
            for r in ar:
                if r[0] <= addr <= r[1]:
                    assert f_found is False, "Invalid address ranges."
                    if addr == r[1]:
                        # Just add range to ar1
                        ar1.append(r)
                    else:
                        # Split
                        ar1.append((r[0], addr))
                        ar2.append((na, r[1]))
                    f_found = True
                    continue

                if f_found is False:
                    ar1.append(r)
                else:
                    ar2.append(r)

            assert len(ar1) + len(ar2) == len(ar) + 1, "Something went wrong..."
            return ar1, ar2        

        if blockId in (self._entryId, self._exitId) or self.get_block_type(blockId) != 'Normal':
            assert False, "Invalid block id: {}".format(blockId)
    
        attrs = self.get_block_attrs(blockId)
        ar = attrs['AddrRanges']
        if addr == ar[-1][1]:
            assert False, "Attempted to split block at the very end..."
        
        # If new attributes are introduced, handle them here too.
        assert len(attrs) == 1 and 'AddrRanges' in attrs, "FIXME."
        
        # Remove block
        pre, suc = self._remove_block(blockId)

        # Handle ranges
        ar1, ar2 = split_ranges(ar, addr)

        self._add_block(ar1[0][0], 'Normal', {'AddrRanges': ar1})
        for p in pre:
            self._add_edge((p, ar1[0][0]))
        self._add_block(ar2[0][0], 'Normal', {'AddrRanges': ar2})
        for s in suc:
            self._add_edge((ar2[0][0], s))

        # Add B1->B2
        self._add_edge((ar1[0][0], ar2[0][0]))

    def _get_address_ranges(self, blockIds, validate=True):
        """
        Returns a SortedDict of address ranges contained in given list
        of block ids.

        Return:
            Dict keyed by starting address of each address range: 
            {R_start:(R_end, blockId) for R in addressRanges}.

        TODO: Save this dict as class member.
        """
        ar = SortedDict()
        for b in blockIds:
            for r in self.get_addr_ranges(b):
                assert r[0] not in ar, "Duplicate/Overlapping address range."
                ar[r[0]] = (r[1], b)

        if not validate:
            return ar

        # Check address ranges for overlaps
        i = 0
        prev_val = None
        for r in ar.items():
            if i == 0:
                prev_val = r[1][0]
                continue
            
            # Check for overlapping ranges
            assert r[0] != prev_val, "Overlapping address ranges."

            i += 1
            prev_val = r[1][0]

        return ar

    def _find_variables(self):
        """
        Scans each basic block for variable access (r/w), updates self._varAccesses.

        Note:
            - self._varAccesses is keyed by block id, with values having
              following form: ([varRead offset key], [varWrite offset key]).
            - Variable names are stored in self._varNames dict, keyed by the
              starting offset of the variable.
        """
        self._varAccesses = {}
        localVars = self._dwData.get_local_variables(self._dieOffset)
        self._varNames = {int(k): localVars[k]['name'] for k in localVars.keys()}
        offsets = {int(k): localVars[k]['byteSize'] for k in localVars.keys()}

        for block in self.digraph.nodes:
            ar = self.get_addr_ranges(block)
            self._varAccesses.update({block: self._insns.get_var_accesses(ar, offsets)})
    
    def _find_func_calls(self):
        """
        Finds function calls, updates _funcCalls: {blockId:funcName}
        
        NOTE: FunctionCall blocks must contain a single call instruction.
        """
        self._funcCalls = {}
        for block in self.get_blocks():
            if self.get_block_type(block) == 'FunctionCall':
                addrRanges = self.get_addr_ranges(block)

                # FIXME: why the follwoing requirements??
                assert len(addrRanges) == 1, \
                    "Function block must have a contiguous address range."
                assert addrRanges[0][0] == addrRanges[0][1], \
                    "Function block must contain a single instruction only."

                block_attrs = self.get_block_attrs(block)
                # use callee info from flow parser if present and nonempty
                if 'calls' in block_attrs:
                    callee = block_attrs['calls'][0]
                else:
                    # find callee ourselves (deprecated)
                    log.warning("Control flow that was read does not resolve function calls; "
                                "please re-run or update flow parser. Trying a workaround...")
                    log.warning("Resolving callee of {}.{}...".format(self.name, block))
                    insn = self._insns._insnMap[addrRanges[0][0]]
                    assert len(insn['Target']) == 1, "Invalid call instruction"
                    callee = self._symbs[insn['Target'][0]]
                if isinstance(callee, (list, set)):
                    assert len(callee) == 1, "icall not supported"
                self._funcCalls.update({block: callee})

    def _validate_json_obj(self, jsonObj):
        validObjKeys = {'Type', 'Name', 'BasicBlocks', 'Edges'}
        status = False

        while True:
            if not isinstance(jsonObj, dict):
                break
            if not validObjKeys <= set(jsonObj.keys()):
                break
            if jsonObj['Type'] != 'Flow':
                break

            status = True
            break

        return status

    def _parse_json_obj(self, jsonObj):
        # Add blocks
        bCount = 0
        for block in jsonObj['BasicBlocks']:
            attrs = {k: [] for k in BinaryControlFlow.attrKeys}
            if block['BlockType'].lower() not in ('entry', 'exit'):
                if not len(block['AddrRanges']):
                    log.error("Block with id {} has invalid AddrRanges.".format(block['ID']))
                    break
                ar = block['AddrRanges']
                if isinstance(ar[0], list):
                    attrs['AddrRanges'] = [(a[0], a[1]) for a in ar]
                else:
                    attrs['AddrRanges'] = [(ar[0], ar[1])]
                if 'calls' in block:  # some flow parsers provide this (OTAWA: y, AVR: n)
                    attrs['calls'] = block['calls']

            bCount += 1            
            super(BinaryControlFlow, self)._add_block(
                block['ID'],
                block['BlockType'],
                attrs
            )
        
        # Add edges
        for e in jsonObj['Edges']:
            super(BinaryControlFlow, self)._add_edge(e)

        # Check if all blocks were added
        if bCount != len(jsonObj['BasicBlocks']):
            return False

        return True

    #############################
    # Override abstract methods #
    #############################
    def _get_block_attr_keys(self):
        return BinaryControlFlow.attrKeys

    def _contract_straight_paths(self):
        # FIXME: there must be an algo? this is higly inefficient
        # TODO: check whether inlining stuff still works.

        def is_function_call(u):
            return self.digraph.nodes[u].get('type', None) == 'FunctionCall'

        merges = 0
        changed = True
        while changed:
            changed = False
            for n in self.digraph.nodes():
                # noinspection PyCallingNonCallable
                if self.digraph.out_degree(n) == 1 and not is_function_call(n):
                    s = next(self.digraph.successors(n))
                    # noinspection PyCallingNonCallable
                    if self.digraph.in_degree(s) == 1 and not is_function_call(s):
                        changed = self._merge_blocks(n, s)
                        if changed:
                            log.debug("Merged {}::{}->{} into {}".format(self.name, n, s, n))
                            merges += 1
                            break
        if merges:
            log.debug("Contracted {} single edges in binary flow '{}'".format(merges, self.name))


class SourceControlFlow(ControlFlow):
    """
    FIXME: - Make self._csvBlocks a dict keyed by node id.
           - Handle virtual node.
    """

    attrKeys = {'begin'}

    def __init__(self, csvObj, delimiterChar=';',
                 headerStartChar='#', headerDelimiterChar=';', simplify=False):
        self._funcCalls = {}
        self._blockIndices = {}

        # Validate csv object columns, get a list of csv blocks (lines)
        self._csvBlocks, self._hCols = self._validate_csv_obj(csvObj, delimiterChar,
                                                              headerStartChar, headerDelimiterChar)

        # Initialize base class
        name = self._csvBlocks[-1][self._hCols['Subprogram']]
        fil = self._csvBlocks[-1][self._hCols['File']]
        super(SourceControlFlow, self).__init__(name, fil, simplify)

        # Parse each csv block
        self._parse_csv_blocks()

        self._calc_discriminators()

        # some workarounds
        self._do_workarounds()

        # Finish initialization
        super(SourceControlFlow, self)._post_init()

    def get_var_accesses(self, blockId):
        raise NotImplementedError

    def get_func_calls(self, blockId):
        sep = ','

        csvBlock = self._get_csv_block(blockId)
        if csvBlock is None:
            log.error("Could not find source block {}.".format(blockId))
            return None

        f_callees = csvBlock[self._hCols['function.call.callees']]
        if f_callees == '':
            return []
        else:
            return f_callees.split(sep)
        
    def get_line_info(self, blockId):
        """
        Returns line info for a given blockId

        Return
            Dict containing the following elements:
                - begin : Begin Line
                - end   : End Line
                - max   : Min Line
                - min   : Max Line
            
            where each element is a dict: {l, c, d} where:
                - l : line
                - c : column
                - d : discriminator

          * Returns None if blockId not in graph.
        """
        """
        # Find csvBlock (FIXME)
        csvBlock = None
        for block in self._csvBlocks:
            if block[self._hCols['BB.index']] != str(blockId):
                continue
            csvBlock = block
            break
        """
        csvBlock = self._get_csv_block(blockId)
        if csvBlock is None:
            log.error("Could not find source block {}.".format(blockId))
            return None

        lcd_b = {
            'l': int(csvBlock[self._hCols['Line.Begin']]),
            'c': int(csvBlock[self._hCols['Col.Begin']]),
            'd': self.digraph.nodes[blockId].get('disc', 0)
        }
        lcd_e = {
            'l': int(csvBlock[self._hCols['Line.End']]),
            'c': int(csvBlock[self._hCols['Col.End']]),
            'd': self.digraph.nodes[blockId].get('disc', 0)
        }

        if lcd_b['l'] == 0 or lcd_e['l'] == 0:
            log.warning("BB {} has null location in {}".format(blockId, self.name))

        return {
            'begin': lcd_b,
            'end': lcd_e,
            'min': lcd_b,
            'max': lcd_e
        }

    def is_virtual_node(self, blockId):
        """
        # Find csvBlock (FIXME)
        csvBlock = None
        for block in self._csvBlocks:
            if block[self._hCols['BB.index']] != str(blockId):
                continue
            csvBlock = block
            break
        """
        csvBlock = self._get_csv_block(blockId)
        if csvBlock is None:
            log.error("Could not find source block {}.".format(blockId))
            return None

        if csvBlock[self._hCols['BB.type']] == 'virtual node':
            return True

        return False

    def find_source_block(self, line, column, node_list):
        """
        Find which source block contains given source location
        FIXME:  - Clean up code, remove the last loop, find max in the first loop instead.
        """
        assert line != 0, "Requesting sBBs at line zero"
        foundBlock = None
        matchedBlocks = dict()
        for n in node_list:
            lInfo = self.get_line_info(n)
            if line >= lInfo['begin']['l'] and column >= lInfo['begin']['c']:
                if line < lInfo['end']['l']:
                    matchedBlocks[n] = (lInfo['begin']['l'],
                                        lInfo['begin']['c'],
                                        lInfo['begin']['d'])
                    """foundBlock = n
                    break"""
                if line == lInfo['end']['l'] and column <= lInfo['end']['c']:
                    matchedBlocks[n] = (lInfo['begin']['l'],
                                        lInfo['begin']['c'],
                                        lInfo['begin']['d'])
                    """foundBlock = n
                    break"""

        maxBlock = None
        for k, v in matchedBlocks.items():
            if maxBlock is None:
                maxBlock = k
                continue
            maxLine, maxColumn, maxDisc = matchedBlocks[maxBlock]
            if v[0] >= maxLine and v[1] > maxColumn:
                maxBlock = k
        if len(matchedBlocks) > 1:
            log.debug("Matched blocks: {}".format(matchedBlocks))
            if maxBlock is not None:
                log.debug("Finding source block for l,c: {},{}".format(line, column))
                log.debug("---------------- Matched source block with lInfo: {}".format
                          (matchedBlocks[maxBlock]))
        return maxBlock

    def find_source_blocks_line_only(self, line, node_list):
        """Find all src-BBs that match a certain source line.
        This function is slow! Hand over lists of lines if multiple queries are needed.

        :param line: line number to look for. Can also be a set.
        :param node_list: list of src nodes to consider
        :type line: int | set
        :return set of bbs or dict, depending on parameter line
        """
        if not isinstance(line, set):
            lines = {line}
        else:
            lines = line
        if 0 in lines:
            log.warning("Querying for src line ZERO in {} - returning all".format(self.name))
        matchedBlocks = {l: set() for l in lines}
        for n in node_list:
            lInfo = self.get_line_info(n)
            for one_line in lines:
                if one_line == 0 or lInfo['begin']['l'] <= one_line <= lInfo['end']['l']:
                    matchedBlocks[one_line].add(n)
        if not isinstance(line, set):
            return matchedBlocks[line]
        else:
            return matchedBlocks
        
    def _get_csv_block(self, blockId):
        index = self._blockIndices.get(blockId, None)
        if index is None:
            return None
        else:
            return self._csvBlocks[index]

    def _parse_csv_blocks(self):
        counter = 0
        for block in self._csvBlocks:
            id = int(block[self._hCols['BB.index']])

            validTypes = {'exit': 'Exit', 'entry': 'Entry', 'node': 'Normal',
                          'virtual node': 'Normal'}
            _type = block[self._hCols['BB.type']]
            assert _type in validTypes.keys(), \
                "Invalid node type in csv file: {}".format(_type)

            # Add block
            locbegin = "{}:{}".format(block[self._hCols['Line.Begin']],
                                      block[self._hCols['Col.Begin']])
            attrs = dict(begin=locbegin)
            super(SourceControlFlow, self)._add_block(id, validTypes[_type], attrs)
            self._blockIndices[id] = counter
            counter += 1

        for block in self._csvBlocks:
            id = int(block[self._hCols['BB.index']])

            # Add edges
            for s in block[self._hCols['Successors']].split(','):
                if s != '':
                    super(SourceControlFlow, self)._add_edge((id, int(s)))

    def _validate_csv_obj(self, csvObj, dl, h, hdl):
        csvLines = csvObj.split('\n')
        assert len(csvLines) > 1, "Csv object is empty."

        hCols = {}
        hLine = csvLines[0]
        assert hLine[0] == h, "Csv object must begin with a header line."

        hIdx = 0
        for c in hLine[1:].split(hdl):
            hCols.update({c: hIdx})
            hIdx += 1
        
        validCols = 'BB.index;BB.type;BB.label;File;Subprogram;' + \
                    'Line.Begin;Col.Begin;Line.End;Col.End;' + \
                    'Exec.Count;Exec.Time.Per;function.call.type;' + \
                    'function.call.callees;Successors;Code'

        # VarWrite/VarRead not always present in *_allflows.csv file
        # validCols += ';VarWrite;VarRead'
        if 'VarRead' in hCols:
            validCols += ';VarWrite;VarRead'
        validCols = set(validCols.split(';'))

        assert set(hCols.keys()) == validCols, "Invalid columns."

        csvBlocks = []
        for line in csvLines[1:]:
            lEntries = []
            lStrIdx = line.find('"')

            lEntries = line[:lStrIdx].split(dl)
            lEntries[-1] = line[lStrIdx:]

            assert len(lEntries) == len(hCols)
            csvBlocks.append(lEntries)

        assert len(csvBlocks) > 0
        return csvBlocks, hCols

    def _merge_blocks(self, blockId1, blockId2):
        """Given two adjacent blocks u -> v
        with u having no other successors and v no other predecessors,
        merge them into first one.

        :returns false if merging is not allowed or possible
        """
        # noinspection PyCallingNonCallable
        assert self.digraph.out_degree(blockId1) == 1 and self.digraph.in_degree(blockId2) == 1
        # --

        def merge_begin(b1, b2):
            def lc(b):
                return [int(p) for p in b.split(":")]
            l1, c1 = lc(b1)
            l2, c2 = lc(b2)
            ml = min(l1, l2)
            if l1 < l2:
                mc = c1
            elif l1 == l2:
                mc = min(c1, c2)
            else:
                mc = c2
            return "{}:{}".format(ml, mc)

        HANDLERS = dict(begin=merge_begin)

        def merge_attrs():
            attr_dst = copy.deepcopy(self.get_block_attrs(blockId1))
            attr_src = self.get_block_attrs(blockId2)
            for a, v in attr_src.iteritems():
                try:
                    attr_dst[a] = HANDLERS[a](attr_dst[a], v)
                except KeyError:
                    log.error("Cannot merge BBs {} and {}: no merger for attr {} known".format
                              (blockId1, blockId2, a))
                    return None
            return attr_dst

        # first see if merging is supported
        if self._exitId == blockId2 and self._entryId == blockId1:
            return False  # must stay distinct, since all other algos downstream do fail

        new_attrs = merge_attrs()
        if new_attrs is None:
            return False
        self.digraph.nodes[blockId1]['attrs'] = new_attrs

        # then do it
        _, suc = self._remove_block(blockId2)
        for s in suc:
            self._add_edge((blockId1, s))

        # correct exit, if we deleted that one.
        if self._exitId == blockId2:
            self._exitId = blockId1
            self.digraph.nodes[blockId1]['type'] = 'Exit'
        # --
        return True

    def _calc_discriminators(self):
        """
        Annotate each src-BB with discriminator info. Calculated based on
        the number of BB encountered in the same line.
        """
        coldict = dict()  # BB -> col
        bb_per_line = dict()  # line -> BBs (sorted by col)

        def add(l, col, bb):
            coldict[bb] = col
            if l not in bb_per_line:
                # noinspection PyArgumentList
                bb_per_line[l] = SortedSet(key=lambda x: coldict[x])
            bb_per_line[l].add(bb)

        for n in self.digraph.nodes:
            li = self.get_line_info(n)
            if li and 'begin' in li and 'end' in li:
                # begin of BB
                line0 = li['begin']['l']
                col0 = li['begin']['c']
                add(line0, col0, n)
                # end of BB must be counted iff it started in an earlier line
                line1 = li['end']['l']
                if line0 < line1:
                    col1 = li['end']['c']
                    add(line1, col1, "{}_e".format(n))

        for line, bbs in bb_per_line.iteritems():
            for d, n in enumerate(bbs):
                if n in self.digraph.nodes:
                    self.digraph.nodes[n]['disc'] = d

    def _do_workarounds(self):
        """For now mainly a workaround for cbb-analyzer: sometimes we have an additional
        exit node after return. That needs to be contracted, otherwise we annotate after
        the return.
        """
        exitnode = self._exitId
        # noinspection PyCallingNonCallable
        if self.digraph.in_degree(exitnode) == 1:
            pred = next(iter(self.digraph.predecessors(exitnode)))
            # noinspection PyCallingNonCallable
            if self.digraph.out_degree(pred) == 1:
                merged = self._merge_blocks(pred, exitnode)
                if merged:
                    log.warning("Merged unreachable trailing node {} in src of '{}'".format
                                (exitnode, self.name))

    #############################
    # Override abstract methods #
    #############################
    def _get_block_attr_keys(self):
        return SourceControlFlow.attrKeys

    def _contract_straight_paths(self):
        pass
