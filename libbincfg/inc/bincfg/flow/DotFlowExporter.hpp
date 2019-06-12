#ifndef DOTFLOWEXPORTER_H
#define DOTFLOWEXPORTER_H

#include <assert.h>

#include "bincfg/flow/FlowExporter.hpp"
#include "bincfg/flow/Flow.hpp"

enum class EDotNodeShape : std::size_t
{
    BOX          = 0,
    CIRCLE       = 1,
    DOUBLECIRCLE = 2
};


enum class EDotBlockType : std::size_t
{
    DEFAULT = 0,
    FUNC    = 1,
    OTHER   = 2
};


struct DotNodeConf
{
    std::string   label;
    EDotNodeShape shape;
};


struct DotBlock
{
    uint64_t                   id;
    std::vector<AddrRangePair> addrRanges;
};


class DotFlowExporter : public FlowExporter
{
private:
    std::string     m_exportPath;
    DotNodeConf     m_entryNode;
    DotNodeConf     m_exitNode;
    DotNodeConf     m_normalNode;
    DotNodeConf     m_funcNode;
    bool            m_addNewFuncBlocks;
    int             m_dummyCounter;
    int             m_entryId;
    int             m_exitId;
    
    void exportBlock(const Flow* flow,
                     const BasicBlock* block, 
                     std::set<uint64_t>& funcLocs,
                     std::ofstream& stream);
    void writeEntryExitNode(std::ofstream& stream, bool isEntry);
    void writeNormalBlock(EDotBlockType blockType, const DotBlock& block,
                          std::ofstream& stream);

    template<class T, class U>
    void writeEdge(T first, U second, std::ofstream& stream)
    {
        stream << first << " -> " << second << "\n\n";
    }

    void writeRowAttr(const std::string& key, const std::string& val,
                      std::ofstream& stream);

    const std::string& getShapeString(const DotNodeConf& conf);
    const DotNodeConf& getNodeConf(EDotBlockType blockType);

public:
    DotFlowExporter();
    ~DotFlowExporter() {};

    bool exportFlow(const Flow* flow, const InsnMap* insnMap,
                    const std::string& exportPath="");

    void setAddFuncBlocks(bool state);
    const std::map<EDotNodeShape, std::string>& getNodeShapeMap() const;
};

#endif /* DOTFLOWEXPORTER_H */