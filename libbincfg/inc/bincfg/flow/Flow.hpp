#ifndef FLOW_H
#define FLOW_H

#include <map>
#include <set>
#include <vector>
#include <algorithm>
#include <memory>
#include <iostream>
#include <assert.h>

#include "bincfg/Log.hpp"
#include "bincfg/flow/BasicBlock.hpp"

using Log = bcfg::Log;
using EdgeMap = std::multimap<std::uint64_t, std::uint64_t>;
using BlockMap = std::map<std::uint64_t, std::shared_ptr<BasicBlock>>;

struct SplitLocation;

class Flow
{
private:
    const std::string  m_name;
    std::size_t        m_bbCount;
    EdgeMap            m_inEdges;
    EdgeMap            m_outEdges;
    BlockMap           m_bBlocks;
    uint64_t           m_postEntryBlock;
    std::set<uint64_t> m_preExitBlocks;
    std::set<uint64_t> m_funcCallLocations;

    std::map<uint64_t, std::vector<uint64_t> > m_funcCallTargets;

    bool addBlock(const BasicBlock& bBlock); // deprecated
    void _appendBlock(std::shared_ptr<BasicBlock> bb);
    void _notify_changed_entry(std::shared_ptr<BasicBlock> blockIt, uint64_t old_entry);

public:
    Flow(std::string name="");

    // Markers
    bool isBlockPresent(uint64_t bStartAddr) const;
    bool isPostEntryBlock(uint64_t bStartAddr) const;
    bool isPreExitBlock(uint64_t bStartAddr) const;
    void markPostEntryBlock(uint64_t address);
    void markPreExitBlock(uint64_t address);
    void markFuncCallLocation(uint64_t address_site, const std::vector<uint64_t>& address_target);

    // Block manipulation methods
    bool addNewContiguousBlock(uint64_t startAddr, uint64_t endAddr,
                               EBBlockType type);

    bool removeBlock(uint64_t bStartAddr, bool updateEntryMarker=true);
    bool splitBlock(std::shared_ptr<BasicBlock> blockIt,
                    const SplitLocation& splitLoc,
                    std::shared_ptr<BasicBlock>* newBlock=NULL);
    bool insertBlockAddrRanges(uint64_t bStartAddr,
                               std::vector<AddrRangePair> addrRanges);

    bool hasCalls(const std::shared_ptr<BasicBlock>& bb) const;

    // Edge related methods
    void addEdge(EdgeMap::value_type pair);
    void addEdges(const std::vector<EdgeMap::value_type>& edges,
                  bool hasIncomingEdgeDirection=false);
    bool removeEdge(EdgeMap::value_type pair);
    bool removeEdges(uint64_t bStartAddr);
    std::size_t removeEdges(std::vector<EdgeMap::value_type> edges);
    std::vector<EdgeMap::value_type> getOutgoingEdges(uint64_t bStartAddr) const;
    std::vector<EdgeMap::value_type> getIncomingEdges(uint64_t bStartAddr) const;

    const BlockMap& getBlocks() const;
    const std::set<uint64_t>& getFuncCallLocations() const;
    const std::map<uint64_t, std::vector<uint64_t> >& getFuncCallTargets() const;

    const std::set<uint64_t>& getPreExitBlocks() const;
    const std::string& getFlowName() const;
    uint64_t getPostEntryBlock() const;


    // Only for debugging, to be removed.
    void printBlocks();
    void printEdges();
};


struct SplitLocation
{
    std::uint64_t insnAddr;
    std::size_t insnSize;
    std::size_t addrRangeHint;
};


#endif /* FLOW_H */
