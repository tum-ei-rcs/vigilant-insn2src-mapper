import logging
import json
import networkx as nx


log = logging.getLogger(__name__)


class FlowGraph:
    """
    A general CFG
    FIXME: why has fparser a separate control_flow class?
    """

    def __init__(self, digraph, isBinary):
        assert isinstance(digraph, nx.DiGraph)
        assert isinstance(isBinary, bool)

        self.digraph = None
        self.type = None
        self.entryID = None
        self.exitID = None
        self.name = ''
        self.nodeAttrs = ['blockType']
        self.blockTypes = ['Entry', 'Exit', 'Normal', 'FunctionCall']

        # Private properties
        self._funcBlocks = []
        self._condensedGraph = None
        self._sccSubgraphs = []
        self._loopInfo = None

        # Initialization
        if isBinary:
            self.type = 'Binary'
        else:
            self.type = 'Source'

        assert 'entryID' in digraph.graph
        assert 'exitID' in digraph.graph
        assert 'name' in digraph.graph

        self.entryID = digraph.graph['entryID']
        self.exitID = digraph.graph['exitID']
        self.name = digraph.graph['name']

        self._set_node_attr_types()
        self._check_block_attributes(digraph)

        self.digraph = digraph

        # Initialize private members
        self._condensedGraph = nx.condensation(self.digraph)
        self._find_scc_subgraphs()

    def __len__(self):
        return len(self.digraph)

    # /////////////////////
    # /  Private methods  /
    # /////////////////////

    def _check_block_attributes(self, digraph):
        for node in digraph.nodes:
            assert set(digraph.nodes[node].keys()).issubset(self.nodeAttrs)

    def _set_node_attr_types(self):
        assert self.type is not None

        if self.type == 'Binary':
            self.nodeAttrs += ['AddrRanges']
        else:

            self.nodeAttrs += []

    def _find_function_blocks(self):
        pass

    """
    Finds all SCC's with more than one component and saves them
    as a list.
    """

    def _find_scc_subgraphs(self):
        assert self._condensedGraph is not None

        for n in self._condensedGraph:
            nodeMembers = set(self._condensedGraph.nodes[n]['members'])
            if len(nodeMembers) < 2:
                continue

            sccEntry = None
            # Find scc entry, a predecessor for the entry node will not
            # be in members set.
            for w in nodeMembers:
                if not nodeMembers.issuperset(self.digraph.predecessors(w)):
                    sccEntry = w
                    break
            assert sccEntry is not None

            sccSubgraph = self.digraph.subgraph(nodeMembers)
            self._sccSubgraphs.append((sccSubgraph, sccEntry))

    def _get_loop_info(self):
        pass

    # ////////////////////
    # /  Public methods  /
    # ////////////////////
    def get_nodes(self, prop=None, subset=None):
        """
        Returns a list of nodes that have a certain property in the 
        given subset.

        NOTE: - If property=None then all nodes are returned.
              - If subset=None then all nodes of the flow graph are searched.
        """
        pass

    """
    Returns a list of tuples (nx.DiGraph, entryID) containing SCC's as subgraphs
    of the flow graph.
    """

    def get_scc_subgraphs(self):
        return self._sccSubgraphs


"""
Function to load a binary flow graph from a json file.

TODO: Parse debug data and return a tuple (flows, debugData).

NOTE: Graph attributes ['entryID', 'exitID', 'name']
NOTE: Block attributes ['blockType']

        where 'blockType' in ['Entry', 'Exit', 'Normal', 'FunctionCall']
"""


def load_json_flows(filePath, objectSplit):
    jsonObjects = []
    flowGraphs = []

    def is_insnmap(jsonObj):
        if 'Type' not in jsonObj:
            return False

        if jsonObj['Type'] != 'InsnMap':
            return False

        if {'Instructions', 'Section'} <= jsonObj.keys():
            assert False, "Invalid instruction map."
        return True

    def jsonobj_to_digraph(jsonObj):
        if not isinstance(jsonObj, dict):
            return None

        if 'Type' not in jsonObj:
            return None

        if jsonObj['Type'] != 'Flow':
            return None

        assert len(jsonObj['BasicBlocks']) > 0, "Flow does not contain basic blocks."
        assert 'Name' in jsonObj, "Missing Name attribute."

        digraph = nx.DiGraph()
        digraph.graph.update({'entryID': None, 'exitID': None, 'name': jsonObj['Name']})

        blockTypes = ['Entry', 'Exit', 'Normal', 'FunctionCall']

        for block in jsonObj['BasicBlocks']:
            digraph.add_node(block['ID'])

            assert block['BlockType'] in blockTypes, "Incorrect(missing) block type."
            digraph.nodes[block['ID']].update({'blockType': block['BlockType']})

            if block['BlockType'] == 'Entry':
                digraph.graph.update({'entryID': block['ID']})
            elif block['BlockType'] == 'Exit':
                digraph.graph.update({'exitID': block['ID']})
            else:
                assert len(block['AddrRanges']) > 0, "Found block with no address ranges."
                digraph.nodes[block['ID']].update({'AddrRanges': block['AddrRanges']})

        assert digraph.graph['entryID'] is not None and digraph.graph['exitID'] is not None, \
            "Given flow does not contain entry/exit block."

        # Add edges
        assert len(jsonObj['Edges']) > 0, "Flow does not contain edges."
        digraph.add_edges_from(jsonObj['Edges'])

        return digraph

    with open(filePath, 'r') as fpJson:
        jsonLines = fpJson.read().split(objectSplit)
        for jsonLine in jsonLines:
            try:
                jsonObjects.append(json.loads(jsonLine))
            except ValueError:
                continue

    insnMap = None
    for obj in jsonObjects:
        digraph = jsonobj_to_digraph(obj)
        if digraph is not None:
            flowGraphs.append(digraph)
            continue

        if is_insnmap(obj):
            insnMap = obj

    return flowGraphs, insnMap


def load_source_flows(filePath, objectSplit, delimiterChar=';',
                      headerStartChar='#', headerDelimiterChar=';'):
    csvObjects = []
    flowGraphs = []

    def csvobj_to_digraph(csvObj):
        if csvObj == '':
            return None

        csvLines = csvObj.split('\n')
        headerColumns = []
        if len(csvLines) > 0:
            headerLine = csvLines[0]
            if len(headerLine) > 0 and headerLine[0] != headerStartChar:
                return None
            headerColumns = [column for column in
                             headerLine[1:].split(headerDelimiterChar)]
        else:
            return None

        digraph = nx.DiGraph()
        digraph.graph.update({'entryID': None, 'exitID': None, 'name': None})

        # Each line in the csv object following the header line represents a
        # basic block. Successors are separated with a comma.
        biIdx = headerColumns.index('BB.index')
        btIdx = headerColumns.index('BB.type')
        spIdx = headerColumns.index('Subprogram')
        scIdx = headerColumns.index('Successors')

        for line in csvLines[1:]:
            if line == '':
                continue

            lineStrIndex = line.find('"')

            lineEntries = line[:lineStrIndex].split(delimiterChar)
            lineEntries[-1] = line[lineStrIndex:]

            assert len(lineEntries) == len(headerColumns)
            if digraph.graph['name'] is None:
                digraph.graph.update({'name': lineEntries[spIdx]})

            blockIdx = int(lineEntries[biIdx])
            digraph.add_node(blockIdx)
            assert lineEntries[btIdx] in ['exit', 'node', 'entry']

            def get_successors(entry):
                return [int(s) for s in entry.split(',')]

            if lineEntries[btIdx] == 'entry':
                digraph.graph.update({'entryID': blockIdx})
                digraph.nodes[blockIdx].update({'blockType': 'Entry'})
                successors = get_successors(lineEntries[scIdx])
                assert len(successors) == 1
                digraph.add_edge(blockIdx, successors[0])

            elif lineEntries[btIdx] == 'exit':
                digraph.graph.update({'exitID': blockIdx})
                digraph.nodes[blockIdx].update({'blockType': 'Exit'})

            else:
                digraph.nodes[blockIdx].update({'blockType': 'Normal'})
                for s in get_successors(lineEntries[scIdx]):
                    digraph.add_edge(blockIdx, s)

        assert digraph.graph['entryID'] is not None
        assert digraph.graph['exitID'] is not None

        return digraph

    if filePath.split('.')[-1] != 'csv':
        return None

    with open(filePath, 'r') as fpCsv:
        csvObjects = fpCsv.read().split(objectSplit)

    for obj in csvObjects:
        digraph = csvobj_to_digraph(obj)
        if digraph is not None:
            flowGraphs.append(digraph)

    return flowGraphs


def load_dwarf_data(filePath):
    """
    Loads dwarf data from the given file.

    Data: * DIEs - Apart from attributes, it also contains DIE offset as well as
                   parent DIE offset in order to build a tree. 
          * LineInfoMap - Instruction address to LineInfoEntry
          * LineInfoEntries - Map of entries containing line info
    """

    def validate_data(data):
        status = False
        while True:
            if {'Type', 'Data'} <= data.keys():
                break
            if data['Type'] != 'DebugInfo':
                break
            if {'DIEs', 'LineInfoEntries', 'LineInfoMap'} <= data['Data'].keys():
                break
            if len(data['Data']['DIEs']) < 1:
                break

            status = True
            break
        return debugData['Data'], status

    debugData = None
    with open(filePath, 'r') as fp:
        debugData = json.load(fp)

    return validate_data(debugData)


def build_die_tree(debugData):
    """
    Children of the root node are Compilation Unit DIE's found in .debug_info
    section. Each node has the the following attributes:
      - tag   : DW_TAG_*
      - attrs : DW_AT_*

    NOTE: Nodes are keyed by DIE offset, the root node having offset 0.
    """

    dieTree = nx.DiGraph()
    dieTree.add_node(0, tag='root')

    for die in debugData['DIEs']:
        assert die['Offset'] != 0, "Invalid DIE."
        # Add node
        dieTree.add_node(die['Offset'], tag=die['Tag'], attrs=die['Attributes'])
        # Add edge to parent
        dieTree.add_edge(die['ParentOffset'], die['Offset'])

    # Check if graph is indeed a tree, raise an error if not.
    assert nx.is_tree(dieTree), "Invalid DIE tree."

    return dieTree
