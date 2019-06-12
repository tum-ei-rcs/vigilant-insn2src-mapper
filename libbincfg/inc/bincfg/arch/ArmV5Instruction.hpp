/**
 * @file ArmV5Instruction.hpp
 * @brief ARMv5 ISA (32bit ARM + 16bit Thumb-1; no Jazelle)
 * According to "ARM Architecture Reference Manual", ARM Ltd, ARM DDI 0100I, 2005.
 */

#ifndef ARMV5INSTRUCTION_H
#define ARMV5INSTRUCTION_H

#include "bincfg/arch/Instruction.hpp"

//#define DEBUG_ARMV5FRONTEND

enum class EArmV5Mnemonic;


class ArmV5Instruction : public Instruction
{
private:
    static const std::map<std::string, EArmV5Mnemonic> s_mnemonicMap;
    // in ARM, most mnemonics can have suffixes for conditional execution
    EArmV5Mnemonic m_armMnemonic;
    std::string    m_armCond; ///< FIXME: maybe not as string

    std::size_t getWordSize() final override;

    bool mayWritePC(void) const;
    bool mayWriteRegister(void) const;

public:
    ArmV5Instruction(const DisasmInstruction& disInsn, bool ignoreErrors=false);
    ~ArmV5Instruction() {};

    bool isSkipInsn()   final override;
    bool isJumpInsn()   final override;
    bool isBranchInsn() final override;
    bool isCallInsn()   final override;
    bool isReturnInsn() final override;

    std::vector<uint64_t> getTargetAddrs(uint64_t currentAddr) final override;
    std::size_t           getInstructionSize() final override;
    std::string           getCond(void) { return m_armCond; }
};

#endif /* ARMV5INSTRUCTION_H */
