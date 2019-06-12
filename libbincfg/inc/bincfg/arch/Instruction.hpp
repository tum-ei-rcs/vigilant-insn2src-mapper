#ifndef INSTRUCTION_H
#define INSTRUCTION_H

#include <regex>
#include <assert.h>

#include "bincfg/disasm/ElfDisassemblyReader.hpp"


class Instruction
{
protected:
    const DisasmInstruction  m_disInsn;
    bool                     m_ignore_errors;
    std::string              m_mnemonic;
    std::vector<std::string> m_operands;

    Instruction(const DisasmInstruction& disInsn, bool defaultRegex, bool ignoreErrors=false);
    virtual const std::regex& getInsnRegex();

    virtual uint64_t    getAbsoluteAddr(const std::string& operand);
    virtual int64_t     getRelativeDiff(const std::string& operand);
    virtual std::size_t getWordSize() = 0;



public:
    virtual ~Instruction() {};

    virtual bool isSkipInsn()   = 0;
    virtual bool isJumpInsn()   = 0;
    virtual bool isBranchInsn() = 0;
    virtual bool isCallInsn()   = 0;
    virtual bool isReturnInsn() = 0;

    virtual std::vector<uint64_t> getTargetAddrs(uint64_t currentAddr) = 0;
    virtual std::size_t           getInstructionSize() = 0;

    const std::string&              getMnemonic() const;
    const std::vector<std::string>& getOperands() const;
};


#endif /* INSTRUCTION_H */
