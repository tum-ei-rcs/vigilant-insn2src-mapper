#include <boost/program_options.hpp>

#include <iostream>
#include <exception>
#include <iomanip>

#include "bincfg/disasm/ElfDisassemblyReader.hpp"

namespace po = boost::program_options;
using std::cout;
using std::cerr;
using std::endl;

void test(const std::string& fPath);

int main(int argc, char* argv[])
{
    std::string fPath {""};

    try {

        po::options_description desc("Usage");
        desc.add_options()
            ("help,h", "this text")
            ("file,f", po::value<std::string>(),
                 "file path of the dissasembled object")
        ;

        po::variables_map vm;
        po::store(po::parse_command_line(argc, argv, desc), vm);
        po::notify(vm);

        if (vm.count("help")) {
            cout << desc << endl;
            return 0;
        }

        if (vm.count("file")) {
            test(vm["file"].as<std::string>());
        }
        else {
            cout << "No file path given." << endl << endl << desc << endl;
        }

    }
    catch(const std::exception& e) {
        cerr << "ERROR: " << e.what() << endl;
        return 1;
    }
    catch(...) {
        cerr << "Exception of unknown type!" << endl;
    }

    return 0;
}


void test(const std::string& fPath)
{
    std::unique_ptr<ElfDisassemblyReader> edr =
        std::unique_ptr<ElfDisassemblyReader>(new ElfDisassemblyReader(fPath));

    std::shared_ptr<DisasmSection> tSect;
    try
    {
        tSect = edr->readSection(".text");
    }
    catch (const std::exception& e)
    {
        std::cout << "Error: " << e.what() << std::endl;
        return;
    }

    auto tSectInstructions = tSect->getInstructions();
    auto tSectSymbols = tSect->getSymbols();

    std::cout << "Instruction count: "
              << tSect->getInstructionCount()
              << std::endl;

    std::ios::fmtflags cFlags {std::cout.flags()};
    for (auto& kv: *tSectInstructions)
    {
        std::cout << "[" << std::hex << kv.first << "] {"
                  << kv.second.textInsn << "}   "
                  << kv.second.comment
                  << std::endl;
        std::cout.flags(cFlags);

        /*
        AvrInstruction avrInsn = bcfg::Avr::getAvrInstruction(kv.second);
        std::cout << "Opcode: " << static_cast<int>(avrInsn.opcode)
                  << " Operands: [" << avrInsn.operand1 << "]  ["
                  << avrInsn.operand2 << "]"
                  << std::endl;
        */
    }

    std::cout << "\n\nSymbols count: "
              << tSect->getSymbolCount()
              << std::endl;

    for (auto& kv: *tSectSymbols)
    {
        std::cout << "[" << std::hex << kv.first << "] "
                  << kv.second
                  << std::endl;
    }
}
