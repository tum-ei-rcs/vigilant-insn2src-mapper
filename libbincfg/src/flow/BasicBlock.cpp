#include "bincfg/flow/BasicBlock.hpp"

BasicBlock::BasicBlock(std::size_t id, EBBlockType type)
    : m_ID(id),
      m_type(type)
{
}


BasicBlock::BasicBlock(std::size_t id, uint64_t startAddr, uint64_t endAddr,
                       EBBlockType type) : BasicBlock(id, type)
{
    addAddrRange(startAddr, endAddr);
}


void
BasicBlock::addAddrRange(uint64_t startAddr, uint64_t endAddr)
{
    m_addrRanges.push_back(std::make_pair(startAddr, endAddr));
}

uint64_t
BasicBlock::getEntryAddr(void) const {
    return m_addrRanges[0].first; // FIXME: completely arbitrary. The second range might also be the entry.
}

/**
 * @brief Trims/shortens the range of a block up to the specified location, returns a vector
 *        of address ranges that were cut off (new block @[trimAddr:end))
 *
 *
 * @param trimAddr The address where the trimming starts.
 * @param insnSize Size of the instruction preceding the trim location.
 * @param rangeHint selects the correct address range to trim. If not known, function is slower.
 * @return std::vector<AddrRangePair> Trimmed address ranges.
 */
std::vector<AddrRangePair>
BasicBlock::trimBlock(uint64_t trimAddr, uint64_t insnSize, std::size_t rangeHint)
{
#if 0
    std::vector<AddrRangePair> trimmedAddrRanges;
    const auto startIt = m_addrRanges.begin();

    // Find the address range containing trimAddr
    // FIXME: do not move unrelated ranges from the BB to the trimmedAddrRange. That's unexpected.
    // Erase the remaining address ranges and push them to trimmedAddrRanges
    for (auto it = startIt; it != m_addrRanges.end(); /* in loop */)
    {
        if (trimAddr > it->first && trimAddr <= it->second) {
            trimmedAddrRanges.push_back(std::make_pair(trimAddr, it->second));
            // keep but modify the affected range in the block
            it->second = trimAddr - insnSize;
            ++it;
        } else {
            // remove all other ranges from the block
            trimmedAddrRanges.push_back(*it);
            it = m_addrRanges.erase(it);
        }
    }
#else
    std::vector<AddrRangePair> trimmedAddrRanges;
    auto rangeIt = m_addrRanges.end();
    auto startIt = m_addrRanges.begin();

    if (rangeHint > 0 && rangeHint < m_addrRanges.size() &&
        (trimAddr >= m_addrRanges[rangeHint].first &&
         trimAddr <= m_addrRanges[rangeHint].second))
    {
        std::advance(startIt, rangeHint);
    }

    // Find the address range containing trimAddr
    for (auto it = startIt; it != m_addrRanges.end(); it++)
    {
        // Check if the given trimAddr is the start of an address range
        if (trimAddr == it->first) {
            rangeIt = it;
            break;
        }

        if (trimAddr > it->first && trimAddr <= it->second) {
            trimmedAddrRanges.push_back(std::make_pair(trimAddr, it->second));
            it->second = trimAddr - insnSize;
            rangeIt = ++it;
            break;
        }
    }

    // Erase the remaining address ranges and push them to trimmedAddrRanges
    // FIXME: Don't erase this way in a vector, unnecessary movement of
    //        all elements after iterator.
    while (rangeIt != m_addrRanges.end())
    {
        trimmedAddrRanges.push_back(*rangeIt);
        rangeIt = m_addrRanges.erase(rangeIt);
    }

#endif
    return trimmedAddrRanges;
}


std::size_t
BasicBlock::getID() const
{
    return m_ID;
}


EBBlockType
BasicBlock::getType() const
{
    return m_type;
}


std::string
BasicBlock::getTypeString() const {
    switch (m_type) {
        case EBBlockType::NORMAL:
            return "Normal";
        case EBBlockType::CALL:
            return "Call";
        default:
            return "OTHER";
    }
}


std::size_t
BasicBlock::getAddrRangeCount() const
{
    return m_addrRanges.size();
}


const std::vector<AddrRangePair>&
BasicBlock::getAddrRanges() const
{
    return m_addrRanges;
}

