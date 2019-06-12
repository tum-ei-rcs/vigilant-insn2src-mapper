#ifndef ELFDISASSEMBLYREADER_H
#define ELFDISASSEMBLYREADER_H

#include <iostream>

#include <fstream>
#include <map>
#include <memory>
#include <iterator>
#include <regex>
#include <string>

struct DisasmInstruction {
    std::uint64_t rawInsn;
    std::string textInsn;
    std::string comment;
};
class DisasmSection;

using InsnMap = std::map<std::uint64_t, DisasmInstruction>;
using SymbMap = std::map<std::uint64_t, std::string>;


class ElfDisassemblyReader {
private:
    static const std::regex s_sectRegex;
    static const std::regex s_insnRegex;
    static const std::regex s_symbRegex;
    std::string             m_fPath;

    void processLines(std::istream& fStream, DisasmSection* disasmSection);
    bool customGetLine(std::istream& stream, std::string& str);
    InsnMap::value_type parseInstructionLine(const std::smatch& match);
    SymbMap::value_type parseSymbolLine(const std::smatch& match);
public:
    ElfDisassemblyReader(const std::string& fPath);
    std::shared_ptr<DisasmSection> readSection(const std::string& section);
};


class DisasmSection {
private:
    std::shared_ptr<InsnMap> m_insnMap;
    std::shared_ptr<SymbMap> m_symbMap;
    std::string              m_secName;

public:
    DisasmSection(const std::string& secName);
    void insertInstruction(InsnMap::value_type pair);
    void insertSymbol(SymbMap::value_type pair);
    
    std::shared_ptr<const InsnMap> getInstructions() const;
    std::shared_ptr<const SymbMap> getSymbols() const;
    SymbMap::const_iterator getSymbolContext(uint64_t address) const;
    InsnMap::size_type getInstructionCount() const;
    SymbMap::size_type getSymbolCount() const;

    const std::string& getSectionName() const;
};


#endif /* ELFDISASSEMBLYREADER_H*/