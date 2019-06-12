#ifndef CSVFLOWEXPORTER_H
#define CSVFLOWEXPORTER_H

#include <fstream>
#include "bincfg/flow/FlowExporter.hpp"


enum class ECsvColumn : std::size_t
{
    File,
    BlockNumber,
    StepAddress,
    TargetAddress,
    LineNumber,
    ColumnNumber
};

using OutColumnPair = std::pair<ECsvColumn, std::string>;

struct CsvInstruction
{
    uint64_t blockNumber;
    uint64_t stepAddr;
    std::vector<uint64_t> targetAddrs;
};

class CsvFlowExporter : public FlowExporter
{
private:
    std::string          m_exportPath;
    char                 m_csvSeparator;
    char                 m_headerStart;
    char                 m_headerSeparator;
    bool                 m_hexNumbers;
    bool                 m_addNewFuncBlocks;
    std::set<ECsvColumn> m_outputColumns;
    
    void writeInstructionLine(const CsvInstruction& csvInstruction,
                              std::ofstream& outStream,
                              bool isFuncBlock=false);
    bool writeLine(const std::vector<OutColumnPair>& stringValues,
                   std::ofstream& outStream);
    void writeHeader(std::ofstream& outStream);
    bool isValidColumn(ECsvColumn column);

public:
    CsvFlowExporter();
    ~CsvFlowExporter() {};

    bool exportFlow(const Flow* flow, const InsnMap* insnMap,
                    const std::string& exportPath="");

    // Options
    bool setOutputColumn(ECsvColumn column, bool includeColumn);
    bool setOutputColumns(const std::vector<ECsvColumn>& columns,
                          bool includeColumns);
    void setDefaultColumns();
    void setDelimiter(char delimiter);
    void setHeaderStartChar(char start);
    void setHeaderDelimiter(char delimiter);
    void setHexNumbers(bool state);
    void setAddFuncBlocks(bool state);
    void setExportPath(const std::string& path);

    const std::map<ECsvColumn, std::string>& getColumnMap() const;
};


#endif /* CSVFLOWEXPORTER_H */
