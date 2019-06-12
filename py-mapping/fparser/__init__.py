import logging
import json
import os.path
from collections import namedtuple
import control_flow as cf
import disassembly as da
import dwarf as dw


log = logging.getLogger(__name__)


class Executable(object):
    """
    Loads binary and source control flows, as well as instructions and debug data
    of the executable to be analyzed.

    Params:
      - binaryJsonPath : Json file containing binary flows and instructions.
      - debugJsonPath  : Json file containing dwarf information.
      - sourcecsvPath  : CSV file containing source flows.
      - jsonSplit      : Split string for separate JSON objects.

    FIXME: - Move instruction map from binary json file.
           - Remove symbols_i.
    """

    def __init__(self, binaryJsonPath, debugJsonPath, sourceCsvPath, optimeCsvPath, simplify=False,
                 jsonSplit='\n\n'):

        self.bFlowGraphs = []
        self.sFlowGraphs = []
        self.flowPairs = []
        self.instructions = None
        self.symbols = None
        self.symbols_i = None
        self.dwarfData = None

        self.dwarfData = dw.DwarfData(debugJsonPath) if debugJsonPath is not None else None
        self._load_binary_flows(binaryJsonPath, jsonSplit, optimeCsvPath, simplify)
        self._load_source_flows(sourceCsvPath, simplify)
        self._map_flow_pairs()

    def get_flow_pairs(self):
        """ Returns a flow pair (bin, src) """
        for pair in self.flowPairs:
            yield self.bFlowGraphs[pair.binIdx], self.sFlowGraphs[pair.srcIdx]

    def _map_flow_pairs(self):
        File = namedtuple('File', 'bSubs sSubs')
        files = {}

        for i, bf in enumerate(self.bFlowGraphs):
            fbase = os.path.basename(bf.file)
            f = files.get(fbase, None)
            if f is None:
                files[fbase] = File({bf.name: i}, {})
            else:
                f.bSubs[bf.name] = i
    
        for i, sf in enumerate(self.sFlowGraphs):
            f = files.get(sf.file)
            if f is None:
                files[sf.file] = File({}, {sf.name: i})
            else:
                f.sSubs[sf.name] = i

        Pair = namedtuple('Pair', 'binIdx srcIdx')
        for _, f in files.iteritems():
            cmn = set(f.bSubs.keys()).intersection(f.sSubs.keys())
            self.flowPairs += [Pair(f.bSubs[name], f.sSubs[name]) for name in cmn]

            if len(cmn) != len(f.bSubs):
                log.error("Could not find all flow pairs in file: {}".format(_))

    def _load_binary_flows(self, bjPath, jSplit, optimeCsv, simplify):
        # Load binary graphs and instructions
        jFlowObjs = []
        for jObj in load_json_objs(bjPath, jSplit):
            # Load flows
            if 'Type' in jObj.keys() and jObj['Type'] == 'Flow':
                jFlowObjs.append(jObj)
            # Load instruction map
            elif 'Type' in jObj.keys() and jObj['Type'] == 'InsnMap':
                assert {'Instructions', 'Section'} < set(jObj.keys()), \
                    "Invalid instruction map in json file."
                assert jObj['Section'] == '.text'

                self.instructions = da.Instructions(jObj['Instructions'])
            elif 'Type' in jObj.keys() and jObj['Type'] == 'SymbolMap':
                assert {'Symbols', 'Section'} < set(jObj.keys()), \
                    "Invalid symbol map in json file."
                assert jObj['Section'] == '.text'

                sym = da.Symbols(jObj['Symbols'])
                self.symbols = sym.symbols
                self.symbols_i = sym.symbols_i
            else:
                continue

        assert self.instructions is not None
        assert self.symbols is not None
        assert len(jFlowObjs) > 0, "Could not find binary flows."

        # Only add flows that have debug info
        dwSubs = self.dwarfData.get_subprograms()  # FIXME: add ALL, incl lib functions

        for jObj in jFlowObjs:
            assert 'Name' in jObj.keys(), "Invalid flow object."
            assert jObj['Name'] != '', "Invalid flow name."

            # Binary flow name corresponds to a symbol, or symbol+offset. Skip
            # the latter case for the moment.
            if jObj['Name'] not in self.symbols_i:
                log.warning("Skipping binary flow graph (symb+offset): {}".format(jObj['Name']))
                continue

            entryAddr = self.symbols_i[jObj['Name']]
            if entryAddr not in dwSubs.keys():
                log.warning("Skipping binary flow graph (no debug info): {}".format(jObj['Name']))
                continue
            
            log.info("Parsing binary flow graph: {}".format(jObj['Name']))
            dieOffset = dwSubs[entryAddr]['dieOffset']
            self.bFlowGraphs.append(cf.BinaryControlFlow(jObj, self.dwarfData,
                                                         self.instructions, self.symbols,
                                                         dieOffset, optimeCsv, simplify=simplify))

    def _load_source_flows(self, csvPath, simplify):
        log.info("Parsing source flow graphs")
        self.sFlowGraphs = [cf.SourceControlFlow(co, simplify=simplify)
                            for co in load_csv_objs(csvPath, '\n\n') if co != '']


#################
# Helper methods
#################

def load_json_objs(jsonPath, jsonSplit):
    jsonObjs = []
    with open(jsonPath, 'r') as fpJson:
        jsonLines = fpJson.read().split(jsonSplit)
        for jsonLine in jsonLines:
            if jsonLine == '':
                continue

            try:
                jsonObjs.append(json.loads(jsonLine))
            except ValueError:
                log.error("Encountered an invalid json object.")
                continue
        
    return jsonObjs


def load_csv_objs(csvPath, objSplit):
    with open(csvPath, 'r') as fpCsv:
        csvObjs = fpCsv.read().split(objSplit)
    # --
    return csvObjs
