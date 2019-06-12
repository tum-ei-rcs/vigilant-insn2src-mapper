#include <iostream>
#include "bincfg/arch/ArmV5FlowGenerator.hpp"
#include "bincfg/arch/ArmV5Instruction.hpp"


std::unique_ptr<Instruction>
ArmV5FlowGenerator::getInstruction(const DisasmInstruction& disasmInsn)
{
    return std::unique_ptr<Instruction>(new ArmV5Instruction(disasmInsn, m_ignore_errors));
}

void
ArmV5FlowGenerator::printBanner(std::ostream& output) const {
    output << "ArmV5 flow generator (incomplete)" << std::endl;
}
