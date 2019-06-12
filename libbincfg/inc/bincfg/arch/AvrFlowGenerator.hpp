#ifndef AVRFLOWGENERATOR_H
#define AVRFLOWGENERATOR_H

#include <queue>
#include <iomanip>

#include "bincfg/flow/FlowGenerator.hpp"
#include "bincfg/arch/AvrInstruction.hpp"


class AvrFlowGenerator : public FlowGenerator
{
public:
    AvrFlowGenerator() {};
    ~AvrFlowGenerator() {};

    std::unique_ptr<Instruction> getInstruction(const DisasmInstruction& disasmInsn);
};

#endif /* AVRFLOWGENERATOR_H */
