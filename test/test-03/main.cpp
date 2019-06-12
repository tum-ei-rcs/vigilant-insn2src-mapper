#include <boost/program_options.hpp>

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

namespace po = boost::program_options;
using std::cout;
using std::cerr;
using std::endl;


void test(const std::string& fPath)
{
    auto lm = new LogManager();
    bcfg::Log::registerLogger(lm->createLogger("bincfg"));

    ElfDisassemblyReader* edr = new ElfDisassemblyReader(fPath);

    auto tSect = edr->readSection(".text");
    auto tInstructions = tSect->getInstructions();
    auto tSymbols = tSect->getSymbols();

    std::cout << "Instruction count: "
              << tSect->getInstructionCount()
              << std::endl;

    std::cout << "Symbols count: "
              << tSect->getSymbolCount()
              << std::endl;

    auto fGenerator = FlowGeneratorFactory::createFGenerator(ETargetArch::Avr);
    auto flowMap = fGenerator->generateFlows(tSect.get());

    CsvFlowExporter* fex = new CsvFlowExporter();
    fex->setAddFuncBlocks(true);

    DotFlowExporter* dex = new DotFlowExporter();
    dex->setAddFuncBlocks(true);

    JsonFlowExporter* jex = new JsonFlowExporter();

    for (auto fIt = flowMap->begin(); fIt != flowMap->end(); fIt++)
    {
        fex->exportFlow(fIt->second.get(), tInstructions.get());
        dex->exportFlow(fIt->second.get(), tInstructions.get());
        jex->exportFlow(fIt->second.get(), tInstructions.get(), "a.json");
    }
    jex->exportSymbMap(tSymbols.get(), ".text");
    //jex->exportInsnMap(tInstructions.get(), ".text");

    delete edr;
    delete lm;
    delete fex;
    delete dex;
    delete jex;
}


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
