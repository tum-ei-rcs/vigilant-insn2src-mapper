#ifndef DWARFFORM_H
#define DWARFFORM_H

#include "dwarf.h"
#include "libdwarf.h"
#include <string>
#include <cstring>
#include <vector>
#include <map>
#include <set>
#include <functional>
#include <iomanip>
#include <assert.h>

#include "bincfg/Log.hpp"

using Log = bcfg::Log;

/******************************************************************************/

enum class EDwarfFormClass {
    REFERENCE = 0,
    ADDR      = 1,
    STRING    = 2,
    CONSTANT  = 3,
    BLOCK     = 4,
    EXPRLOC   = 5,
    UNKNOWN   = 6
};


class DwarfForm
{
protected:
    EDwarfFormClass m_formClass;
    Dwarf_Half      m_formType;
    bool            m_isValid;

    DwarfForm(Dwarf_Attribute d_attr, EDwarfFormClass formClass);
    void setValidity(bool value);

public:
    virtual ~DwarfForm();
    virtual std::string getValueAsString() = 0;

    EDwarfFormClass getFormClass();
    bool            isValid();
};


using DFInstanceFunction = std::function<DwarfForm*(Dwarf_Attribute)>;


namespace Dwarf {
    DwarfForm* createDwarfForm(Dwarf_Attribute d_attr);
}
/******************************************************************************/


/******************************************************************************/

class GlobalRefDwarfForm : public DwarfForm
{
private:
    Dwarf_Off m_sectionOffset;

public:
    GlobalRefDwarfForm(Dwarf_Attribute d_attr);
    ~GlobalRefDwarfForm() {};
    std::string getValueAsString() final override;
    Dwarf_Off getOffset() const;
};


class AddrDwarfForm : public DwarfForm
{
private:
    Dwarf_Addr m_addr;

public:
    AddrDwarfForm(Dwarf_Attribute d_attr);
    ~AddrDwarfForm() {};
    std::string getValueAsString() final override;
};

/**
 * @note There isn't a unique way to get a string pointer for all forms of
 *       string class in libdwarf.
 */
class StringDwarfForm : public DwarfForm
{
private:
    std::string m_str;

public:
    StringDwarfForm(Dwarf_Attribute d_attr);
    ~StringDwarfForm() {};
    std::string getValueAsString() final override;
};


class ConstantDwarfForm : public DwarfForm
{
private:
    Dwarf_Unsigned m_uValue;
    Dwarf_Signed   m_sValue;
    int            m_sign;

public:
    ConstantDwarfForm(Dwarf_Attribute d_attr);
    ~ConstantDwarfForm() {};

    Dwarf_Unsigned getUnsigned()      const;
    Dwarf_Signed   getSigned()        const;
    std::string    getValueAsString() final override;
};


/******************************************************************************/

class DwarfBlock
{
public:
    typedef std::vector<uint8_t> blockdata_t;

private:
    /**
     * typedef struct {
     *     Dwarf_Unsigned bl_len;
     *     Dwarf_Ptr      bl_data;
     * } Dwarf_Block;
     *
     *     * bl_len   the length in bytes.
     *     * bl_data  points to uninterpreted data.
     *
     */
    std::shared_ptr<blockdata_t> m_blockData;
    uint64_t                     m_blockLen;

public:
    DwarfBlock(Dwarf_Block* dwBlock);

    std::shared_ptr<blockdata_t>  getDataPtr();
    uint64_t                      getLength();
    std::string                   getRawHexString();
};


/**
 * @note This is sometimes used for DW_AT_location (not specified in manual),
 *       along with data_4 and data_8 form.
 *
 */
class BlockDwarfForm : public DwarfForm
{
private:
    std::unique_ptr<DwarfBlock> m_dwBlock;

public:
    BlockDwarfForm(Dwarf_Attribute d_attr);
    ~BlockDwarfForm() {};
    std::string getValueAsString() final override;
};

/******************************************************************************/


class ExprlocDwarfForm : public DwarfForm
{
private:
    std::unique_ptr<DwarfBlock> m_dwBlock;

public:
    ExprlocDwarfForm(Dwarf_Attribute d_attr);
    ~ExprlocDwarfForm() {};
    std::string getValueAsString() final override;
};

#endif /* DWARFFORM_H */
