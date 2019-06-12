import logging
import tempfile
import fparser
import networkx as nx
from flow import render


log = logging.getLogger(__name__)


def match(bFlow, sFlow, extLoopInfo=None, do_render=False):
    """
    Return a matching of loops (not the nodes inside them) based on dbg info
    N.B.: also checks for irreducible loops.
    """

    def _match_loop_trees():
        """
        Returns potential matches of loops between binary and source control flows.

        Args
            bFlow: Binary flow object.
            sFlow: Source flow object.

        Return
            Dictionary mapping bFlow loop nodes to sFlow loop nodes.
        """
        assert isinstance(bFlow, fparser.control_flow.BinaryControlFlow)
        assert isinstance(sFlow, fparser.control_flow.SourceControlFlow)

        def find_unq_dw(bFlow):
            """
            Find unique dwarf lines for each loop. If one line is ref'd at multiple levels,
            then the innermost wins (process innermost nesting first). See THESIS-Sect. 5.2.1.
            """
            assert isinstance(bFlow, fparser.control_flow.BinaryControlFlow)
            lInfo = bFlow.get_loop_info()

            # Discard root node, sort loop tree nodes according to their rev.preorder number
            sorted_plist = [(lInfo.get_preorder_number(n), n)
                            for n in lInfo._lTree.nodes if n != lInfo._rootId]
            sorted_plist = sorted(sorted_plist, reverse=True, key=lambda tup: tup[0])

            dwUnqMap = {}
            dwLinesAll = {}
            blockKeys = {}
            processedKeys = set()
            for _, n in sorted_plist:
                # log.debug("Finding unique dwLines for loop header {}...".format(n))
                # Get loop nodes
                ln = {n}
                bn = lInfo.get_body_nodes(n)
                if bn is not None:
                    ln = ln.union(bn)

                new_keys_all = set()
                for b in ln:
                    # log.debug("Processing block {}...".format(b))
                    ranges = bFlow.get_addr_ranges(b)
                    dwLines = bFlow._dwData.get_dw_lines(ranges)
                    dwLinesAll.update(dwLines)
                    blockKeys[b] = set(dwLines.keys())

                    for k, l in dwLines.items():
                        # log.debug("DwLine({})={}".format(k,l))
                        pass

                    new_keys = set(dwLines.keys()) - processedKeys
                    for k in new_keys:
                        processedKeys.add(k)
                        # log.debug("Unique key {}".format(k))
                    new_keys_all = new_keys_all.union(new_keys)
                dwUnqMap.update({n: new_keys_all})

            # Print unique dwarf line map
            for k, v in dwUnqMap.items():
                log.debug("Printing unique dwLines for loop block {}:".format(k))
                for l in v:
                    log.debug("dwLine({}): {}".format(l, dwLinesAll[l]))
                log.debug("")
            # --
            return dwUnqMap, dwLinesAll

        def get_sorted_plist(flow):
            assert isinstance(flow, fparser.control_flow.ControlFlow)
            lInfo = flow.get_loop_info()
            # Discard root node, sort loop tree nodes according to their preorder number
            sorted_plist = [(lInfo.get_preorder_number(n), n)
                            for n in lInfo._lTree.nodes if n != lInfo._rootId]
            sorted_plist = sorted(sorted_plist, reverse=True, key=lambda tup: tup[0])
            return sorted_plist

        def get_loop_ranges(sFlow, sorted_plist):
            """
            Get the source ranges of loops
            Return
                Dict keyed by loop nodes in source flow with values consisting of tuples
                (l_min, l_max),where l_min and l_max are dictionaries of the following form:
                    - {'l':line, 'c':column, 'd':discriminator}

            Note
                An AssertionError is raised if a source loop is contained in a single
                line (improper formatting).
            """
            assert isinstance(sFlow, fparser.control_flow.SourceControlFlow)
            lInfo = sFlow.get_loop_info()
            minmax = {}

            for _, lh in sorted_plist:
                bn = lInfo.get_body_nodes(lh)
                if bn is None:
                    bn = {lh}
                else:
                    bn = bn.union([lh])

                for n in bn:
                    l_info = sFlow.get_line_info(n)
                    # Tuple min, max of dict lcd ('l':line, 'c':column, 'd':discriminator)
                    # where d is always 0.
                    l_min = l_info['min']
                    l_max = l_info['max']
                    minmax[n] = (l_min, l_max)
                    if sFlow.is_virtual_node(n):
                        assert n != lh, "Header node in source loop is virtual."
                        continue
                    assert l_min != l_max, "Invalid line info for source node " \
                        "n={} , min {}, max {}.".format(n, l_min, l_max)

            return minmax

        def get_loop_tree(sFlow, lines_minmax, sorted_plist):
            """Returns a loop tree where each node contains a line range 'r' as attr."""

            def get_loop_min_max(lInfo, lh):
                # Returns min, max line found in loop body nodes given loop header lh.
                mm = lines_minmax[lh]
                line_min = mm[0]['l']
                line_max = mm[0]['l']

                bn = lInfo.get_body_nodes(lh)
                if bn is None:
                    return line_min, line_max
                for n in bn:
                    if sFlow.is_virtual_node(n):
                        continue

                    l_min, l_max = lines_minmax[n]
                    if l_max['l'] > line_max:
                        line_max = l_max['l']
                    if l_min['l'] < line_min:
                        line_min = l_min['l']

                return line_min, line_max

            lInfo = sFlow.get_loop_info()
            rTree = nx.DiGraph()
            rTree.add_nodes_from(lInfo._lTree.nodes)
            rTree.add_edges_from(lInfo._lTree.edges)
            rTree.graph['root'] = lInfo._rootId

            for n in rTree.nodes:
                if n == rTree.graph['root']:
                    continue
                line_min, line_max = get_loop_min_max(lInfo, n)
                # annotate some info
                rTree.nodes[n].update(lInfo._lTree.nodes[n])
                rTree.nodes[n]['line_min'] = int(line_min)
                rTree.nodes[n]['line_max'] = int(line_max)
                # --
                if len(list(rTree.successors(n))) == 0:
                    if line_min == line_max:
                        log.warning("Loop {} contained in a single line only.".format(n))
                    continue
                assert line_min != line_max, \
                    "Source loop in single line, min {}, max {}".format(line_min, line_max)

            # Fix max number in outerloops
            for _, n in s_sorted_plist:
                pre = list(rTree.predecessors(n))
                # Skip outermost loops
                if pre == [rTree.graph['root']]:
                    continue
                assert len(pre) == 1
                p = pre[0]

                n_line_max = rTree.nodes[n]['line_max']
                p_line_max = rTree.nodes[p]['line_max']
                if n_line_max > p_line_max:
                    rTree.nodes[p]['line_max'] = n_line_max

            # Sort the outermost loops, save the sorted list of outermost loops ids.
            ol = [(n, rTree.nodes[n]['line_min']) for n in rTree.successors(rTree.graph['root'])]
            ol = sorted(ol, key=lambda tup: tup[1])
            rTree.graph['ol_sorted'] = [n for n, _ in ol]
            # --
            return rTree

        def get_source_loop(rTree, line):
            """
            Returns the loop tree node the given line corresponds to.

            Note
                - Source loops are assumed to be properly formatted, i.e. not contained
                  in a single line, so they can be properly distinguished.
                - For a given line that falls out of the outermost loops scope, i.e.
                  it isn't part of a SCC, then the nearest loop is returned. If the
                  given line is past the last outermost loop scope, then an error
                  is raised.

            Args
                rTree : Source loop tree with annotated line ranges.
                line  : Source file line.

            Return
                Node id in source loop tree.
            """

            def visit_node(n, line):
                l_min = rTree.nodes[n]['line_min']
                l_max = rTree.nodes[n]['line_max']
                if l_min <= line <= l_max:
                    # log.debug("Visiting node n={}, line in range min,max={},{}".format
                    # (n, l_min, l_max))
                    if len(list(rTree.successors(n))) == 0:
                        return n
                    else:
                        for s in rTree.successors(n):
                            # log.debug("Recursive with s={}".format(s))
                            res = visit_node(s, line)
                            if visit_node(s, line) is not None:
                                return res
                        return n
                else:
                    # log.debug("Visiting node n={}, line not in range min,max={},{}.".format
                    # (n, l_min, l_max))
                    return None

            # 1. Get root children
            ol_sorted = rTree.graph['ol_sorted']

            # 2. Iterate over all root children,
            for n in ol_sorted:
                l_min = rTree.nodes[n]['line_min']
                # log.debug("Searching line {}, in loop node n={}, l_min={}".format(line, n, l_min))
                if line < l_min:
                    log.warning(
                        "Found line out of loop scope. line={}, l_min={}".format(line, l_min))
                    # return n
                    return None
                res = visit_node(n, line)
                # log.debug("Result from visiting node is: {}".format(res))
                if res is not None:
                    return res
                else:
                    # Search other loops
                    continue

            # If we land here, then something went wrong, line past last loop,
            # or most likely loop introduced by compiler that is not contained
            # in any SCC of the flow under analysis.
            return None

        # Get loop info
        blInfo = bFlow.get_loop_info()
        slInfo = sFlow.get_loop_info()

        dwUnqMap, dwLinesAll = find_unq_dw(bFlow)

        s_sorted_plist = get_sorted_plist(sFlow)
        b_sorted_plist_r = reversed(get_sorted_plist(bFlow))

        s_lines_minmax = get_loop_ranges(sFlow, s_sorted_plist)
        s_rTree = get_loop_tree(sFlow, s_lines_minmax, s_sorted_plist)

        # export loop tree
        if do_render:
            render.render_graph(s_rTree, dir=tempfile.tempdir,
                                name=sFlow.name + '_looptree', prefix="src",
                                topnode=s_rTree.graph['root'],
                                attrs=['line_min', 'line_max', 'body', 'backPreds'])

        # Map dwLines to source loops
        map_loop_binary = {}
        map_loop_source = {k: set() for _, k in s_sorted_plist}

        for _, b_n in b_sorted_plist_r:
            # Get unique dw keys for this block
            dwLines = dwUnqMap[b_n]
            parent_node = blInfo.get_parent_node(b_n)

            log.debug("")
            log.debug("Matching dw line info for binary loop header node {}:".format(b_n))

            # Check if empty, note that this may happen if a loop is copied
            # multiple times in binary code, sibling loops in binary loop tree
            # are processed "arbitrarily". TODO: Handle this case.
            assert len(dwLines) != 0, "No info for this loop"

            min_dwl = None
            max_dwl = None
            min_sn = None
            max_sn = None
            for l in dwLines:
                dwLine = dwLinesAll[l]
                s_n = get_source_loop(s_rTree, dwLine['LineNumber'])

                if parent_node != blInfo._rootId:
                    assert parent_node in map_loop_binary
                    # TODO: New loops correspond to single dwLines, add extra check
                    #       for this case elsewhere.
                    if s_n == map_loop_binary[parent_node] and len(dwLines) > 1:
                        log.warning("Ignoring dwLine({}).".format(l))
                        continue
                if s_n is None:
                    log.info("Ignoring dwLine({}), not contained in any source loop.".format(l))
                    continue

                if min_dwl is None:
                    min_dwl = dwLine['LineNumber']
                    min_sn = s_n
                if max_dwl is None:
                    max_dwl = dwLine['LineNumber']
                    max_sn = s_n
                if dwLine['LineNumber'] < min_dwl:
                    min_dwl = dwLine['LineNumber']
                    min_sn = s_n
                if dwLine['LineNumber'] > max_dwl:
                    max_dwl = dwLine['LineNumber']
                    max_sn = s_n

                log.debug("dwLine({}) is matched to source loop {}".format(l, s_n))

            if extLoopInfo is not None:
                if str(b_n) in extLoopInfo["loops"]:
                    if "skip" in extLoopInfo["loops"][str(b_n)]:
                        if extLoopInfo["loops"][str(b_n)]["skip"] == "True":
                            log.info("Not matching binary loop {}, ".format(b_n) +
                                     "skip flag set in external loop info file.")
                            map_loop_binary[b_n] = None
                            continue

            if min_sn is None or max_sn is None:
                log.debug("min_dwl={}, max_dwl={}".format(min_dwl, max_dwl))
                log.debug("min_sn={}, max_sn={}".format(min_sn, max_sn))
                log.warning("Could not match binary loop {}.".format(b_n))
                map_loop_binary[b_n] = None
                continue

            p_min = slInfo.get_preorder_number(min_sn)
            p_max = slInfo.get_preorder_number(max_sn)
            if p_min < p_max:
                matched_loop = min_sn
            else:
                matched_loop = max_sn

            log.debug("Matched to source loop {}.".format(matched_loop))
            map_loop_binary[b_n] = matched_loop
            map_loop_source[matched_loop].add(b_n)

        return map_loop_binary, map_loop_source

    def filter_loops(map_loop_binary, map_loop_source):
        """
        Returns only those loops that can be matched.
         - Excludes binary loops that have no source equivalent (e.g., loops implementing shift ops)
         - Excludes source loops that have no binary equivalent (e.g., unrolled loops)
        """
        loops_to_match = dict()
        skipped_b_loops = set()
        skipped_s_loops = set()
        # FIXME: For now, loops introduced by compiler are all assumed to be self loops.
        # A more complex analysis is needed in order to decide which loop is actually
        # the source loop. Issue a warning for these loops.
        blInfo = bFlow.get_loop_info()
        for k, v in map_loop_source.items():
            locstr = sFlow.get_loc_string(k)
            if len(v) == 0:
                log.warning("Source loop {} at {} has likely been unrolled.".format(k, locstr))
                skipped_s_loops.add(k)
            if len(v) > 1:
                log.warning("Multiple bin loops mapped to src loop {} at {}.".format(k, locstr))
                self_loop_count = 0
                non_self_loop_id = None
                for bLoop in v:
                    if blInfo.get_node_type(bLoop) == 'self':
                        self_loop_count += 1
                        skipped_b_loops.add(bLoop)
                    else:
                        non_self_loop_id = bLoop
                if self_loop_count == len(v):
                    log.warning("Skipping all bin loops {} belonging to src loop {} at {}".format
                                (v, k, locstr))
                else:
                    # TODO: Handle the case when for a partially unrolled source loop,
                    #       not all binary loops introduced by compiler are self-loops.
                    assert self_loop_count == len(v) - 1, "Unhandled case"
                    log.warning("Binary loop {} is the main loop for src loop {} at {}".format
                                (non_self_loop_id, k, locstr))
                    loops_to_match[k] = non_self_loop_id
            else:
                loops_to_match[k] = next(iter(v))

        for k, v in map_loop_binary.items():
            if v is None:
                skipped_b_loops.add(k)
        # --
        return loops_to_match, skipped_b_loops, skipped_s_loops

    log.info("Matching loops in {}...".format(bFlow.name))

    map_loop_bin2src, map_loop_src2bin = _match_loop_trees()
    log.debug("Binary loop map={}".format(map_loop_bin2src))
    log.debug("Source loop map={}".format(map_loop_src2bin))

    # exclude some impossible-to-match loops
    loops_to_match, sbl, ssl = filter_loops(map_loop_bin2src, map_loop_src2bin)
    log.debug("Loops to match={}".format(loops_to_match))
    log.debug("Skipped binary loops={}".format(sbl))
    log.debug("Skipped source loops={}".format(ssl))

    # ensure each skip is demanded by user
    for sk in sbl:
        justified = False
        if extLoopInfo is not None:
            justified = str(sk) in extLoopInfo['loops']
        if not justified:
            log.error("The following binary loop requires user annotations in {}: {}".format
                      (bFlow.name, sk))

    # Note that sbl not contained in loops_to_match (1-to-1 mapping)
    assert (len(loops_to_match) + len(sbl)) == bFlow.get_loop_info().get_loop_count(), \
        "Not all binary loops were processed."
    log.debug("Total binary loop count: {}".format(bFlow.get_loop_info().get_loop_count()))

    rpt = {
        "map": loops_to_match,
        "map_note": "key=source_id, val=binary_id",
        "skipped_bin_loops": list(sbl),
        "skipped_src_loops": list(ssl)
    }
    # --
    return loops_to_match, rpt
