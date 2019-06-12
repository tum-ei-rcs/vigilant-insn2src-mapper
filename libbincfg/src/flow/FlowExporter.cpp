#include "bincfg/flow/FlowExporter.hpp"

bool
FlowExporter::openFile(std::ofstream& fStream, const std::string& fPath)
{
    bool status = true;

    fStream.open(fPath, std::ofstream:: out | std::ofstream::app);
    if ((fStream.rdstate() & std::ofstream::failbit) != 0)
    {
        fStream.close();
        status = false;
    }
    
    return status;
}