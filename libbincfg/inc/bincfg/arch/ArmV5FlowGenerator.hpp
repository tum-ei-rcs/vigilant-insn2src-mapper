#ifndef ARMV5FLOWGENERATOR_H
#define ARMV5FLOWGENERATOR_H

#include <ostream>
#include <queue>
#include <iomanip>

#include "bincfg/flow/FlowGenerator.hpp"


class ArmV5FlowGenerator : public FlowGenerator
{
public:
    ArmV5FlowGenerator() {};
    ~ArmV5FlowGenerator() {};

    std::unique_ptr<Instruction> getInstruction(const DisasmInstruction& disasmInsn);

    void printBanner(std::ostream& output) const;
};

#endif /* ARMV5FLOWGENERATOR_H */
