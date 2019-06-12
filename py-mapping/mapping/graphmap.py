import logging
import copy


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
        return '{}: {}'.format(self.name(), str(self._map))

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


class GraphMap(PartialMap):
    """
    Describes a partial mapping from one graph to another

    Each map can have one or more associated predecessors.
    """

    def __init__(self, gA, gB, dict_map, name="", predecessors=None):
        self.graph_A = gA  # graph of domain
        self.graph_B = gB  # graph of image
        self._predecessors = set(predecessors) if predecessors is not None else set()
        clean_map = {k: v for k, v in dict_map.iteritems() if v is not None}
        unmapped = set(gA.nodes()) - set(clean_map.keys()) if gA is not None else set()
        PartialMap.__init__(self, clean_map, unmapped, name)

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

    def __init__(self, name, predecessors=None):
        self.name = name
        self.children = []  # list of HierarchicalGraphMap
        self.mapping = None  # instance of GraphMap
        self._predecessors = set(predecessors) if predecessors is not None else set()

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
        """:returns GraphMap that holds a non-hierarchic ("flattened") representation"""
        assert isinstance(self.mapping, GraphMap)
        # --
        ret = copy.deepcopy(self.mapping)  # XXX: slow, but needs to be deep
        for c in self.children:
            f = c.flatten()
            ret.add(f)
        return ret

