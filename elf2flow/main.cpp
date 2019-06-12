#include <boost/program_options.hpp>
#include <boost/filesystem.hpp>

#include <iostream>
#include <exception>
#include <iomanip>
#include <vector>
#include <queue>

#include "common/LogManager.hpp"
#include "bincfg/Log.hpp"

#include "bincfg/disasm/ElfDisassemblyReader.hpp"
#include "bincfg/flow/FlowGeneratorFactory.hpp"
#include "bincfg/flow/CsvFlowExporter.hpp"
#include "bincfg/flow/DotFlowExporter.hpp"
#include "bincfg/flow/JsonFlowExporter.hpp"
#include "bincfg/dwarf/DwarfReader.hpp"

namespace po = boost::program_options;
using std::cout;
using std::cerr;
using std::endl;

static std::shared_ptr<DisasmSection>
elf2disasm(const std::string& fPath)
{
    auto edr = std::unique_ptr<ElfDisassemblyReader>(new ElfDisassemblyReader(fPath));
    auto tSect = edr->readSection(".text");
    return tSect;
}

/**
 * @brief generate control flow graph from ELF and export to JSON
 */
static void
elf2flow(std::shared_ptr<DisasmSection>& tSect,
         const std::string& arch, const std::string& outflowfile,
         bool exportInsns, bool exportSymbols, bool ignoreErrors)
{
    auto tInstructions = tSect->getInstructions();
    auto tSymbols = tSect->getSymbols();

    std::cout << "Instruction count: "
              << tSect->getInstructionCount()
              << std::endl;

    std::cout << "Symbols count: "
              << tSect->getSymbolCount()
              << std::endl;

    auto fGenerator = FlowGeneratorFactory::createFGenerator(arch);
    fGenerator->setIgnoreErrors(ignoreErrors);
    fGenerator->printBanner(std::cout);
    auto flowMap = fGenerator->generateFlows(tSect.get());
    if (flowMap->empty()) {
        std::cerr << "No flows found!" << std::endl;
    }

    if (!outflowfile.empty()) {
        // choose exporter according to file extension
        auto exporter = std::unique_ptr<FlowExporter>();
        const std::string ext = boost::filesystem::extension(outflowfile);
        if (ext == ".csv") {
            auto ex = new CsvFlowExporter();
            ex->setAddFuncBlocks(true);
            exporter.reset(ex);
            std::cout << "Writing CSV" << endl;
        } else if (ext == ".dot") {
            auto ex = new DotFlowExporter();
            ex->setAddFuncBlocks(true);
            exporter.reset(ex);
            std::cout << "Writing dot" << endl;
        } else {
            auto ex = new JsonFlowExporter();
            exporter.reset(ex);
            std::cout << "Writing JSON" << endl;

        }
        boost::filesystem::remove(outflowfile);

        for (auto fIt = flowMap->begin(); fIt != flowMap->end(); fIt++)
        {
            const std::string flowName = fIt->second->getFlowName();
            std::cout << "Writing flow of " << flowName << "..." << std::endl;
            exporter->exportFlow(fIt->second.get(), tInstructions.get(), outflowfile);
        }

        if (ext != ".csv" && ext != ".dot") {
            auto jex = static_cast<JsonFlowExporter*>(exporter.get());
            if (exportInsns) {
                jex->exportInsnMap(tInstructions.get(), fGenerator, ".text", outflowfile);
                std::cout << "Exported instruction map to: " << outflowfile
                          << std::endl;
            }
            if (exportSymbols) {
                jex->exportSymbMap(tSymbols.get(), ".text", outflowfile);
                std::cout << "Exported symbol map to : " << outflowfile
                          << std::endl;
            }
        }
    }
    delete fGenerator;
}

/**
 * @brief read debug info from ELF and export to JSON
 */
static bool
elf2debug(const std::string& outPath, const std::string& elfPath,
          const DisasmSection* textSection, bool ignoreErrors)
{
    auto tInstructions = textSection->getInstructions();

    auto dwarfReader = new DwarfReader();
    auto debugData = dwarfReader->readDwarfData(elfPath);
    if (!debugData->isValid()) {
        std::cout << "Could not process dwarf data successfully (data invalid)" << std::endl;
        if (!ignoreErrors) return false;
    }

    JsonFlowExporter* jex = new JsonFlowExporter();
    jex->exportDebugData(debugData.get(), tInstructions.get(), outPath);

    delete jex;
    delete dwarfReader;
    return true;
}


int main(int argc, char* argv[])
{
    auto lm = std::unique_ptr<LogManager>(new LogManager());

    std::string asmfile;
    std::string arch;
    std::string outflowfile;
    std::string outdebugfile;
    std::string elffile;

    try {
        /*****************
         * parse options
         *****************/
        po::options_description desc("Usage");
        desc.add_options()
            ("help,h", "this text")
            ("list-arch,l", "list supported architectures")
            ("asm,m", po::value<std::string>(&asmfile)->required(),
                "file path of the dissasembled object")
            ("arch,a", po::value<std::string>(&arch)->required(),
                "select architecture")
            ("flow,f", po::value<std::string>(&outflowfile),
                "output path of flow information (JSON/CSV/dot)")
            ("debug,d", po::value<std::string>(&outdebugfile),
                "output path of debug information (JSON)")
            ("elf,e", po::value<std::string>(&elffile),
                "file path of elf object")
            ("inc-insn,i", "export disassembled instructions if exporting to JSON")
            ("inc-symb,s", "export symbol map if exporting to JSON")
            ("suppress-log", "suppress logging")
            ("ignore-errors", "plough on despite hazards");

        po::variables_map vm;
        po::store(po::parse_command_line(argc, argv, desc), vm);

        // options for which required args are not needed:
        if (vm.count("help")) {
            cout << desc << endl;
            return 0;
        }
        if (vm.count("list-arch")) {
            std::vector<std::string> archs = FlowGeneratorFactory::getArchList();
            std::cout << "Supported architectures: " << std::endl;
            for (auto & it : archs) {
                std::cout << " " << it << std::endl;
            }
            return 0;
        }
        // check required args and bail out
        po::notify(vm);

        /*****************
         * handle options
         *****************/
        if (outflowfile.empty()) {
            outflowfile = asmfile + ".csv"; // by default
        }

        bool exportInsns = false;
        bool exportSymbols = false;
        bool ignErr = false;
        if (vm.count("inc-insn")) exportInsns = true;
        if (vm.count("inc-symb")) exportSymbols = true;
        if (vm.count("ignore-errors")) ignErr = true;
        if (!vm.count("suppress-log")) bcfg::Log::registerLogger(lm->createLogger("elf2flow"));

        /*****************
         * do it
         *****************/

        cout << "Reading disassembly from " << asmfile << "..." << endl;
        auto textSection = elf2disasm(asmfile);

        if (vm.count("flow")) {
            cout << "Generating flow graphs ..." << endl;
            elf2flow(textSection, arch, outflowfile, exportInsns, exportSymbols, ignErr);
            cout << "Written file " << outflowfile << endl;
        }

        if (vm.count("debug")) {
            cout << "Reading debugging information of ELF " << elffile << endl;
            if (!vm.count("elf")) {
                std::cout << "Please provide the file path of the elf object."
                          << std::endl;
                return 1;
            }
            if (!elf2debug(outdebugfile, elffile, textSection.get(), ignErr)) {
                std::cerr << "Failed to export debug data." << std::endl;
                return 1;
            }
            std::cout << "Written file " << outdebugfile << endl;
        }

    }
    catch(const std::exception& e) {
        cerr << "ERROR: " << e.what() << endl;
        return 1;

    } catch(...) {
        cerr << "Exception of unknown type!" << endl;
        return 1;
    }

    return 0;
}
