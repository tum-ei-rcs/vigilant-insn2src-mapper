#ifndef DWARFATTRIBUTE_H
#define DWARFATTRIBUTE_H

#include "dwarf.h"
#include "libdwarf.h"
#include <assert.h>
#include <string>
#include <map>
#include <vector>
#include <functional>

#include "bincfg/Log.hpp"
#include "bincfg/dwarf/DwarfForm.hpp"
#include "bincfg/dwarf/DwarfLocation.hpp"


/**
 * @note For the moment, due to the fact that the value of an attribute may be
 *       encoded in different forms (9 different classes), it is saved as 
 *       a string for convenience of easy handling.
 * 
 * @todo Better error handling. If an error occurs when querying attributes,
 *       it will simply get logged by the dwarfErrorHandler callback. libdwarf
 *       does not guarantee the validity of the returned values even when
 *       the returned error code is DW_DLV_OK.
 */
class DwarfAttr
{
protected:
    Dwarf_Half                  m_type;
    std::shared_ptr<DwarfForm>  m_form;
    bool                        m_isValid;

public:
    DwarfAttr(Dwarf_Attribute d_attr);
    virtual ~DwarfAttr() {};

    bool                isValid()          const;
    virtual std::string getValueAsString() const;
    Dwarf_Half          getType()          const;

    friend bool operator< (const DwarfAttr& lhs, const DwarfAttr& rhs);
};

/******************************************************************************/

// FIXME: Move this
struct DwarfOperator
{
    Dwarf_Small    d_atom;
    Dwarf_Unsigned d_operand1;
    Dwarf_Unsigned d_operand2;
    Dwarf_Unsigned d_operand3;
    Dwarf_Unsigned d_offsetBranch;

    std::string getOpAsString() const;
};

// Helper struct
struct DwarfLocDescEntry
{
    Dwarf_Small    d_lleVal;
    Dwarf_Addr     d_lowPc;
    Dwarf_Addr     d_highPc;

    Dwarf_Unsigned d_loclistCount;
    Dwarf_Locdesc_c d_locEntry;
    Dwarf_Small     d_loclistSource;
    
    Dwarf_Unsigned  d_exprOffset;
    Dwarf_Unsigned  d_locdescOffset;
};

class DwarfLocEntry
{
private:
    std::vector<DwarfOperator> m_operators;
    bool                       m_isValid;

public:
    DwarfLocEntry(Dwarf_Loc_Head_c d_loclistHead, Dwarf_Unsigned index);

    bool                              isValid()          const;
    const std::vector<DwarfOperator>& getOperators()     const;
    std::string                       getEntryAsString() const;
};

/******************************************************************************/

class LocDwarfAttr : public DwarfAttr
{
private:
    std::vector<DwarfLocEntry> m_locEntries;
 
public:
    LocDwarfAttr(Dwarf_Debug d_debug, Dwarf_Attribute d_attr);
    ~LocDwarfAttr() override {};

    std::string getValueAsString() const final override;
};


class RangeDwarfAttr: public DwarfAttr
{
private:
    struct RangeEntry {
        uint64_t low;
        uint64_t high;

        std::string getEntryAsString() const {
            return std::to_string(low) + ',' + std::to_string(high);
        }
    };

    std::vector<RangeEntry> m_rangeEntries;

public:
    RangeDwarfAttr(Dwarf_Debug d_debug, Dwarf_Attribute d_attr);
    ~RangeDwarfAttr() override {};

    std::string getValueAsString() const final override;
};


/******************************************************************************/

// Custom set
using AttrUniquePtr = std::unique_ptr<DwarfAttr>;
struct AttrUniquePtr_cmp
{
    bool operator() (const AttrUniquePtr& lhs, const AttrUniquePtr& rhs) const
    {
        return *(lhs.get()) < *(rhs.get());
    }
};
using AttrSet = std::set<AttrUniquePtr, AttrUniquePtr_cmp>;


/******************************************************************************/

namespace Dwarf {
    AttrSet             getAttributes(Dwarf_Debug d_debug, Dwarf_Die d_inDie,
                                      bool& status);
    const std::string&  getAttrType(Dwarf_Half attrType);
}

#endif /* DWARFATTRIBUTE_H */