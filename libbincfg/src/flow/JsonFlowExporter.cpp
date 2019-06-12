#include "bincfg/flow/JsonFlowExporter.hpp"
#include "nlohmann/json.hpp"

using json = nlohmann::json;


JsonFlowExporter::JsonFlowExporter()
{
}


JsonFlowExporter::~JsonFlowExporter()
{
}


bool
JsonFlowExporter::exportFlow(const Flow* flow, const InsnMap* insnMap,
                             const std::string& exportPath)
{
    auto& bBlocks = flow->getBlocks();
    auto funcLocs = flow->getFuncCallLocations();


    std::ofstream outStream;
    std::string fPath;
    if (exportPath.empty()) {
        fPath = flow->getFlowName() + ".json";
    } else {
        fPath = exportPath;
    }

    if (!openFile(outStream, fPath)) {
        Log::log() << "Could not open output file: " << fPath
                   << ELogLevel::LOG_ERROR;
        return false;
    }

    json outJson;

    outJson["Type"] = "Flow";
    outJson["Name"] = flow->getFlowName();

    outJson["BasicBlocks"] = json::array();
    auto&& jsonEdges = json::array();

    // Add entry and exit nodes
    int dummyCounter = 0;
    outJson["BasicBlocks"].push_back({
        {"ID", --dummyCounter},
        {"BlockType", "Entry"}
    });
    jsonEdges.push_back({dummyCounter, flow->getPostEntryBlock()});

    outJson["BasicBlocks"].push_back({
        {"ID", --dummyCounter},
        {"BlockType", "Exit"}
    });
    for (auto peId : flow->getPreExitBlocks())
    {
        jsonEdges.push_back({peId, dummyCounter});
    }

    for (auto& block : bBlocks)
    {
        auto& blockRanges = block.second->getAddrRanges();
        assert(blockRanges.size() && "Block with no address range.");

        // Add block address ranges
        auto&& jsonRanges = json::array();
        for (auto& range : blockRanges)
        {
            jsonRanges.push_back({range.first, range.second});
        }

        outJson["BasicBlocks"].push_back({
            {"ID", blockRanges[0].first},
            {"AddrRanges", jsonRanges},
            {"BlockType", "Normal"}
        });

        // Get block edges
        auto outEdges = flow->getOutgoingEdges(blockRanges[0].first);

        // We insert one extra block for callees
        // FIXME: goa via block type instead of comparing addresses (too low-level for exporter)
        auto fIt = funcLocs.find(blockRanges.back().second);
        if (fIt != funcLocs.end()) {

            assert(block.second->getType() == EBBlockType::CALL && "inconsistency");

            // New edge from current block to a new dummy block
            jsonEdges.push_back({blockRanges[0].first, --dummyCounter});

            for (auto& edge : outEdges)
            {
                jsonEdges.push_back({dummyCounter, edge.second});
            }

            const std::vector <std::string> callees = block.second->getCallees();
            json j_vec(callees);

            // Add the function block
            outJson["BasicBlocks"].push_back({
                {"ID", dummyCounter},
                {"AddrRanges", {*fIt, *fIt}},
                {"BlockType", "FunctionCall"},
                {"calls", j_vec}
            });

            funcLocs.erase(fIt);
        }
        else {
            for (auto& edge : outEdges)
            {
                jsonEdges.push_back({edge.first, edge.second});
            }
        }
    }

    assert(funcLocs.size() == 0 && "Not all function calls were processed.");

    // Edges
    outJson["Edges"] = jsonEdges;

    // Dump the json object to the output stream. Output can be indented
    // to make it more readable.
    outStream << outJson.dump() << std::endl << std::endl;
    return true;
}

/**
 * @brief: Exports debug data of an executable to JSON format. Output contains
 *         a map of debug line info entries as well as an auxiliary map for
 *         mapping vma to their according line info entry.
 *
 *
 * @todo: Add compilation units to output as well as source files.
 *
 * @todo: Speed up the line info look up by 'caching' the last line info entry.
 *        Check if next instruction is in the 'local' line info range (high, low).
 *
 * @todo: Move this to DwarfData.
 */
static void
exportDie(json& outJson, const DwarfDie& die, const std::set<Dwarf_Half>& validTags)
{
    if (validTags.count(die.getTagValue())) {
        // Export attributes
        auto attrs = json::object();
        for (auto& attrPtr: die.getAttributes())
        {
            attrs[Dwarf::getAttrType(attrPtr->getType())] = attrPtr->getValueAsString();
        }
        // Write json object
        outJson["Data"]["DIEs"].push_back(json::object({
            {"Offset",       die.getOffset()},
            {"ParentOffset", die.getParentOffset()},
            {"Tag",          Dwarf::getTagType(die.getTagValue())},
            {"IsValid",      die.isValid()},
            {"Attributes",   std::move(attrs)}
        }));
        // Recursive traversal
        for (auto& child: die.getChildren())
        {
            exportDie(outJson, child, validTags);
        }
    }
}

bool
JsonFlowExporter::exportDebugData(const DwarfData* debugData,
                                  const InsnMap* insnMap,
                                  const std::string& exportPath)
{
    std::ofstream outStream;
    std::string fPath;

    if (exportPath == "") {
        fPath = "dbg.json";
    }
    else {
        fPath = exportPath;
    }

    if (!openFile(outStream, fPath)) {
        Log::log() << "Could not open output file: " << fPath
                   << ELogLevel::LOG_ERROR;
        return false;
    }

    json outJson;

    outJson["Type"] = "DebugInfo";
    outJson["Data"] = {
        {"LineInfoEntries", json::object()},
        {"CompilationUnits", json::array()},
        {"DIEs", json::array()},
        {"LineInfoMap", json::object()}
    };
    outJson["Description"] = "LineInfoMap maps instructions with valid"
        "debug line info to a line info entry in LineInfoEntries.";

    // - Export DIE tree, include only specific DIE_TAG's
    //     * DW_TAG_compile_unit
    //     * DW_TAG_subprogram
    //     * DW_TAG_inlined_subroutine
    //     * DW_TAG_variable
    //
    // - Export all valid attributes
    //
    // - FORMAT: "Data":"Dies": array of DIEs
    auto& cuDieMap = debugData->getCuDieMap();
    static const std::set<Dwarf_Half> s_validTags {
        DW_TAG_subprogram,
        DW_TAG_inlined_subroutine,
        DW_TAG_variable,
        DW_TAG_compile_unit,
        DW_TAG_base_type,
        DW_TAG_lexical_block
    };

    for (CuDieMap::const_iterator cuDieIt = cuDieMap.begin();
         cuDieIt != cuDieMap.end();
         ++cuDieIt)
    {
        exportDie(outJson, cuDieIt->second, s_validTags);
    }


    // Iterate over all CU's that have dwarf line information
    auto& dwlMaps = debugData->getDwarfLines();
    for (auto dwlMapIt = dwlMaps.begin(); dwlMapIt != dwlMaps.end(); ++dwlMapIt)
    {
        auto& dwlMap = dwlMapIt->second;
        for (auto it = dwlMap.begin(); it != dwlMap.end(); ++it)
        {
            outJson["Data"]["LineInfoEntries"][std::to_string(it->first)] = {
                {"CU", dwlMapIt->first},
                {"LowPc", it->second.d_lineAddress},
                {"HighPc", it->second.d_highPc},
                {"LineNumber", it->second.d_lineNumber},
                {"LineOffset", it->second.d_lineOffset},
                {"Discriminator", it->second.d_discriminator}
            };
        }
    }

    // Iterate over all instructions, add to json output if instruction
    // has valid debug line information.
    for (auto insnIt = insnMap->begin(); insnIt != insnMap->end(); ++insnIt)
    {
        // 1. Check if debug data contains info for the current vma
        bool status = false;
        DwarfLineInfo dwlInfo = debugData->getLineInfo(insnIt->first, status);
        if (!status) continue;

        outJson["Data"]["LineInfoMap"][std::to_string(insnIt->first)] =
            std::to_string(dwlInfo.lowPc);
    }

    outStream << outJson.dump(2) << std::endl << std::endl;
    return true;
}


bool
JsonFlowExporter::exportSymbMap(const SymbMap* symbMap, const std::string& section,
                                const std::string& exportPath)
{
    std::ofstream outStream;
    std::string fPath = exportPath;

    if (!openFile(outStream, fPath)) {
        Log::log() << "Could not open output file: " << fPath
                   << ELogLevel::LOG_ERROR;
        return false;
    }

    json outJson;
    outJson["Type"] = "SymbolMap";
    outJson["Section"] = section;
    outJson["Symbols"] = json::array();

    for (auto sIt = symbMap->begin(); sIt != symbMap->end(); ++sIt)
    {
        outJson["Symbols"].push_back({
            {"Addr",sIt->first},
            {"Symbol", sIt->second}
        });
    }

    outStream << outJson.dump(2) << std::endl << std::endl;
    return true;
}

bool
JsonFlowExporter::exportInsnMap(const InsnMap* insnMap, FlowGenerator* fGenerator,
                                const std::string& section, const std::string& exportPath)
{
    std::ofstream outStream;
    std::string fPath = exportPath;

    if (!openFile(outStream, fPath)) {
        Log::log() << "Could not open output file: " << fPath
                   << ELogLevel::LOG_ERROR;
        return false;
    }

    json outJson;
    outJson["Type"] = "InsnMap";
    outJson["Section"] = section;
    outJson["Instructions"] = json::array();

    for (auto iIt = insnMap->begin(); iIt != insnMap->end(); ++iIt)
    {
        std::unique_ptr<Instruction> insn = fGenerator->getInstruction(iIt->second);
        outJson["Instructions"].push_back({
            {"Addr", iIt->first},
            {"Mnem", insn->getMnemonic()},
            {"Op", insn->getOperands()},
            {"Target", insn->getTargetAddrs(iIt->first)}
        });
    }

    outStream << outJson.dump() << std::endl << std::endl;
    return true;
}
