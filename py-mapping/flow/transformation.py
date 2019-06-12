import logging
import transformer
from abc import ABCMeta, abstractmethod


log = logging.getLogger(__name__)


class Transformation(object):
    __metaclass__ = ABCMeta
    """Stores info about any sort of change that has been made do a graph"""

    @abstractmethod
    def undo_transformation(self, tfg, region_id):
        """Reverses transformation in the given tfg."""


class ReducedLoopTransf(Transformation):
    def __init__(self, head_node, exit_edges, level, parentloop):
        self._body_ee = exit_edges
        self._head_node = head_node
        self.parentloop = parentloop
        self.level = level

    def get_header_node(self):
        return self._head_node

    def undo_transformation(self, tfg, region_id):
        assert isinstance(tfg, transformer.TransformedFlowGraph)
        raise NotImplementedError


class MergeNodesTransf(Transformation):
    def __init(self):
        pass

    def undo_transformation(self, tfg, region_id):
            assert isinstance(tfg, transformer.TransformedFlowGraph)
            raise NotImplementedError
