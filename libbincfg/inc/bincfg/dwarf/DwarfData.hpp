#ifndef DWARFDATA_H
#define DWARFDATA_H

#include <vector>
#include <map>
#include <set>
#include <iostream>
#include <iomanip>
#include <assert.h>
#include "bincfg/Log.hpp"

#include "dwarf.h"
#include "libdwarf.h"

#include "bincfg/dwarf/DwarfDie.hpp"

struct DwarfLine;
struct DwarfLineInfo;
struct DwarfRange;


using DwarfLineMap  = std::map<uint64_t, DwarfLine>;
using DwarfLinesMap = std::map<uint64_t, DwarfLineMap>;
using SourceFileMap = std::map<uint64_t, std::vector<std::string>>;
using AddrRangeMap  = std::map<uint64_t, DwarfRange>;
using CuDieMap      = std::map<uint64_t, DwarfDie>;
using Log = bcfg::Log;


class DwarfData
{
private:
    bool          m_isValid;
    DwarfLinesMap m_dwarfLines;
    SourceFileMap m_sourceFiles;
    AddrRangeMap  m_addrRanges;
    CuDieMap      m_cuDies;

    DwarfLine findDwarfLine(Dwarf_Addr vmAddress, uint64_t cuId, bool& status) const;

public:
    DwarfData();

    void addDwarfLines(const std::vector<DwarfLine>& dwarfLine, uint64_t cuId);
    const DwarfLinesMap& getDwarfLines() const;
    bool addSourceFiles(std::vector<std::string>&& sourceFiles, uint64_t cuId);
    bool addAddrRange(const DwarfRange& dwarfRange);
    bool addCuDie(DwarfDie&& cuDie);
    const CuDieMap& getCuDieMap() const;

    const std::string& getSourceFile(std::size_t index, uint64_t cuId) const;
    DwarfLineInfo getLineInfo(Dwarf_Addr vmAddress, bool& status) const;
    
    void printRangeMap();
    void printDwarfLines();

    bool isValid() const;
    void setValidFlag(bool isValid);
};


void printDwarfLine(DwarfLine dwLine);


struct DwarfLineInfo
{
    uint64_t cuId;
    uint64_t fileIndex;
    uint64_t lineNumber;
    uint64_t lineOffset;
    uint64_t discriminator;
    uint64_t lowPc;
    uint64_t highPc;
};


struct DwarfLine
{
    Dwarf_Bool     d_isStmt        = 0;
    Dwarf_Bool     d_isEndSequence = 0;
    Dwarf_Unsigned d_lineNumber    = 0;
    Dwarf_Unsigned d_lineOffset    = 0;
    Dwarf_Unsigned d_discriminator = 0;
    Dwarf_Addr     d_lineAddress   = 0;
    Dwarf_Addr     d_highPc        = 0;
    Dwarf_Unsigned d_fileIndex     = 0;
    uint64_t       cuId            = 0;
};


struct DwarfRange
{
    Dwarf_Addr     d_start  = 0;
    Dwarf_Unsigned d_length = 0;
    uint64_t       cuId     = 0;
};


#endif /* DWARFDATA_H */