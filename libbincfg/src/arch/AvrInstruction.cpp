#include "bincfg/arch/AvrInstruction.hpp"
#include <stdio.h>

/**
 * @note The removed WORD "mnemonic" appears in e.g. debug sections, not really
 *       an instruction.
 */
AvrInstruction::AvrInstruction(const DisasmInstruction& disInsn, bool ignoreErrors)
    : Instruction(disInsn, true, ignoreErrors)
{
    assert(m_operands.size() <= 2 && "Invalid number of operands.");

    // m_mnemonic in base class, m_avrMnemonic in derived class
    auto mIt = s_mnemonicMap.find(m_mnemonic);
    if (mIt == s_mnemonicMap.end()) {
        printf("Unknown opcode '%s' in: %s\n", disInsn.textInsn.c_str(), m_mnemonic.c_str());
        assert(false && "Unknown AVR opcode");
    }

    //printf("Instruction: %s\n", disInsn.textInsn.c_str());
    m_avrMnemonic = mIt->second;
}

bool
AvrInstruction::isSkipInsn()
{
    // Not the actual opcode per se...
    int opcode = static_cast<int>(m_avrMnemonic);

    // Magic numbers from enum class: 39 -> CPI, 44 -> BRBS
    if (m_avrMnemonic == EAvrMnemonic::CPSE ||
        (opcode > 39 && opcode < 44))
    {
        return true;
    }

    return false;
}


bool
AvrInstruction::isJumpInsn()
{
    if (m_avrMnemonic == EAvrMnemonic::JMP ||
        m_avrMnemonic == EAvrMnemonic::IJMP ||
        m_avrMnemonic == EAvrMnemonic::RJMP)
    {
        return true;
    }

    return false;
}


bool
AvrInstruction::isBranchInsn()
{
    int opcode = static_cast<int>(m_avrMnemonic);

    // Magic numbers from enum class: 43 -> SBIS, 64 -> MOV
    if (opcode > 43 && opcode < 64) {
        return true;
    }

    return false;
}


bool
AvrInstruction::isCallInsn()
{
    if (m_avrMnemonic == EAvrMnemonic::CALL  ||
        m_avrMnemonic == EAvrMnemonic::RCALL ||
        m_avrMnemonic == EAvrMnemonic::ICALL)
    {
        return true;
    }

    return false;
}


bool
AvrInstruction::isReturnInsn()
{
    if (m_avrMnemonic == EAvrMnemonic::RET ||
        m_avrMnemonic == EAvrMnemonic::RETI)
    {
        return true;
    }

    return false;
}


/**
 * @brief Returns a vector of target addresses.
 *
 * @note For the moment, no instruction yields multiple return addresses. (ICALL, IJMP)
 *
 * @todo: Avoid double checks. Also check that currentAddr + relDiff does not
 *        wrap around (should not actually happen).
 */
std::vector<uint64_t>
AvrInstruction::getTargetAddrs(uint64_t currentAddr)
{
    std::vector<uint64_t> targetAddrs;

    if (this->isCallInsn() || this->isJumpInsn()) {
        if (m_avrMnemonic == EAvrMnemonic::CALL ||
            m_avrMnemonic == EAvrMnemonic::JMP)
        {
            uint64_t targetAddr = getAbsoluteAddr(m_operands[0]);
            targetAddrs.push_back(targetAddr);
        }
        else if (m_avrMnemonic == EAvrMnemonic::RCALL ||
                 m_avrMnemonic == EAvrMnemonic::RJMP)
        {
            uint64_t targetAddr = currentAddr + getRelativeDiff(m_operands[0]);
            targetAddrs.push_back(targetAddr);
        }
        else
        {
            Log::log() << "Indirect call/jump @" << currentAddr
                       << " not supported!" << ELogLevel::LOG_WARNING;
        }
    }

    if (this->isBranchInsn()) {
        uint64_t targetAddr = currentAddr + getRelativeDiff(m_operands[0]);
        targetAddrs.push_back(targetAddr);
    }

    return targetAddrs;
}


std::size_t
AvrInstruction::getInstructionSize()
{
    if (m_avrMnemonic == EAvrMnemonic::CALL ||
        m_avrMnemonic == EAvrMnemonic::JMP  ||
        m_avrMnemonic == EAvrMnemonic::LDS  ||
        m_avrMnemonic == EAvrMnemonic::STS)
    {
        return 4;
    }
    else if (m_avrMnemonic == EAvrMnemonic::BYTE)
    {
        return 1;
    }
    return 2;
}


std::size_t
AvrInstruction::getWordSize()
{
    return 2;
}


const std::map<std::string, EAvrMnemonic> AvrInstruction::s_mnemonicMap {
    {"ADD",    EAvrMnemonic::ADD},    {"ADC",   EAvrMnemonic::ADC},
    {"ADIW",   EAvrMnemonic::ADIW},   {"SUB",   EAvrMnemonic::SUB},
    {"SUBI",   EAvrMnemonic::SUBI},   {"SBC",   EAvrMnemonic::SBC},
    {"SBCI",   EAvrMnemonic::SBCI},   {"SBIW",  EAvrMnemonic::SBIW},
    {"AND",    EAvrMnemonic::AND},    {"ANDI",  EAvrMnemonic::ANDI},
    {"OR",     EAvrMnemonic::OR},
    {"ORI",    EAvrMnemonic::ORI},    {"EOR",   EAvrMnemonic::EOR},
    {"COM",    EAvrMnemonic::COM},    {"NEG",   EAvrMnemonic::NEG},
    {"SBR",    EAvrMnemonic::SBR},    {"CBR",   EAvrMnemonic::CBR},
    {"INC",    EAvrMnemonic::INC},    {"DEC",   EAvrMnemonic::DEC},
    {"TST",    EAvrMnemonic::TST},    {"CLR",   EAvrMnemonic::CLR},
    {"SER",    EAvrMnemonic::SER},    {"MUL",   EAvrMnemonic::MUL},
    {"MULS",   EAvrMnemonic::MULS},   {"MULSU", EAvrMnemonic::MULSU},
    {"FMUL",   EAvrMnemonic::FMUL},   {"FMULS", EAvrMnemonic::FMULS},
    {"FMULSU", EAvrMnemonic::FMULSU}, {"RJMP",  EAvrMnemonic::RJMP},
    {"IJMP",   EAvrMnemonic::IJMP},   {"JMP",   EAvrMnemonic::JMP},
    {"RCALL",  EAvrMnemonic::RCALL},  {"ICALL", EAvrMnemonic::ICALL},
    {"CALL",   EAvrMnemonic::CALL},   {"RET",   EAvrMnemonic::RET},
    {"RETI",   EAvrMnemonic::RETI},   {"CPSE",  EAvrMnemonic::CPSE},
    {"CP",     EAvrMnemonic::CP},     {"CPC",   EAvrMnemonic::CPC},
    {"CPI",    EAvrMnemonic::CPI},    {"SBRC",  EAvrMnemonic::SBRC},
    {"SBRS",   EAvrMnemonic::SBRS},   {"SBIC",  EAvrMnemonic::SBIC},
    {"SBIS",   EAvrMnemonic::SBIS},   {"BRBS",  EAvrMnemonic::BRBS},
    {"BRBC",   EAvrMnemonic::BRBC},   {"BREQ",  EAvrMnemonic::BREQ},
    {"BRNE",   EAvrMnemonic::BRNE},   {"BRCS",  EAvrMnemonic::BRCS},
    {"BRCC",   EAvrMnemonic::BRCC},   {"BRSH",  EAvrMnemonic::BRSH},
    {"BRLO",   EAvrMnemonic::BRLO},   {"BRMI",  EAvrMnemonic::BRMI},
    {"BRPL",   EAvrMnemonic::BRPL},   {"BRGE",  EAvrMnemonic::BRGE},
    {"BRLT",   EAvrMnemonic::BRLT},   {"BRHS",  EAvrMnemonic::BRHS},
    {"BRHC",   EAvrMnemonic::BRHC},   {"BRTS",  EAvrMnemonic::BRTS},
    {"BRTC",   EAvrMnemonic::BRTC},   {"BRVS",  EAvrMnemonic::BRVS},
    {"BRVC",   EAvrMnemonic::BRVC},   {"BRIE",  EAvrMnemonic::BRIE},
    {"BRID",   EAvrMnemonic::BRID},   {"MOV",   EAvrMnemonic::MOV},
    {"MOVW",   EAvrMnemonic::MOVW},   {"LDI",   EAvrMnemonic::LDI},
    {"LD",     EAvrMnemonic::LD},     {"LDD",   EAvrMnemonic::LDD},
    {"LDS",    EAvrMnemonic::LDS},    {"ST",    EAvrMnemonic::ST},
    {"STD",    EAvrMnemonic::STD},    {"STS",   EAvrMnemonic::STS},
    {"LPM",    EAvrMnemonic::LPM},    {"ELPM",  EAvrMnemonic::ELPM},
    {"SPM",    EAvrMnemonic::SPM},    {"IN",    EAvrMnemonic::IN},
    {"OUT",    EAvrMnemonic::OUT},    {"PUSH",  EAvrMnemonic::PUSH},
    {"POP",    EAvrMnemonic::POP},    {"SBI",   EAvrMnemonic::SBI},
    {"CBI",    EAvrMnemonic::CBI},    {"LSL",   EAvrMnemonic::LSL},
    {"LSR",    EAvrMnemonic::LSR},    {"ROL",   EAvrMnemonic::ROL},
    {"ROR",    EAvrMnemonic::ROR},    {"ASR",   EAvrMnemonic::ASR},
    {"SWAP",   EAvrMnemonic::SWAP},   {"BSET",  EAvrMnemonic::BSET},
    {"BCLR",   EAvrMnemonic::BCLR},   {"BST",   EAvrMnemonic::BST},
    {"BLD",    EAvrMnemonic::BLD},
    {"SEC",    EAvrMnemonic::SEC},    {"CLC",   EAvrMnemonic::CLC},
    {"SEN",    EAvrMnemonic::SEN},    {"CLN",   EAvrMnemonic::CLN},
    {"SEZ",    EAvrMnemonic::SEZ},    {"CLZ",   EAvrMnemonic::CLZ},
    {"SEI",    EAvrMnemonic::SEI},    {"CLI",   EAvrMnemonic::CLI},
    {"SES",    EAvrMnemonic::SES},    {"CLS",   EAvrMnemonic::CLS},
    {"SEV",    EAvrMnemonic::SEV},    {"CLV",   EAvrMnemonic::CLV},
    {"SET",    EAvrMnemonic::SET},    {"CLT",   EAvrMnemonic::CLT},
    {"SEH",    EAvrMnemonic::SEH},    {"CLH",   EAvrMnemonic::CLH},
    {"NOP",    EAvrMnemonic::NOP},    {"SLEEP", EAvrMnemonic::SLEEP},
    {"WDR",    EAvrMnemonic::WDR},    {"BREAK", EAvrMnemonic::BREAK},
    {"BYTE",   EAvrMnemonic::BYTE},   {"WORD",  EAvrMnemonic::WORD}
};


