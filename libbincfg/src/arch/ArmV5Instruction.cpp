/**
 * @file ArmV5Instruction.cpp
 * @brief ARMv5TE ISA (32bit ARM + 16bit Thumb-1; no Jazelle)
 * According to "ARM Architecture Reference Manual", ARM Ltd, ARM DDI 0100I, 2005.
 * @note Conceptually, there is not difference between calls, jumps, branches and returns on ARM.
 * @todo targets cannot be determined as it is. Needs analysis of entire function.
 * @todo parsing mnemonics is not easily possible and simply wrong here. See MOVs example.
 */

#include <iostream>
#include <boost/algorithm/string/predicate.hpp>
#include "bincfg/arch/ArmV5Instruction.hpp"

enum class EArmV5Mnemonic
{
    /********************
     * ARM -- 32bit wide
     ********************/
    // branching (A3-6 may switch to Thumb)
    B, BL,
    BLX, BX, ///< switching to thumb

    // data processing (A3-9)
    ADC, ADD, SBC, SUB,
    AND, EOR, MOV, MVN,
    ORR, RSB, RSC,
    BIC, CMN, CMP,
    TEQ, TST,

    // multiply (A3-13)
    MLA, MUL, SMULL, UMLAL,
    UMULL,

    // status reg (A3-20)
    MRS, MSR, CPS,

    // load/store (A3-25, A3-27, A3-28)
    LDR, LDRB, LDRBT, LDRH,
    LDRSB, LDRSH, LDRT,
    STR, STRB, STRBT, STRH,
    STRT,
    LDM, LDMDA, LDMDB, LDMIA, LDMIB, ///< alias: POP
    STM, ///< alias: STBDM=PUSH
    SWP, SWPB,

    // co-processor instructions (A3-31)
    CDP, CDP2, LDC, LDC2,
    MCR, MCR2, MRC, MRC2,
    STC, STC2,

    // exception-generating (A3-29)
    BKPT, SWI,

    // other
    CLZ,
    NOP, ///< does not exist per se. Most instructions can act as nop if condition field is not SAT.

    /**********************
     * Thumb -- 16bit wide
     **********************/
    // only those not already defined in ARM
    ASR, LSL, LSR, NEG,
    ROR, POP,
    PUSH, STMIA,

    /**********************
     * INLINE DATA, PADDING
     **********************/
    // instruction stream may contain inline data. Appears as an instruction, but is unreachable.
    // E.g., such "instructions" may be referenced with
    //    ldr r3, [pc, #32]
    // where pc+32 is data and not an instruction. That is done because some values are too big
    // to be an immediate, so they are encoded this way.
    _DATA
};

enum class EArmV5Condition {
    EQ, NE, CS, HS, CC, LO,
    MI, PL, VS, VC, HI, LS,
    GE, LT, GT, LE, AL
};

ArmV5Instruction::ArmV5Instruction(const DisasmInstruction& disInsn, bool ignoreErrors)
    : Instruction(disInsn, false, ignoreErrors)
{
    if (boost::starts_with(disInsn.comment, " <UNDEFINED>")) {
        // inline data, not a real instruction
        m_mnemonic    = "NOP";
        m_armMnemonic = EArmV5Mnemonic::_DATA;

    } else {
        /**************
         * map to enum
         **************/
        const std::regex mnemoRex { R"((\S+)(\s+.*)$)" }; // FIXME: opcodes with no operand
        std::smatch match;

        // mnemo
        bool regResult = std::regex_match(disInsn.textInsn, match, mnemoRex);
        if (!regResult) {
            assert(false && "mnemo RegEx failed");
            return;  ///< in case asserts are off
        }
        std::string::const_iterator       it_rem = disInsn.textInsn.begin() + match.position(2);
        const std::string::const_iterator it_end = disInsn.textInsn.end();
        m_mnemonic = match.str(1);
        for (auto& c : m_mnemonic) c = std::toupper(c);

        // almost all mnemonics may have conditions. Longest prefix isn't always correct.
        // E.g., "blt.n" is not BL, but B. Therefore, we have to chomp conditions off first.
        // XXX: doesn't work either. MOVS is actually MOV, but becomes base=MO, cond=VS.
        const std::regex mnemoPartsRex
            { R"((\w+?)((EQ|NE|CS|HS|CC|LO|MI|PL|VS|VC|HI|LS|GE|LT|GT|LE)(\..)?)?)" };
        regResult = std::regex_match(m_mnemonic, match, mnemoPartsRex);
        if (!regResult) {
            assert(false && "mnemo RegEx failed");
            return;  ///< in case asserts are off
        }
        const std::string mnemo_base = match.str(1);
        if (match.position(2) >= 0) {
            m_armCond = match.str(2);
        }
        #ifdef DEBUG_ARMV5FRONTEND
        std::cout << "Insn=" << m_mnemonic
                  << " => base=" << mnemo_base << ", cond=" << m_armCond << std::endl;
        #endif

        // now we got the base form -> map to enum
        auto mIt = s_mnemonicMap.find(mnemo_base);
        if (s_mnemonicMap.end() == mIt) {
            std::cerr << "Unknown mnemonic '" << mnemo_base << std::endl;
            if (!m_ignore_errors) assert(false && "unknown mnemonic");
            m_armMnemonic = EArmV5Mnemonic::NOP;
            return;  ///< in case assert are off
        }
        m_armMnemonic = mIt->second;

        /**************
         * operands
         **************/
        // FIXME: this super slow, despite iterators to avoid copy
        const std::regex opParens { R"(([\[\{][^\]\}]+[\]\}][!\^]?)(?:,(.+))?$)" };
        const std::regex opNoParens { R"(([^,]+)(?:,(.*))?$)" };
        while (it_rem != it_end) {
            while(it_rem != it_end && std::isspace(*it_rem)) ++it_rem;
            if (it_end == it_rem) break;

            const std::regex* opRex;
            if (it_rem[0] == '[' || it_rem[0] == '{') {
                opRex = &opParens;
            } else {
                opRex = &opNoParens;
            }
            assert(it_rem != it_end);

            bool regResult = std::regex_match(it_rem, it_end, match, *opRex);
            if (!regResult) {
                if (!m_ignore_errors) assert(false && "op RegEx failed");
                return;  ///< in case asserts are off
            }

            m_operands.push_back(match.str(1)); // copy
            #ifdef DEBUG_ARMV5FRONTEND
            std::cout << "size=" << match.size()
            << ", rem pos=" << match.position(2)
            << ", rem='" << match.str(2) << "'" << std::endl;
            #endif
            if (match.position(2) < 0 || match.str(2).empty()) break; // we need the second cond, because g++ otherwise is giving pos beyond end -- bug?
            assert (match.position(2) < 10 && "suspicious pos");
            it_rem += match.position(2);
        }
    }
    #ifdef DEBUG_ARMV5FRONTEND
    std::cout << "I: '" << disInsn.textInsn << "' => " << m_mnemonic;
    if (!m_armCond.empty()) std::cout << " (" << m_armCond << ")";
    if (!m_operands.empty()) std::cout << ":\t";
    for (auto & it : m_operands) std::cout << " " << it << ";";
    std::cout << std::endl;
    #endif
}

inline bool
ArmV5Instruction::mayWriteRegister(void) const {
    return (m_armMnemonic >= EArmV5Mnemonic::LDR && m_armMnemonic <= EArmV5Mnemonic::SWPB) ||
           (m_armMnemonic >= EArmV5Mnemonic::ADC && m_armMnemonic <= EArmV5Mnemonic::RSC) ||
           (m_armMnemonic >= EArmV5Mnemonic::ASR && m_armMnemonic <= EArmV5Mnemonic::STMIA);

}

/**
 * @brief check whether instruction could be altering PC directly,
 * that is, besides B, BL, BLX, BX
 */
inline bool
ArmV5Instruction::mayWritePC(void) const {
    if (!mayWriteRegister()) return false;

    // analyze whether the write contains pc. we possibly overapproximate
    if (boost::contains(m_operands[0], "pc") || boost::contains(m_operands[0], "r15"))
        return true;

    return false;
}


bool
ArmV5Instruction::isSkipInsn()
{
    return false; // don't exist
}

/**
 * @brief must be unconditional
 * @note this is complete
 */
bool
ArmV5Instruction::isJumpInsn()
{
    if ( ! m_armCond.empty()) return false;

    if (m_armMnemonic == EArmV5Mnemonic::B ||
        m_armMnemonic == EArmV5Mnemonic::BX)
    {
        return !isReturnInsn();

    } else {
        return mayWritePC();
    }
}

/**
 * @brief must be conditional
 * @note this is complete
 */
bool
ArmV5Instruction::isBranchInsn()
{
    if (m_armCond.empty()) return false;

    if (m_armMnemonic == EArmV5Mnemonic::B ||
        m_armMnemonic == EArmV5Mnemonic::BX)
    {
        return !isReturnInsn();

    } else {
        return mayWritePC();
    }
}

/**
 * @brief function call
 * @note Complete. Although assembly could do "MOV lr,*" followed by "B *".
 *       But we interpret this as a branch rather than a call.
 **/
bool
ArmV5Instruction::isCallInsn()
{
    // BL, BLX are equivalent to calls. But they could be conditional.
    if (m_armMnemonic == EArmV5Mnemonic::BL  ||
        m_armMnemonic == EArmV5Mnemonic::BLX)
    {
        return true;
    }

    return false;
}

/**
 * @brief function return
 * @note complete. Although assembly could write PC directly,
 * but we count this as branch rather than a return.
 */
bool
ArmV5Instruction::isReturnInsn()
{
    // usually it's bx lr, but technically any other register
    // (not only lr) could hold return address. So it's not
    // easily distinguishable from jump/branch
    //

    if (m_armMnemonic == EArmV5Mnemonic::B ||
        m_armMnemonic == EArmV5Mnemonic::BX)
    {
        return "lr" == m_operands[0];
    } else if (m_armMnemonic == EArmV5Mnemonic::POP) {
        // this is commonly used as return. E.g., pop {r1, r2, pc}.
        return mayWritePC();
    }

    return false;
}

/**
 * @brief Returns a vector of target addresses, besides PC++
 *
  * @todo: incomplete
 */
std::vector<uint64_t>
ArmV5Instruction::getTargetAddrs(uint64_t currentAddr)
{
    std::vector<uint64_t> targetAddrs;

    if (isBranchInsn() || isCallInsn() || isJumpInsn()) { // not called for return
        // BL, B are actually relative, but objdump seems to decode that)
        // absolute: BLX, BX, POP, LDR,

            const std::regex re_hex { R"(\s*[0-9a-fA-F]+\s*$)" };
            std::smatch match;
            if (m_operands.size() > 0) {
                const bool op0_is_literal = std::regex_match(m_operands[0], match, re_hex);
                if (op0_is_literal) {
                    uint64_t targetAddr = getAbsoluteAddr(m_operands[0]);
                    targetAddrs.push_back(targetAddr);
                } else {
                    // there is no way to tell targets without analyzing surrounding code
                    // e.g., "bx lr", no comment available. Target is in lr, for which we need analysis now.
                    std::cerr << "Cannot determine destination of instruction @0x"
                              << std::hex << currentAddr << std::endl;
                }
            } else {
                std::cerr << "Cannot determine destination of instruction @0x"
                          << std::hex << currentAddr << " (no operands)" << std::endl;
            }
    }
    return targetAddrs;
}

// FIXME: if that works, move to base class.
std::size_t
ArmV5Instruction::getInstructionSize()
{
    // look at opcode. Not possible via mnemonic, since Thumb and ARM have similar ones.
    return (m_disInsn.rawInsn <= 0xFFFF) ? 2 : 4; // FIXME: endianness?
}

std::size_t
ArmV5Instruction::getWordSize()
{
    return 4;
}

// FIXME: find a nifty trick to not rewrite all enum values and guarantee completeness w.r.t enum.
#define MNEMO_UNCOND(X) {#X, EArmV5Mnemonic::X} ///< unconditional instruction space
#define MNEMO(X) {#X, EArmV5Mnemonic::X} ///< conditional instruction space
const std::map<std::string, EArmV5Mnemonic> ArmV5Instruction::s_mnemonicMap {
    MNEMO(B),
    MNEMO(BL),
    MNEMO_UNCOND(BLX),
    MNEMO(BX),
    MNEMO(ADC),
    MNEMO(ADD),
    MNEMO(AND),
    MNEMO(BIC),
    MNEMO(CMN),
    MNEMO(CMP),
    MNEMO(EOR),
    MNEMO(MOV),
    MNEMO(MVN),
    MNEMO(ORR),
    MNEMO(RSB),
    MNEMO(RSC),
    MNEMO(SBC),
    MNEMO(SUB),
    MNEMO(TEQ),
    MNEMO(TST),
    MNEMO(MLA),
    MNEMO(MUL),
    MNEMO(SMULL),
    MNEMO(UMLAL),
    MNEMO(UMULL),
    MNEMO(MRS),
    MNEMO(MSR),
    MNEMO(CPS),
    MNEMO(LDR),
    MNEMO(LDRB),
    MNEMO(LDRBT),
    MNEMO(LDRH),
    MNEMO(LDRSB),
    MNEMO(LDRSH),
    MNEMO(LDRT),
    MNEMO(STR),
    MNEMO(STRB),
    MNEMO(STRBT),
    MNEMO(STRH),
    MNEMO(STRT),
    MNEMO(LDM),
    MNEMO(LDMDA),
    MNEMO(LDMDB),
    MNEMO(LDMIA),
    MNEMO(LDMIB),
    MNEMO(STM),
    MNEMO(SWP),
    MNEMO(SWPB),
    MNEMO(CDP),
    MNEMO_UNCOND(CDP2),
    MNEMO(LDC),
    MNEMO_UNCOND(LDC2),
    MNEMO(MCR),
    MNEMO_UNCOND(MCR2),
    MNEMO(MRC),
    MNEMO_UNCOND(MRC2),
    MNEMO(STC),
    MNEMO_UNCOND(STC2),
    MNEMO(BKPT),
    MNEMO(SWI),
    MNEMO(CLZ),
    MNEMO(NOP),
    MNEMO(ASR),
    MNEMO(LSL),
    MNEMO(LSR),
    MNEMO(NEG),
    MNEMO(ROR),
    MNEMO(LDMIA),
    MNEMO(STMIA),
    MNEMO(POP),
    MNEMO(PUSH),
    MNEMO_UNCOND(_DATA)
};
#undef MNEMO


