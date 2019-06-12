#
# This completes the gaps in a partial mapping by assigning the unmapped nodes in a specific way.
#
import logging
import tempfile
from mapping.mapper import AbstractMapper
from graphmap import GraphMap
import fparser.control_flow as cf
from flow.transformer import TransformedFlowGraph, HierarchicalFlowGraph
from flow import render
from sortedcontainers import SortedKeyList


log = logging.getLogger(__name__)


class DominatorLumping(AbstractMapper):
    """
    Yields a complete mapping by lumping unmapped nodes into pre- or post-dominators.
    """

    def __init__(self, input_hmap, bFlow, sFlow, bhFlow, shFlow,
                 maintain_order=True, do_render=True):
        """

        :param input_hmap: hierarchical map to be completed
        :param bFlow: binary CFG
        :param sFlow: source CFG
        :param bhFlow: hierarchical binary
        :param shFlow:
        :param maintain_order: if False, we can do better, but ordering between source and
                               binary nodes is changed, which is not allowed for cached targets
        :param do_render:
        """
        assert input_hmap is not None
        super(DominatorLumping, self).__init__(input_hmap, bFlow, sFlow, bhFlow, shFlow)
        self.do_render = do_render
        self.maintain_order = maintain_order

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

                if self.maintain_order:
                    # this needs to be done on the full graph, since hierarchy hides nodes
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

        def contract_dominator_tree(merged_nodes, sets_nodes):
            last_nodes = unmapped_nodes.difference(merged_nodes)

            # First pass on the remaining node, rule out specific cases. Head nodes
            # in simple paths are processed here.
            first_pass_merged_nodes = set()
            for n in last_nodes:

                pred = list(btfg_flow.get_graph().predecessors(n))
                succ = list(btfg_flow.get_graph().successors(n))

                # dom_pred = list(b_tfg.get_dom_tree()._domTree.predecessors(n))
                dom_succ = list(btfg_flow.get_dom_tree()._domTree.successors(n))

                # if len(pred) == 1 and len(succ) == 1:
                #    assert False, "Something missing in the previous step, fix needed..."

                # Node with multiple in_edges and single out_edge, this node
                # dominates the successor in domTree, merge to fix_point downwards
                # if fix_point is already a mapped node, or it is mapped in the previous
                # step.
                if len(pred) > 1 and len(succ) == 1:
                    if len(dom_succ) != 1:
                        continue
                    # Check if node is merged in the previous step
                    last_succ = Find(succ[0])
                    if last_succ in mapped_nodes:
                        # Assign this node to last_succ
                        log.debug("Assigned node {} with mult_in_edg and single out_edg to {}.".
                                  format(n, last_succ))
                        Union(n, last_succ)
                        first_pass_merged_nodes.add(n)

            merged_nodes = merged_nodes.union(first_pass_merged_nodes)
            last_nodes = last_nodes.difference(first_pass_merged_nodes)

            # Second pass on the remaining nodes, perform generic contraction. Either
            # structurally, cutting the connected subgraphs of uncolored nodes, or
            # process nodes iteratively bottom-up in the dominator tree. Uncolored
            # nodes here are always assigned upwards in dominator tree.
            nlist = SortedKeyList(iterable=last_nodes,
                                  key=btfg_flow.get_dom_tree().get_preorder_number)

            for n in reversed(nlist):
                # Pred is already checked to have length 1, domTree is valid
                dom_pred = list(btfg_flow.get_dom_tree()._domTree.predecessors(n))
                last_pred = Find(dom_pred[0])
                if last_pred in mapped_nodes:
                    # Already found a fixed point (simple_path)
                    log.debug("[2nd pass] Assigning {} to fixed node {}".format(n, last_pred))
                    Union(n, last_pred)
                    merged_nodes.add(n)
                else:
                    # Assign upwards
                    # log.debug("[2nd pass] Assigning {} upwards to node {}".format(n, dom_pred[0]))
                    # Union(n, dom_pred[0])
                    log.debug("[2nd pass] Assigning {} upwards to node {}".format(n, last_pred))
                    Union(n, last_pred)
                    merged_nodes.add(n)

            for n in last_nodes:
                assert len(sets_nodes[n]) == 0, "Algorithm failed, must fix."

            # Yet another sanity check
            for n in btfg_flow.get_graph().nodes:
                m = Find(n)
                if m not in mapped_nodes:
                    assert False, "Not all unmapped nodes were assigned to mapped points.\n" \
                                  "Unmapped node {}.\n Node Sets: {}".format(m, sets_nodes)

        log.info("Completing mapping of {}".format(btfg.name))
        unmapped_nodes = input_map.unmapped()
        mapped_nodes = input_map.mapped()
        log.debug("Unmapped binary nodes: {}".format(list(unmapped_nodes)))

        if self.do_render:
            eid = btfg_flow.get_entry_id()
            render.render_graph(btfg_flow.get_dom_tree()._domTree, dir=tempfile.tempdir,
                                name=self.bFlow.name + '_domTree_' + str(eid), prefix="bin",
                                topnode=eid)

        node_sets = {n: {n} for n in btfg_flow.get_graph().nodes}
        node_lookup = {n: n for n in btfg_flow.get_graph().nodes}
        nodes_merged = set()
        merge_simple_paths(nodes_merged, node_sets)  # FIXME: deprecated. Task of linelump mapper.
        contract_dominator_tree(nodes_merged, node_sets)

        mapping_dict = dict()
        for n in btfg_flow.get_graph().nodes:
            matched_src_node = input_map[Find(n)]
            assert matched_src_node is not None
            mapping_dict[n] = matched_src_node
        # --
        smap = GraphMap(btfg_flow, stfg_flow, mapping_dict, "domlump.map", predecessors=[input_map])
        report = dict(comment="no report implemented")
        return smap, report
