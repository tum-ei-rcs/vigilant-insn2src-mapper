#include "bincfg/flow/FlowGenerator.hpp"


std::unique_ptr<FuncMap>
FlowGenerator::findFunctions(const DisasmSection* section)
{
    FuncMap* funcMap = new FuncMap();

    auto insnMap = section->getInstructions();
    auto symbMap = section->getSymbols();

    for (auto currInsn = insnMap->begin();
         currInsn != insnMap->end();
         currInsn++)
    {
        uint64_t targetAddr;

        if (isFuncCallInstruction(currInsn->second, currInsn->first, targetAddr)) {
            // FIXME: Handle the case when the target address is not in this
            //        section.
            auto sIt = symbMap->find(targetAddr);
            if (sIt != symbMap->end()) {
                // Add to funcMap if new function
                if (!funcMap->count(sIt->first)) {
                    funcMap->insert(std::make_pair(sIt->first, sIt->second));
                }
            }
            else {
                // Create new symbol for this function, get symbol context
                std::string funcName;
                uint64_t relDiff;

                // Get symbol context
                auto symbContextIt = section->getSymbolContext(targetAddr);
                relDiff = targetAddr - symbContextIt->first;

                std::stringstream tmpStream;
                tmpStream << symbContextIt->second << std::hex
                          << "+0x" << relDiff;

                funcName = tmpStream.str();
                funcMap->insert(std::make_pair(targetAddr, funcName));
            }
        }
    }

    return std::unique_ptr<FuncMap>(funcMap);
}

/**
 * @brief Generate flows for functions found in the given disassembled section.
 *
 *
 * @param section Contains functions to generate flows for.
 *
 * @return std::unique_ptr<FlowMap> Map containing flow objects keyed by
 *                                  function entry address.
 */
std::unique_ptr<FlowMap>
FlowGenerator::generateFlows(const DisasmSection* section)
{
    FlowMap* flowMap = new FlowMap();
    auto funcMap = this->findFunctions(section);

    for (auto& currFunc : *funcMap)
    {
        Log::log() << "Creating flow for function: " << currFunc.second
                   << " @[0x" << std::hex << currFunc.first << "]"
                   << ELogLevel::LOG_INFO;

        flowMap->emplace(currFunc.first, std::move(createFuncFlow(section, currFunc)));
    }

    return std::unique_ptr<FlowMap>(flowMap);
}

/**
 * @brief Create a flow object given a function entry address.
 *
 *
 * @param section  The disassembled section that contains the function.
 * @param funcPair Pair that contains the address and name of the function.
 *
 * @return shared_ptr<Flow> The flow object for the given function.
 */
std::unique_ptr<Flow>
FlowGenerator::createFuncFlow(const DisasmSection* section,
                              const FuncMap::value_type& funcPair)
{
    Flow* flow = new Flow(funcPair.second);
    auto insnMap = section->getInstructions();
    auto symbMap = section->getSymbols();

    // First block starts at function entry, initialize the worklist
    std::map<uint64_t, uint64_t> blockRefCount;
    std::queue<uint64_t> candidateQueue;

    candidateQueue.push(funcPair.first);
    flow->markPostEntryBlock(funcPair.first);

    while (candidateQueue.size()) {
        uint64_t startAddr;

        auto currInsn = insnMap->find(candidateQueue.front());
        candidateQueue.pop();

        // Check if the block currently being processed exists
        auto it = blockRefCount.find(currInsn->first);
        if (it != blockRefCount.end()) {
            it->second++;
            continue;
        }
        else {
            blockRefCount.insert(std::make_pair(currInsn->first, 1));
            startAddr = currInsn->first;
        }

        // Process instructions, update worklist and flow
        while (currInsn != insnMap->end()) {
            if (updateWorklist(*currInsn, insnMap.get(), candidateQueue, flow, startAddr)) {
                break;
            }
            else {
                currInsn++;
            }
        }
    }

    fixOverlaps(insnMap.get(), flow);
    mergeJumpBlocks(insnMap.get(), flow);
    manageFuncCallBlocks(insnMap.get(), flow);
    symbolize(symbMap.get(), flow);

    return std::unique_ptr<Flow>(flow);
}




/**
 * @brief Determines if the given instruction is a function call.
 *
 * *Note*: Calls targeting a location immediately after the function call will
 *         not be processed.
 *
 *
 * @param disasmInsn  Disassembled instruction to test for function calls.
 * @param insnAddr    The address of the given instruction. It is needed for
 *                    relative calls.
 * @param targetAddr  Reference to the output target address of the function
 *                    call.
 * @param suppressLog Suppresses logging if true.
 *
 * @return true  Given instruction is a call instruction, targetAddr is valid.
 * @return false Not a call instruction, targetAddr is left unaltered.
 */
bool
FlowGenerator::isFuncCallInstruction(const DisasmInstruction& disasmInsn,
                                     uint64_t insnAddr,
                                     uint64_t& targetAddr,
                                     bool suppressLog)
{
    auto insn = this->getInstruction(disasmInsn);

    if (insn->isCallInsn()) {
        std::vector<uint64_t> targetAddrs = insn->getTargetAddrs(insnAddr);

        const bool regular_call = targetAddrs.size() == 1;
        if (!m_ignore_errors) {
            assert(regular_call && "unsupported call");
        } else {
            return false;
        }

        auto insnSize = insn->getInstructionSize();

        if (targetAddrs[0] == insnAddr + insnSize) {
            Log::log() << "Call instruction @0x" << std::hex << insnAddr
                       << " does not lead to a function call."
                       << ELogLevel::LOG_DEBUG;

            return false;
        }

        targetAddr = targetAddrs[0];

        return true;
    }

    return false;
}

/**
 * @brief Populate the given flow with basic blocks as well as update the given
 * worklist with basic block candidates.
 *
 *
 * @param currInsn       The current instruction to be checked for branches and
 *                       skips.
 * @param insnMap        Contains the disassembled instructions
 *                       (DisasmInstruction).
 * @param candidateQueue Reference to the worklist to be updated.
 * @param flow           The flow object where edges and blocks are added.
 * @param startAddr      The start address of the block currently being
 *                       processed.

 * @return true  No further instructions must be processed for the current
 *               work item. A new block is added to the flow along with its
 *               outgoing edges.
 * @return false The given instruction does not cause an alternation in flow.
 */
bool
FlowGenerator::updateWorklist(const InsnMap::value_type& currInsn,
                              const InsnMap* insnMap,
                              std::queue<uint64_t>& candidateQueue,
                              Flow* flow,
                              uint64_t startAddr)
{
    auto pushNewCandidate = [&](uint64_t target)
    {
        candidateQueue.push(target);
        flow->addEdge(std::make_pair(startAddr, target));
    };

    auto addNewContiguousBlock = [=]()
    {
        flow->addNewContiguousBlock(startAddr,
                                    currInsn.first,
                                    EBBlockType::NORMAL);
    };

    auto insn = this->getInstruction(currInsn.second);
    std::size_t insnSize = insn->getInstructionSize();

    bool updateStatus = false;

    if (insn->isSkipInsn()) {
        updateStatus = true;

        // Push next instruction following skip into queue
        pushNewCandidate(currInsn.first + insnSize);

        // Find the skipped instruction
        auto tmpIt = insnMap->find(currInsn.first + insnSize);
        assert(tmpIt != insnMap->end() &&
               "Cannot find the requested instruction.");

        auto nextInsn = this->getInstruction(tmpIt->second);
        pushNewCandidate(currInsn.first + insnSize + nextInsn->getInstructionSize());

        addNewContiguousBlock();
    }

    if (insn->isBranchInsn()) {
        updateStatus = true;

        auto targetAddrs = insn->getTargetAddrs(currInsn.first);
        assert(targetAddrs.size() == 1 && "Multiple target addresses returned.");

        pushNewCandidate(targetAddrs[0]);
        pushNewCandidate(currInsn.first + insnSize);
        addNewContiguousBlock();
    }

    if (insn->isJumpInsn()) {
        updateStatus = true;

        auto targetAddrs = insn->getTargetAddrs(currInsn.first);
        assert(targetAddrs.size() == 1 && "Multiple target addresses returned.");

        pushNewCandidate(targetAddrs[0]);
        addNewContiguousBlock();
    }

    if (insn->isReturnInsn())
    {
        updateStatus = true;

        addNewContiguousBlock();
        flow->markPreExitBlock(startAddr);
    }

    if (insn->isCallInsn()) {
        auto targetAddrs = insn->getTargetAddrs(currInsn.first);
        assert(targetAddrs.size() == 1 && "ICALL not supported.");

        if (targetAddrs[0] != currInsn.first + insnSize) {
            flow->markFuncCallLocation(currInsn.first, targetAddrs);
        }
        else
        {
            if (insn->getMnemonic() == "RCALL") {
                // known compiler shortcut to push stack.
                Log::log() << "Ignoring rcall .+0 instruction @0x" << std::hex << currInsn.first
                           << " in updateWorkList()."
                           << ELogLevel::LOG_DEBUG;
            }
            else
            {
                Log::log() << "Ignoring call instruction @0x" << std::hex << currInsn.first
                           << " in updateWorkList()."
                           << ELogLevel::LOG_WARNING;
            }
        }
    }

    return updateStatus;
}

/**
 *
 * @brief Filter incoming edges when fixing overlaps.
 *
 *
 * @note EdgeMap is a multimap, the function addEdge() prevents duplicate
 *       edges from being added to the EdgeMap. Therefore, retrieving edges
 *       for a single basic block will always result in a vector of edges
 *       with unique entries of edges (no duplicates) when calling
 *       getOutgoingEdges() and getIncomingEdges().
 *
 */
using EdgeVector = std::vector<EdgeMap::value_type>;


static EdgeVector
getEdgeDifference(const EdgeVector& in,
                  uint64_t duplicateBlock)
{
    // InEdges  has e = (n_1, n_2) where n_1 is head, n_2 is tail
    // OutEdges has e = (n_1, n_2) where n_1 is tail, n_2 is head
    EdgeVector ret_vec;
    for(auto it = in.begin(); it != in.end(); ++it)
    {
        // Check whether current edge forms a self loop
        if (it->first == it->second) {
            std::pair<const uint64_t, uint64_t> e(it->first, duplicateBlock);
            auto f_it = std::find(in.begin(), in.end(), e);
            // Check if an edge exists from duplicate block to trimmed block
            if (f_it != in.end()) {
                Log::log() << "getEdgeDifference(): Skipping edge [h,t] ("
                           << it->first << "," << it->second << ")."
                           << ELogLevel::LOG_DEBUG;
                continue;
            }
        }
        ret_vec.push_back(*it);
    }
    return ret_vec;
}


/**
 * @brief Fix overlapping blocks in flow.
 *
 * All blocks processed in this step must contain a single contiguous address
 * range. There might be more than two blocks that overlap into each other's
 * address range. This is taken care of by iterating over the sorted block map,
 * where blocks are also trimmed iteratively.
 *
 *
 * @param insnMap Contains the disassembled instructions (DisasmInstruction).
 * @param flow    The flow object where the jump blocks will be merged.
 */
void
FlowGenerator::fixOverlaps(const InsnMap* insnMap, Flow* flow)
{
    BlockMap blockMap = flow->getBlocks();
    for (auto currBlockIt = blockMap.begin();
         currBlockIt != blockMap.end();
         currBlockIt++)
    {
        // Block keys are sorted in increasing order
        auto& currAddrRanges = currBlockIt->second->getAddrRanges();
        assert(currAddrRanges.size() == 1 &&
               "Block must have a single contiguous address range here.");

        if (currAddrRanges[0].first == currAddrRanges[0].second) {
            continue;
        }

        // Get the lower bound for the current block end address
        auto startUpperBound = blockMap.upper_bound(currAddrRanges[0].first);
        auto endLowerBound = blockMap.lower_bound(currAddrRanges[0].second);

        if (startUpperBound->first == endLowerBound->first &&
            endLowerBound->first != currAddrRanges[0].second)
        {
            continue;
        }

        // Fix overlaps:
        //     1. Save the incoming edges of the current block and remove block
        //     2. Add the trimmed block and the saved edges
        //     3. Add a single edge from the trimmed block to upper bound
        auto incomingEdges = flow->getIncomingEdges(currAddrRanges[0].first);
        flow->removeBlock(currAddrRanges[0].first, false);

        // Get the length of the last instruction
        auto lastInsnIt = insnMap->find(startUpperBound->first);
        assert(lastInsnIt != insnMap->end() &&
               "Cannot find the requested instruction.");

        uint64_t lastInsnAddr = startUpperBound->first;
        auto lastInsn = this->getInstruction((--lastInsnIt)->second);

        lastInsnAddr -= lastInsn->getInstructionSize();

        flow->addNewContiguousBlock(currAddrRanges[0].first,
                                    lastInsnAddr,
                                    EBBlockType::NORMAL);

        // Update edges
        //flow->addEdges(incomingEdges, true);
        flow->addEdges(getEdgeDifference(incomingEdges, startUpperBound->first), true);
        flow->addEdge(
            std::make_pair(currAddrRanges[0].first, startUpperBound->first));
    }
}

/**
 * @brief Merge jump blocks.
 *
 * Blocks ending with a jump instruction (A) are merged with an adjacent block
 * (B) if the latter contains only one incoming edge. Merge direction is B to A.
 * If the block to be merged (B) is marked as a preexit block, the markers in
 * flow are updated accordingly when B is erased.
 *
 *
 * @param insnMap Contains the disassembled instructions (DisasmInstruction).
 * @param flow    The flow object where the jump blocks will be merged.
 */
void
FlowGenerator::mergeJumpBlocks(const InsnMap* insnMap, Flow* flow)
{
    auto& blockMap = flow->getBlocks();
    std::vector<BlockMap::const_iterator> blocksToMerge;

    for (auto blockIt = blockMap.begin(); blockIt != blockMap.end(); blockIt++)
    {
        // 1. A ends with RJMP or JMP and A->B
        auto outEdges_A = flow->getOutgoingEdges(blockIt->first);

        if (outEdges_A.size() != 1) {
            continue;
        }

        auto& addrRanges_A = blockIt->second->getAddrRanges();
        assert (addrRanges_A.size() == 1 &&
                "Blocks in this step must have a single address range only.");

        // Get last instruction of block A
        auto lastInsn_A = insnMap->find(addrRanges_A[0].second);
        assert(lastInsn_A != insnMap->end() &&
               "Cannot find instruction in insnMap.");

        // Only process if last instruction is a jump instruction
        auto insn = this->getInstruction(lastInsn_A->second);
        if (!insn->isJumpInsn()) {
            continue;
        }

        // Only merge A and B if block B has a single incoming edge
        auto bStartAddr_B = outEdges_A[0].second;
        auto inEdges_B = flow->getIncomingEdges(bStartAddr_B);

        if (inEdges_B.size() != 1) {
            continue;
        }
        else {
            blocksToMerge.push_back(blockMap.find(bStartAddr_B));
        }
    }


    // Merge B to A
    //     - 1. Make a local copy of B and remove it.
    //     - 2. Update address ranges in A.
    //     - 3. Add saved edges
    //     - 4. Update markers in flow if B was a preexit block.
    for (auto blockIt : blocksToMerge)
    {
        BasicBlock bBlock_B = *(blockIt->second);

        auto bStartAddr_A = flow->getIncomingEdges(blockIt->first)[0].second;
        auto bStartAddr_B = blockIt->first;

        auto blockIt_A = blockMap.find(bStartAddr_A);
        assert(blockIt_A != blockMap.end() && "Cannot find block.");

        // Edges of B will also be removed here, no iterator will be invalidated.
        auto outEdges_B = flow->getOutgoingEdges(bStartAddr_B);
        flow->removeBlock(bStartAddr_B);

        // Update address ranges for block A
        auto insertionResult = flow->
            insertBlockAddrRanges(bStartAddr_A, bBlock_B.getAddrRanges());

        assert(insertionResult && "Cannot insert address ranges in block ");

        // Add the saved outgoing edges
        if (outEdges_B.size()) {
            for (auto edgeIt : outEdges_B) {
                flow->addEdge(std::make_pair(bStartAddr_A, edgeIt.second));
            }
        }
        else {
            // If we land here, then B must have been a preexit block, update
            // marker for block A accordingly.
            //flow->markPostEntryBlock(bStartAddr_A);
            flow->markPreExitBlock(bStartAddr_A);
        }
    }
}


void
FlowGenerator::symbolize(const SymbMap* symbols, Flow* flow) {
    /**************************
     * symbolize callee names
     **************************/
    // iterate BBs with calls, find targets, look up addresses
    const auto callsite2targets = flow->getFuncCallTargets();
    const auto callsites = flow->getFuncCallLocations();
    for (auto& blockIt : flow->getBlocks())
    {
        std::shared_ptr<BasicBlock> bb = blockIt.second;
        if (bb->getType() == EBBlockType::CALL) {
            bool found = false;

            // look through all address ranges to find callee address
            const auto& addrRanges = bb->getAddrRanges();
            for (auto currRange = addrRanges.rbegin();
                 currRange != addrRanges.rend();
                 currRange++)
            {
                uint64_t rBegin = currRange->first;
                uint64_t rEnd   = currRange->second;
                const auto lbIt = callsites.lower_bound(rBegin);
                const auto ubIt = callsites.upper_bound(rEnd);
                if (lbIt == ubIt) continue;  // no calls here
                for (auto fIt = ubIt; fIt != lbIt;)
                {
                    --fIt;
                    found = true;
                    const uint64_t callsite = *fIt;
                    assert(callsite >= rBegin && callsite <= rEnd && "Out of range");
                    auto its = callsite2targets.find(callsite);
                    assert(its != callsite2targets.end() && "missing call targets");
                    const std::vector<uint64_t>& targets = its->second;
                    for (auto& addr : targets) {
                        // try to symbolize, fallback to string of address
                        std::string callee;
                        auto sIt = symbols->find(addr);
                        if (sIt != symbols->end()) {
                            callee = sIt->second;
                        } else {
                            std::stringstream ss;
                            ss << "0x" << std::hex << addr;
                            callee = ss.str();
                        }
                        bb->addCallee(callee);
                        Log::log() << "symbolize: BB " << blockIt.first << std::hex
                               << " [" << rBegin << ".." << rEnd << "] callsite @0x"
                               << callsite << std::dec << ": " << callee <<  ELogLevel::LOG_DEBUG;

                    }
                }
            } // curr contiguous instruction range
            assert(found && "callsite not found");
        }
    }

    // FIXME: symbolize other stuff, maybe
}

/**
 * @brief marks blocks as CALL if they contain function calls, and
 * ensures at most one fcn call per block <=> make real BBs from blocks
 */
void
FlowGenerator::manageFuncCallBlocks(const InsnMap* insnMap, Flow* flow)
{
    auto getInsnSize = [=](uint64_t address) -> std::size_t
    {
        auto insnIt = insnMap->find(address);
        assert(insnIt != insnMap->end() && "Invalid instruction address.");

        return this->getInstruction(insnIt->second)->getInstructionSize();
    };

    std::set<uint64_t> funcCallLocs = flow->getFuncCallLocations();
    if (!funcCallLocs.size()) {
        return;
    }

    for (auto& blockIt : flow->getBlocks())
    {
        const auto& addrRanges = blockIt.second->getAddrRanges();

        // Iterate over address ranges backwards, split if containing function
        // calls.
        std::size_t rIndex = addrRanges.size() - 1;

        for (auto currRange = addrRanges.rbegin();
             currRange != addrRanges.rend();
             currRange++)
        {
            uint64_t rBegin = currRange->first;
            uint64_t rEnd   = currRange->second;

            if (!funcCallLocs.size()) {
                break;
            }

            auto lbIt = funcCallLocs.lower_bound(rBegin);
            auto ubIt = funcCallLocs.upper_bound(rEnd);

            if (lbIt == ubIt) {
                continue;  // no calls here
            }

            blockIt.second->setType(EBBlockType::CALL);

            // split block at each callsite
            bool first = true;
            for (auto fIt = ubIt; fIt != lbIt;)
            {
                auto insnSize = getInsnSize(*--fIt);
                if (*fIt != addrRanges.back().second) {
                    Log::log() << "split: BB " << blockIt.first << std::hex
                               << "[" << rBegin << ".." << rEnd << "] after 0x"
                               << *fIt << std::dec << ELogLevel::LOG_DEBUG;
                    SplitLocation splitLoc {*fIt, insnSize, rIndex};
                    const uint64_t nBegin = splitLoc.insnAddr + splitLoc.insnSize;
                    std::shared_ptr<BasicBlock> newBlock;
                    assert(flow->splitBlock(blockIt.first, splitLoc, &newBlock));
                    // first new block may or may not have a function call after split, others do.
                    if (first) {
                        const auto lbnIt = funcCallLocs.lower_bound(nBegin);
                        const bool hasCall = !first || (lbnIt != ubIt);
                        newBlock->setType(hasCall ? EBBlockType::CALL : EBBlockType::NORMAL);
                        Log::log() << "split: new BB " << std::hex
                                   << "[" << nBegin << ".." << *fIt << "] has call: "
                                   << hasCall << ELogLevel::LOG_DEBUG;
                    }
                }
                first = false;
            }

            funcCallLocs.erase(lbIt, ubIt);
            rIndex--;
        }

        if (!funcCallLocs.size()) {
            break;
        }
    }

    assert(!funcCallLocs.size() && "Not all function calls were processed.");
}
