#include "bincfg/flow/CsvFlowExporter.hpp"

CsvFlowExporter::CsvFlowExporter()
    : m_exportPath(""),
      m_csvSeparator(';'),
      m_headerStart('#'),
      m_headerSeparator(','),
      m_hexNumbers(false),
      m_addNewFuncBlocks(false)
{
    setDefaultColumns();
}

/**
 * @brief Exports flow to a csv file
 *
 *
 * @todo Better stream handling (errors), remove the output file in case of
 *       errors, return false.
 * @todo Add option to save flows in a single csv file.
 * @todo Add support for printing numbers in hex.
 * @todo Unified file handling in all derived FlowExporter classes.
 *
 * @return false Export path is invalid.
 */
bool
CsvFlowExporter::exportFlow(const Flow* flow, const InsnMap* insnMap,
                            const std::string& exportPath)
{
    auto& bBlocks = flow->getBlocks();
    auto funcLocs = flow->getFuncCallLocations();

    std::ofstream outStream;
    std::string fPath;
    if (exportPath.empty()) {
        fPath = m_exportPath + flow->getFlowName() + ".csv";
    } else {
        fPath = exportPath;
    }

    Log::log() << "Exporting flow to csv format: " << flow->getFlowName()
               << ", file " << fPath
               << ELogLevel::LOG_INFO;

    if (!openFile(outStream, fPath)) {
        Log::log() << "Could not open output file: " << fPath
                   << ELogLevel::LOG_ERROR;
        return false;
    }

    writeHeader(outStream);

    for (auto& block : bBlocks)
    {
        auto& addrRanges = block.second->getAddrRanges();
        for (auto rangeIt = addrRanges.begin(); rangeIt != addrRanges.end(); rangeIt++)
        {
            auto nextRangeIt = rangeIt;
            nextRangeIt++;

            auto iBeginIt = insnMap->find(rangeIt->first);
            auto iEndIt = insnMap->find(rangeIt->second);

            assert(iBeginIt != insnMap->end() && "Cannot find begin instruction.");
            assert(iEndIt != insnMap->end() && "Cannot find end instruction.");

            // Write csv line for each instruction
            InsnMap::const_iterator insnIt;
            InsnMap::const_iterator nextInsnIt;

            for (insnIt = iBeginIt; insnIt != iEndIt; insnIt++)
            {
                nextInsnIt = insnIt;
                nextInsnIt++;

                writeInstructionLine(CsvInstruction {block.first,
                                                     insnIt->first,
                                                     {nextInsnIt->first}},
                                     outStream);
            }

            // Find target for last instruction in range
            if (nextRangeIt != addrRanges.end()) {
                // Find the first instruction in the following address range
                nextInsnIt = insnMap->find(nextRangeIt->first);
                assert(nextInsnIt != insnMap->end());

                writeInstructionLine(CsvInstruction {block.first,
                                                     insnIt->first,
                                                     {nextInsnIt->first}},
                                     outStream);
            }
            else {
                // Get outgoing edges of the current block
                std::vector<uint64_t> targetAddrs;
                for (auto& eIt : flow->getOutgoingEdges(block.first))
                {
                    targetAddrs.push_back(eIt.second);
                }

                // Check if the last instruction in block is a function call
                auto fIt = funcLocs.find(insnIt->first);
                if (fIt != funcLocs.end() && m_addNewFuncBlocks) {
                    // End current block, target addr = step addr
                    writeInstructionLine(CsvInstruction {block.first,
                                                         insnIt->first,
                                                         {insnIt->first}},
                                         outStream);

                    // New dummy block with a single call instruction
                    writeInstructionLine(CsvInstruction {block.first,
                                                         insnIt->first,
                                                         targetAddrs},
                                         outStream);

                    funcLocs.erase(fIt);
                }
                else {
                    writeInstructionLine(CsvInstruction {block.first,
                                                         insnIt->first,
                                                         targetAddrs},
                                         outStream);
                }
            }
        }
    }

    outStream.close();
    return true;
}


/**
 * @brief Writes a CsvInstruction to the given stream
 *
 *
 * *TODO*: Retrieve line info from DebugData here.
 */
void
CsvFlowExporter::writeInstructionLine(const CsvInstruction& csvInstruction,
                                      std::ofstream& outStream,
                                      bool isFuncBlock)
{
    auto uiListToStr = [](std::vector<uint64_t> list) -> std::string
    {
        std::stringstream sStream;
        for (auto uiIt = list.begin(); uiIt != list.end(); uiIt++)
        {
            sStream << *uiIt;
            auto tIt = uiIt;
            if (++tIt != list.end()) sStream << ", ";
        }
        return sStream.str();
    };

    std::vector<OutColumnPair> stringValues {
        std::make_pair(ECsvColumn::BlockNumber,   std::to_string(csvInstruction.blockNumber)),
        std::make_pair(ECsvColumn::StepAddress,   std::to_string(csvInstruction.stepAddr)),
        std::make_pair(ECsvColumn::TargetAddress, uiListToStr(csvInstruction.targetAddrs))
    };

    writeLine(stringValues, outStream);
}


bool
CsvFlowExporter::writeLine(const std::vector<OutColumnPair>& stringValues,
                           std::ofstream& outStream)
{
    if (!stringValues.size()) {
        return false;
    }

    auto peIt = --stringValues.end();
    for (auto cIt = stringValues.begin(); cIt != peIt; cIt++)
    {
        if (m_outputColumns.count(cIt->first)) {
            outStream << cIt->second << m_csvSeparator << ' ';
        }
    }

    // Write the last one
    if (m_outputColumns.count(peIt->first)) {
        outStream << peIt->second << '\n';
    }

    return true;
}


bool
CsvFlowExporter::isValidColumn(ECsvColumn column)
{
    auto& columnMap = getColumnMap();
    if (columnMap.find(column) == columnMap.end()) {
        return false;
    }

    return true;
}


bool
CsvFlowExporter::setOutputColumn(ECsvColumn column, bool includeColumn)
{
    bool status = true;

    if (!isValidColumn(column)) {
        return false;
    }

    if (includeColumn) {
        m_outputColumns.insert(column);
    }
    else {
        if (!m_outputColumns.erase(column)) {
            status = false;
        }
    }

    return status;
}


bool
CsvFlowExporter::setOutputColumns(const std::vector<ECsvColumn>& columns,
                                  bool includeColumns)
{
    bool status = true;

    for (auto& column : columns)
    {
        if(!setOutputColumn(column, includeColumns)) {
            status = false;
        }
    }

    return status;
}


void
CsvFlowExporter::setDefaultColumns()
{
    bool status = true;

    status = setOutputColumn(ECsvColumn::BlockNumber, true);
    status = setOutputColumn(ECsvColumn::StepAddress, true);
    status = setOutputColumn(ECsvColumn::TargetAddress, true);

    assert(status);
}


void
CsvFlowExporter::setDelimiter(char delimiter)
{
    m_csvSeparator = delimiter;
}


void
CsvFlowExporter::setHeaderStartChar(char start)
{
    m_headerStart = start;
}


void
CsvFlowExporter::setHeaderDelimiter(char delimiter)
{
    m_headerSeparator = delimiter;
}


void
CsvFlowExporter::setHexNumbers(bool state)
{
    m_hexNumbers = state;
}


void
CsvFlowExporter::setAddFuncBlocks(bool state)
{
    m_addNewFuncBlocks = state;
}


void
CsvFlowExporter::setExportPath(const std::string& path)
{
    m_exportPath = path;
}


void
CsvFlowExporter::writeHeader(std::ofstream& outStream)
{
    if (!m_outputColumns.size()) {
        return;
    }

    outStream << m_headerStart << ' ';

    auto& columnMap = getColumnMap();

    auto lastIt = --m_outputColumns.end();
    for (auto ocIt = m_outputColumns.begin(); ocIt != m_outputColumns.end(); ocIt++)
    {
        auto cIt = columnMap.find(*ocIt);
        assert(cIt != columnMap.end());

        outStream << cIt->second;
        if (ocIt != lastIt) {
            outStream << m_headerSeparator << ' ';
        }
        else {
            outStream << '\n';
        }
    }
}


const std::map<ECsvColumn, std::string>&
CsvFlowExporter::getColumnMap() const
{
    static std::map<ECsvColumn, std::string> columnMap {
      {ECsvColumn::File,          "File"},
      {ECsvColumn::BlockNumber,   "Block number"},
      {ECsvColumn::StepAddress,   "Step address"},
      {ECsvColumn::TargetAddress, "Target address"},
      {ECsvColumn::LineNumber,    "Line number"},
      {ECsvColumn::ColumnNumber,  "Column number"}
    };

    return columnMap;
}



