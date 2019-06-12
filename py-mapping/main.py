import logging
import coloredlogs
import argparse
import os.path
import tempfile
import sys
import json
import time
import fparser
import mapping
from flow import render
import report
import mapping.graphmap as gm
import networkx as nx


# Set up logging
lvl = 'DEBUG'
coloredlogs.install(level=lvl, fmt='[ %(levelname)s ] <%(name)s> %(message)s')
log = logging.getLogger(__file__)


def do_render_flows(bFlow, sFlow, attrs=None):
    """render a pair"""
    bAttrs = attrs if attrs is not None else dict(attrs=bFlow.attrKeys)
    sAttrs = attrs if attrs is not None else dict(attrs=sFlow.attrKeys)
    render.render_graph(bFlow.digraph, dir=tempfile.tempdir, name=bFlow.name,
                        prefix="bin", attrs=bAttrs, interactive=True)
    render.render_graph(sFlow.digraph, dir=tempfile.tempdir, name=sFlow.name,
                        prefix="src", attrs=sAttrs, interactive=True)


def do_mapping(bFlow, sFlow, annot_func, hom_order, mapper_name, do_render=False, trust_dbg=False):
    """Compute mapping between a pair of CFGs and return report"""
    start_time = time.time()
    final_map, reprt = mapping.map_flows(bFlow, sFlow, mapper_name=mapper_name,
                                         hom_order=hom_order, extLoopInfo=annot_func,
                                         do_render=do_render, trust_dbg=trust_dbg)
    end_time = time.time()
    log.debug("Elapsed time for flow {}: {:.2f}s".format(bFlow.name, end_time - start_time))
    # --
    assert isinstance(final_map, mapping.graphmap.HierarchicalGraphMap)
    return final_map, reprt


def do_render_mapping(bFlow, sFlow, hierarchical_map, annot_file):
    """
    Render mapping for a CFG pair
    """

    def add_pre(s, p):
        return "{}{}".format(p, s)

    def copy_and_rename(gdst, gfrom, prefix, maxid):
        """copy nodes, edges and attributes from gsrc to gdst, while adding a prefix"""
        gdst.add_nodes_from([(add_pre(n, prefix), gfrom.nodes[n]) for n in gfrom.nodes
                             if n <= maxid])  # FIXME: not elegant with maxid
        gdst.add_edges_from([(add_pre(e[0], prefix), add_pre(e[1], prefix)) for e in gfrom.edges
                             if e[0] <= maxid and e[1] <= maxid])
        # node attrs
        for _n in gfrom.nodes:
            at = gfrom.nodes[_n]
            gdst.nodes[add_pre(_n, prefix)].update(at)
        for _e0, _e1 in gfrom.edges:
            at = gfrom.edges[(_e0, _e1)]
            gdst.edges[(add_pre(_e0, prefix), add_pre(_e1, prefix))].update(at)

    def build_clusters(hmap):
        assert isinstance(hmap, gm.HierarchicalGraphMap)
        parts = hmap.name.split("|")
        if len(parts) == 2:
            cbname = parts[0]
            csname = parts[1]
        else:
            cbname = "bin_{}".format(hmap.name)
            csname = "src_{}".format(hmap.name)
        cluster_bin = render.GraphCluster(cbname)
        cluster_src = render.GraphCluster(csname)
        # children
        for c in hmap.children:
            ccb, ccs = build_clusters(c)
            if ccb is not None:
                cluster_bin.add_child(ccb)
            if ccs is not None:
                cluster_src.add_child(ccs)
        # myself
        b_nodes = hmap.mapping.mapped() | hmap.mapping.unmapped()  # bin BBs!
        if hmap.mapping.graph_B is not None:
            s_nodes = hmap.mapping.graph_B.get_graph().nodes()
        else:
            s_nodes = set()
        if s_nodes:
            cluster_src.add_nodes(map(lambda x: add_pre(x, "s"), s_nodes))
            cluster_src.topnode = add_pre(hmap.mapping.graph_B.entryId, 's')
        if b_nodes:
            cluster_bin.add_nodes(map(lambda x: add_pre(x, "b"), b_nodes))
            cluster_bin.topnode = add_pre(hmap.mapping.graph_A.entryId, 'b')

        if cluster_src.empty():
            return cluster_bin, None
        else:
            cluster_bin.add_relative(cluster_src)
            return cluster_bin, cluster_src

    def locstr(loc):
        disc = loc.get('d', None)
        col = loc.get('c', 0)
        line = loc.get('l', 0)
        s = "{}".format(line)
        if col != 0:
            s += ":{}".format(col)
        if disc is not None:
            s += " ({})".format(disc)
        return s

    def decorate():
        """add some more informative attrs to graph"""
        def deco(flow):
            for n in flow.digraph.nodes:
                dec = dict()
                # line info
                lid = flow.get_line_info(n)
                if lid:
                    try:
                        dec = dict(begin=locstr(lid["begin"]), end=locstr(lid["end"]))
                        dec.update(dict(min=locstr(lid["min"]), max=locstr(lid["max"])))
                    except KeyError:
                        pass
                # func calls
                fc = flow.get_func_calls(n)
                if fc:
                    dec['calls'] = str(fc)
                # timing
                if hasattr(flow, "_blockTimes"):
                    try:
                        dec['time'] = flow._blockTimes[n]
                    except KeyError:
                        pass
                # --
                flow.digraph.node[n].update(dec)
        deco(bFlow)
        deco(sFlow)

    decorate()

    ############################
    # copy both graphs into one
    ############################
    both_graphs = nx.DiGraph()
    both_graphs.graph.update(bFlow.digraph.graph)  # take graph attrs from bin
    copy_and_rename(both_graphs, bFlow.digraph, "b", bFlow._maxId)
    copy_and_rename(both_graphs, sFlow.digraph, "s", sFlow._maxId)

    # get cluster/subgraph hierarchy
    clusters = build_clusters(hierarchical_map)
    if not clusters[0].check_cluster():
        log.warning("Cluster bin of {} inconsistent".format(hierarchical_map.name))
    if not clusters[1].check_cluster():
        log.warning("Cluster src of {} inconsistent".format(hierarchical_map.name))

    # get the mapping itself
    flatmap = hierarchical_map.flatten()
    allmap = {add_pre(k, 'b'): add_pre(v, 's') for k, v in flatmap.get_map().iteritems()
              if k <= bFlow._maxId}

    # add one commonn entry/exit node for better visualization
    entries = ['b{}'.format(bFlow._entryId), 's{}'.format(sFlow._entryId)]
    exits = ['b{}'.format(bFlow._exitId), 's{}'.format(sFlow._exitId)]
    both_graphs.add_node("entry", shape='diamond')
    both_graphs.add_node("exit", shape='diamond')
    both_graphs.add_edges_from([('entry', n) for n in entries])
    both_graphs.add_edges_from([(n, 'exit') for n in exits])

    # mark control edges in color:
    for e in both_graphs.edges:
        if 'ctrl' in both_graphs.edges[e]:
            both_graphs.edges[e]['color'] = both_graphs.edges[e]['fontcolor'] = 'red'

    ##############################
    # mark precisely mapped nodes
    ##############################
    precise_nodes = set()
    try:
        preds = hierarchical_map.get_predecessors()
        assert len(preds) == 1, "more than one predecessor; cannot mark precisely mapped nodes"
        precise_map = next(iter(preds))
        pflatmap = precise_map.flatten()
        mapped_nodes = [add_pre(n, 'b') for n in pflatmap.mapped() if n <= bFlow._maxId]
        precise_nodes |= set(mapped_nodes)
        for n in mapped_nodes:
            both_graphs.nodes[n].update(dict(fillcolor='darkolivegreen1', style='filled'))

    except AssertionError:
        log.warning("cannot highlight precisely mapped nodes in mapping")

    ###################
    # add mapping edges
    ###################
    if precise_nodes:
        mapping_edges = [(k, v) for k, v in allmap.iteritems() if k in precise_nodes]
    else:
        mapping_edges = [(k, v) for k, v in allmap.iteritems()]
    both_graphs.add_edges_from(mapping_edges,
                               virtual=True, color='gray80', style='dashed', constraint='False')

    # ... and finally render
    imgname = "map_" + hierarchical_map.name
    render.render_graph(G=both_graphs, dir=tempfile.tempdir, name=imgname, interactive=True,
                        topnode='entry', botnode='exit', clusters=list(clusters), keepfiles=False,
                        attrs=('color', 'fillcolor', 'fontcolor', 'style', 'shape', 'arrowhead',
                               'constraint', 'begin', 'end', 'min', 'max', 'time', 'calls'))


def main(args):
    # Load binary and source flow graphs
    exe = fparser.Executable(args.bin_json, args.dwarf_json, args.src_csv, args.optime_csv,
                             simplify=(not args.no_simplify))
    log.debug("Optime_csv={}".format(args.optime_csv))

    ##########################
    # Load external loop info
    ##########################
    annot_file = None
    if args.annot_file is not None:
        with open(args.annot_file, 'r') as fp:
            annot_file = json.load(fp)
        log.info("External annot file loaded.")
        log.info(json.dumps(annot_file, indent=4))

    #########################
    # Process flows pairwise
    #########################
    time_all_begin = time.time()
    funcs_all = set()
    funcs_mapped = dict()
    n_tot = n_grp = n_prec = 0
    for bFlow, sFlow in exe.get_flow_pairs():
        funcs_all.add(bFlow.name)
        log.debug("Mapping {} ({}) to {} ({}).".format
                  (bFlow.name, bFlow.file, sFlow.name, sFlow.file))
        if args.render_graphs:
            do_render_flows(bFlow=bFlow, sFlow=sFlow)

        ##############
        # Annotations?
        ##############
        annot_func = None
        if annot_file is not None and bFlow.name in annot_file:
            annot_func = annot_file[bFlow.name]

        ##########
        # mapping
        ##########
        try:
            full_map, rpt = do_mapping(bFlow=bFlow, sFlow=sFlow, annot_func=annot_func,
                                       hom_order=args.hom_order, mapper_name=args.mapper,
                                       do_render=args.render_graphs, trust_dbg=args.trust_dbg_info)
            funcs_mapped[bFlow.name] = full_map
            # get statistics for precise mapping (=predecessors of completer)
            preds = full_map.get_predecessors()
            if preds:
                assert len(preds) == 1
                stats = next(iter(preds)).calc_statistics()
            else:
                stats = full_map.calc_statistics()
            if stats is not None:
                n_grp += stats.data.get('graphs', 0)
                n_tot += stats.data.get('total', 0)
                n_prec += stats.data.get('mapped', 0)
        except AssertionError:
            full_map = rpt = None
            log.error("Failed to match flow {}.".format(bFlow.name), exc_info=True)

        #########
        # report
        #########
        try:
            report.write(bFlow=bFlow, sFlow=sFlow, annot_func=annot_func, mapping=full_map,
                         reportdata=rpt)
        except:
            import traceback
            log.error("Could not write report for {}".format(bFlow.name))
            traceback.print_exc()

        #########
        # render
        #########
        if args.render_graphs:
            full_map.name = bFlow.name
            try:
                do_render_mapping(bFlow=bFlow, sFlow=sFlow,
                                  annot_file=annot_file, hierarchical_map=full_map)
            except AssertionError:
                log.warning("Error during rendering of mapping {}".format(full_map.name))
                import traceback
                traceback.print_exc()

    #####################
    # Overall Statistics
    #####################
    funcs_unmapped = funcs_all.difference(set(funcs_mapped.keys()))
    time_all_end = time.time()
    percent_precise = (100.*n_prec)/n_tot if n_tot > 0 else 100.
    log.info("Statistics: {} subgraphs with {} nodes, {:.2f}% precise".format
             (n_grp, n_tot, percent_precise))
    log.info("Mapped {} out of {} functions in {:.2f} seconds".format
             (len(funcs_mapped), len(funcs_all), time_all_end - time_all_begin))
    if len(funcs_unmapped) > 0:
        log.warning("Unmapped functions: {}".format(", ".join(sorted(list(funcs_unmapped)))))
    # --
    return len(funcs_unmapped)


def check_file(fpath):
    if not os.path.isfile(fpath):
        raise argparse.ArgumentTypeError('Invalid file path given.')
    return fpath


def check_dir(dpath):
    if not os.path.isdir(dpath):
        raise argparse.ArgumentTypeError('Invalid directory path given.')
    return dpath


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Mapping script")
    parser.add_argument('--temp-dir', type=check_dir, default=None,
                        help='temporary/output dir path')
    parser.add_argument('--suppress-log', default=False, action='store_true',
                        help='suppress logging')
    parser.add_argument('--render-graphs', default=False, action='store_true',
                        help='enable generating graph images (warning: slow)')
    parser.add_argument('--hom-order', default='predominated-first',
                        help='Choose the sorting order used by the dominator homomorphism algorithm'
                        'Default is "predominated-first".')
    parser.add_argument('--mapper', default='ctrldep',  # ctrldep, homomorphism
                        help='Select the mapping strategy')
    parser.add_argument('--no-simplify', default=False, action='store_true',
                        help='Do not simplify CFGs (usually improves matching)')
    parser.add_argument('--annot-file', type=check_file, default=None,
                        help='Annotation file containing loop cycle counts for low level loops.')
    parser.add_argument('--trust-dbg-info', default=False, action='store_true',
                        help='Use column info for mapping (not safe, not always better!)')
    
    required = parser.add_argument_group('required arguments')

    required.add_argument('--bin-json',   type=check_file, required=True,
                          help='path to JSON file containing binary flows')
    required.add_argument('--dwarf-json', type=check_file, required=True,
                          help='path to JSON file containing DWARF information')
    required.add_argument('--src-csv',    type=check_file, required=True,
                          help='path to CSV file containing source flows')
    required.add_argument('--optime-csv', type=check_file, required=True,
                          help='path to CSV file containing opcode time info')
    
    pargs = parser.parse_args()

    # Update temp dir if set
    if pargs.temp_dir is not None:
        tempfile.tempdir = pargs.temp_dir

    if pargs.suppress_log:
        log.setLevel(logging.ERROR)

    sys.exit(main(pargs))
