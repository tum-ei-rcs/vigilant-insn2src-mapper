#include "bincfg/arch/Instruction.hpp"

Instruction::Instruction(const DisasmInstruction& disInsn, bool defaultRegex, bool ignoreErrors)
    : m_disInsn(disInsn), m_ignore_errors(ignoreErrors)
{
    if (!defaultRegex) {
        return;
    }

    auto& insnRegex = this->getInsnRegex();
    std::smatch match;

    bool regResult = std::regex_search(m_disInsn.textInsn, match, insnRegex);
    assert(regResult && match.size() == 4 && "Regex error.");

    // Update the default constructed m_mnemonic, convert to upper case.
    m_mnemonic = match.str(1);
    for (auto& c : m_mnemonic) c = std::toupper(c);

    // Default regex captures at most two operands (match[2] and match[3]).
    if (match.str(2) != "") {
        m_operands.push_back(match.str(2));
    }

    if (match.str(3) != "") {
        assert(match.str(2) != "");
        m_operands.push_back(match.str(3));
    }
}


const std::regex&
Instruction::getInsnRegex()
{
    static const std::regex insnRegex
        { R"(\.?([a-zA-Z]+)(?:\s+([\d\w\.\+\-]+)(?:,\s+([\d\w\.\+\-]+))?)?)" };

    return insnRegex;
}


uint64_t
Instruction::getAbsoluteAddr(const std::string& operand)
{
    return std::stoull(operand, nullptr, 16);
}


/**
 * @todo: Don't throw exception. Use assert instead.
 *
 */
int64_t
Instruction::getRelativeDiff(const std::string& operand)
{
    static const std::regex r { R"(.([\+|\-][0-9]+))" };
    std::smatch match;

    if (std::regex_search(operand, match, r)) {
        return std::stoi(match[1]) + getWordSize();
    }
    else {
        //throw std::runtime_error("Regex error in getRelativeDiff().");
        assert(false && "regex error in getRelativeDiff()");
    }}


const std::string&
Instruction::getMnemonic() const
{
    return m_mnemonic;
}


const std::vector<std::string>&
Instruction::getOperands() const
{
    return m_operands;
}
