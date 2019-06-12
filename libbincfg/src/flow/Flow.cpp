#include "bincfg/flow/Flow.hpp"

Flow::Flow(std::string name)
    : m_name(name),
      m_bbCount(0),
      m_postEntryBlock(0)
{
}

// FIXME: Combine lower_bound with key test to save an extra lookup
//        during emplace (emplace_hint)
bool
Flow::isBlockPresent(uint64_t bStartAddr) const
{
    return m_bBlocks.count(bStartAddr);
}

void
Flow::_appendBlock(std::shared_ptr<BasicBlock> bb) {
    const uint64_t startAddr = bb->getEntryAddr();
    assert(m_bBlocks.find(startAddr) == m_bBlocks.end());
    m_bBlocks.emplace(startAddr, bb);
}

bool
Flow::addNewContiguousBlock(uint64_t startAddr, uint64_t endAddr,
                            EBBlockType type)
{
    if (isBlockPresent(startAddr)) {
        return false;
    }

    auto bBlock = std::make_shared<BasicBlock>(m_bbCount++, startAddr, endAddr, type);
    _appendBlock(bBlock);
    return true;
}


bool
Flow::addBlock(const BasicBlock& bBlock)
{
    auto bAddrRanges = bBlock.getAddrRanges();
    if (!bAddrRanges.size() || isBlockPresent(bAddrRanges[0].first))
    {
        return false;
    }

    // Copy address ranges
    auto _bType = bBlock.getType();
    auto _bBlock = std::make_shared<BasicBlock>(m_bbCount++, _bType);
    for (auto& kv: bAddrRanges)
    {
        _bBlock->addAddrRange(kv.first, kv.second);
    }
    _appendBlock(_bBlock);

    return true;
}


bool
Flow::removeBlock(uint64_t bStartAddr, bool updateEntryMarker)
{
    auto bBlock = m_bBlocks.find(bStartAddr);
    if (bBlock == m_bBlocks.end()) {
        return false;
    }

    if (bStartAddr == m_postEntryBlock && updateEntryMarker) {
        assert(m_outEdges.count(m_postEntryBlock) == 1 &&
               "Cannot remove post entry block.");
        markPostEntryBlock(m_outEdges.find(m_postEntryBlock)->second);
    }

    auto peBlock = m_preExitBlocks.find(bStartAddr);
    if (peBlock != m_preExitBlocks.end()) {
        m_preExitBlocks.erase(peBlock);
    }

    // Remove block from blockMap
    m_bBlocks.erase(bBlock);

    //if (peBlock != m_preExitBlocks.end() && !m_outEdges.count(*peBlock)) {
    //    return true;
    //}

    // Remove block edges
    assert(removeEdges(bStartAddr) == true &&
           "Present block in block map has no corresponding edges.");
    return true;
}


bool
Flow::insertBlockAddrRanges(uint64_t bStartAddr,
                            std::vector<AddrRangePair> addrRanges)
{
    auto blockIt = m_bBlocks.find(bStartAddr);
    if (blockIt == m_bBlocks.end()) {
        return false;
    }

    for (auto& range : addrRanges)
    {
        blockIt->second->addAddrRange(range.first, range.second);
    }

    return true;
}


/**
 * @brief determine whether BB contains callsites
 */
bool
Flow::hasCalls(const std::shared_ptr<BasicBlock>& bb) const {
    if (m_funcCallLocations.empty()) return false;

    const auto& addrRanges = bb->getAddrRanges();
    for (auto currRange = addrRanges.rbegin();
             currRange != addrRanges.rend();
             currRange++)
    {
        uint64_t rBegin = currRange->first;
        uint64_t rEnd   = currRange->second;
        auto lbIt = m_funcCallLocations.lower_bound(rBegin);
        auto ubIt = m_funcCallLocations.upper_bound(rEnd);  // rEnd is the original end, not the current one when splitting
        return lbIt != ubIt; // instructions in between => has calls
    }
    return false;
}

/**
 * @brief in case the entry address of a block has changed, we have to update the maps.
 */
void
Flow::_notify_changed_entry(std::shared_ptr<BasicBlock> blockIt, uint64_t old_entry)
{
    const uint64_t new_entry = blockIt->getEntryAddr();
    if (new_entry == old_entry) return;

    Log::log() << "entry address of BB " << blockIt->getID() << "changed. Edges might be broken" 
               << ELogLevel::LOG_WARNING;

    auto it = m_bBlocks.find(old_entry);
    m_bBlocks.erase(it);
    m_bBlocks.emplace(new_entry, blockIt);

}

/**
 * @brief Split a basic block at a given location.
 *
 * FIXME:  A. Not very efficient if a block is split at different locations.
 *            A new function is needed for this case.
 *         B. Move the trimmed address ranges directly into the new block
 *            instead of copying them.
 *         C. Define private methods for handling edges given a block iterator.
 *
 *
 * @param bStartAddr Block starting address.
 * @param splitLoc   Location after which the new block starts.
 * @param newBlock   if not NULL; the shared ptr is filled with pointer to the new block
 *
 * @return true  Split was successful.
 * @return false Split could not be performed, block is left unaltered.
 */
bool
Flow::splitBlock(std::shared_ptr<BasicBlock> blockIt, const SplitLocation& splitLoc,
std::shared_ptr<BasicBlock>* retNewBlock)
{
    // Check if there is a block starting after the given split location
    if (m_bBlocks.find(splitLoc.insnAddr+splitLoc.insnSize) != m_bBlocks.end()) {
        return false;
    }

    uint64_t bStartAddr = blockIt->getEntryAddr();

    // Do not split at the very end of the block.
    auto& lastAddrRange = blockIt->getAddrRanges().back();
    if (splitLoc.insnAddr == lastAddrRange.second) {
        Log::log() << "splitBlock: not trimming at end" << ELogLevel::LOG_DEBUG;
        return false;
    }

    // cut off instructions after insnAddr -> this moves unrelated addr ranges to the trimmedRanges,
    // removing them from the original BB
    auto trimmedRanges = blockIt->
        trimBlock(splitLoc.insnAddr+splitLoc.insnSize, splitLoc.insnSize,
                  splitLoc.addrRangeHint);

    if (!trimmedRanges.size()) {
        Log::log() << "splitBlock: trimmed ranges empty" << ELogLevel::LOG_DEBUG;
        return false;
    }
    //assert(blockIt->getAddrRanges().size() == 1); // see edge handling below

    // first update the maps, since entry address of original BB might have changed
    _notify_changed_entry(blockIt, bStartAddr);

    // Add a new basic block
    auto newBlock = std::make_shared<BasicBlock>(m_bbCount++, blockIt->getType());
    if (retNewBlock) *retNewBlock = newBlock;
    for (auto rIt = trimmedRanges.begin(); rIt != trimmedRanges.end(); rIt++)
    {
        newBlock->addAddrRange(rIt->first, rIt->second);
    }
    _appendBlock(newBlock);

    // Update preexit markers. TODO: we don't know whether this range was the last
    if (m_preExitBlocks.erase(bStartAddr)) {
        this->markPreExitBlock(trimmedRanges[0].first);
    }

    // Handle edges: since the new BB also contains also all unrelated address ranges, the
    // outgoing edges of the original BB now definitely belong to the new BB.
    for (auto& eIt : this->getOutgoingEdges(bStartAddr))
    {
        this->removeEdge(eIt);
        this->addEdge(std::make_pair(trimmedRanges[0].first, eIt.second));
    }
    this->addEdge(std::make_pair(bStartAddr, trimmedRanges[0].first));

    return true;
}

void
Flow::addEdge(EdgeMap::value_type pair)
{
    // Check if given pair already exists
    auto eqRange = m_outEdges.equal_range(pair.first);
    for (auto it = eqRange.first; it != eqRange.second; it++) {
        if (it->second == pair.second) {
            return;
        }
    }

    // Hint from previous eqRange
    m_outEdges.insert(eqRange.second, pair);
    m_inEdges.insert(std::make_pair(pair.second, pair.first));
}


void
Flow::addEdges(const std::vector<EdgeMap::value_type>& edges,
               bool hasIncomingEdgeDirection)
{
    for (auto edgeIt = edges.begin(); edgeIt != edges.end(); edgeIt++)
    {
        if (hasIncomingEdgeDirection) {
            addEdge(std::make_pair(edgeIt->second, edgeIt->first));
        }
        else {
            addEdge(*edgeIt);
        }
    }
}


void
Flow::markPostEntryBlock(uint64_t address)
{
    m_postEntryBlock = address;
    Log::log() << "Post-entry address: " << address
               << ELogLevel::LOG_DEBUG;
}


bool
Flow::isPostEntryBlock(uint64_t bStartAddr) const
{
    if (bStartAddr == m_postEntryBlock) {
        return true;
    }

    return false;
}


void
Flow::markPreExitBlock(uint64_t address)
{
    m_preExitBlocks.insert(address);
}


bool
Flow::isPreExitBlock(uint64_t bStartAddr) const
{
    if (m_preExitBlocks.find(bStartAddr) != m_preExitBlocks.end()) {
        return true;
    }

    return false;
}


void
Flow::markFuncCallLocation(uint64_t address_site, const std::vector<uint64_t>& address_target)
{
    m_funcCallLocations.insert(address_site);
    m_funcCallTargets.insert(std::make_pair(address_site, address_target));
}


bool
Flow::removeEdge(EdgeMap::value_type pair)
{
    auto eqRange = m_outEdges.equal_range(pair.first);
    auto edge = m_outEdges.end();

    for (auto it = eqRange.first; it != eqRange.second; it++) {
        if (it->second == pair.second) {
            edge = it;
        }
    }

    if (edge == m_outEdges.end()) {
        return false;
    }

    m_outEdges.erase(edge);

    // If the given edge is found in outEdges, it is also present in inEdges
    eqRange = m_inEdges.equal_range(pair.second);
    edge = m_inEdges.end();

    for (auto it = eqRange.first; it != eqRange.second; it++) {
        if (it->second == pair.first) {
            edge = it;
        }
    }

    assert(edge != m_inEdges.end() &&
           "The given edge must be present in inEdges map.");

    m_inEdges.erase(edge);

    return true;
}


bool
Flow::removeEdges(uint64_t bStartAddr)
{
    // TODO: Rewrite this and add appropriate checks
    auto outEdges = getOutgoingEdges(bStartAddr);
    for (auto it : outEdges)
    {
        removeEdge(it);
    }

    auto inEdges = getIncomingEdges(bStartAddr);
    for (auto it : inEdges)
    {
        removeEdge(std::make_pair(it.second, it.first));
    }

    return true;
}


std::size_t
Flow::removeEdges(std::vector<EdgeMap::value_type> edges)
{
    std::size_t removedCount = 0;

    for (auto edgeIt = edges.begin(); edgeIt != edges.end(); edgeIt++)
    {
        if (removeEdge(*edgeIt)) {
            removedCount++;
        }
    }

    return removedCount;
}

std::vector<EdgeMap::value_type>
Flow::getOutgoingEdges(uint64_t bStartAddr) const
{
    std::vector<EdgeMap::value_type> outgoingEdges;
    auto eqRange = m_outEdges.equal_range(bStartAddr);
    for (auto edgeIt = eqRange.first; edgeIt != eqRange.second; edgeIt++)
    {
        outgoingEdges.push_back(std::make_pair(edgeIt->first, edgeIt->second));
    }

    return outgoingEdges;
}


std::vector<EdgeMap::value_type>
Flow::getIncomingEdges(uint64_t bStartAddr) const
{
    std::vector<EdgeMap::value_type> incomingEdges;
    auto eqRange = m_inEdges.equal_range(bStartAddr);
    for (auto edgeIt = eqRange.first; edgeIt != eqRange.second; edgeIt++)
    {
        incomingEdges.push_back(std::make_pair(edgeIt->first, edgeIt->second));
    }

    return incomingEdges;
}


const BlockMap&
Flow::getBlocks() const
{
    return m_bBlocks;
}


const std::set<uint64_t>&
Flow::getFuncCallLocations() const
{
    return m_funcCallLocations;
}

const std::map<uint64_t, std::vector<uint64_t> >&
Flow::getFuncCallTargets() const
{
    return m_funcCallTargets;
}

uint64_t
Flow::getPostEntryBlock() const
{
    return m_postEntryBlock;
}

const std::set<uint64_t>&
Flow::getPreExitBlocks() const
{
    return m_preExitBlocks;
}


const std::string&
Flow::getFlowName() const
{
    return m_name;
}


// Only for debugging, to be removed.
void
Flow::printBlocks()
{
    for (auto it = m_bBlocks.begin(); it != m_bBlocks.end(); it++)
    {
        std::cout << "BB " <<  it->second->getID() << " [" << std::hex << it->first << "]: "
                  << std::endl;

        auto addrRanges = it->second->getAddrRanges();
        for (auto range = addrRanges.begin(); range != addrRanges.end(); range++)
        {
            std::cout << "    [" << range->first << "]:[" << range->second << "]"
                      << std::endl;
        }
        std::cout << std::dec;
    }

    std::cout << std::endl;
}


void
Flow::printEdges()
{
    std::cout << "OutEdges:" << std::endl;

    for (auto edge = m_outEdges.begin(); edge != m_outEdges.end(); edge++)
    {
        std::cout << "    Edge " << std::hex << edge->first << " to "
                  << edge->second << "."
                  << std::endl;
    }

    std::cout << "InEdges:" << std::endl;

    for (auto edge = m_inEdges.begin(); edge != m_inEdges.end(); edge++)
    {
        std::cout << "    Edge " << std::hex << edge->first << " to "
                  << edge->second << "."
                  << std::endl;
    }


    std::cout << std::endl << "Post entry block: [" << m_postEntryBlock
              << "]." << std::endl;

    std::cout << "Pre exit blocks: ";
    for (auto pb = m_preExitBlocks.begin(); pb != m_preExitBlocks.end(); pb++)
    {
        std::cout << "[" << *pb  << "] ";
    }
    std::cout << std::endl;
}
