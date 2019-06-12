import logging
from collections import defaultdict


log = logging.getLogger(__name__)


class PartialMap(object):
    """
    Describes a partial mathematical mapping from domain A to image B

    These maps do not permit entries that map to None. These are counted as unmapped
    """

    def __init__(self, dict_map, unmapped, name=""):
        self._name = name if name else "PartialMap"
        self._map = {k: v for k, v in dict_map.iteritems() if v is not None}
        self._mapped_nodes = set(self._map.keys())
        self._unmapped_nodes = set(unmapped)
        self.consistency_check()

    def consistency_check(self):
        assert not (self._unmapped_nodes & self._mapped_nodes), "invalid state"
        assert len(self._mapped_nodes) == self.__len__()

    def __str__(self):
        return 'PartialMap {}: {}'.format(self.name(), str(self._map))

    def __len__(self):
        """returns number of mapped"""
        return len(self._map)

    def unmapped(self):
        return self._unmapped_nodes

    def mapped(self):
        assert len(self._mapped_nodes) == self.__len__()
        return self._mapped_nodes

    def get_map(self):
        return self._map

    def __getitem__(self, k):
        return self._map[k]

    def name(self):
        return self._name

    def add(self, other):
        assert isinstance(other, PartialMap)
        assert self.mapped() ^ other.mapped(), "must be disjoint"
        # --
        self._map.update(other._map)
        self._mapped_nodes = set(self._map.keys())
        self._unmapped_nodes = (self.unmapped() | other.unmapped()) - self.mapped()
        self.consistency_check()


class MappingStatistics(object):
    """information about #nodes, #precisely mapped and #graphs of a mapping"""
    def __init__(self, name=""):
        self.data = dict()
        self.name = name

    def merge_in(self, other):
        for k, v in other.data.iteritems():
            if k in self.data:
                self.data[k] += v
            else:
                self.data[k] = v


class ExecCountRange(object):
    """Denotes a range of how often a mapped entry executes"""

    def __init__(self, lo=1, hi=1):
        self.lo = lo
        self.hi = hi

    def __add__(self, other):
        return ExecCountRange(self.lo + other.lo, self.hi + other.hi)

    def __iadd__(self, other):
        self.lo += other.lo
        self.hi += other.hi
        return self


class GraphMap(PartialMap):
    """
    Describes a partial mapping from one graph to another

    Each map can have one or more associated predecessors.
    """

    def __init__(self, gA, gB, dict_map, name="", predecessors=None, dict_exec_count=None,
                 ignore_virtual=False):
        """
        :param gA: graph of domain. If set, automatically computes unmapped nodes.
        :param gB: graph of image
        :param dict_map: mappint gA -> gB
        :param name: name of this map
        :param predecessors: optionally point to maps that were used to build this one
        :param dict_exec_count: by default, each v\in gA is assumed to execute once. Override here.
        :param ignore_virtual: filter out any virtual nodes in dict_map
        """
        self.graph_A = gA  # graph of domain
        self.graph_B = gB  # graph of image
        self._predecessors = set(predecessors) if predecessors is not None else set()
        self.exec_count = defaultdict(ExecCountRange)  # range of execution count for mapped
        if dict_exec_count is not None:
            assert isinstance(dict_exec_count, dict)
            for n, cnt in dict_exec_count.iteritems():
                assert isinstance(cnt, ExecCountRange)
                self.exec_count[n] = cnt

        # clean the map
        if ignore_virtual and gA:
            lastnode = gA.get_original_cflow().get_max_id()
            clean_map = {k: v for k, v in dict_map.iteritems() if v is not None and k <= lastnode}
        else:
            clean_map = {k: v for k, v in dict_map.iteritems() if v is not None}

        # determine unmapped
        if gA:
            lastnode = gA.get_original_cflow().get_max_id()
            allnodes = gA.nodes() if not ignore_virtual else {n for n in gA.nodes()if n <= lastnode}
            unmapped = allnodes - set(clean_map.keys())
        else:
            unmapped = set()

        PartialMap.__init__(self, clean_map, unmapped, name)

    def add(self, other):
        assert isinstance(other, GraphMap)
        # merge counts: only accumulate already present ones (others are by default)
        self_mapped = self.mapped()
        for n, other_count in other.exec_count.iteritems():
            # if we are here, other_count is not default
            self_count = self.exec_count[n] if n in self_mapped else ExecCountRange(0, 0)
            self.exec_count[n] = self_count + other_count
        # merge actual map
        super(GraphMap, self).add(other)

    def copy(self, remove_virtual=False, rename=None):
        """
        Neither shallow nor deep. Makes deep copies of the mapping itself, but keeps
        all underlying graphs
        Optionally omits map entries which are virtual graph nodes
        """
        newname = rename if rename is not None else self.name()
        return GraphMap(gA=self.graph_A, gB=self.graph_B, dict_map=self._map, name=newname,
                        predecessors=self._predecessors, ignore_virtual=remove_virtual)

    def add_predecessor(self, p):
        assert isinstance(p, GraphMap)
        self._predecessors |= p

    def get_predecessors(self):
        return self._predecessors

    def calc_statistics(self):
        """summarize info about mapping"""
        # --
        mapstat = MappingStatistics(self.name())
        n_map = len(self.mapped())
        mapstat.data["mapped"] = n_map
        mapstat.data["total"] = n_map + len(self.unmapped())
        mapstat.data["graphs"] = 1
        return mapstat


class HierarchicalGraphMap(object):
    """Maps one graph to another, but may subdivide the graph into subgraphs"""

    def __init__(self, name, predecessors=None, skip=False):
        self.name = name
        self.skip = skip
        self.children = []  # list of HierarchicalGraphMap
        self.mapping = None  # instance of GraphMap
        self._predecessors = set(predecessors) if predecessors is not None else set()
        self.is_precise = False  # indicates whether overapproximations have been made

    def __str__(self):
        return '{}: {} children'.format(self.name, len(self.children))

    def add_predecessor(self, p):
        assert isinstance(p, HierarchicalGraphMap)
        self._predecessors.add(p)

    def get_predecessors(self):
        return self._predecessors

    def calc_statistics(self):
        """return information about #nodes, #precisely mapped and #graphs"""
        ret = self.mapping.calc_statistics()
        for c in self.children:
            ret.merge_in(c.calc_statistics())
        return ret

    def consistency_check(self):
        for c in self.children:
            c.consistency_check()
        self.mapping.consistency_check()

    def flatten(self):
        """
        Get non-hierarchic ("flattened") representation of hierarchic mapping.
        Replaces all surrogate nodes by their real ones, such that the resulting flat
        map only contains nodes that really exist in both graphs.

        :returns GraphMap (non-hierarchical)
        """
        assert isinstance(self.mapping, GraphMap)
        # --

        def handle_skipped_subflow():
            """
            Some day we might want to do something with it if the surrogate is mapped.
            However, the surrogate is not necessarily mapped.
            """
            if False:
                skip_headnode = c.mapping.graph_A.entryId
                if skip_headnode not in c.mapping.mapped():
                    surro = rcoll.get_loop_region_id(skip_headnode)
                    skipped_map = c.mapping.copy()
                    try:
                        surro_maps_to = self.mapping[surro]
                        raise NotImplementedError  # TODO: add entry to map and correct unmapped
                    except KeyError:
                        # this can indeed happen, if we flatten an incomplete map.
                        log.warning("During flatten of {}: surrogate {} of subgraph{} is "
                                    "unmapped".format(self.name, surro, c.name))
                else:
                    skipped_map = c.mapping
            return c.mapping

        def squash_mapsto_surrogates():
            """replace mappings to src-surrogate nodes with their actual nodes"""
            last_dom = ret.graph_A.get_original_cflow().get_max_id()
            last_img = ret.graph_B.get_original_cflow().get_max_id()
            scoll = ret.graph_B.get_region_collection()
            thismap = ret.get_map()
            for dom in thismap.keys():
                img = thismap[dom]
                assert dom <= last_dom, "bin surrogate nodes should no longer be in the mapping"
                if img > last_img:
                    # find the head node of src subgraph
                    region = scoll.get_region(img)
                    real_node = region.get_transf().get_header_node()
                    # update map
                    thismap[dom] = real_node

        ret = self.mapping.copy(True)  # clean from hierarchy artifacts (surrogate nodes)
        assert isinstance(ret, GraphMap)
        ret.name = self.name
        squash_mapsto_surrogates()
        rcoll = self.mapping.graph_A.get_region_collection()
        for c in self.children:
            if not c.skip:
                childmap = c.flatten()
                ret.add(childmap)
            else:
                ret.add(handle_skipped_subflow())
        return ret

