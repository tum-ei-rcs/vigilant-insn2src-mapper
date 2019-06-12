#ifndef DWARFREADER_H
#define DWARFREADER_H

#include <stdio.h>
#include <vector>

#include "bincfg/Log.hpp"
#include "bincfg/dwarf/DwarfData.hpp"
#include "bincfg/dwarf/DwarfDie.hpp"

// Libdwarf headers
#include "dwarf.h"
#include "libdwarf.h"

// Cannot include "dwarf_base_types.h" and "libdwarfdefs.h" needed by "dwarf_error.h"
// because of conflicting typedefs with stdio.h. Need to find a way to fix this.
//   --> Define functions needing either stdio.h or dwarf_error in a separate
//       cpp file. Include the stdio.h header for example in the cpp file.
typedef signed long Dwarf_Sword;
#include "dwarf_error.h"
//#include "dwarf_base_types.h"
//#include "libdwarfdefs.h"

using Log = bcfg::Log;


class DwarfReader
{
private:
    static const std::string m_logIdentifier;

    // Methods
    static void dwarfErrorHandler(Dwarf_Error error, Dwarf_Ptr errarg);
    Dwarf_Debug dwarfInit(FILE* elfFd, bool& initStatus);
    bool dwarfFinish(Dwarf_Debug d_debug);

    std::vector<Dwarf_Die> readCompilationUnits(Dwarf_Debug d_debug, bool d_isInfo);
    bool readSourceFiles(Dwarf_Debug d_debug, const std::vector<Dwarf_Die>& cuDies,
                         DwarfData* debugData);

    bool readLineNumbers(const std::vector<Dwarf_Die>& cuDies, DwarfData* debugData);
    bool processLineContext(Dwarf_Line_Context context, uint64_t cuId,
                            DwarfData* debugData);

    bool readAddressRanges(Dwarf_Debug d_debug, DwarfData* debugData);
    bool buildDieTree(Dwarf_Debug d_debug, const std::vector<Dwarf_Die>& cuDies,
                      DwarfData* debugData);



public:
    DwarfReader();

    std::shared_ptr<DwarfData> readDwarfData(const std::string& elfPath);
};

#endif /* DWARFREADER_H */