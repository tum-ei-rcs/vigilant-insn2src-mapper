import logging
import networkx
import fparser.control_flow
import region
import transformation
from flow import dominator
from itertools import product


log = logging.getLogger(__name__)


def get_skeleton_graph(flow):
    """
    Returns a "skeleton" flow digraph, that is, a light-weight and independent copy of an
    existing one, but without any attributes.
    
    Args
        flow : ControlFlow object (either binary or source)

    Return
        networkx.DiGraph object.

    Note
        Querying information for individual graph nodes only through ControlFlow.
    """
    assert isinstance(flow, fparser.control_flow.ControlFlow)
    # Initialize new skeleton flow digraph
    sk_flow = networkx.DiGraph()
    sk_flow.add_nodes_from(flow.digraph.nodes)
    sk_flow.add_edges_from(flow.digraph.edges)
    return sk_flow


def get_reduced_hierarchy(cFlow):
    """
    Convenience function. Returns reduced subgraphs found in control flow.
    It collapses all cycles into single nodes.

    Args
        cFlow : ControlFlow object (either binary or source)

    Return
        Tuple (tfg, l_tfgs) where tfg is the condensed flow graph where all loops
        are reduced, whereas and is a list of reduced subgraphs (loops). All
        returned flow graphs are TransformedFlowGraph's.
    """
    assert isinstance(cFlow, fparser.control_flow.ControlFlow)
    # --
    tfg = TransformedFlowGraph(c_flow=cFlow)
    tfg.reduce_all_loops()

    try:
        ret = HierarchicalFlowGraph(cFlow.name, tfg, parent=None)
        l_hierarchy = tfg.get_individual_loops_as_hierarchy()
    except:
        ret = l_hierarchy = None
        import traceback
        traceback.print_exc()
    # plug children into top-level:
    ret.subflows.extend(l_hierarchy.values())
    for node_id, hfg in l_hierarchy.iteritems():
        hfg.set_parent(ret, node_id)
    ret.check()
    # --
    return ret


def get_reduced_flows(cFlow):
    """
    deprecated!
    Convenience function. Returns reduced subgraphs found in control flow.
    It collapses all cycles into single nodes.

    Args
        cFlow : ControlFlow object (either binary or source)

    Return
        Tuple (tfg, l_tfgs) where tfg is the condensed flow graph where all loops
        are reduced, whereas and is a list of reduced subgraphs (loops). All
        returned flow graphs are TransformedFlowGraph's.
    """
    assert isinstance(cFlow, fparser.control_flow.ControlFlow)
    tfg = TransformedFlowGraph(c_flow=cFlow)
    tfg.reduce_all_loops()
    l_tfgs = tfg.get_individual_loops_as_list()  # flat list
    return tfg, l_tfgs


class HierarchicalFlowGraph(object):
    """
    Defines a hierarchically partitioned flow graph
    Each hierarchy level carries one flow graph, and a list of children (next level, subflows).
    """

    def __init__(self, name, c_subflow, parent=None, loop_id=None, node_in_parent=None, skip=False):
        assert isinstance(c_subflow, TransformedFlowGraph)
        # --
        self.name = name
        self.flow = c_subflow
        self.skip = skip
        self.subflows = []
        self.parent = parent
        self.topnode = None  # FIXME: isn't it the same as loop_id?
        self.loop_id = loop_id  # original node id in original flowgraph. FIXME: rename.
        self.node_in_parent = node_in_parent  # this graph is "anchored" in new node in the parent
        self.partner = None  # used to indicate a semantic relationship between this and another

    def set_partner(self, other):
        """Indicate that other is a partner (whatever that means) of this one"""
        assert isinstance(other, HierarchicalFlowGraph)
        self.partner = other
        other.partner = self

    def set_parent(self, parent, node_id_in_parent):
        assert isinstance(parent, HierarchicalFlowGraph)
        self.loop_id = node_id_in_parent
        self.parent = parent

    def find(self, ident):
        """returs subflow with given id
        FIXME: slow. use a dict.
        """
        ret = None
        for c in self.subflows:
            if c.loop_id == ident:
                return c
        return ret

    def count_subflows(self, include_skipped=False, recursive=False):
        """return number of subflows, optionally with those that are marked as skip"""
        s = 0
        for c in self.subflows:
            if not c.skip or include_skipped:
                s += 1
                if recursive:
                    s += c.count_subflows(include_skipped, recursive)
        # --
        return s

    def check(self):
        for c in self.subflows:
            c.check()
        if self.parent is None:
            assert self.loop_id is None


class TransformedFlowGraph(object):
    """Given a flow graph, this builds a graph where all cycles are collapsed into single nodes"""

    def __init__(self, c_flow=None, transf_flow=None, subg=None):
        """
        :param c_flow: original control flow graph (only for those who don't have parents)
        :param transf_flow: if the CFG was changed, then this is the graph
        :param subg: subgraph which this represents
        """
        self._c_flow = None
        self._isSubflow = None
        self._regions = None
        self._curr_graph = None
        self._domTree = None
        self.entryId = None
        self.exitId = None
        
        if c_flow is not None:
            assert isinstance(c_flow, fparser.control_flow.ControlFlow)

            self._isSubflow = False
            self.entryId = c_flow._entryId
            self.exitId = c_flow._exitId
            self._c_flow = c_flow
            self._regions = region.RegionCollection(c_flow.get_max_id())
            
            # Set graph.
            self._curr_graph = get_skeleton_graph(c_flow)  # make a copy, because we change stuff
            for n in self._curr_graph:
                # each node becomes a region. why is each node a region (w/o any trafo)?
                r_graph = networkx.DiGraph()
                r_graph.add_node(n)
                self._regions.add_region(region.Region(n, r_graph, None))
        else:
            assert isinstance(transf_flow, TransformedFlowGraph)
            assert isinstance(subg, networkx.DiGraph)

            self._isSubflow = True
            self.entryId = transf_flow.get_entry_id()
            self.entryId = transf_flow.get_exit_id()
            self.copy_references(self, transf_flow)
            
            # Set graph
            self._curr_graph = subg

    def _graph_changed(self):
        self._domTree = None

    def get_entry_id(self):
        if self.entryId is None:
            if not self.is_subflow():
                self.entryId = self.get_orig_flow_entry_id()
            else:
                raise ValueError("Have no entry ID")
        return self.entryId

    def get_exit_id(self):
        if self.exitId is None:
            if not self.is_subflow():
                self.exitId = self.get_orig_flow_exit_id()
            else:
                raise ValueError("Have no exit ID")
        return self.exitId

    def reduce_to_connected_subgraph(self, nbunch):
        """Connect-through all nodes that are not part of nbunch"""
        assert nbunch, "Really? That would empty the graph"
        # --
        keepnodes = nbunch | {self.entryId, self.exitId}
        for n in list(self._curr_graph.nodes):
            # delete non-conflicting
            if n not in keepnodes:
                preds = self._curr_graph.predecessors(n)
                succs = self._curr_graph.successors(n)
                self._curr_graph.add_edges_from(product(preds, succs))
                self._curr_graph.remove_node(n)

    def reduce_single_loop(self, n, level, parentloop):

        def translate_node_id(b):
            """
            Header nodes of already reduced loops are replaced by new nodes. Given
            the original node id, this function returns the new block id if loop
            is already reduced, else it returns the given node id itself.
            """
            new_id = self._regions._loopRegions_i.get(b, None)
            if new_id is None:
                return b
            else:
                return new_id

        def get_loop_nodes():
            """Returns loop nodes, including header node."""
            lInfo = self._c_flow.get_loop_info()
            bNodes = lInfo.get_body_nodes(n)
            bNodes = set([translate_node_id(b) for b in bNodes])
            return bNodes.union([n])

        def get_exit_edges(lNodes):
            """Return a set of exit edges."""
            ee = set([])
            for _n in lNodes:
                succ = list(self._curr_graph.successors(_n))
                for s in succ:
                    if s not in lNodes:
                        ee.add((_n, s))
            return ee

        def get_entry_edges():
            """
            Returns loop entry edge(s). Not all loops contain preheader nodes,
            therefore the header node may contain multiple entry edges.
            """
            lInfo = self._c_flow.get_loop_info()
            ie = set(self._curr_graph.in_edges(n))
            be = set([(translate_node_id(b), n) for b in lInfo.get_back_edges(n)])
            
            log.debug("get_entry_edges: ie={}, be={}".format(ie, be))
            # FIXME: Check if entry edge comes from an already reduced loop!
            #       translate_node_id() must return the new region id for
            #       original reduced loop body nodes too.

            return ie.difference(be)

        self._graph_changed()
        # 0. First get all loop nodes
        lNodes = get_loop_nodes()

        # 1. Get entry and exit edges.
        e_entry = get_entry_edges()
        e_exit = get_exit_edges(lNodes)
        
        # 2. Save a copy of loop's subgraph, remove loop nodes from control flow graph.
        lSubg = networkx.DiGraph(self._curr_graph.subgraph(lNodes))
        self._curr_graph.remove_nodes_from(lNodes)
        
        # 3. Insert new dummy node in graph that represents the reduced loop
        r_id = self._regions.generate_new_region_id()
        self._curr_graph.add_node(r_id)

        # Log
        log.debug("New loop region id: {}".format(r_id))
        log.debug("Entry edges: {}".format(e_entry))
        log.debug("Exit edges: {}".format(e_exit))
        
        # 4. Add entry and exit edges for this node
        self._curr_graph.add_edges_from([(b, r_id) for b, _ in e_entry])
        self._curr_graph.add_edges_from([(r_id, b) for _, b in e_exit])

        # 5. Save subgraph as 'region' attribute, first add the new region.
        tf = transformation.ReducedLoopTransf(n, e_exit, level=level, parentloop=parentloop)
        self._regions.add_region(region.Region(r_id, lSubg, tf))
        self._curr_graph.nodes[r_id]['region'] = self._regions.get_region(r_id)

    def reduce_all_loops(self):
        """
        Use info from prior loop analysis to collapse all loops into single nodes.
        Loop reduction must be performed before all other transformations.
        """
        self._graph_changed()
        linfo = self._c_flow.get_loop_info()
        sorted_plist = linfo.get_sorted_plist()  # post-order
        log.debug("Sorted plist in reduce_all_loops: {}".format(sorted_plist))
        for n in sorted_plist:
            lvl = linfo.get_loop_level(n)
            tmp = linfo.get_parent_node(n)
            parentloop = tmp if linfo.is_loop_header(tmp) else None
            self.reduce_single_loop(n, level=lvl, parentloop=parentloop)

    def get_graph(self):
        return self._curr_graph

    def nodes(self):
        return self._curr_graph.nodes()

    def get_dom_tree(self):
        """return (pre-)dominator tree"""
        if self._domTree is None:
            self._domTree = dominator.PreDominatorTree(self._curr_graph,
                                                       entryId=self.get_entry_id())
        return self._domTree

    def get_region_as_tfg(self, region_id):
        g = self._regions.get_region(region_id).get_graph()
        return TransformedFlowGraph(transf_flow=self, subg=g)

    def get_individual_loops_as_hierarchy(self):
        """return loop regions as dict(node in parent graph, hierarchical flowgraph)"""

        # Iterate over all loop regions and collect graphs and order them by level
        hierarchy = dict()
        for lr_i in self._regions._loopRegions:
            lr = self._regions.get_region(lr_i)
            lr_transf = lr.get_transf()
            assert isinstance(lr_transf, transformation.ReducedLoopTransf)

            lvl = lr_transf.level
            lr_head_node_original = lr_transf.get_header_node()
            subtfg = self.get_region_as_tfg(lr_i)
            subtfg.entryId = lr_head_node_original
            node_in_parent = self._regions._loopRegions_i.get(lr_head_node_original, None)
            subtype = "bin" if isinstance(subtfg.get_original_cflow(),
                                          fparser.control_flow.BinaryControlFlow) else "src"
            subname = "{}_{}_{}".format(subtype, self._c_flow.name, subtfg.entryId)
            hfg = HierarchicalFlowGraph(name=subname, c_subflow=subtfg,
                                        parent=None,  # we don't know it, yet
                                        node_in_parent=node_in_parent,
                                        loop_id=lr_head_node_original)
            if lvl not in hierarchy:
                hierarchy[lvl] = []
            hierarchy[lvl].append(hfg)

        # assemble hierarchy
        for lvl in sorted(hierarchy.keys()):
            for hfg in hierarchy[lvl]:
                if lvl > 0:
                    # connect to parent (=the one who contains my entry node)
                    for phfg in hierarchy[lvl-1]:
                        if hfg.node_in_parent in phfg.flow.nodes():
                            hfg.parent = phfg
                            phfg.subflows.append(hfg)
                            break
                    if hfg.parent is None:
                        assert False, "could not build flow graph hierarchy"
        # --
        return {hfg.loop_id: hfg for hfg in hierarchy.get(0, [])}  # dict: node in parent, hfg

    def get_individual_loops_as_list(self):
        """deprecated. yields a flat list"""
        l_tfgs = dict()
        # Iterate over all loop regions
        for lr_i in self._regions._loopRegions:
            lr = self._regions.get_region(lr_i)
            lr_transf = lr.get_transf()
            assert isinstance(lr_transf, transformation.ReducedLoopTransf)
            lr_head_node_original = lr_transf.get_header_node()
            subtfg = self.get_region_as_tfg(lr_i)
            l_tfgs[lr_head_node_original] = subtfg
            subtfg.entryId = lr_head_node_original
        return l_tfgs

    def get_region_collection(self):
        return self._regions

    def get_original_cflow(self):
        """Returns a reference to the origian ControlFlow object."""
        return self._c_flow

    def get_orig_flow_entry_id(self):
        """
        Returns the bb entry id of the original ControlFlow object associated
        with this transformed flow graph. 

        NOTE: Not to be confused with region entry id.
        """
        return self._c_flow._entryId

    def get_orig_flow_exit_id(self):
        """Returns the bb exit id of the original ControlFlow object."""
        return self._c_flow._exitId

    def is_subflow(self):
        """Returns true if TFG instance is constructed from a subflow of
           another TransformedFlowGraph instance."""
        return self._isSubflow

    @staticmethod
    def copy_references(lhs, rhs):
        assert isinstance(rhs, TransformedFlowGraph)
        assert isinstance(lhs, TransformedFlowGraph)
        lhs._regions = rhs._regions
        lhs._c_flow = rhs._c_flow
