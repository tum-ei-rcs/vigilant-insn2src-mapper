import logging
import networkx as nx


log = logging.getLogger(__name__)
SELFCHECK_SLOW = False


class AbstractDominatorTree(object):
    """
    Dominator tree (unique) build from immediate dominators of each node in the
    given flow graph of type fparser.control_flow.ControlFlow.

    Dominance (a dom b) can be tested by calling test_dominance(a, b).

    FIXME: Fails for trivial graphs. Need to correct _build_dom_tree and _mark_dfs_preorder_number.
    """
    def __init__(self, digraph, entryId, exitId):
        assert isinstance(digraph, nx.DiGraph)
        assert entryId in digraph.nodes
        assert entryId is not None  # exit might be None, we don't care
        # --
        self._domTree = nx.DiGraph()
        self._rootId = entryId
        self._exitId = exitId
        self._build_dom_tree(digraph, self._rootId)
        self._mark_dfs_preorder_number()

    def _build_dom_tree(self, digraph, entry):
        if len(digraph.nodes) == 1:
            self._domTree.add_node(entry)
            return
        # Code below assumes digraph has more then one node
        idom_list = nx.immediate_dominators(digraph, entry).items()
        for tup in idom_list:
            if tup[0] == entry:
                continue
            self._domTree.add_edge(tup[1], tup[0])

    def get_tree(self):
        return self._domTree

    def get_root(self):
        return self._rootId

    def _mark_dfs_preorder_number(self):
        counter = [0]

        def dfs(node, counter):
            # log.debug("DFS counter={}".format(counter[0]))
            self._domTree.nodes[node]['num'] = counter[0]
            self._domTree.nodes[node]['vis'] = True
            counter[0] += 1
            for s in self._domTree.successors(node):
                if not self._domTree.nodes[s]['vis']:
                    dfs(s, counter)
            self._domTree.nodes[node]['las'] = counter[0] - 1
    
        for n in self._domTree.nodes:
            self._domTree.nodes[n]['vis'] = False
        if self._domTree.number_of_nodes() > 0:
            dfs(self._rootId, counter)
    
    def get_preorder_number(self, node):
        if self._domTree.number_of_nodes() == 0:
            return None
        else:
            assert node in self._domTree.nodes, \
                "Node {} not in original flow graph.".format(node)
            return self._domTree.nodes[node]['num']

    def parent_of(self, n):
        try:
            return next(self._domTree.predecessors(n))
        except StopIteration:
            return None

    def test_dominance(self, a, b):
        """
        Returns true if a dom b.

        Note:
            Dominance test is performed in constant time.
        """
        num_a = self.get_preorder_number(a)
        num_b = self.get_preorder_number(b)
        return (num_a <= num_b) and num_b <= self._domTree.nodes[a]['las']

    def nearest_common_dominator(self, nodes, strictly=False):
        """
        In graph Gr, find the common dominator of all given nodes.

        If len(nodes)==1, then the only element in nodes is returned (self-domination).

        Uses "Optimal Algorithm for the Nearest Common Dominator Problem" Jeff Chu, 1991.
        O(n') time, with n'=number of arcs in subgraph of Gr containing nodes and dominator.
        In case G is large and common dominator is close to nodes, n'<<n. It's magic.

        Params:
         - nodes: a set of node IDs for which we want to find the common dominator
         - strictly: if len(nodes) == 1 and stricly=False, then this returns nodes[0], otherwise
                     the immediate dominator of nodes[0] (if any)

        FIXME: unsurprisingly, this is rather slow

        We use list() as stacks. Push=append(), Pop=pop(). Thus, top is at end of list.
        """
        Gr = self._domTree
        assert isinstance(nodes, set)
        if SELFCHECK_SLOW:
            assert all([n in Gr for n in nodes]), "Internal error: at least one node not in Gr"
        # ---
        if len(nodes) == 1:
            if not strictly:
                return list(nodes)[0]
            else:
                raise NotImplementedError

        def mark_node_reentered(u):
            """re-entered implies visited"""
            mark_node_visited(u)
            Gr.nodes[u]['re'] = True

        def is_node_reentered(u):
            return Gr.nodes[u].get('re', False)

        def mark_arc_visited(u, v, on=True):
            Gr.edges[(u, v)]['vi'] = on

        def mark_node_visited(u, on=True):
            # we cannot mark as unvisited if it is already marked as re-entered.
            # Marking as visited when it is already re-entered *does* happen, whenever we use
            # make_stack() at the end of the main loop
            assert on or not is_node_reentered(u),\
                "Trying to mark re-enterd node '{}' as unvisited={}".format(u, is_node_reentered(u))
            Gr.nodes[u]['vi'] = on

        def is_node_visited(u):
            return Gr.nodes[u].get('vi', False)

        def is_arc_visited(u, v):
            return Gr.edges[(u, v)].get('vi', False)

        def init_node_marking(node):
            Gr.nodes[node].update({'vi': False, 're': False})

        def init_edge_marking(edge):
            Gr.edges[edge].update({'vi': False})

        def make_stack(u):
            mark_node_reentered(u)
            return [u]

        def nonempty_stacks(stcks):
            return [st for st in stcks if len(st) > 0]

        def do_dfs_step(stk):
            """finds and visits one unseen arc for given stack"""
            w = None
            unvisited_arcs = []
            while len(stk) > 0:
                w = stk[-1]  # topmost
                # log.debug("-DFS step: stack={}, finding unvisited arcs into {}".format(stk, w))
                unvisited_arcs = [u for u in Gr.predecessors(w) if not is_arc_visited(u, w)]
                if len(unvisited_arcs) == 0:
                    stk.pop()
                    # log.debug("None, popping -> {}".format(stk))
                else:
                    break
            if len(stk) > 0:
                # log.debug("DFS step: stack={}, unvisitd arcs from={}".format(stk, unvisited_arcs))
                w1 = stk[-1]
                assert w1 == w
                u = unvisited_arcs.pop()
                # log.debug("DFS step: visiting arc=({},{})".format(u, w))
                mark_arc_visited(u, w)
                if not is_node_visited(u):
                    mark_node_visited(u)
                    stk.append(u)
                    # log.debug("*pred {} is newly visited => stack = {}".format(u, stk))
                else:
                    mark_node_reentered(u)
                    # log.debug("pred {} is re-entered".format(u))
            # log.debug("-DFS step finished: {}".format(stk))

        def do_multi_dfs_round():
            """Visits one unseen arc from each non-empty stack"""
            # log.debug("--Multi-DFS round begins")
            for st in stacks:
                if len(st) == 0:
                    continue
                if st[-1] != self._rootId:  # top element
                    # log.debug("Stepping stack {}".format(st))
                    do_dfs_step(st)
                else:
                    # log.debug("Not stepping stack - reached root: {}".format(st))
                    # now we can pop out a path P from s to some node in U
                    pass
            # log.debug("--Multi-DFS round finished")

        log.debug("Searching nearest common dominator for {} in {}, root={}".format
                  (nodes, Gr.edges(), self._rootId))

        # initialize maks for all nodes (necessary, otherwise second time around not same result)
        map(lambda node: init_node_marking(node), Gr.nodes)
        map(lambda edge: init_edge_marking(edge), Gr.edges)

        stacks = [make_stack(u) for u in nodes]
        while True:
            log.debug("Stacks before multi-DFS: {}".format([str(s) for s in stacks]))
            while True:
                nes = nonempty_stacks(stacks)
                if len(nes) <= 1:
                    break
                do_multi_dfs_round()
            assert len(nes) == 1, "Not exactly one non-empty stack; instead: {}".format(len(nes))
            stack = nes.pop()
            # log.debug("#Got exactly one stack to examine: {}".format(stack))
            # search backwards (top to bottom), find first item that is reentered
            pos_topmost_re, topmost_re = next(((rev_pos, el) for rev_pos, el in
                                               enumerate(reversed(stack))
                                               if is_node_reentered(el)))  # counts from top to bot
            # log.debug("Top-most re-entered: {} at rpos {}".format(topmost_re, pos_topmost_re))
            # unvisit elements on top of topmost re-entered element in bottom->top direction
            below_v = None
            for v in stack[-pos_topmost_re - 1:]:
                if v != topmost_re:
                    # log.debug("{} on top of re-entered.".format(v))
                    mark_node_visited(v, False)
                if below_v:
                    mark_arc_visited(v, below_v, False)
                below_v = v
            if pos_topmost_re > 0:
                del stack[-pos_topmost_re:]  # pop all on top of re-entered
            # log.debug("Popped all non-reentered: stack={}. Remaining as new stacks:".format(
            # stack))
            for n in stack:
                stacks.append(make_stack(n))
                # log.debug("New stack: {}".format(n))
            del stack[:]  # FIXME: could remove the entire stack
            # log.debug("Finished with the one stack: {}".format(stack))
            nes = nonempty_stacks(stacks)
            if len(nes) <= 1:
                break

        log.debug("Done with common dominator. Stacks={}".format(nes))
        if len(nes) == 0:
            log.warning("No common dominator found for {}. Returning root.".format(nodes))
            # no common dominator found -> take root node (since it is not considered by
            # the algorithm above, but it is always a common dominator)
            if SELFCHECK_SLOW:
                assert all([nx.has_path(Gr, self._rootId, u) for u in nodes]),\
                    "common dominator algorithm failed"
            d = self._rootId
        else:
            single_nonempty_stack = nes.pop()
            assert len(single_nonempty_stack) == 1, \
                "Nonempty stack must have exactly one element, which is the common dominator."
            d = single_nonempty_stack.pop()
        # ---
        log.debug("Common dominator for {} is {}".format(nodes, d))
        assert d in Gr  # there must always be one common one (at least start or end node)
        if SELFCHECK_SLOW:
            assert all([self.test_dominance(d, u) for u in nodes]), \
                "Internal error: Wrong result computed"
        return d


class PreDominatorTree(AbstractDominatorTree):
    """
    Dominator tree (unique) build from immediate dominators of each node in the
    given flow graph of type fparser.control_flow.ControlFlow.
    Dominance (a dom b) can be tested by calling test_dominance(a, b).
    """
    def __init__(self, digraph, entryId, exitId=None):
        assert isinstance(digraph, nx.DiGraph)
        super(PreDominatorTree, self).__init__(digraph, entryId=entryId, exitId=exitId)


class PostDominatorTree(AbstractDominatorTree):
    """
    Dominator tree (unique) build from immediate dominators of each node in the
    given flow graph of type fparser.control_flow.ControlFlow.
    Dominance (a dom b) can be tested by calling test_dominance(a, b).
    """
    def __init__(self, digraph, exitId, entryId=None):
        assert isinstance(digraph, nx.DiGraph)
        super(PostDominatorTree, self).__init__(digraph.reverse(), entryId=exitId, exitId=entryId)
