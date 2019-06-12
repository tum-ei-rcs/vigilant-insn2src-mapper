#
# Constructs a mapping of perfect matches between two flow graphs
#
import logging
import tempfile
from graphmap import GraphMap
from mapping.mapper import AbstractMapper
from flow import render, transformation, transformer
from sortedcontainers import SortedSet, SortedKeyList
from flow.transformer import HierarchicalFlowGraph


log = logging.getLogger(__name__)


class HomomorphismMapper(AbstractMapper):
    """
    Establishes a dominator homomorphism mapping between flow graphs,
    considering already-matched loops
    """

    def __init__(self, input_hmap, bFlow, sFlow, bhFlow, shFlow,
                 hom_order='predominated-first',
                 hom_order_src='predominator-first',
                 do_render=True, check_inputs=False, trust_dbg=False):
        """
        :param input_hmap:
        :param bFlow:
        :param sFlow:
        :param bhFlow:
        :param shFlow:
        :param hom_order: "<pre|post>dominated-first", "<pre|post>dominator-first"
        Decides which binary BBs are mapped preferably first.
        :param hom_order_src: same, but for source
        :param do_render:
        :param check_inputs:
        :param trust_dbg:
        """
        assert input_hmap is None, "Not taking any input maps"
        # --
        super(HomomorphismMapper, self).__init__(None, bFlow, sFlow, bhFlow, shFlow, check_inputs)
        self.hom_order = hom_order
        self.hom_order_src = hom_order_src
        self.do_render = do_render
        self.quick = False  # set to true for faster, but less precise mapping
        self.trust_dbg_columns = trust_dbg

    def _compute_mapping(self):
        return self.walk_subgraphs(), self.bhFlow, self.shFlow

    def _map_subgraph(self, input_map, btfg, stfg):
        assert isinstance(btfg, HierarchicalFlowGraph)
        assert isinstance(stfg, HierarchicalFlowGraph)

        def compute_potential_map():
            """
            Using debug info and function calls, determine a potential mapping bin->[srcbb]
            :returns dict(binBB -> list(srcBB))
            """

            def get_sblocks_matching_dwarflines():
                """
                Find sBBs that match to each dwarf line
                :returns tuple (map_precise, map_fallback) where
                            map_precise: dw line -> src BB. considering column/discr info
                            map_fallback: dw line -> src BB. considering only line numbers
                """

                def verbose_unique():
                    """just debug output"""
                    nodes_unq_dwlines = self.bFlow.get_unique_dw_lines(
                        nodes_b)  # map: dwarf line -> unique BB
                    log.debug("Unique dwlines:")
                    for dwl_i, node in nodes_unq_dwlines.items():
                        log.debug("Found in node {}, dwl={}".format
                                  (node, self.bFlow._dwData._dwData['LineInfoEntries'][str(dwl_i)]))
                    log.debug("")

                verbose_unique()

                # LUT
                allDwLines = dict()
                for n in nodes_b:
                    dwLines = self.bFlow._dwData.get_dw_lines(self.bFlow.get_addr_ranges(n))
                    allDwLines.update(dwLines)

                # precise (line+col/discr)
                dw2src_map = dict()
                if self.trust_dbg_columns:
                    haveCol = False
                    for key, dwLine in allDwLines.items():
                        line = dwLine['LineNumber']
                        column = dwLine['LineOffset']
                        dw2src_map[key] = self.sFlow.find_source_block(line, column, nodes_s)
                        haveCol = haveCol or (column != 0)
                    if not haveCol:
                        log.warning("No column numbers in debug info. Turn on to improve mapping.")

                # fallback (only by line number)
                lines = {dw['LineNumber'] for k, dw in allDwLines.items()}
                srcline2sbb = self.sFlow.find_source_blocks_line_only(lines, nodes_s)
                dw2src_map_line_only = {key: srcline2sbb[dw['LineNumber']]
                                        for key, dw in allDwLines.items()}
                # --
                return dw2src_map, dw2src_map_line_only

            def add_refs_by_location():
                dwLines = self.bFlow._dwData.get_dw_lines(self.bFlow.get_addr_ranges(n))
                for key, dwLine in dwLines.items():
                    mapped_source_block = dw2src_map_precise.get(key, None)
                    if mapped_source_block is None:
                        mapped_blocks = dw2src_map_fallback[key]
                        log.debug("dwline with key {} in block {} has following matching blocks"
                                  "(line only): {}".format(key, n, mapped_blocks))
                        for b in mapped_blocks:
                            p_b.add(b)
                        continue
                    else:
                        p_b.add(mapped_source_block)

            def add_refs_by_fcalls():
                b_fcalls = self.bFlow.get_func_calls(n)
                for f in b_fcalls:
                    if f not in s_funccalls_inv:
                        continue
                    for source_node in s_funccalls_inv[f]:
                        if source_node in nodes_s:
                            p_b.add(source_node)
                            log.debug("*********---- Added s_node fcall reference: {}".format
                                      (source_node))

            def add_refs_by_varaccess():
                # FIXME: implement matching by accessed variables
                pass

            dw2src_map_precise, dw2src_map_fallback = get_sblocks_matching_dwarflines()
            ret_map_bin2src = dict()
            for n in nodes_b:
                # src nodes always sorted by pre-porder number, i.e., dominating ones come first
                if self.hom_order_src == 'predominator-first':
                    # noinspection PyArgumentList
                    p_b = SortedSet(key=self.sFlow.predom_tree().get_preorder_number)
                elif self.hom_order_src == 'postdominator-first':
                    # noinspection PyArgumentList
                    p_b = SortedSet(key=self.sFlow.postdom_tree().get_preorder_number)
                elif self.hom_order_src == 'predominated-first':
                    # noinspection PyArgumentList
                    p_b = SortedSet(key=lambda x: -self.sFlow.predom_tree().get_preorder_number(x))
                elif self.hom_order_src == 'postdominated-first':
                    # noinspection PyArgumentList
                    p_b = SortedSet(key=lambda x: -self.sFlow.postdom_tree().get_preorder_number(x))
                else:
                    assert False, "Invalid argument (self.hom_order_src)."
                add_refs_by_location()
                add_refs_by_fcalls()
                add_refs_by_varaccess()
                ret_map_bin2src[n] = p_b
            # --
            return ret_map_bin2src

        def get_original_loop_id(tfg, regionId):
            assert isinstance(tfg, transformer.TransformedFlowGraph)
            # --
            # Get region collection
            tfg_regions = tfg.get_region_collection()
            assert regionId in tfg_regions._loopRegions
            # All nodes represent region IDs, the new ones must be reduced loops
            l_region = tfg_regions.get_region(regionId)
            assert l_region is not None, "Invalid region id."
            l_transf = l_region.get_transf()
            # --
            assert isinstance(l_transf, transformation.ReducedLoopTransf)
            return l_transf.get_header_node()

        def compute_dom_homomorphic_map():
            """
            filter map using dominator homomorphism
            :returns GraphMap
            """

            def test_homomorphism(binary_nodes):
                """Check whether all the mapping is valid so far"""

                def translate_id(node_id, isBinary):
                    if isBinary:
                        if node_id > self.bFlow.get_max_id():
                            return nodes_new_b[node_id]
                    else:
                        if node_id > self.sFlow.get_max_id():
                            return nodes_new_s[node_id]
                    return node_id

                failed_count = 0
                for b in binary_nodes:
                    for b_ in binary_nodes:
                        if b_ == b:
                            continue
                        a = f_map.get(b, None)
                        a_ = f_map.get(b_, None)
                        if a is None or a_ is None:
                            continue
                        # Get original IDs for dominance check
                        og_b = translate_id(b, True)
                        og_b_ = translate_id(b_, True)
                        og_a = translate_id(a, False)
                        og_a_ = translate_id(a_, False)
                        log.debug("b,b_={},{};  a,a_={},{}".format(b, b_, a, a_))
                        log.debug("og_b,og_b_={},{};  og_a,og_a_={},{}".format
                                  (og_b, og_b_, og_a, og_a_))
                        if self.bFlow.predom_tree().test_dominance(og_b, og_b_) != \
                                self.sFlow.predom_tree().test_dominance(og_a, og_a_) or \
                                self.bFlow.predom_tree().test_dominance(og_b_, og_b) != \
                                self.sFlow.predom_tree().test_dominance(og_a_, og_a):
                            log.debug("bin_dominance={}, src_dominance={}".format
                                      (self.bFlow.predom_tree().test_dominance(og_b, og_b_),
                                       self.sFlow.predom_tree().test_dominance(og_a, og_a_)))
                            log.debug("Preorder numbers og_b,og_b_: {},{}".format
                                      (self.bFlow.predom_tree().get_preorder_number(og_b),
                                       self.bFlow.predom_tree().get_preorder_number(og_b_)))
                            log.debug("Preorder numbers og_a,og_a_: {},{}".format
                                      (self.sFlow.predom_tree().get_preorder_number(og_a),
                                       self.sFlow.predom_tree().get_preorder_number(og_a_)))
                            add_back_to_worklist(b)
                            add_back_to_worklist(b_)
                            failed_count += 1
                            log.debug("Homomorphism failed")
                return failed_count

            def add_back_to_worklist(b):
                if b in fixed_points:
                    return
                worklist.add(b)
                f_map[b] = None

            def check_conflict(r, b):
                """check if src-bb r is known to be a bad choice for bin-bb b,
                given the current state of the mapping.
                """
                if r not in f_confl[b]:
                    return False
                # see if any of the known conflicts are already in the map
                hasConflict = False
                for b_, r_ in f_confl[b][r]:
                    if f_map.get(b_, None) == r_:  # is the conflicting one in the map?
                        log.debug("conflict: {}->{} not allowed because {}->{} in mapping".format
                                  (b, r, b_, r_))
                        hasConflict = True
                        break
                return hasConflict

            def select_reference(b):
                """Among possible references, return the first non-conflicting one
                XXX: heuristic!
                """
                # FIXME: select the innermost src bb first for loops
                # hom_order = pre: bin body come here first, and are paired with src hdr first
                # hom_order = post: bin hdrs come here first, and are paired with src hdr first
                p_b = potential_map_bin2src[b]
                # for r in reversed(p_b):  # picking src dominated first
                for r in p_b:  # picking src dominators first
                    if not check_conflict(r, b):
                        return r
                return None

            def add_conflict(b, a, b_, a_):
                """
                Store that b->a and b->a' are conflicting decisions
                b*= binary, a*=source
                """
                if a not in f_confl[b]:
                    f_confl[b][a] = set()
                if a_ not in f_confl[b_]:
                    f_confl[b_][a_] = set()
                f_confl[b][a].add((b_, a_))  # b->a conflicts with b'->a'
                f_confl[b_][a_].add((b, a))  # b'->a conflicts with b->a
                log.debug("{}->{} conflicts with {}->{}".format(b, a, b_, a_))

            def remove_ambiguous():
                """Remove all entries from f_map that where we could have confused siblings"""

                def do_level(node):
                    """Dive down dom tree, and check for ambiguity at each level"""
                    mapped_by = dict()  # src-bb -> bin-bb in this btfg
                    for ch in pdt.successors(node):
                        # if has children, their dom. relationships will make it unambig.
                        if ch in f_map and pdt.out_degree(ch) == 0:
                            srcbbs = potential_map_bin2src[ch]
                            for sbb in srcbbs:
                                if sbb not in mapped_by:
                                    mapped_by[sbb] = set()
                                mapped_by[sbb].add(ch)
                    # remove those which have multiple src locations
                    delbb = {bb for _, bbb in mapped_by.iteritems() if len(bbb) > 1 for bb in bbb}
                    if delbb:
                        ambiguous_bbb.update(delbb)
                        for db in delbb:
                            del f_map[db]
                    # dive down
                    for ch in pdt.successors(node):
                        do_level(ch)

                ambiguous_bbb = set()
                pdt = self.bFlow.predom_tree().get_tree()
                do_level(self.bFlow.predom_tree().get_root())
                # --
                return ambiguous_bbb

            f_map = dict()
            log.info("Running dominator homomorphism mapping on '{}', order: {}".format
                     (btfg.name, self.hom_order))
            if self.hom_order == 'predominated-first':
                worklist = SortedKeyList(iterable=nodes_b,
                                         key=lambda x:
                                         -self.bFlow.predom_tree().get_preorder_number(x))
            elif self.hom_order == 'postdominated-first':
                worklist = SortedKeyList(iterable=nodes_b,
                                         key=lambda x:
                                         -self.bFlow.postdom_tree().get_preorder_number(x))
            elif self.hom_order == 'predominator-first':
                worklist = SortedKeyList(iterable=nodes_b,
                                         key=self.bFlow.predom_tree().get_preorder_number)
            elif self.hom_order == 'postdominator-first':
                worklist = SortedKeyList(iterable=nodes_b,
                                         key=self.bFlow.postdom_tree().get_preorder_number)
            else:
                assert False, "Invalid argument (self.hom_order)."

            # Add known relations between entry and exit nodes of subgraphs & test for safety
            if flag_isCondensed:
                f_map[btfg.flow.entryId] = fixed_points[btfg.flow.entryId]
                f_map[btfg.flow.exitId] = fixed_points[btfg.flow.exitId]
            else:
                f_map[btfg.loop_id] = stfg.loop_id
            log.debug("Fixed points={}".format(f_map.items()))
            assert test_homomorphism(f_map.keys()) == 0, \
                "Initial homomorphism test failed for fixed points."

            f_confl = {n: dict() for n in nodes_b}
            log.debug("Initial worklist={}".format(worklist))
            rounds = 0
            while len(worklist) > 0:
                rounds += 1
                # Select non conflicting elements for all in worklist
                for _ in range(len(worklist)):
                    if self.hom_order == 'pre':
                        b = worklist.pop(-1)  # using preDom, matching bin dominated (body) first
                    else:
                        b = worklist.pop(0)  # using postDom, matching bin dominator (header) first
                    log.debug("Current worklist element: {}".format(b))
                    if b in fixed_points.keys():
                        continue
                    a = select_reference(b)  # multiple b's might pull the same a here.
                    if a is None:
                        log.debug("Only conflicting references for {} left...".format(b))
                        continue
                    else:
                        f_map[b] = a
                        if not self.quick:
                            # avoids spurious conflicts, but is at least O(n^3)
                            break
                # Test for homomorphism and reject those violating it
                rejected = False
                test_nodes = {k for k, v in f_map.iteritems() if v is not None}  # was: nodes_b
                for b in test_nodes:  # reversing improves run-time (heuristic)
                    for b_ in test_nodes:
                        if b_ == b:
                            continue
                        a = f_map.get(b, None)
                        a_ = f_map.get(b_, None)
                        if a is None or a_ is None:  # could still be None if we removed it
                            continue
                        # FIXME: could cache the following
                        fwd_fail = self.bFlow.predom_tree().test_dominance(b, b_) != \
                            self.sFlow.predom_tree().test_dominance(a, a_)
                        rev_fail = self.bFlow.predom_tree().test_dominance(b_, b) != \
                            self.sFlow.predom_tree().test_dominance(a_, a)
                        if fwd_fail or rev_fail:
                            log.debug("Dominance check failed: b,a=({},{}) ; b_,a_=({},{})".format
                                      (b, a, b_, a_) + ". Fail type: {}".format
                                      ('both' if fwd_fail and rev_fail else
                                       ('fwd' if fwd_fail else 'rev')))
                            add_conflict(b, a, b_, a_)
                            add_back_to_worklist(b)  # and remove from map
                            add_back_to_worklist(b_)
                            rejected = True
                if not rejected:
                    log.debug("Nothing was rejected by homomorphism")
                log.debug("Map after {} rounds: {}".format
                          (rounds, {k: v for k, v in f_map.iteritems() if v is not None}))
            log.debug("Homomorphism mapper finished on {} after {} rounds".format
                      (btfg.name, rounds))
            # some undistinguishable BBs might have been mapped. Remove to prevent switching some.
            rem_bbs = remove_ambiguous()
            if rem_bbs:
                log.info("{}: Removed {} ambiguous map entries: {}".format
                         (btfg.name, len(rem_bbs), rem_bbs))
            report['ambiguous-bin'] = rem_bbs
            # --
            g = GraphMap(gA=btfg.flow, gB=stfg.flow, dict_map=f_map, name="dominator homomorphism")
            return g

        report = dict()
        flag_isCondensed = btfg.parent is None and stfg.parent is None

        ################
        # Render graphs
        ################
        if self.do_render:
            if flag_isCondensed:
                render.render_graph(btfg.flow.get_graph(), dir=tempfile.tempdir,
                                    name=btfg.name + "_allreduced", prefix="bin")
                render.render_graph(stfg.flow.get_graph(), dir=tempfile.tempdir,
                                    name=stfg.name + "_allreduced", prefix="src")
            else:
                render.render_graph(btfg.flow.get_graph(), dir=tempfile.tempdir,
                                    name=btfg.name, prefix="sub")
                render.render_graph(stfg.flow.get_graph(), dir=tempfile.tempdir,
                                    name=stfg.name, prefix="sub")

        ###############
        # Fixed-points
        ###############
        # 0.a Find new nodes, save original loop headers as fixed points
        nodes_b = [n for n in btfg.flow.get_graph().nodes if n <= self.bFlow.get_max_id()]
        nodes_s = [n for n in stfg.flow.get_graph().nodes if n <= self.sFlow.get_max_id()]
        fixed_points = dict()

        nodes_new_b = {n: get_original_loop_id(btfg.flow, n) for n in
                       btfg.flow.get_graph().nodes if n > self.bFlow.get_max_id()}
        nodes_new_s = {n: get_original_loop_id(stfg.flow, n) for n in
                       stfg.flow.get_graph().nodes if n > self.sFlow.get_max_id()}

        b_regions = btfg.flow.get_region_collection()
        s_regions = stfg.flow.get_region_collection()
        for n in nodes_new_b.keys():
            if not b_regions.is_loop_region_matched(n):
                continue
            # Get corresponding new source loop region id
            needed_sid = nodes_new_b[n]
            sub_b = btfg.find(needed_sid)
            partner_s = sub_b.partner
            assert partner_s is not None
            l_source_origin_id = partner_s.loop_id
            l_source_region_id = s_regions.get_loop_region_id(l_source_origin_id)
            assert l_source_region_id in nodes_new_s.keys()
            # Add fixed point
            fixed_points[n] = l_source_region_id

        # 0.b Add entry and exit node as fixed point for the condensed flow.
        if flag_isCondensed:
            assert btfg.flow.is_subflow() is not True, "Not a condensed flow."
            assert stfg.flow.is_subflow() is not True, "Not a condensed flow."
            fixed_points[btfg.flow.get_orig_flow_entry_id()] = \
                stfg.flow.get_orig_flow_entry_id()
            fixed_points[btfg.flow.get_orig_flow_exit_id()] = \
                stfg.flow.get_orig_flow_exit_id()

        # 0.c Add entry node of reduced flow if not condensed
        if not flag_isCondensed:
            assert btfg.flow.is_subflow() is True
            assert stfg.flow.is_subflow() is True
            # b_loop_id and s_loop_id are entry node id's
            fixed_points[btfg.loop_id] = stfg.loop_id

        log.debug("Fixed points: {}".format(fixed_points))

        # Build inverse map for function calls found in source flow graph.
        s_funccalls_inv = dict()
        for n in nodes_s:
            fcalls = self.sFlow.get_func_calls(n)
            for f in fcalls:
                el = s_funccalls_inv.get(f, None)
                if el is None:
                    s_funccalls_inv[f] = {n}
                    continue
                s_funccalls_inv[f].add(n)

        #########################################
        # find potential map (based on dbg info)
        #########################################
        # FIXME: Process fcalls and variable accesses after initial homomorphism mapping?
        potential_map_bin2src = compute_potential_map()
        report['dbgMap'] = {k: list(v) for k, v in potential_map_bin2src.items()}

        # Source line info
        log.debug("Source line info:")
        for n in nodes_s:
            log.debug("Node {}, lInfo={}".format(n, self.sFlow.get_line_info(n)))

        ###################
        # Filter by homomo
        ###################
        h_map = compute_dom_homomorphic_map()

        report['domHomomorphMap'] = h_map
        report['trust-dbg-info'] = self.trust_dbg_columns
        # --
        return h_map, report
