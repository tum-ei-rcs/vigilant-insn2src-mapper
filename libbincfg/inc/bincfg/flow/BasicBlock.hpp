#ifndef BASICBLOCK_H
#define BASICBLOCK_H

#include <cstddef>
#include <cstdint>
#include <vector>

using AddrRangePair = std::pair<uint64_t, uint64_t>;

enum class EBBlockType : std::size_t {
    NORMAL  = 1,
    OTHER   = 2
};

class BasicBlock
{
private:
    std::size_t m_ID;
    EBBlockType m_type;
    std::vector<AddrRangePair> m_addrRanges;

public:
    BasicBlock(std::size_t id, EBBlockType type);
    BasicBlock(std::size_t id, uint64_t startAddr, uint64_t endAddr,
               EBBlockType type);

    void addAddrRange(uint64_t startAddr, uint64_t endAddr);

    std::vector<AddrRangePair> trimBlock(uint64_t trimAddr, uint64_t insnSize,
                                         std::size_t rangeHint=0);

    std::size_t getID() const;
    EBBlockType getType() const;
    std::size_t getAddrRangeCount() const;
    const std::vector<AddrRangePair>& getAddrRanges() const;
};


#endif /* BASICBLOCK_H */
