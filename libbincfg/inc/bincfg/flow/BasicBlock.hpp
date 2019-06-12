#ifndef BASICBLOCK_H
#define BASICBLOCK_H

#include <cstddef>
#include <cstdint>
#include <vector>
#include <string>

using AddrRangePair = std::pair<uint64_t, uint64_t>;

enum class EBBlockType : std::size_t {
    NORMAL  = 1,
    OTHER   = 2,
    CALL    = 3
};

class BasicBlock
{
private:
    std::size_t m_ID;
    EBBlockType m_type;
    std::vector<AddrRangePair> m_addrRanges;
    std::vector<std::string> m_callees;  // filled by symbolize()

public:
    BasicBlock(std::size_t id, EBBlockType type);
    BasicBlock(std::size_t id, uint64_t startAddr, uint64_t endAddr,
               EBBlockType type);

    void addAddrRange(uint64_t startAddr, uint64_t endAddr);

    uint64_t getEntryAddr(void) const;

    void setType(const EBBlockType& typ) { m_type = typ; }
    void addCallee(const std::string& callee) { m_callees.push_back(callee); }

    std::vector<AddrRangePair> trimBlock(uint64_t trimAddr, uint64_t insnSize,
                                         std::size_t rangeHint=0);

    std::size_t getID() const;
    EBBlockType getType() const;
    std::string getTypeString() const;
    std::size_t getAddrRangeCount() const;
    std::vector<std::string> getCallees() const { return m_callees; }
    const std::vector<AddrRangePair>& getAddrRanges() const;
};


#endif /* BASICBLOCK_H */
