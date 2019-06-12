#ifndef JSONFLOWEXPORTER_H
#define JSONFLOWEXPORTER_H

#include "bincfg/flow/FlowExporter.hpp"
#include "bincfg/flow/FlowGenerator.hpp"
#include "bincfg/flow/Flow.hpp"
#include "bincfg/dwarf/DwarfData.hpp"

#include <iostream>

class JsonFlowExporter : public FlowExporter
{
private:

public:
    JsonFlowExporter();
    ~JsonFlowExporter();

    bool exportFlow(const Flow* flow, const InsnMap* insnMap,
                    const std::string& exportPath="");
    bool exportDebugData(const DwarfData* debugData,
                         const InsnMap* insnMap,
                         const std::string& exportPath="");
    bool exportInsnMap(const InsnMap* insnMap, FlowGenerator* fGenerator,
                      const std::string& section, const std::string& exportPath="");
    bool exportSymbMap(const SymbMap* symbMap, const std::string& section,
                       const std::string& exportPath="");
};

#endif /* JSONFLOWEXPORTER_H */