#include <iostream>
#include <boost/program_options.hpp>

#include "common/LogManager.hpp"
#include "bincfg/Log.hpp"
#include "bincfg/disasm/ElfDisassemblyReader.hpp"
#include "bincfg/dwarf/DwarfReader.hpp"
#include "bincfg/flow/JsonFlowExporter.hpp"

namespace po = boost::program_options;


void test(const std::string& dfPath, const std::string& efPath)
{
    auto lm = new LogManager();
    bcfg::Log::registerLogger(lm->createLogger("bincfg"));

    ElfDisassemblyReader* edr = new ElfDisassemblyReader(dfPath);
    auto tSect = edr->readSection(".text");
    auto tInstructions = tSect->getInstructions();

    auto dwarfReader = new DwarfReader();
    auto debugData = dwarfReader->readDwarfData(efPath);

    JsonFlowExporter* jex = new JsonFlowExporter();
    jex->exportDebugData(debugData.get(), tInstructions.get(), "dbg.json");

    delete jex;
    delete dwarfReader;
    delete edr;
}


int main(int argc, char* argv[])
{
    std::string dfPath {""};
    std::string efPath {""};

    try {

        po::options_description desc("Usage");
        desc.add_options()
            ("help,h", "this text")
            ("d", po::value<std::string>(),
                "file path of the dissasembled object")
            ("e", po::value<std::string>(),
                "file path of the elf object")
        ;

        po::variables_map vm;        
        po::store(po::parse_command_line(argc, argv, desc), vm);
        po::notify(vm);    

        if (vm.count("help")) {
            std::cout << desc << std::endl;
            return 0;
        }

        if (vm.count("d") && vm.count("e")) {
            test(vm["d"].as<std::string>(), vm["e"].as<std::string>());
        } 
        else {
            std::cout << "No file path(s) given." << std::endl << std::endl << desc << std::endl;
        }

    }
    catch(const std::exception& e) {
        std::cerr << "(main) ERROR: " << e.what() << std::endl;
        return 1;
    }

    return 0;
}
