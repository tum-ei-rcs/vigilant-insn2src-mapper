#
# Establishes a mapping between source code blocks and binary basic blocks.
# (C) 2018 Marius Pazaj, Martin Becker
#
import logging
import tempfile
import loop_matcher
import edge_matcher
from homo_mapper import HomomorphismMapper
from ctrldep_mapper import CtrlDependencyMapper
from domlump_mapper import DominatorLumping
from linelump_mapper import StraightLineLumping
from skip_mapper import SkipMapper
import graphmap as gm
from flow import render, transformer


log = logging.getLogger(__name__)


def map_flows(bFlow, sFlow, mapper_name, hom_order, extLoopInfo=None, do_render=False,
              trust_dbg=False):
    """
    Establish a mapping between a pair of source and binary CFGs.
    Returns a hierarchical graph map that maps bin to source.
    FIXME: generalize hom_order into mapper arguments.
    """
    def report_tfg(report_dic, tfg, ident):
        """write some details about a transformed flow graph to the report"""
        assert ident not in report_dic, "Duplicate transformed flow graph."
        # --
        nodes_to_scan = [n for n in tfg.get_graph().nodes if n <= tfg._c_flow._maxId]
        fcall_dict = {n: tfg._c_flow.get_func_calls(n) for n in nodes_to_scan}
        report_dic[ident] = {
            "edges": list(tfg.get_graph().edges),
            "nodes": list(tfg.get_graph().nodes),
            "fcalls": fcall_dict
        }

    def set_hierarchy_pairs(bhf, shf, matches_s2b, extLoopInfo):
        """Indicate which subgraphs in hierarchy are pairs, based on the loop matching."""

        def walk_level_b(bl):
            """mark those that shall be skipped"""
            if extLoopInfo and str(bl.loop_id) in extLoopInfo['loops']:  # FIXME: extLoopinfo is str
                bl.skip = True
                return
            for sub_bhf in bl.subflows:
                walk_level_b(sub_bhf)

        def walk_level_s2b(bl, sl):
            """pair all subflows at this level, and send pairs down for another walk"""
            bl.set_partner(sl)
            for sub_shf in sl.subflows:
                needed_bb = matches_s2b[sub_shf.loop_id]
                sub_bhf = None
                for this_sub_bhf in bl.subflows:
                    if this_sub_bhf.loop_id == needed_bb:
                        sub_bhf = this_sub_bhf
                        break
                assert sub_bhf is not None
                walk_level_s2b(sub_bhf, sub_shf)
        # --
        walk_level_b(bhf)
        walk_level_s2b(bhf, shf)

    def mark_matched_loops(matches, report_dic):
        """Mark which loops have been matched. Mainly for report"""
        b_rcoll = b_hflow.flow.get_region_collection()
        s_rcoll = s_hflow.flow.get_region_collection()
        for s_loop, b_loop in matches.items():
            b_r_id = b_rcoll.get_loop_region_id(b_loop)
            b_rcoll.mark_loop_region_as_matched(b_r_id)
            s_r_id = s_rcoll.get_loop_region_id(s_loop)
            s_rcoll.mark_loop_region_as_matched(s_r_id)
        # add more retails for skipped binary loops (their corresponding binary loop region id)
        sbl = report_dic.get("skipped_bin_loops", None)
        skipped_b_loops_region_ids = dict()
        b_loops_region_collection = b_hflow.flow.get_region_collection()
        for bLoop in sbl:
            skipped_b_loops_region_ids[bLoop] = b_loops_region_collection.get_loop_region_id(bLoop)
        report_dic["skipped_bin_r_ids"] = skipped_b_loops_region_ids

    def map_all(chosen_mapper):
        """
        Run sequence of mapppers and return final mapping
        FIXME: it's a pipeline, implement it in a generic way
        """
        report["mapping_collection"].update(precise=dict(), linelump=dict(), domlump=dict(),
                                            complete=dict())
        # precise mapper:
        chosen_mapper.set_report(report["mapping_collection"]["precise"])
        pmap, b_hflow0, s_hflow0 = chosen_mapper.compute_mapping()
        pmap.consistency_check()

        # lumps some remaining nodes into their direct pre/succ:
        slmapper = StraightLineLumping(input_hmap=pmap, bFlow=bFlow, sFlow=sFlow,
                                       bhFlow=b_hflow0, shFlow=s_hflow0, do_render=False)
        slmapper.set_report(report["mapping_collection"]["linelump"])
        lmap, b_hflow1, s_hflow1 = slmapper.compute_mapping()
        lmap.consistency_check()
        lmap.add_predecessor(pmap)

        # lumps all remaining nodes into dominators:
        dlmapper = DominatorLumping(input_hmap=lmap, bFlow=bFlow, sFlow=sFlow, bhFlow=b_hflow1,
                                    shFlow=s_hflow1, do_render=do_render)
        dlmapper.set_report(report["mapping_collection"]["domlump"])
        dmap, b_hflow2, s_hflow2 = dlmapper.compute_mapping()
        dmap.consistency_check()
        dmap.add_predecessor(lmap)

        # handles skipped subflows:
        skipmapper = SkipMapper(input_hmap=dmap, bFlow=bFlow, sFlow=sFlow, bhFlow=b_hflow2,
                                shFlow=s_hflow2, annot=extLoopInfo, do_render=False)
        skipmapper.set_report(report["mapping_collection"]["complete"])
        hmap, _, _ = skipmapper.compute_mapping()
        hmap.consistency_check()
        hmap.add_predecessor(dmap)

        # -- stats:
        stats = pmap.calc_statistics()  # MappingStatistics
        percent_precise = ((100. * stats.data['mapped']) / stats.data['total']
                           if stats.data['total'] > 0 else 0.)

        log.info("Function '{}': Mapped {} (sub)graphs with {} nodes, {:.2f}% precise".format
                 (bFlow.name, stats.data['graphs'], stats.data['total'], percent_precise))
        # --
        assert isinstance(hmap, gm.HierarchicalGraphMap)
        return hmap

    ####################
    # Initialize report
    ####################
    report = {
        "bin_func_name": bFlow.name,
        "src_func_name": sFlow.name,
        "bb_timing": bFlow._blockTimes,
        "matched_loops": dict(),
        "flows_bin": dict(),
        "flows_src": dict(),
        "mapping_collection": dict(),
        "mapping_details": dict(),
        "max_bin_id": bFlow._maxId,
        "max_src_id": sFlow._maxId
    }

    #############
    # edge match
    #############
    rpt = edge_matcher.match(bFlow=bFlow, sFlow=sFlow, do_render=do_render, trust_dbg=trust_dbg)
    report['edge-matches'] = rpt

    #############################################
    # Collapse loops -> condensed/reduced graphs
    #############################################
    # subprogram with N loops will produce N+1 tfgs ( |b_l_tfgs| = N, |b_tfg|=1 ) in a hierarchy
    b_hflow = transformer.get_reduced_hierarchy(bFlow)
    s_hflow = transformer.get_reduced_hierarchy(sFlow)
    report_tfg(report["flows_bin"], b_hflow.flow, "all_reduced")  # report top-level
    report_tfg(report["flows_src"], s_hflow.flow, "all_reduced")

    if do_render:
        render.render_graph(bFlow.postdom_tree()._domTree, dir=tempfile.tempdir,
                            name=bFlow.name + '_postDomTree', prefix="bin", topnode=bFlow._exitId,
                            attrs=['num'])
        render.render_graph(bFlow.predom_tree()._domTree, dir=tempfile.tempdir,
                            name=bFlow.name + '_domTree', prefix="bin", topnode=bFlow._entryId,
                            attrs=['num'])
        render.render_graph(sFlow.predom_tree()._domTree, dir=tempfile.tempdir,
                            name=sFlow.name + '_domTree', prefix="src", topnode=sFlow._entryId,
                            attrs=['num'])

    #############################
    # Loops & Hierachical decomp
    #############################
    # we match loops (as a whole, not their nodes) first. FIXME: why independent of flow reduction?
    matched_loops, rpt = loop_matcher.match(bFlow=bFlow, sFlow=sFlow,
                                            extLoopInfo=extLoopInfo, do_render=do_render)
    mark_matched_loops(matched_loops, report_dic=rpt)
    report["matched_loops"] = rpt
    set_hierarchy_pairs(b_hflow, s_hflow, matched_loops, extLoopInfo)

    ###########
    # ctrl dep
    ###########
    def mark_ctrl_edges(g, ebunch):
        for e in ebunch:
            g.edges[e]['ctrl'] = True

    ctrl_bin = bFlow.get_control_dependencies()
    ctrl_src = sFlow.get_control_dependencies()
    mark_ctrl_edges(bFlow.digraph, ctrl_bin.keys())
    mark_ctrl_edges(sFlow.digraph, ctrl_src.keys())
    report["control-dependency"] = dict(bin={str(k): str(list(v)) for k, v in ctrl_bin.iteritems()},
                                        src={str(k): str(list(v)) for k, v in ctrl_src.iteritems()})

    ##########
    # Mapping
    ##########
    def select_mapper():
        m = None
        if mapper_name == 'homomorphism':
            m = HomomorphismMapper(input_hmap=None, sFlow=sFlow, bFlow=bFlow,
                                   bhFlow=b_hflow, shFlow=s_hflow,
                                   hom_order=hom_order, trust_dbg=trust_dbg,
                                   do_render=do_render, check_inputs=True)
        elif mapper_name == 'ctrldep':
            m = CtrlDependencyMapper(input_hmap=None, sFlow=sFlow, bFlow=bFlow,
                                     bhFlow=b_hflow, shFlow=s_hflow, trust_dbg=trust_dbg,
                                     do_render=do_render, check_inputs=True)
        return m

    mapper = select_mapper()
    if mapper is None:
        log.error("Unknown mapper: {}".format(mapper_name))
    try:
        final_mapping = map_all(mapper)
    except:
        import traceback
        traceback.print_exc()
        raise ValueError

    # --
    assert isinstance(final_mapping, gm.HierarchicalGraphMap)
    return final_mapping, report
