#ifndef FLOWGENERATOR_H
#define FLOWGENERATOR_H

#include <queue>
#include "bincfg/disasm/ElfDisassemblyReader.hpp"
#include "bincfg/flow/Flow.hpp"
#include "bincfg/arch/Instruction.hpp"

using FlowMap = std::map<uint64_t, std::unique_ptr<Flow>>;
using FuncMap = std::map<uint64_t, std::string>;

/**
 * @note: It seems that my solution is more or less
 *        the same as in "Kruegel - Static disassembly of obfuscated binaries".
 *
 * @note: We assume that no intentional obfuscation has taken place (e.g. changing
 *        all function calls to a single branching function that resolves the
 *        real target).
 *
 * @note: Functions or parts of functions may be "inlined" in functions transferring
 *        control via branches and not calls. This does not represent a problem,
 *        it simply leads to a larger code region attributed to a function.
 *
 * @note: If needed, function entries can be found using heuristics, e.g. sequence
 *        of instructions in function prolog setting up a new stack frame.
 */
class FlowGenerator
{
protected:
    // Default implementations that can be overridden by specializations.
    virtual bool isFuncCallInstruction(const DisasmInstruction& disasmInsn,
                                       uint64_t insnAddr,
                                       uint64_t& targetAddr,
                                       bool suppressLog=false);

    virtual std::unique_ptr<FuncMap> findFunctions(const DisasmSection* section);
    virtual std::unique_ptr<Flow> createFuncFlow(const DisasmSection* section,
                                                 const FuncMap::value_type& funcPair);
    virtual bool updateWorklist(const InsnMap::value_type& currInsn,
                                const InsnMap* insnMap,
                                std::queue<uint64_t>& candidateQueue,
                                Flow* flow,
                                uint64_t startAddr);

    virtual void fixOverlaps(const InsnMap* insnMap, Flow* flow);
    virtual void mergeJumpBlocks(const InsnMap* insnMap, Flow* flow);
    virtual void splitFuncCallBlocks(const InsnMap* insnMap, Flow* flow);

public:
    virtual ~FlowGenerator() {};

    virtual std::unique_ptr<FlowMap>
        generateFlows(const DisasmSection* section);

    virtual std::unique_ptr<Instruction> getInstruction(const DisasmInstruction& disasmInsn) = 0;
};


#endif /* FLOWGENERATOR_H */
