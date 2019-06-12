#include "bincfg/arch/AvrFlowGenerator.hpp"


std::unique_ptr<Instruction>
AvrFlowGenerator::getInstruction(const DisasmInstruction& disasmInsn)
{
    return std::unique_ptr<Instruction>(new AvrInstruction(disasmInsn)); 
}
