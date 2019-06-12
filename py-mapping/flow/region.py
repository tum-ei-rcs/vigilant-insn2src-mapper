import networkx
import logging
import transformation as tf


log = logging.getLogger(__name__)


class RegionCollection(object):
    """A set of regions"""

    def __init__(self, initialCounter):
        self._currentCount = initialCounter + 1
        self._regions = dict()
        self._loopRegions = set()
        self._loopRegions_i = dict()
        self._matchedLoopRegions = set()

    def generate_new_region_id(self):
        self._currentCount += 1
        return self._currentCount - 1

    def add_region(self, region):
        assert isinstance(region, Region)

        region_id = region.get_id()
        assert region_id not in self._regions
        self._regions[region_id] = region
        
        transf = region.get_transf()
        if isinstance(transf, tf.ReducedLoopTransf):
            self._loopRegions.add(region_id)
            self._loopRegions_i[transf.get_header_node()] = region_id

    def get_region(self, region_id):
        return self._regions.get(region_id, None)

    def get_loop_region_id(self, original_loop_id):
        """Returns the region id which holds the reduced loop headed by
        original_loop_id (loop head node). Returns None if given original_loop_id
        is not reduced (or it isn't a loop header node). This function must be
        called after all loops have been reduced, i.e. this collection holds
        reduced subgraphs of all loops."""
        assert original_loop_id in self._loopRegions_i, "Invalid loop node id."
        return self._loopRegions_i[original_loop_id]

    def mark_loop_region_as_matched(self, region_id):
        assert region_id in self._loopRegions, \
            "Given region_id does not hold a reduced loop subgraph."
        self._matchedLoopRegions.add(region_id)
    
    def is_loop_region_matched(self, region_id):
        assert region_id in self._loopRegions, \
            "Given region_id does not hold a reduced loop subgraph."
        if region_id in self._matchedLoopRegions:
            return True
        else:
            return False


class Region(object):
    """part of a graph and details about transformation done on it, if any"""

    def __init__(self, ident, graph, transformation):
        assert isinstance(graph, networkx.DiGraph)
        assert isinstance(ident, int)
        if transformation is not None:
            assert isinstance(transformation, tf.Transformation)

        self._id = ident
        self._subGraph = graph  # FIXME: rename to "graph". otherwise confusing
        self._transf = transformation

    def get_id(self):
        return self._id

    def get_graph(self):
        return self._subGraph

    def get_transf(self):
        return self._transf

    def undo_transformation(self, tfg):
        self._transf.undo_transformation(tfg, self._id)
