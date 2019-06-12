#include "bincfg/flow/DotFlowExporter.hpp"


DotFlowExporter::DotFlowExporter()
    : m_exportPath       {""},
      m_entryNode        {"entry", EDotNodeShape::CIRCLE},
      m_exitNode         {"exit",  EDotNodeShape::DOUBLECIRCLE},
      m_normalNode       {"BB",    EDotNodeShape::BOX},
      m_funcNode         {"FCall", EDotNodeShape::BOX},
      m_addNewFuncBlocks {false},
      m_dummyCounter     {0},
      m_entryId          {0},
      m_exitId           {0}
{
}


bool
DotFlowExporter::exportFlow(const Flow* flow, const InsnMap* insnMap,
                            const std::string& exportPath)
{
    auto& bBlocks = flow->getBlocks();
    auto funcLocs = flow->getFuncCallLocations();

    Log::log() << "Exporting flow to dot format: " << flow->getFlowName()
               << ELogLevel::LOG_INFO;

    std::ofstream outStream;
    std::string fPath;
    if (exportPath.empty()) {
        fPath = m_exportPath + flow->getFlowName() + ".dot";
    } else {
        fPath = exportPath;
    }

    if (!openFile(outStream, fPath)) {
        Log::log() << "Could not open output file: " << fPath
                   << ELogLevel::LOG_ERROR;
        return false;
    }

    // digraph open
    outStream << "digraph G { \n\n"
              << "label=\"" << flow->getFlowName() << "\";\n"
              << "labelloc=\"top\"\n\n";

    // Write entry block
    writeEntryExitNode(outStream, true);
    writeEdge(m_entryId, flow->getPostEntryBlock(), outStream);

    // Iterate over flow nodes
    for (auto& block : bBlocks)
    {
        exportBlock(flow, block.second.get(), funcLocs, outStream);
    }

    // Write exit block
    writeEntryExitNode(outStream, false);
    for (auto peId : flow->getPreExitBlocks())
    {
        writeEdge(peId, m_exitId, outStream);
    }

    // digraph close
    outStream << "}";

    m_dummyCounter = 0;
    return true;
}

/**
 * @brief Writes a basic block as dot node along with its edges to the given
 *        stream.
 *
 *
 * @note Basic blocks are keyed by the starting address of the first address
 *       range.
 *
 * @todo Write the target symbol for function calls.
 */
void
DotFlowExporter::exportBlock(const Flow* flow, const BasicBlock* block,
                             std::set<uint64_t>& funcLocs, std::ofstream& stream)
{
    // Get address ranges
    auto& addrRanges = block->getAddrRanges();
    assert(addrRanges.size());

    DotBlock dotBlock {addrRanges[0].first, addrRanges};
    writeNormalBlock(EDotBlockType::DEFAULT, dotBlock, stream);

    // Check if block ends with function call
    auto lastPair = addrRanges.back();
    auto fIt = funcLocs.find(lastPair.second);

    auto outEdges = flow->getOutgoingEdges(addrRanges[0].first);
    if (fIt != funcLocs.end() && m_addNewFuncBlocks) {
        // Handle edges
        writeEdge(dotBlock.id, --m_dummyCounter, stream);
        for (auto& edge : outEdges)
        {
            writeEdge(m_dummyCounter, edge.second, stream);
        }

        // Add a new dummy block, actual ID will be read from m_dummyCounter
        dotBlock = DotBlock {0, {{lastPair.second, lastPair.second}}};
        writeNormalBlock(EDotBlockType::FUNC, dotBlock, stream);

        funcLocs.erase(fIt);
    }
    else {
        for (auto& edge : outEdges)
        {
            writeEdge(edge.first, edge.second, stream);
        }
    }
}

/**
 * @note Writes a normal (not entry/exit) dot block.
 *
 */
void
DotFlowExporter::writeNormalBlock(EDotBlockType blockType, const DotBlock& block,
                                  std::ofstream& stream)
{
    DotNodeConf nodeConf = getNodeConf(blockType);

    // m_dummyCounter holds the dummy ID of the function block
    if (blockType == EDotBlockType::FUNC) {
        stream << std::to_string(m_dummyCounter);
    }
    else {
        stream << std::to_string(block.id);
    }

    stream << " [shape=" << getShapeString(nodeConf) << ", margin=0, label=<"
           << "<TABLE border=\"0\" cellborder=\"0\" cellpadding=\"0\">"
           << "<TR><TD colspan=\"2\" border=\"1\" sides=\"b\">"
           << nodeConf.label;

    if (blockType == EDotBlockType::DEFAULT) {
        stream << std::to_string(block.id);
    }
    stream << "</TD></TR> \n";

    // Write address ranges
    for (auto& range : block.addrRanges)
    {
        std::stringstream valStream;
        valStream << range.first << ":" << range.second;

        writeRowAttr("Range", valStream.str(), stream);
    }

    stream << "</TABLE>>]; \n\n";
}


void
DotFlowExporter::writeRowAttr(const std::string& key, const std::string& val,
                              std::ofstream& stream)
{
    stream << "<TR><TD align=\"right\" colspan=\"2\">";

    stream << "<FONT FACE=\"courier\" POINT-SIZE=\"10\" color=\"blue\">"
           << key << ": </FONT>";

    stream << "<FONT FACE=\"courier\" POINT-SIZE=\"12\">"
           << val << "</FONT>";

    stream << "</TD></TR> \n";
}


void
DotFlowExporter::writeEntryExitNode(std::ofstream& stream, bool isEntry)
{
    auto& nodeShapeMap = getNodeShapeMap();
    DotNodeConf nodeConf;
    int nodeId;

    if (isEntry) {
        nodeConf = m_entryNode;
        nodeId = --m_dummyCounter;
        m_entryId = m_dummyCounter;
    }
    else {
        nodeConf = m_exitNode;
        nodeId = --m_dummyCounter;
        m_exitId = m_dummyCounter;
    }

    auto shapeIt = nodeShapeMap.find(nodeConf.shape);
    assert(shapeIt != nodeShapeMap.end());

    stream << nodeId << " [shape=" << shapeIt->second << ", label="
           << nodeConf.label << "] \n\n";
}


const DotNodeConf&
DotFlowExporter::getNodeConf(EDotBlockType blockType)
{
    switch (blockType) {
        case EDotBlockType::FUNC:
            return m_funcNode;
        default:
            return m_normalNode;
    };
}


const std::string&
DotFlowExporter::getShapeString(const DotNodeConf& conf)
{
    auto& nodeShapeMap = getNodeShapeMap();
    auto shapeIt = nodeShapeMap.find(conf.shape);
    assert(shapeIt != nodeShapeMap.end());

    return shapeIt->second;
}


void
DotFlowExporter::setAddFuncBlocks(bool state)
{
    m_addNewFuncBlocks = state;
}


const std::map<EDotNodeShape, std::string>&
DotFlowExporter::getNodeShapeMap() const
{
    static const std::map<EDotNodeShape, std::string> nodeShapeMap {
        {EDotNodeShape::BOX,          "box"},
        {EDotNodeShape::CIRCLE,       "circle"},
        {EDotNodeShape::DOUBLECIRCLE, "doublecircle"}
    };

    return nodeShapeMap;
}
