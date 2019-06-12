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

std::shared_ptr<DisasmSection>
elf2flow(const std::string& arch, const std::string& fPath, const std::string& outfile,
         bool exportInsns, bool exportSymbols)
{
    auto edr = std::unique_ptr<ElfDisassemblyReader>(new ElfDisassemblyReader(fPath));
    auto tSect = edr->readSection(".text");
    auto tInstructions = tSect->getInstructions();
    auto tSymbols = tSect->getSymbols();

    std::cout << "Instruction count: "
              << tSect->getInstructionCount()
              << std::endl;

    std::cout << "Symbols count: "
              << tSect->getSymbolCount()
              << std::endl;

    auto fGenerator = FlowGeneratorFactory::createFGenerator(arch);
    auto flowMap = fGenerator->generateFlows(tSect.get());

    // choose exporter according to file extension
    auto exporter = std::unique_ptr<FlowExporter>();
    const std::string ext = boost::filesystem::extension(outfile);
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
    boost::filesystem::remove(outfile);

    for (auto fIt = flowMap->begin(); fIt != flowMap->end(); fIt++)
    {
        const std::string flowName = fIt->second->getFlowName();
        exporter->exportFlow(fIt->second.get(), tInstructions.get(), outfile);
    }

    if (ext != ".csv" && ext != ".dot") {
        auto jex = static_cast<JsonFlowExporter*>(exporter.get());
        if (exportInsns) {
            jex->exportInsnMap(tInstructions.get(), fGenerator, ".text", outfile);
            std::cout << "Exported instruction map to: " << outfile
                      << std::endl;
        }
        if (exportSymbols) {
            jex->exportSymbMap(tSymbols.get(), ".text", outfile);
            std::cout << "Exported symbol map to : " << outfile
                      << std::endl;
        }
    }

    delete fGenerator;
    return tSect;
}


bool
exportDebug(const std::string& outPath, const std::string& elfPath,
            const DisasmSection* textSection)
{
    auto tInstructions = textSection->getInstructions();

    auto dwarfReader = new DwarfReader();
    auto debugData = dwarfReader->readDwarfData(elfPath);
    if (!debugData->isValid()) {
        std::cout << "Could not process dwarf data successfully." << std::endl;
        return false;
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
    std::string outfile;
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
            ("file,f", po::value<std::string>(&asmfile)->required(),
                "file path of the dissasembled object")
            ("arch,a", po::value<std::string>(&arch)->required(),
                "select architecture")
            ("out,o", po::value<std::string>(&outfile),
                "output path of JSON/CSV/dot file")
            ("debug,d", po::value<std::string>(&outdebugfile),
                "output path of debug information (JSON)")
            ("elf,e", po::value<std::string>(&elffile),
                "file path of elf object")
            ("inc-insn,i", "export disassembled instructions if exporting to JSON")
            ("inc-symb,s", "export symbol map if exporting to JSON")
            ("suppress-log", "suppress logging");

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
        if (outfile.empty()) {
            outfile = asmfile + ".csv"; // by default
        }

        bool exportInsns = false;
        bool exportSymbols = false;
        if (vm.count("inc-insn")) exportInsns = true;
        if (vm.count("inc-symb")) exportSymbols = true;
        if (!vm.count("suppress-log")) bcfg::Log::registerLogger(lm->createLogger("elf2flow"));

        /*****************
         * do it
         *****************/
        cout << "Analyzing " << asmfile << endl;
        auto textSection = elf2flow(arch, asmfile, outfile, exportInsns, exportSymbols);
        cout << "Written file " << outfile << endl;

        if (vm.count("debug")) {
            if (!vm.count("elf")) {
                std::cout << "Please provide the file path of the elf object."
                          << std::endl;
                return 1;
            }

            if (!exportDebug(outdebugfile, elffile, textSection.get())) {
                std::cerr << "Failed to export debug data." << std::endl;
                return 1;
            }
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
