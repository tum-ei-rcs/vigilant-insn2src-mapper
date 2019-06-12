#ifndef DWARFLOCATION_H
#define DWARFLOCATION_H

#include "dwarf.h"
#include "libdwarf.h"
#include <string>

namespace Dwarf {
    const std::string& getOpType(Dwarf_Small opType);
}

#endif /* DWARFLOCATION_H */