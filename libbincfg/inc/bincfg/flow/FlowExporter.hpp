#ifndef FLOWEXPORTER_H
#define FLOWEXPORTER_H

#include <assert.h>

#include "bincfg/disasm/ElfDisassemblyReader.hpp"
#include "bincfg/flow/Flow.hpp"
#include "bincfg/Log.hpp"

using Log = bcfg::Log;

class FlowExporter
{
protected:
    virtual bool openFile(std::ofstream& fStream, const std::string& fPath);

public:
    virtual ~FlowExporter() {};
    
    virtual bool exportFlow(const Flow* flow, const InsnMap* insnMap,
                            const std::string& exportPath) = 0;
};

#endif /* FLOWEXPORTER_H */
