import os.path
import logging
import fparser.control_flow
from mapping.homo_mapper import HomomorphismMapper
from flow.transformer import HierarchicalFlowGraph, TransformedFlowGraph


log = logging.getLogger(__name__)


# noinspection PyUnusedLocal
def match(bFlow, sFlow, do_render=False, trust_dbg=False, ignore_discriminators=False):
    """
    Assign labels to edges that are semantically similar in both flow graphs.
    Based on careful use of debug information.
    """
    assert isinstance(bFlow, fparser.control_flow.BinaryControlFlow)
    assert isinstance(sFlow, fparser.control_flow.SourceControlFlow)
    # --
    report = dict()

    label_counter = dict()  # line -> label count (starting with zero when one label)

    def make_label(lno):
        """generates a unique label for line 'lno' """
        label_counter[lno] = label_counter.get(lno, -1) + 1
        return "p{}".format(label_counter[lno])

    def match_discriminators():
        """Compiler can enumerate discriminators almost arbitrarily (only rule: single BB is zero).
        Thus we try to match the discriminators and put a common label on matches. Non-matches
        have unique labels. As a result, two discrs with the same label are identical.

        Since column info is completely unreliable, we use a dominator homomorphism matching here.
        Only a complete match is considered.

        :returns dict giving matches for (line, label) -> {s: source discriminator, b: bin discr}
        """
        def register_bb(bb, line2discr, loc):

            def reg(b, l, d):
                if l not in line2discr:
                    line2discr[l] = dict()
                # this errs on the safe side. existence of d implies existence of d-1 ... 0:
                for p in xrange(0, d+1):
                    if p not in line2discr[l]:
                        line2discr[l][p] = set()
                    if p == d:
                        line2discr[l][p].add(b)

            if loc and 'min' in loc and 'max' in loc:
                line0 = loc['min']['l']
                discr0 = loc['min']['d']
                line1 = loc['max']['l']
                discr1 = loc['max']['d']
                reg(bb, line0, discr0)
                if line0 < line1:
                    reg(bb, line1, discr1)

        def match_by_structure(sbbs, bbbs):
            """try matching discrs via dominator homomo mapper. Believe only if complete"""
            discriminator_map = None
            btfg = TransformedFlowGraph(c_flow=bFlow)
            btfg.reduce_to_connected_subgraph(bbbs)
            stfg = TransformedFlowGraph(c_flow=sFlow)
            stfg.reduce_to_connected_subgraph(sbbs)
            # now remove all nodes that are not the discriminators that we wanna match
            bhFlow = HierarchicalFlowGraph("bin-discr", btfg)
            shFlow = HierarchicalFlowGraph("src-discr", stfg)
            hm = HomomorphismMapper(None, bFlow, sFlow, bhFlow, shFlow,
                                    hom_order="predominated-first",
                                    hom_order_src="predominated-first",
                                    do_render=False)
            hmap, _, _ = hm.compute_mapping()
            dmap = hmap.mapping
            if not dmap.unmapped():
                discriminator_map = {k: v for k, v in dmap.get_map().iteritems()
                                     if k not in (bFlow._entryId, bFlow._exitId)}
            else:
                log.debug("Discriminator matching failed: unmapped: {}".format
                          (dmap.unmapped()))
            # --
            return discriminator_map  # dict bin->src or None

        matches = dict()  # (line, label) -> {sd: <int> , bd: <int>}
        # count discrs on each line (only considering lines where we have BB boundaries)
        line2discr_src = dict()  # line -> discrs -> src BBs
        line2discr_bin = dict()  # line -> discrs -> bin BBs
        for n in sFlow.digraph.nodes():
            register_bb(n, line2discr_src, sFlow.get_line_info(n))
        for n in bFlow.digraph.nodes():
            register_bb(n, line2discr_bin, bFlow.get_line_info(n))
        lines = set(line2discr_src.keys() + line2discr_bin.keys())
        report['discriminators'] = {l: dict(src=str(line2discr_src.get(l, '')),
                                            bin=str(line2discr_bin.get(l, ''))) for l in lines}
        # assign labels to matches
        for line, sdiscs in line2discr_src.iteritems():
            if line in line2discr_bin:
                # we only accept one-to-one matches
                bdiscs = line2discr_bin[line]
                if len(sdiscs) == len(bdiscs) == 1:
                    lbl = make_label(line)
                    matches[(line, lbl)] = dict(s=next(iter(sdiscs)), b=next(iter(bdiscs)))
                elif trust_dbg:
                    # match discriminators based on column info. Not safe unless dbg info is safe
                    for bd, bbs in bdiscs.iteritems():
                        if not bbs:
                            continue
                        for onebb in bbs:
                            bloc = bFlow.get_line_info(onebb)
                            if 'min' in bloc:
                                bcol = bloc['min'].get('c')
                                if bcol:
                                    sb = sFlow.find_source_block(line, bcol, sFlow.digraph.nodes)
                                    if sb is not None:
                                        sd = sFlow.get_line_info(sb)['min']['d']
                                        log.debug("{}:{} matched discrs via dbg info: {}->{}".format
                                                  (bFlow.name, line, bd, sd))
                                        lbl = make_label(line)
                                        matches[(line, lbl)] = dict(s=sd, b=bd)
                                        break

                else:
                    # grab one representative BB from each discr
                    bbunch = {next(iter(bbs)) for bbs in bdiscs.itervalues() if len(bbs) > 0}
                    sbunch = {next(iter(bbs)) for bbs in sdiscs.itervalues() if len(bbs) > 0}
                    bbmap = match_by_structure(sbunch, bbunch)
                    if bbmap is None:
                        log.debug("{}:{}: Unmatched discrs: s={}, b={}".format
                                  (bFlow.name, line, sdiscs, bdiscs))
                    else:
                        log.debug("{}:{} matched discrs via structural properties: {}".format
                                  (bFlow.name, line, bbmap))
                        for bd, bbbs in bdiscs.iteritems():
                            if not bbbs:
                                continue
                            # find the representative
                            onebbb = next(b for b in bbbs if b in bbmap)
                            # find the source discr belonging to here
                            onesbbb = bbmap[onebbb]
                            found = False
                            for sd, sbbs in sdiscs.iteritems():
                                if onesbbb in sbbs:
                                    lbl = make_label(line)
                                    matches[(line, lbl)] = dict(s=sd, b=bd)
                                    found = True
                            assert found, "internal whoopsie"
        # --
        return matches

    def do_enum(cat, enumdict, locstr):
        try:
            oldid = enumdict[locstr]['id']
            enumdict[locstr]['where'].add(cat)
            return oldid
        except KeyError:
            newid = len(enumdict)
            enumdict[locstr] = dict(id=newid, where={cat})
            return newid

    def label_decision_edges():
        """Assign a common label to decision edges in src and bin that are equivalent"""

        def assign_edge_labels(fg, ebunch, cat):
            """
            Enumerate set of decision edges according to their target debug info

            Location of node with outgoing edge enumerates the decision
            Location of target node enumerates the consequents/outcome
            => cX.Y means "decision X, outcome Y"
            """

            def get_discr_label(look_line, look_discr):
                discr_label = dlabel_lookup.get((fg, look_line, look_discr), None)
                return make_label(look_line) if discr_label is None else discr_label

            num = 0
            fname = os.path.basename(fg.file)
            for e in ebunch:
                dloc = fg.get_line_info(e[0])['max']  # decision location
                cloc = fg.get_line_info(e[1])['min']  # consequent location
                log.debug("g={}-{}: dec@{}, con@{}".format(cat, fg.name, dloc, cloc))
                sdloc = "{}::{}".format(fname, dloc['l'])
                scloc = "{}::{}".format(fname, cloc['l'])
                if not ignore_discriminators:
                    # look up discriminator *labels* to enumerate, since numbers have no relevance
                    sdloc += ".{}".format(get_discr_label(dloc['l'], dloc['d']))
                    scloc += ".{}".format(get_discr_label(cloc['l'], cloc['d']))
                edec = do_enum(cat, edict_decisions, sdloc)
                econ = do_enum(cat, edict_consequents, scloc)
                num += 1
                fg.digraph.edges[e]['label'] = "c{}.{}".format(edec, econ)
            return num

        def enum_flow_decisions(fg, cat):
            """Labels all decision edges in flow graph fg."""
            num = 0
            for n in fg.digraph.nodes:
                # all edges that are part of a decision
                if fg.digraph.out_degree(n) > 1:
                    ebunch = fg.digraph.out_edges(n)
                    num += assign_edge_labels(fg, ebunch, cat)
            log.debug("Enumerated {} decision edges in {}-{}".format(num, cat, fg.name))

        # pair src and bin discriminators that belong together, assign a common label to them
        discr_matches = match_discriminators()  # (line, discr label) -> (s: s-discr, b: b-discr)
        report['matched-discrs'] = {str(k): v for k, v in discr_matches.iteritems()}

        # we need the matches the other way around
        dlabel_lookup = {(bFlow, line, v['b']): lbl
                         for (line, lbl), v in discr_matches.iteritems()}
        dlabel_lookup.update({(sFlow, line, v['s']): lbl
                              for (line, lbl), v in discr_matches.iteritems()})

        # now enumerate the different decisions edges ~ enumeration of decisions and consequents
        edict_decisions = dict()
        edict_consequents = dict()
        enum_flow_decisions(sFlow, "src")
        enum_flow_decisions(bFlow, "bin")
        report['enumerated'] = dict(decisions=edict_decisions, consequents=edict_consequents)

    def debug_bbdata(cat, flow):
        for b in flow.digraph.nodes:
            loc = flow.get_line_info(b)
            log.debug("{}: {}-{}: loc={}".format(flow.name, cat, b, loc))

    # debug_bbdata('bin', bFlow)
    # debug_bbdata('src', sFlow)

    log.info("Matching and labeling ctrl edges in {}".format(bFlow.name))
    label_decision_edges()

    report['trust-dbg-info'] = trust_dbg
    # --
    return report
