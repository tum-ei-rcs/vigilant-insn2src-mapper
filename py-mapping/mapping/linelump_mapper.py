#
# This maps a few more BBs, possibly not all. Whatever is additionally mapped here:
# execution counts are not overapproximated
#
import copy
import logging
from mapping.mapper import AbstractMapper
from graphmap import GraphMap
import fparser.control_flow as cf
from flow.transformer import TransformedFlowGraph, HierarchicalFlowGraph
from sortedcontainers import SortedKeyList


log = logging.getLogger(__name__)


class StraightLineLumping(AbstractMapper):
    """
    Adds to the mapping by lumping unmapped nodes into their only pre/successors, if possible.
    """

    def __init__(self, input_hmap, bFlow, sFlow, bhFlow, shFlow, do_render=True):
        assert input_hmap is not None
        super(StraightLineLumping, self).__init__(input_hmap, bFlow, sFlow, bhFlow, shFlow)
        self.do_render = do_render

    def _compute_mapping(self):
        return self.walk_subgraphs(), self.bhFlow, self.shFlow

    def _map_subgraph(self, input_map, btfg, stfg):
        assert isinstance(input_map, GraphMap)
        assert isinstance(self.bFlow, cf.BinaryControlFlow)
        assert isinstance(self.sFlow, cf.SourceControlFlow)
        assert isinstance(btfg, HierarchicalFlowGraph)
        assert isinstance(stfg, HierarchicalFlowGraph)
        # --
        btfg_flow = btfg.flow
        stfg_flow = stfg.flow
        assert isinstance(btfg_flow, TransformedFlowGraph)
        assert isinstance(stfg_flow, TransformedFlowGraph)
        # --

        def Union(a, b):
            # Move elements of a to b
            node_sets[b] = node_sets[b].union(node_sets[a])
            for n in node_sets[a]:
                node_lookup[n] = b

            node_sets[a] = set()

        def Find(el):
            assert el in node_lookup
            return node_lookup[el]

        def merge_simple_paths(merged_nodes, node_sets):
            """
            This algorithm ensures that fixpoints are propagated in simple paths.

            Notes:
                This must be done in-order (dfs preorder) to avoid useless path traversals;
                each unmapped node is visited exactly once.Process dominator tree
                bottom-up until a fixed point is found (mapped_nodes). Repeat this
                until all nodes from unmapped_nodes are processed.
            """
            nlist = SortedKeyList(iterable=unmapped_nodes,
                                  key=btfg_flow.get_dom_tree().get_preorder_number)
            for n in reversed(nlist):
                pred = list(btfg_flow.get_graph().predecessors(n))
                succ = list(btfg_flow.get_graph().successors(n))

                if len(pred) != 1 or len(succ) != 1:
                    continue

                if pred[0] == btfg_flow.entryId:
                    # this one is most definitely a loop header and thus not a simple path
                    # note that this separate check is needed, since the out_degree code below
                    # does only look with this subgraph, which does not contain the edge beyond loop
                    continue

                # TODO: still not okay. This sometimes assigns downwards to loop headers
                # which isn't good, since they execute more often

                if btfg_flow.get_graph().out_degree(pred[0]) != 1 or \
                   btfg_flow.get_graph().in_degree(succ[0]) != 1:
                    continue

                dom_pred = list(btfg_flow.get_dom_tree()._domTree.predecessors(n))
                dom_succ = list(btfg_flow.get_dom_tree()._domTree.successors(n))
                assert len(dom_pred) == 1, "Dom tree not really a tree"

                # First nodes in nlist are leaf nodes in predominator tree
                if len(dom_succ) == 0:
                    # Assign to predecessor node in predom tree
                    log.debug("Assigning leaf {} to {}.".format(n, dom_pred))
                    # assert dom_pred[0] in mapped_nodes -> not needed.
                    Union(n, dom_pred[0])
                    merged_nodes.add(n)
                    continue
                else:
                    # Not a leaf node in predominator tree
                    assert len(dom_succ) == 1, "Invalid dominator tree."
                    last_succ = Find(dom_succ[0])
                    # prefer downwards
                    if last_succ in mapped_nodes:
                        # Assign this set to last_succ
                        log.debug("Assigned {} downwards to fixed point {}.".format(n, last_succ))
                        Union(n, last_succ)
                        merged_nodes.add(n)
                        continue
                    else:
                        log.debug("Assigned {} upwards to point {}.".format(n, dom_pred[0]))
                        # assert dom_pred[0] in mapped_nodes -> not needed
                        Union(n, dom_pred[0])
                        merged_nodes.add(n)
                        continue
                # --
                # noinspection PyUnreachableCode
                assert False, "should not land here"

            for n in merged_nodes:
                assert len(node_sets[n]) == 0, "Algorithm failed, must fix."

        report = dict(comment="no report implemented")  # FIXME: write a report of stuff done
        if False:
            log.info("Improving mapping of {}".format(btfg.name))
            unmapped_nodes = input_map.unmapped()
            mapped_nodes = input_map.mapped()
            log.debug("Unmapped binary nodes: {}".format(list(unmapped_nodes)))

            node_sets = {n: {n} for n in btfg_flow.get_graph().nodes}
            node_lookup = {n: n for n in btfg_flow.get_graph().nodes}
            merged_nodes = set()
            merge_simple_paths(merged_nodes, node_sets)

            mapping_dict = dict()
            for n in btfg_flow.get_graph().nodes:
                try:
                    fin = Find(n)
                    matched_src_node = input_map[fin]
                    mapping_dict[n] = matched_src_node
                except KeyError:
                    pass  # whatever we lumped into isn't mapped itself

        else:
            log.warning("Linelump mapper unsafe, doing nothing.")
            mapping_dict = copy.deepcopy(input_map.get_map())

        mapped_now = set(mapping_dict.keys())
        mapped_before = input_map.mapped()
        assert mapped_now.issuperset(mapped_before)
        log.info("{}: Mapped {} more nodes".format(btfg.name, len(mapped_now) - len(mapped_before)))
        smap = GraphMap(btfg_flow, stfg_flow, mapping_dict, "linelump.map",
                        predecessors=[input_map])
        return smap, report
