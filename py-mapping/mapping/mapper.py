import logging
import fparser
from flow import transformer
import graphmap as gm


log = logging.getLogger(__name__)


class AbstractMapper(object):
    """
    Super class for all mapping algorithms.

    Each mapper must take as input a previous mapping (but may choose to ignore it),
    as well as two hierarchical flow graphs for source (shFlow) and binary (bhFlow),
    and the original binary and source flows.
    Mappers may choose to rewrite the hierarchical flow graphs. The result of the
    function compute() is therefore a new hierarchical mapping and new hierarchical flows.

    Maps and flows that are produced *must match* in their hierarchy, which is
    a class invariant being checked automatically.
    """

    def __init__(self, input_hmap, bFlow, sFlow, bhFlow, shFlow, check_inputs=False):
        """
        :param input_hmap: prior mapping, which may or may not be used by mapper
        :param bFlow: the real, original binary control flow graph
        :param sFlow:
        :param bhFlow: the binary control flow grph as a hierarchy matching the hierarchy of
                       input_hmap
        :param shFlow:
        """
        if input_hmap is not None:
            assert isinstance(input_hmap, gm.HierarchicalGraphMap)
        assert isinstance(bFlow, fparser.control_flow.BinaryControlFlow)
        assert isinstance(sFlow, fparser.control_flow.SourceControlFlow)
        assert isinstance(bhFlow, transformer.HierarchicalFlowGraph)
        assert isinstance(shFlow, transformer.HierarchicalFlowGraph)
        # --
        if check_inputs:
            AbstractMapper.check_hierarchy(input_hmap, bhFlow, shFlow)
        self.report = None
        self.bFlow = bFlow
        self.sFlow = sFlow
        self.bhFlow = bhFlow
        self.shFlow = shFlow
        self.input_hmap = input_hmap

    @staticmethod
    def check_hierarchy(hmap, bhflow, shflow):
        """checks that hierarchy matches between hmap and bhflow, shflow"""

        def walk_children(level_hmap, sub_b, sub_s):
            if level_hmap is not None:
                assert isinstance(level_hmap, gm.HierarchicalGraphMap)
                assert len(level_hmap.children) == sub_b.count_subflows(include_skipped=True)
            assert isinstance(sub_b, transformer.HierarchicalFlowGraph)
            assert isinstance(sub_s, transformer.HierarchicalFlowGraph)
            # --
            assert sub_b.count_subflows() == sub_s.count_subflows(), "unpaired flows in {}".format\
                (bhflow.name)

            # check that all src flows have a partner
            for ss in sub_s.subflows:
                sb = ss.partner
                assert not sb.skip
                assert sb is not None, "Hierarchy pairing incomplete"
                assert sb in sub_b.subflows, "Pairing across different hierarchy levels "
                # find sub-input map, if any:
                if level_hmap is not None:
                    sub_input_map = None
                    for c in level_hmap.children:  # this works since the hierarchies must match
                        if c.mapping.graph_A == sb.flow and c.mapping.graph_B == ss.flow:
                            sub_input_map = c
                            break
                    if level_hmap is not None and sub_input_map is None:
                        raise ValueError("Hierarchical flows and input mapping mismatching")
                else:
                    sub_input_map = None
                walk_children(sub_input_map, sb, ss)

        # --
        walk_children(hmap, bhflow, shflow)

    def compute_mapping(self):
        """
        Dispatches the mapping to the subclass, and checks whether results (new flows, mapping)
        match in their hierarchy.
        :returns new hierachical map and new hierarchical flows (hmap, bhflow, shflow)
        """

        hmap, bhflow, shflow = self._compute_mapping()  # call to dispatch
        AbstractMapper.check_hierarchy(hmap=hmap, bhflow=bhflow, shflow=shflow)
        # --
        return hmap, bhflow, shflow

    def _compute_mapping(self):
        """
        This must be overridden by the subclass
        :returns new hierachical map and new hierarchical flows (hmap, bhflow, shflow)
        """
        raise NotImplementedError("derived class must implement this")

    def set_report(self, report):
        self.report = report

    def walk_subgraphs(self):
        """
        Walks the flow hierarchy (bhFlow, shFlow), pairs them up at each level using
        pairing hints, and calls _map_subgraph (must be implemented in derived class)
        for each pair.

        :return: hierarchical map
        """

        def make_empty_hmap(mname, sub_b, sub_s):
            """
            :param str mname: name of map
            :param sub_b: binary subflow
            :param sub_s: source subflow
            :type sub_b: transformer.HierarchicalFlowGraph | None
            :type sub_s: transformer.HierarchicalFlowGraph | None
            :return: the empty map
            """
            ehm = gm.HierarchicalGraphMap(mname)
            sf = sub_s.flow if sub_s is not None else None
            bf = sub_b.flow if sub_b is not None else None
            em = gm.GraphMap(bf, sf, dict(), mname)
            ehm.mapping = em
            return ehm

        def handle_unmapped_bflows(parent_mapping, mapping, sub_b):
            """Create dummy mappings for unpaired binary flows within hierarchical flow graph"""

            def get_submap(inmap, ssbb):
                for c in inmap.children:
                    if c.mapping.graph_A == ssbb.flow:
                        return c
                return None

            c = 0
            this_mapping = mapping
            if sub_b not in paired_bflows:
                log.debug("Skipped subflow '{}' in mapping of function '{}'".format
                          (sub_b.name, self.bFlow.name))
                # mapping should be None, so we set it and thus enable diving down into children
                # of the skipped flow.
                assert mapping is None, "expected state"
                this_mapping = make_empty_hmap("skip_{}".format(sub_b.name), sub_b, None)
                assert parent_mapping is not None, "internal error"
                parent_mapping.children.append(this_mapping)
                c += 1
            for sb in sub_b.subflows:
                submap = get_submap(this_mapping, sb)
                c += handle_unmapped_bflows(this_mapping, submap, sb)
            return c

        def map_hierarchical(input_hmap, sub_b, sub_s, report):
            """
            Maps all flows that are children of these two flows. Pairs them up on the same
            hierarchy level.
            FIXME: We have no support for loop interchange etc, where levels switch.

            :param input_hmap
            :param sub_b: hierarchical control flow of binary. Must match input_map, if any.
            :param sub_s: hierarchical control flow of src. Must match input_map, if any.
            :param report: hook in report dict where current hierarchy level is reported
            :return: tuple (hierarchicalGraphMap)
            """
            pairname = "{}|{}".format(sub_b.name, sub_s.name)
            hmap = gm.HierarchicalGraphMap(pairname)

            # children first. Pair them using the pairing hints
            subreport = None
            if report is not None:
                if pairname not in report:
                    report[pairname] = dict()
                if sub_s.subflows:
                    subreport = report[pairname]["subflows"] = dict()
            for ss in sub_s.subflows:
                if ss.skip:
                    cmap = make_empty_hmap("skip_{}".format(ss.name), None, ss)
                    log.warning("Skipped subflow '{}' in mapping of function '{}'".format
                                (ss.name, self.sFlow.name))
                else:
                    sb = ss.partner
                    assert sb is not None, "unmatched loop"
                    # find sub-input map, if any:
                    if input_hmap is not None:
                        sub_input_map = None
                        for c in input_hmap.children:  # this works since the hierarchies must match
                            if c.mapping.graph_A == sb.flow and c.mapping.graph_B == ss.flow:
                                sub_input_map = c
                                break
                        if sub_input_map is None:
                            raise ValueError("Hierarchical flows and input mapping mismatching")
                    else:
                        sub_input_map = None
                    # map the pair
                    cmap = map_hierarchical(input_hmap=sub_input_map,
                                            sub_s=ss, sub_b=sb, report=subreport)
                # --
                hmap.children.append(cmap)

            # then myself
            input_map = input_hmap.mapping if input_hmap is not None else None
            hmap.mapping, details = self._map_subgraph(input_map=input_map, btfg=sub_b, stfg=sub_s)
            assert isinstance(hmap.mapping, gm.GraphMap)
            # ensure that the collapsed nodes are in the map
            for sb in sub_b.subflows:
                if sb.node_in_parent not in hmap.mapping.mapped():
                    log.error("Mapper missed to register fixed points in map")
                    assert False
            # --
            paired_bflows.add(sub_b)
            if report is not None:
                self.report_submap(report, pairname, hmap.mapping, details, "mapping")
            # --
            return hmap

        # --
        paired_bflows = set()
        mapping = map_hierarchical(input_hmap=self.input_hmap,
                                   sub_b=self.bhFlow, sub_s=self.shFlow, report=self.report)
        num_unpaired = handle_unmapped_bflows(None, mapping, self.bhFlow)
        if num_unpaired > 0:
            log.info("Skipped {} subflows in mapping of {}".format(num_unpaired, self.bFlow.name))
        # --
        return mapping

    def _map_subgraph(self, input_map, btfg, stfg):
        """
        walk_subgraphs calls this, to flatten hierarchical graphs to flat ones for derives classes
        who want this. Must be overridden by the derived class which want to use walk_subgraphs.
        :param input_map: previously known mapping between the following two graphs
        :param btfg: TransformedFlowGraph (binary)
        :param stfg:
        :return:
        """
        raise NotImplementedError("derived class must implement this")

    @staticmethod
    def report_submap(hook, subname, smap, details, category):
        """
        Can be used by derived classes to yield a mapping report
        We take the details and additional info, and put it into "hook"
        """
        assert isinstance(smap, gm.GraphMap)
        # --
        if hook is None:
            return
        stats = smap.calc_statistics()
        if subname not in hook:
            hook[subname] = dict()
        if category not in hook[subname]:
            hook[subname][category] = dict()
        hook[subname][category]["mapping"] = smap.get_map()
        if details is not None:
            hook[subname][category]["details"] = details
        if stats is not None:
            hook[subname][category]["stats"] = stats
