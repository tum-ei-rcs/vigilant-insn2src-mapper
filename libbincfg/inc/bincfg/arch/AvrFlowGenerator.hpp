#ifndef AVRFLOWGENERATOR_H
#define AVRFLOWGENERATOR_H

#include <ostream>
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

    void printBanner(std::ostream& output) const;
};

#endif /* AVRFLOWGENERATOR_H */
