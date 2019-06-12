#include "bincfg/dwarf/DwarfData.hpp"

/**
 * 
 * @note: We pass a vector of CU DIE's to initialize the map of DwarfLines.
 */
DwarfData::DwarfData()
    : m_isValid(false)
{
}


bool
DwarfData::addSourceFiles(std::vector<std::string>&& sourceFiles, uint64_t cuId)
{
    // Check if given CU die ID exists in map
    auto sfIt = m_sourceFiles.find(cuId);
    if (sfIt != m_sourceFiles.end()) {
        Log::log() << "Attempting to insert source files in SourceFileMap"
                   << " for an already processed CU die."
                   << ELogLevel::LOG_ERROR;
        return false;
    }

    // Will call the appropriate std::pair constructor for moving the vector.
    m_sourceFiles.emplace(cuId, sourceFiles);
    return true;
}

/**
 * @note: When a DwarfLine with d_isEndSequence is encountered, this updates
 *        the d_highPc member of the previous DwarfLine. Further, the DwarfLine
 *        in question need not be saved as a separate DwarfLine, as it does not
 *        encode any new information.
 * 
 * @todo: Add a sanity check at the end to check for overlaps, issue an error,
 *        a DwarfLine returned by libdwarf contains incorrect isEndSequence flag.
 */
void
DwarfData::addDwarfLines(const std::vector<DwarfLine>& dwarfLines, uint64_t cuId)
{
    // Emplace a new empty map into m_dwarfLines
    auto dlIt = m_dwarfLines.lower_bound(cuId);
    if (dlIt != m_dwarfLines.end()) {
        return;
    }
    auto dlMapIt = m_dwarfLines.emplace_hint(dlIt, cuId, DwarfLineMap());
    auto& dlMap = dlMapIt->second;

    // Iterate over all dwarfLines, update d_highPc accordingly.
    auto dwLineIt = dlMap.end();
    auto dwLinePrevIt = dwLineIt;
    bool hasSequenceEnded = true;

    for (auto& dwLine : dwarfLines)
    {
        if (dwLine.d_isEndSequence) {
            // Update d_highPc of the previous dwLine entry in the dlMap
            assert(dlMap.size() && "DwarfLine vector must not begin with 'end-sequence'");
            dwLinePrevIt->second.d_highPc = dwLine.d_lineAddress - 1;
            hasSequenceEnded = true;
            continue;
        }

        dwLineIt = dlMap.insert(dwLineIt,
                                std::make_pair(dwLine.d_lineAddress, dwLine));

        // Update high pc of previous line
        if (hasSequenceEnded) {
            hasSequenceEnded = false;
        }
        else {
            dwLinePrevIt->second.d_highPc = dwLine.d_lineAddress - 1;
        }

        // Set previous line to actual line, increment dwLineIt to serve as hint
        // for the next insertion.
        dwLinePrevIt = dwLineIt;
        ++dwLineIt;
    }

    /*
    auto dwIt = m_dwarfLines.end();
    for (auto& dwLine : dwarfLines)
    {
        dwIt = ++(m_dwarfLines.insert(dwIt,
            std::make_pair(dwLine.d_lineAddress,dwLine)));
    }
    */
}


const DwarfLinesMap&
DwarfData::getDwarfLines() const
{
    return m_dwarfLines;
}


void
DwarfData::printDwarfLines()
{
    for (auto& dlMap: m_dwarfLines)
    {
        std::cout << "\n\nPrinting instructions for CU@0x" << std::hex
                  << dlMap.first
                  << std::endl;

        for (auto& dwLine : dlMap.second)
        {
            printDwarfLine(dwLine.second);
        } 
    }
}


/**
 * @todo: Emplace new elements in map with hint.
 * 
 * @fixme: Address ranges here are added in increasing order most of the time,
 *         map search not optimal. Cache the last lower_bound iterator internally.
 */
bool
DwarfData::addAddrRange(const DwarfRange& dwarfRange)
{
    auto inRange = [](Dwarf_Addr addr, DwarfRange& dwRange) -> bool
    {
        if (addr >= dwRange.d_start &&
            addr <= dwRange.d_start + dwRange.d_length - 1)
        {
            return true;
        }
        return false;
    };

    bool status = false;
    do {
        if (m_addrRanges.empty()) {
            status = true;
            break;
        }
        else {
            // Map is keyed by range start address.
            auto lbIt = m_addrRanges.lower_bound(dwarfRange.d_start);

            if (lbIt == m_addrRanges.end()) {
                // Map has at least one element
                auto prevIt = lbIt; --prevIt;
                if (!inRange(dwarfRange.d_start, prevIt->second)) {
                    status = true;
                }
                break;
            }

            if (lbIt->first == dwarfRange.d_start) {
                break;
            }
            else {
                // Check for overlaps
                if (lbIt == m_addrRanges.begin()) {
                    status = true;
                    break;
                }
                auto prevIt = lbIt; --prevIt;
                if (!inRange(dwarfRange.d_start, prevIt->second)) {
                    status = true;
                }
            }
        }
    } while (false);

    if (status == true) {
        m_addrRanges.emplace(dwarfRange.d_start, dwarfRange);
    } 

    return status;
}


/**
 * @brief: Returns a DwarfLineInfo for the given vmAddress and sets the status
 *         bit if the returned info is valid.
 */

DwarfLineInfo
DwarfData::getLineInfo(Dwarf_Addr vmAddress, bool& status) const
{
    DwarfLineInfo dwLineInfo;
    status = false;
    if (m_addrRanges.empty()) {
        return dwLineInfo;
    }

    // First find the arange this address belongs to, get upper_bound
    auto rangeIt = m_addrRanges.upper_bound(vmAddress);
    if (rangeIt == m_addrRanges.begin()) {
        return dwLineInfo;
    }
    
    // Get the previous range
    --rangeIt;

    DwarfRange currentRange = rangeIt->second;
    // Check if it is in range
    if (vmAddress >= currentRange.d_start &&
        vmAddress <= currentRange.d_start + currentRange.d_length - 1)
    {
        auto dwLine = findDwarfLine(vmAddress, currentRange.cuId, status);
        if (!status) {
            return dwLineInfo;
        }
        else {
            // We have the DwarfLine we want, update dwLineInfo and return.
            dwLineInfo.cuId = dwLine.cuId;
            dwLineInfo.lowPc = dwLine.d_lineAddress;
            dwLineInfo.highPc = dwLine.d_highPc;
            dwLineInfo.lineNumber = dwLine.d_lineNumber;
            dwLineInfo.lineOffset = dwLine.d_lineOffset;
        }
    }

    return dwLineInfo;
}


/**
 * @brief: Returns the DwarfLine entry containing information about the
 *         given vma. d_lineAddress and d_highPc members in a DwarfLine
 *         specify the address range the line information is valid for.
 * 
 * 
 * @note: Address ranges in a dwarf line map are assumed to be non-overlapping.
 * 
 * @fixme: Rewrite this function (incomplete). Remove assertion, a CU may not 
 *         contain debug data in some cases.
 */
DwarfLine
DwarfData::findDwarfLine(Dwarf_Addr vmAddress, uint64_t cuId, bool& status) const
{
    DwarfLine dwLine;
    bool _status = false;

    do {
        if (m_dwarfLines.empty()) {
            break;
        }

        // Get dwarfLines for the given cuId
        auto dwlMapIt = m_dwarfLines.find(cuId);
        if (dwlMapIt == m_dwarfLines.end()) {
            break;
        }
        auto& dwlMap = dwlMapIt->second; 
        assert(dwlMap.size() != 0);

        // Get upper bound (map is not empty)
        auto dwlIt = dwlMap.upper_bound(vmAddress);
        if (dwlIt == dwlMap.begin()) {
            break;
        }
        else {
            --dwlIt;
        }

        // Check if in range
        if (vmAddress >= dwlIt->second.d_lineAddress &&
            vmAddress <= dwlIt->second.d_highPc)
        {
            _status = true;
            dwLine = dwlIt->second;
        }
    } while (false);

    status = _status;
    return dwLine;
}


void
DwarfData::printRangeMap()
{
    std::cout << "Printing address ranges." << std::endl;

    for (auto& range: m_addrRanges)
    {
        std::cout << "[" << std::hex << range.first << "]  Range: "
                  << "0x" << range.second.d_start << "  -  "
                  << "0x" << range.second.d_start + range.second.d_length - 1
                  << " CU[0x" << range.second.cuId << "]"
                  << std::endl;
    }
}


bool
DwarfData::isValid() const
{
    return m_isValid;
}


void
DwarfData::setValidFlag(bool isValid)
{
    m_isValid = isValid;
}


void printDwarfLine(DwarfLine dwLine)
{
    std::ios::fmtflags oldFlags(std::cout.flags());
    std::cout << "dwLine @[0x" << std::hex << dwLine.d_lineAddress;

    std::cout << "], CU @[0x" << dwLine.cuId << "], HighPc @[0x"
              << dwLine.d_highPc;
    std::cout.flags(oldFlags);

    std::cout << "], BT: " << dwLine.d_isStmt
              << ", ESeq: " << dwLine.d_isEndSequence
              << ", LNum: " << dwLine.d_lineNumber
              << ", LOff: " << dwLine.d_lineOffset
              << ", Disc: " << dwLine.d_discriminator
              << std::endl;
}



bool
DwarfData::addCuDie(DwarfDie&& cuDie)
{
    auto cuIt = m_cuDies.find(cuDie.getOffset());
    if (cuIt != m_cuDies.end()) {
        Log::log() << "CU Die @0x" << std::hex << cuDie.getOffset()
                   << " already present in map."
                   << ELogLevel::LOG_ERROR;
        return false;
    }

    m_cuDies.insert(cuIt, std::make_pair(cuDie.getOffset(), std::move(cuDie)));
    return true;
}


const CuDieMap&
DwarfData::getCuDieMap() const
{
    return m_cuDies;
}
