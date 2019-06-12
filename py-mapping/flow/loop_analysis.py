import logging
import copy
import networkx as nx


log = logging.getLogger(__name__)


class DfsTree:
    def __init__(self, graph, checkTree=True, entryID=None):
        """
        Note: If an entryID is not specified, it is assumed that the graph
              contains an attribute labeled as 'entryID'.
        """
        assert isinstance(graph, nx.DiGraph)
        
        # Mark the entry id
        if entryID is None:
            assert 'entryID' in graph.graph.keys()
            self._entryID = int(graph.graph['entryID'])
        else:
            self._entryID = entryID
        assert graph.has_node(self._entryID)
        
        # Initialize the tree
        self._tree = nx.DiGraph()
        self._tree.add_nodes_from(graph.nodes, visited=False, number=None, last=None)

        self._counter = 0
        self._preorderList = []
        self._dfs(self._entryID, graph)
        self._checkTree(checkTree, graph)
        self._sortPreorderList()

    def _sortPreorderList(self):
        self._preorderList.sort(key=lambda tup: tup[0])

    def _checkTree(self, checkTree, graph):
        """
        Raises an AssertionError if the DFS tree is not actually a tree. As
        we add all nodes from the original graph in the tree during initialization,
        this test fails when the tree is not an acyclic connected graph.
        """
        if not checkTree:
            return

        for n in self._tree:
            assert self._tree.nodes[n]['visited']
        
        assert nx.is_tree(self._tree)

    def _dfs(self, node, graph):
        """
        DFS as in Havlak's paper "Nesting of Reducible and Irreducible Loops".
    
        Note: This visits nodes recursively and marks them accordingly. Apart
              from DFS number, the preorder number of the last descendant is
              also recorded as an attribute for each tree node.
        """
        self._tree.nodes[node]['number'] = self._counter
        self._preorderList.append((self._counter, node))
        self._tree.nodes[node]['visited'] = True
        self._counter += 1

        for s in graph.successors(node):
            if not self._tree.nodes[s]['visited']:
                # First add an edge in tree
                self._tree.add_edge(node, s)
                self._dfs(s, graph)
        
        self._tree.nodes[node]['last'] = self._counter - 1

    def getTree(self):
        """
        Returns a copy of the dfs tree as an nx.DiGraph object where each node
        will have the following attributes:
          - number : The preorder number in the DFS tree.
          - last   : The preorder number of the last descendant.

        Additionally, the tree graph will contain a sorted auxiliary dict for
        mapping DFS preorder numbers to actual node ID's.

        Note: Nodes in this tree retain the ID in the original input graph.
        """
        tree = self._tree
        for n in tree.nodes:
            assert tree.nodes[n].pop('visited', None) is not None

        tree.graph.update({'preorderList': [a[1] for a in self._preorderList]})

        return tree

    def isAncestor(self, w, v):
        assert w < len(self._tree) and v < len(self._tree), \
            "Invalid preorder numbers given as arguments."
    
        w_i = self._tree.graph['preorderList'][w]
        return (w <= v) and v <= self._tree.nodes[w_i]['last']


def analyze_loops(graph, entryID=None):
    """
    Implements Havlak's algorithm for analyzing loops.

    Note: - Node type is in ['nonheader', 'reducible', 'irreducible', 'self'].
          - Nodes in DFS tree are keyed by their original index, not DFS preorder
            number.

    TODO: 1. Fix (split) irreducible loop headers (as in Havlak's paper).
    """
    assert isinstance(graph, nx.DiGraph)
    if entryID is not None:
        assert graph.has_node(entryID)
    else:
        assert 'entryID' in graph.graph.keys()
        entryID = graph.graph['entryID']

    dfsTree = DfsTree(graph, entryID=entryID)
    T = dfsTree.getTree()
    nodeSets = {n: {n} for n in xrange(0, len(T.graph['preorderList']))}
    nodeLookup = {n: n for n in xrange(0, len(T.graph['preorderList']))}

    def Union(x, y):
        """
        x and y are DFS preorder numbers (indices for nodeSets)
        """
        nodeSets[y] = nodeSets[y].union(nodeSets[x])
        for n in nodeSets[x]:
            nodeLookup[n] = y

        nodeSets[x] = set()

    def Find(el):
        if el not in nodeLookup.keys():
            return None
        else:
            return nodeLookup[el]

    def _get_node_index(num):
        return T.graph['preorderList'][num]

    def _get_preorder_number(index):
        return T.nodes[index]['number']

    def _build_loop_tree(T):
        """
        Builds the loop nesting tree given an annotated DFS tree. Each node
        in the tree represents a loop header. Furthermore, each node in the
        loop that isn't the header of another (nested) loop is attributed to
        the according loopTree node in node[i]['nonheader'].

        NOTE: 'nonheader' nodes are attributed to the root node in order
              to include all the graph nodes in the tree. The root node itself
              does not represent a loop header.
        
        NOTE: Descendants of the root node represent the header (entry) nodes
              of SCC's in the given graph.
        """
        loopTree = nx.DiGraph()
        # Add an entry node so that we get a tree instead of a loop forest.
        rootId = _get_node_index(0)
        loopTree.graph['rootId'] = rootId

        assert T.nodes[rootId]['header'] is None, \
            "Error in DFS tree, root node's header is not None."
        loopTree.add_node(rootId, nonheader=[], type='root')
        for i in xrange(1, len(T.graph['preorderList'])):
            n_i = _get_node_index(i)
            h_i = _get_node_index(T.nodes[n_i]['header'])
            
            if T.nodes[n_i]['type'] == 'nonheader':
                loopTree.nodes[h_i]['nonheader'].append(n_i)     
            elif T.nodes[n_i]['type'] == 'reducible':
                bp_i = [_get_node_index(n) for n in T.nodes[n_i]['backPreds']]
                loopTree.add_node(n_i, nonheader=[], type='reducible',
                                  backPreds=bp_i)
                loopTree.add_edge(h_i, n_i)
            elif T.nodes[n_i]['type'] == 'self':
                bp_i = [_get_node_index(n) for n in T.nodes[n_i]['backPreds']]
                loopTree.add_node(n_i, nonheader=[], type='self',
                                  backPreds=bp_i)
                loopTree.add_edge(h_i, n_i)
            elif T.nodes[n_i]['type'] == 'irreducible':
                assert False, "Found irreducible loop."
            else:
                assert False, "Unknown node type in DFS tree."
        return loopTree 
    
    entry_i = _get_node_index(0)

    # [A] Find backedges and initialize nodes
    for w in xrange(0, len(T.graph['preorderList'])):
        # w_i is the node in graph corresponding to DFS preorder number w
        w_i = _get_node_index(w)

        T.nodes[w_i].update({
            'nonBackPreds': set(),
            'backPreds': set(),
            'header': 0,
            'type': 'nonheader'
        })

        # p_i is the node index, v its according preorder number in DFS tree
        for p_i in graph.predecessors(w_i):
            v = _get_preorder_number(p_i)

            if dfsTree.isAncestor(w, v):
                T.nodes[w_i]['backPreds'].add(v)
            else:
                T.nodes[w_i]['nonBackPreds'].add(v)

    T.nodes[entry_i]['header'] = None

    # [B]
    for w in reversed(xrange(0, len(T.graph['preorderList']))):
        P = []
        w_i = _get_node_index(w)

        for v in T.nodes[w_i]['backPreds']:
            if v != w:
                b = Find(v)
                P.append(b)
            else:
                T.nodes[w_i]['type'] = 'self'
        
        # Deepcopy P
        worklist = copy.deepcopy(P)
        if len(P) > 0:
            T.nodes[w_i]['type'] = 'reducible'

        while len(worklist) > 0:
            x = worklist.pop()
            x_i = _get_node_index(x)
            for y in T.nodes[x_i]['nonBackPreds']:
                y1 = Find(y)
                if not dfsTree.isAncestor(w, y1):
                    T.nodes[w_i]['type'] = 'irreducible'
                    T.nodes[w_i]['nonBackPreds'].add(y1)
                elif (y1 not in P) and (y1 != w):
                    P.append(y1)
                    worklist.append(y1)
        
        if len(P) > 0:
            for x in P:
                x_i = _get_node_index(x)
                T.nodes[x_i]['header'] = w
                Union(x, w)

    return _build_loop_tree(T)


class LoopInfo:
    def __init__(self, graph, entryID=None):
        self._lTree = analyze_loops(graph, entryID)
        self._rootId = self._lTree.graph['rootId']
        self._lookup = {}
        self._preorder = {}

        self._note_loop_body_nodes()
        self._find_exit_edges(graph)
        self._note_preorder_number()
        
    def get_loop_count(self):
        # Discard root node which is used to connect separate trees in the loop
        # forest.
        return len(self._lTree) - 1

    def get_loop_tree(self):
        return self._lTree

    def get_preorder_number(self, blockId):
        """Returns the dfs preorder number of the tree."""
        assert blockId in self._lTree, "Invalid node id."
        p = self._preorder.get(blockId, None)
        assert p is not None, "Node is missing in preorder dict."
        return p

    def get_sorted_plist(self):
        """Returns sorted list of loop tree nodes (innermost first, postorder)."""
        plist = [(self._preorder[n], n) for n in self._lTree.nodes if n != self._rootId]
        plist = sorted(plist, reverse=True, key=lambda tup: tup[0])
        # Return a sorted list of loop tree node ids.
        return [t[1] for t in plist]

    def is_loop_header(self, blockId):
        """Check if blockId is a loop header."""
        if blockId == self._rootId:
            return False
        return blockId in self._lTree

    def lookup_node(self, blockId):
        """Returns loop header if blockId is part of a loop, None otherwise.
        FIXME: does it return the innermost?
        """
        if self.is_loop_header(blockId):
            return blockId
        else:
            return self._lookup.get(blockId, None)

    def get_back_edges(self, blockId):
        """
        Returns set of tail nodes of back edges. None is returned if blockId 
        not in lTree.
        """
        return self._get_header_attr(blockId, 'backPreds')

    def get_exit_edges(self, blockId):
        """
        Returns set of exit edges. None is returned if blockId not in lTree.
        """
        return self._get_header_attr(blockId, 'exitEdges')

    def get_loop_level(self, blockId):
        """level 0 is outermost"""
        assert self.is_loop_header(blockId)
        lvl = 0
        while True:
            blockId = self.get_parent_node(blockId)
            if not self.is_loop_header(blockId):
                assert blockId == self._rootId
                break
            lvl += 1
        return lvl

    def get_body_nodes(self, blockId):
        """
        Returns a set of loop body nodes. None is returned if blockId not in
        lTree. Only returns direct body nodes. If nested loops inside, their bodies
        are not contained!
        """
        return self._get_header_attr(blockId, 'body')

    def get_nonheader_nodes(self, blockId):
        """
        Returns a set of loop body nodes that aren't header nodes to nested loops.
        """
        return self._get_header_attr(blockId, 'nonheader')

    def get_parent_node(self, blockId):
        """
        Returns the parent node of given block. Returns None if blockId not in
        lTree. Returns -1 if no enclosing one
        """
        if blockId not in self._lTree or blockId == self._rootId:
            return None
        
        pre = list(self._lTree.predecessors(blockId))
        assert len(pre) == 1, "Invalid loop tree."

        return pre[0]

    def get_node_type(self, blockId):
        """Returns the type of loop tree node."""
        return self._get_header_attr(blockId, 'type')

    def _get_header_attr(self, blockId, attr):
        """
        Returns 'attr' from blockId in loop tree if block is valid node,
        None otherwise.

        Note:
            Valid attr values: 'body', 'exitEdges', 'backPreds'
        """
        if blockId == self._rootId:
            return None
        
        block = self._lTree.nodes.get(blockId, None)
        if block is not None:
            return block[attr]
        else:
            return None

    def _find_exit_edges(self, g):
        """
        Processes each node in loop tree, marks a set of exit edges as 'exitEdges'
        attribute.
        """
        for n in self._lTree:
            if n == self._rootId:
                continue
            bn = self.get_body_nodes(n)  # Might be empty for self-loops

            ee = set()
            for b in self._lTree.nodes[n]['nonheader'] + [n]:
                for s in g.successors(b):
                    if s not in bn and s != n:
                        ee.add((b, s))

            self._lTree.nodes[n]['exitEdges'] = ee
            if len(ee) == 0:
                log.warning("Found eternal loop in {}, node={}".format(g.name, n))
            log.debug("Loop entry id {}: Exit edges={}".format(n, ee))

    def _note_loop_body_nodes(self):
        """
        Processes each node in loop tree, marks a set of loop body nodes as
        'body' attribute. This set also includes body nodes that serve as 
        header to nested loops.
        """
        for n in self._lTree:
            if n == self._rootId:
                continue
            lh = self._lTree.nodes[n]
            lh['body'] = set(lh['nonheader'] + list(self._lTree.successors(n)))
            self._lookup[n] = n
            self._lookup.update({b: n for b in lh['body']})

    def _note_preorder_number(self):
        """Visits tree nodes recursively (DFS), marks the preorder number."""
        def visit_node(n, counter):
            counter += 1
            # Mark preorder number in dict
            self._preorder[n] = counter
            for s in self._lTree.successors(n):
                visit_node(s, counter)

        counter = 0
        visit_node(self._rootId, counter)

        assert len(self._preorder.keys()) == len(self._lTree.nodes), \
            "Not all loop nodes were visited."
