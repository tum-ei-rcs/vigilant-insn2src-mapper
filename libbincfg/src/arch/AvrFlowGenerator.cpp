#include <iostream>
#include "bincfg/arch/AvrFlowGenerator.hpp"


std::unique_ptr<Instruction>
AvrFlowGenerator::getInstruction(const DisasmInstruction& disasmInsn)
{
    return std::unique_ptr<Instruction>(new AvrInstruction(disasmInsn, m_ignore_errors));
}

void
AvrFlowGenerator::printBanner(std::ostream& output) const {
    output << "AVR flow generator (stable)" << std::endl;
}
