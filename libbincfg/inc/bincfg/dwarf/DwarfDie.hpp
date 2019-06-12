#ifndef DWARFDIE_H
#define DWARFDIE_H

#include "dwarf.h"
#include "libdwarf.h"
#include <vector>
#include <string>
#include <functional>
#include <map>

#include "bincfg/Log.hpp"
#include "bincfg/dwarf/DwarfAttribute.hpp"


class DwarfDie
{
protected:
    std::vector<DwarfDie>  m_dieChildren;
    AttrSet                m_attrs;
    Dwarf_Off              m_dieOffset;
    Dwarf_Off              m_parentOffset;
    Dwarf_Half             m_tagValue;
    Dwarf_Half             m_dieVersion;
    Dwarf_Half             m_dieOffsetSize;
    bool                   m_isValid;
    bool                   m_isInfo;

    bool findDieChildren(Dwarf_Debug d_debug, Dwarf_Die d_inDie);
    bool readAttributes(Dwarf_Debug d_debug, Dwarf_Die d_inDie);

public:
    DwarfDie(Dwarf_Debug d_debug, Dwarf_Die d_inDie, Dwarf_Off d_parentOffset,
             bool findChildren=true);
    
    DwarfDie(const DwarfDie&)              = delete;
    DwarfDie& operator= (const DwarfDie&)  = delete;
    DwarfDie(DwarfDie&& dwDie)             = default;
    DwarfDie& operator= (DwarfDie&& dwDie) = default;


    // Public methods
    const std::vector<DwarfDie>& getChildren()      const;
    const AttrSet&               getAttributes()    const;
    Dwarf_Off                    getOffset()        const;
    Dwarf_Off                    getParentOffset()  const;
    Dwarf_Half                   getTagValue()      const;
    Dwarf_Half                   getDieVersion()    const;
    Dwarf_Half                   getDieOffsetSize() const;
    bool                         isValid()          const;
    bool                         isInfo()           const;
};

namespace Dwarf {
    const std::string& getTagType(Dwarf_Half tagType);
}

#endif /* DWARFDIE_H */