#ifndef AVRINSTRUCTION_H
#define AVRINSTRUCTION_H

#include "bincfg/arch/Instruction.hpp"
#include "bincfg/Log.hpp"
using Log = bcfg::Log;

enum class EAvrMnemonic;


class AvrInstruction : public Instruction
{
private:
    static const std::map<std::string, EAvrMnemonic> s_mnemonicMap;
    EAvrMnemonic m_avrMnemonic;

    std::size_t getWordSize() final override;

public:
    AvrInstruction(const DisasmInstruction& disInsn, bool ignoreErrors=false);
    ~AvrInstruction() {};

    bool isSkipInsn()   final override;
    bool isJumpInsn()   final override;
    bool isBranchInsn() final override;
    bool isCallInsn()   final override;
    bool isReturnInsn() final override;

    std::vector<uint64_t> getTargetAddrs(uint64_t currentAddr) final override;
    std::size_t           getInstructionSize() final override;
};


enum class EAvrMnemonic
{
    ADD, ADC, ADIW,
    SUB, SUBI, SBC,
    SBCI, SBIW, AND,
    ANDI, OR, ORI,
    EOR, COM, NEG,
    SBR, CBR, INC,
    DEC, TST, CLR,
    SER, MUL, MULS,
    MULSU, FMUL, FMULS,
    FMULSU,

    RJMP, IJMP, JMP,
    RCALL, ICALL, CALL,
    RET, RETI, CPSE,
    CP, CPC, CPI,
    SBRC, SBRS, SBIC,
    SBIS, BRBS, BRBC,
    BREQ, BRNE, BRCS,
    BRCC, BRSH, BRLO,
    BRMI, BRPL, BRGE,
    BRLT, BRHS, BRHC,
    BRTS, BRTC, BRVS,
    BRVC, BRIE, BRID,

    MOV, MOVW, LDI,
    LD, LDD, LDS,
    ST, STD, STS,
    LPM, ELPM, SPM,
    IN, OUT, PUSH,
    POP,

    SBI, CBI, LSL,
    LSR, ROL, ROR,
    ASR, SWAP, BSET,
    BCLR, BST, BLD, SEC,
    CLC, SEN, CLN,
    SEZ, CLZ, SEI,
    CLI, SES, CLS,
    SEV, CLV, SET,
    CLT, SEH, CLH,

    NOP, SLEEP, WDR,
    BREAK,

    /* pseudo opcodes in code segment */
    BYTE, WORD
};


#endif /* AVRINSTRUCTION_H */
