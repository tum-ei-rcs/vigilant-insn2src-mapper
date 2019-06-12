#
# Constructs a mapping of perfect matches between two flow graphs
#
import logging
import tempfile
from graphmap import GraphMap
from mapping.mapper import AbstractMapper
from flow import render, transformation, transformer
from flow.transformer import HierarchicalFlowGraph


log = logging.getLogger(__name__)


class CtrlDependencyMapper(AbstractMapper):
    """
    Establishes ctrl-dependency mapping between flow graphs,
    considering already-matched loops.
    """

    def __init__(self, input_hmap, bFlow, sFlow, bhFlow, shFlow,
                 do_render=True, check_inputs=False, trust_dbg=False):
        assert input_hmap is None, "Not taking any input maps"
        # --
        super(CtrlDependencyMapper, self).__init__(None, bFlow, sFlow, bhFlow, shFlow, check_inputs)
        self.do_render = do_render
        self.trust_dbg_columns = trust_dbg

    def _compute_mapping(self):
        mapping = self.walk_subgraphs()
        mapping.is_precise = True
        return mapping, self.bhFlow, self.shFlow

    def _map_subgraph(self, input_map, btfg, stfg):
        assert isinstance(btfg, HierarchicalFlowGraph)
        assert isinstance(stfg, HierarchicalFlowGraph)

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

        def compute_ctrldep_map():
            """
            filter map using dominator homomorphism
            :returns GraphMap
            """

            def get_bb_ctrlprops(flow, tfg, ctrldep):
                """label dependent BBs with the labels of their immediate controlling edges
                :returns dict(edge_label in tfg: immediately controlled nodes in tfg)
                """
                g = tfg.flow.get_graph()
                node2edges = dict()  # nodes -> edge labels
                for e, controlled_nodes in ctrldep.iteritems():
                    if e in g.edges:
                        for c in controlled_nodes:
                            lbl = flow.digraph.edges[e]['label']  # must not fail
                            if c not in node2edges:
                                node2edges[c] = set()
                            node2edges[c].add(lbl)
                # -- make them hashable
                node2cond = {k: frozenset(v) for k, v in node2edges.iteritems()}
                return node2cond

            def get_subgraph_ctrldeps():
                """filter flow-wide deps to only hold edges and nodes of this subgraph,
                and also remove self-dep of loop headers"""

                def get_and_filter_subgraph(tfg, flow):
                    ctrldep = flow.get_control_dependencies()
                    g = tfg.flow.get_graph()
                    ctrldep_here = {k: set(filter(lambda x: x in g.nodes and x != tfg.loop_id, v))
                                    for k, v in ctrldep.iteritems() if k in g.edges}
                    return ctrldep_here

                deps_bin = get_and_filter_subgraph(btfg, self.bFlow)
                deps_src = get_and_filter_subgraph(stfg, self.sFlow)
                return deps_bin, deps_src

            f_map = dict()
            f_map.update(fixed_points)
            log.info("Running ctrl-dep mapping on '{}'".format(btfg.name))
            log.debug("Fixed points={}".format(f_map.items()))

            #####################
            # ctrldep properties
            #####################
            ctrldep_bin, ctrldep_src = get_subgraph_ctrldeps()
            report["control-dependency"] = dict(
                    bin={str(k): str(list(v)) for k, v in ctrldep_bin.iteritems()},
                    src={str(k): str(list(v)) for k, v in ctrldep_src.iteritems()})
            bnode2ctrl = get_bb_ctrlprops(self.bFlow, btfg, ctrldep_bin)
            snode2ctrl = get_bb_ctrlprops(self.sFlow, stfg, ctrldep_src)
            report['node-ctrl-props'] = dict(bin={k: " || ".join(list(v))
                                                  for k, v in bnode2ctrl.iteritems()},
                                             src={k: " || ".join(list(v))
                                                  for k, v in snode2ctrl.iteritems()})

            ###########
            # matching
            ###########
            # reverse snode to match them
            rev = dict()
            for node, cond in snode2ctrl.iteritems():
                if cond not in rev:
                    rev[cond] = {node}
                else:
                    rev[cond].add(node)

            for bb, cond in bnode2ctrl.iteritems():
                snodes = rev.get(cond, {})
                if snodes:
                    log.debug("{}: bin-{} maps to src nodes: {}".format(btfg.name, bb, snodes))
                    # If there are multiple src BBs, we can annotate to any of them
                    # however, some of them are loop headers. Do not annotate there.
                    found = False
                    for sn in snodes:
                        # FIXME: see paper whether they have addressed that one.
                        loc = self.sFlow.get_line_info(sn)
                        if 'min' in loc and loc['min'].get('l', 0) > 0:
                            f_map[bb] = sn
                            found = True
                            break
                    if not found:
                        log.debug("{} No valid src locations for {}".format(btfg.name, bb))
                else:
                    log.debug("{}: no match for bin-{}, cond={}".format(btfg.name, bb, cond))

            # --
            g = GraphMap(gA=btfg.flow, gB=stfg.flow, dict_map=f_map, name="ctrl dependency")
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

        ##########
        # Mapping
        ##########
        h_map = compute_ctrldep_map()
        report['ctrlDepMap'] = h_map
        report['trust-dbg-info'] = self.trust_dbg_columns
        # --
        return h_map, report
