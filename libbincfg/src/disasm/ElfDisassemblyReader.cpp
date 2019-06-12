#include "bincfg/disasm/ElfDisassemblyReader.hpp"

const std::regex ElfDisassemblyReader::s_symbRegex 
    { R"(([0-9a-fA-F]+) <([^>]+)>:)" };
const std::regex ElfDisassemblyReader::s_insnRegex
    { R"(([0-9a-fA-F]+):\t([0-9a-fA-F ]+)\t([^;<]+)(?:$|(?:\t;| )(.*)))" };
const std::regex ElfDisassemblyReader::s_sectRegex
    { R"(Disassembly of section (.*):)"};


ElfDisassemblyReader::ElfDisassemblyReader(const std::string& fPath)
    : m_fPath(fPath)
{
}

/**
 * @fixme: Don't throw exception, set a validity bit DisasmSection object.
 */
std::shared_ptr<DisasmSection>
ElfDisassemblyReader::readSection(const std::string& sName)
{
    auto disasmSection = std::make_shared<DisasmSection>(sName);

    bool status = false;
    std::ifstream fStream;
    fStream.exceptions(std::ifstream::failbit | std::ifstream::badbit);

    try
    {
        fStream.open(m_fPath.c_str(), std::ifstream::in);

        processLines(fStream, disasmSection.get());

        fStream.close();

    }
    catch (const std::ifstream::failure& e)
    {
        // Error processing file; TODO: LOG/Throw custom exception?
        std::cout << "Stream failure: " << e.what() << std::endl;
        status = false;
    }
    catch (const std::regex_error& e) {
        // Error parsing line; TODO: LOG/Throw custom exception?
        std::cout << "Regex error." << std::endl;
        status = false;
    }

    if (disasmSection->getInstructionCount() > 0 &&
        disasmSection->getSymbolCount() > 0)
    {
        status = true;
    }

    if (!status) {
        // TODO: Throw custom exception
        throw std::runtime_error("Could not read the requested section.");
    }

    return disasmSection;
}


void
ElfDisassemblyReader::processLines(std::istream& fStream,
                                   DisasmSection* disasmSection)
{
    const std::string& secName = disasmSection->getSectionName();
    bool foundSection = false;
    std::string currLine;
    std::smatch match;

    while (customGetLine(fStream, currLine))
    {
        // TODO: Also test if the given file is an disassembled ELF object

        if (!foundSection && 
            std::regex_search(currLine, match, s_sectRegex)) 
        {
            if (match.size() == 2 && match[1] == secName) {
                foundSection = true;
            }
        }
        else if (foundSection) {
            // 1. Test if current line is an instruction
            if (std::regex_search(currLine, match, s_insnRegex)) {
                disasmSection->
                    insertInstruction(parseInstructionLine(match));
            }
            // 2. Test if current line is a symbol
            else if (std::regex_search(currLine, match, s_symbRegex)){
                disasmSection->
                    insertSymbol(parseSymbolLine(match));
            }
            // 3. Test if we have reached the end of the text section
            else if (std::regex_search(currLine, match, s_sectRegex)) {
                break;
            }
        }
    }
}


bool
ElfDisassemblyReader::customGetLine(std::istream& stream, std::string& str)
{
    try {
        return static_cast<bool>(std::getline(stream, str));
    }
    catch(const std::ifstream::failure& f)
    {
         if (!stream.eof()) {
             throw;
         }
         return false;
    }
}


InsnMap::value_type
ElfDisassemblyReader::parseInstructionLine(const std::smatch& match)
{
    if (match.size() != 5) {
        throw std::runtime_error("Could not parse instruction.");
    }

    uint64_t address = std::stoull(match[1], nullptr, 16);
    DisasmInstruction dInsn { std::stoull(match[2], nullptr, 16),
        match[3],
        match[4]};
    return std::make_pair(address, dInsn);
}


SymbMap::value_type
ElfDisassemblyReader::parseSymbolLine(const std::smatch& match)
{
    if (match.size() != 3) {
        throw std::runtime_error("Could not parse symbol.");
    }

    uint64_t address = std::stoull(match[1], nullptr, 16);
    std::string section = match[2];
    return std::make_pair(address, section);
}


// DisasmSection
DisasmSection::DisasmSection(const std::string& secName)
    : m_insnMap(std::make_shared<InsnMap>()),
      m_symbMap(std::make_shared<SymbMap>()),
      m_secName(secName)
{
}

void
DisasmSection::insertInstruction(InsnMap::value_type pair)
{
    m_insnMap->insert(pair);
}


void
DisasmSection::insertSymbol(SymbMap::value_type pair)
{
    m_symbMap->insert(pair);
}


std::shared_ptr<const InsnMap> DisasmSection::getInstructions() const
{
    return std::const_pointer_cast<const InsnMap>(m_insnMap);
}


std::shared_ptr<const SymbMap> DisasmSection::getSymbols() const
{
    return std::const_pointer_cast<const SymbMap>(m_symbMap);
}


SymbMap::const_iterator
DisasmSection::getSymbolContext(uint64_t address) const
{
    // FIXME: Check if the given address is in the current section,
    //        if not, return the end iterator.
    auto tmpIt = --(m_symbMap->end());

    if (address < tmpIt->first) {
        tmpIt = --(m_symbMap->lower_bound(address));
    }

    return tmpIt;
}


InsnMap::size_type
DisasmSection::getInstructionCount() const
{
    return m_insnMap->size();
}


SymbMap::size_type
DisasmSection::getSymbolCount() const
{
    return m_symbMap->size();
}

const std::string&
DisasmSection::getSectionName() const
{
    return m_secName;
}
