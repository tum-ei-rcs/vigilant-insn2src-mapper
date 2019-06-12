#include "bincfg/dwarf/DwarfForm.hpp"


static const std::map<Dwarf_Half, EDwarfFormClass> s_formMap {
    // Reference
    {DW_FORM_ref_addr,     EDwarfFormClass::REFERENCE},
    {DW_FORM_ref1,         EDwarfFormClass::REFERENCE},
    {DW_FORM_ref2,         EDwarfFormClass::REFERENCE},
    {DW_FORM_ref4,         EDwarfFormClass::REFERENCE},
    {DW_FORM_ref8,         EDwarfFormClass::REFERENCE},
    {DW_FORM_ref_udata,    EDwarfFormClass::REFERENCE},
    {DW_FORM_ref_sig8,     EDwarfFormClass::REFERENCE},
    {DW_FORM_sec_offset,   EDwarfFormClass::REFERENCE},
    // Addr
    {DW_FORM_addr,         EDwarfFormClass::ADDR},
    // String
    {DW_FORM_string,       EDwarfFormClass::STRING},
    {DW_FORM_GNU_strp_alt, EDwarfFormClass::STRING},
    {DW_FORM_strp_sup,     EDwarfFormClass::STRING},
    {DW_FORM_strx,         EDwarfFormClass::STRING},
    {DW_FORM_strp,         EDwarfFormClass::STRING},
    {DW_FORM_line_strp,    EDwarfFormClass::STRING},
    // Constant
    {DW_FORM_data1,        EDwarfFormClass::CONSTANT},
    {DW_FORM_data2,        EDwarfFormClass::CONSTANT},
    {DW_FORM_data4,        EDwarfFormClass::CONSTANT},
    {DW_FORM_data8,        EDwarfFormClass::CONSTANT},
    {DW_FORM_sdata,        EDwarfFormClass::CONSTANT},
    {DW_FORM_udata,        EDwarfFormClass::CONSTANT},
    // Block
    {DW_FORM_block1,       EDwarfFormClass::BLOCK},
    {DW_FORM_block2,       EDwarfFormClass::BLOCK},
    {DW_FORM_block4,       EDwarfFormClass::BLOCK},
    {DW_FORM_block,        EDwarfFormClass::BLOCK},
    // Exprloc
    {DW_FORM_exprloc,      EDwarfFormClass::EXPRLOC}
    // Flag
};


static const std::map<EDwarfFormClass, DFInstanceFunction> s_formInstanceMap {
    #define DFORM(a,b) {EDwarfFormClass::a, [](Dwarf_Attribute d_attr){\
        return new b(d_attr);}},

    DFORM(REFERENCE, GlobalRefDwarfForm)
    DFORM(ADDR,      AddrDwarfForm)
    DFORM(STRING,    StringDwarfForm)
    DFORM(CONSTANT,  ConstantDwarfForm)
    DFORM(BLOCK,     BlockDwarfForm)
    DFORM(EXPRLOC,   ExprlocDwarfForm)

    #undef DFORM
};


/**
 * @return Returns nullptr if something goes wrong (e.g. unsupported DW_FORM_*).
 *
 */
DwarfForm*
Dwarf::createDwarfForm(Dwarf_Attribute d_attr)
{
    DwarfForm* dwForm = nullptr;

    do {
        Dwarf_Half formType;

        if (dwarf_whatform(d_attr, &formType, nullptr) != DW_DLV_OK) {
            break;
        }

        auto it1 = s_formMap.find(formType);
        if (it1 == s_formMap.end()) {
            break;
        }

        auto it2 = s_formInstanceMap.find(it1->second);
        if (it2 == s_formInstanceMap.end()) {
            break;
        }

        dwForm = it2->second(d_attr);
    } while (false);

    return dwForm;
}
/******************************************************************************/


DwarfForm::DwarfForm(Dwarf_Attribute d_attr, EDwarfFormClass formClass)
    : m_formClass(EDwarfFormClass::UNKNOWN),
      m_isValid(false)
{
    // Check form type in case a derived class is not instantiated in
    // createDwarfForm().
    Dwarf_Half formType;
    if (dwarf_whatform(d_attr, &formType, nullptr) != DW_DLV_OK) {
        return;
    }

    auto it = s_formMap.find(formType);
    if (it == s_formMap.end()) {
        return;
    }

    if (it->second != formClass) {
        return;
    }
    else {
        m_formClass = formClass;
    }

    m_formType = formType;
    setValidity(true);
}


DwarfForm::~DwarfForm()
{
}


void
DwarfForm::setValidity(bool value)
{
    m_isValid = value;
}


bool
DwarfForm::isValid()
{
    return m_isValid;
}



EDwarfFormClass
DwarfForm::getFormClass()
{
    return m_formClass;
}

// Derived classes

/******************************************************************************/

/******************
 * Reference form *
 ******************/
GlobalRefDwarfForm::GlobalRefDwarfForm(Dwarf_Attribute d_attr)
    : DwarfForm(d_attr, EDwarfFormClass::REFERENCE)
{
    if (!isValid()) {
        return;
    }

    if (dwarf_global_formref(d_attr, &m_sectionOffset, nullptr) != DW_DLV_OK) {
        setValidity(false);
        return;
    }
}


std::string
GlobalRefDwarfForm::getValueAsString()
{
    if (isValid()) {
        return std::to_string(m_sectionOffset);
    }
    else {
        return "";
    }
}


Dwarf_Off
GlobalRefDwarfForm::getOffset() const
{
    return m_sectionOffset;
}

/******************************************************************************/

/******************************************************************************/

/****************
 * Address Form *
 ****************/

AddrDwarfForm::AddrDwarfForm(Dwarf_Attribute d_attr)
    : DwarfForm(d_attr, EDwarfFormClass::ADDR)
{
    if (!isValid()) {
        return;
    }

    if (dwarf_formaddr(d_attr, &m_addr, nullptr) != DW_DLV_OK) {
        setValidity(false);
        return;
    }
}


std::string
AddrDwarfForm::getValueAsString()
{
    return std::to_string(m_addr);
}
/******************************************************************************/

/******************************************************************************/

/***************
 * String Form *
 ***************/

StringDwarfForm::StringDwarfForm(Dwarf_Attribute d_attr)
    : DwarfForm(d_attr, EDwarfFormClass::STRING)
{
    if (!isValid()) {
        return;
    }

    char* d_str;
    if (dwarf_formstring(d_attr, &d_str, nullptr) != DW_DLV_OK) {
        setValidity(false);
        return;
    }

    // Copy string
    m_str = std::string(d_str);
}

std::string
StringDwarfForm::getValueAsString()
{
    return m_str;
}

/******************************************************************************/

/*****************
 * Constant Form *
 *****************/

ConstantDwarfForm::ConstantDwarfForm(Dwarf_Attribute d_attr)
    : DwarfForm(d_attr, EDwarfFormClass::CONSTANT)
{
    if (!isValid()) {
        return;
    }

    do {
        // m_sign : 2 -> signed, 1 -> unsigned, 0 -> unspecified
        if (m_formType == DW_FORM_sdata) {
            m_sign = 2;
            if (dwarf_formsdata(d_attr, &m_sValue, nullptr) != DW_DLV_OK) {
                setValidity(false);
                break;
            }
        }
        else if (m_formType == DW_FORM_udata) {
            m_sign = 1;
            if (dwarf_formudata(d_attr, &m_uValue, nullptr) != DW_DLV_OK) {
                setValidity(false);
                break;
            }
        }
        else {
            m_sign = 0;
            if (dwarf_formsdata(d_attr, &m_sValue, nullptr) != DW_DLV_OK) {
                setValidity(false);
                break;
            }
            if (dwarf_formudata(d_attr, &m_uValue, nullptr) != DW_DLV_OK) {
                setValidity(false);
                break;
            }
        }
    } while (false);
}


std::string
ConstantDwarfForm::getValueAsString()
{
    std::string retStr;

    switch (m_sign) {
        case 2:
            retStr = "S_" + std::to_string(m_sValue);
            break;
        case 1:
            retStr = "U_" + std::to_string(m_uValue);
            break;
        case 0:
            retStr = "S_"  + std::to_string(m_sValue) +
                     "_U_" + std::to_string(m_uValue);
            break;
        default:
            retStr = "";
    }

    return retStr;
}


Dwarf_Unsigned
ConstantDwarfForm::getUnsigned() const
{
    return m_uValue;
}


Dwarf_Signed
ConstantDwarfForm::getSigned() const
{
    return m_sValue;
}

/******************************************************************************/

/**************
 * Block Form *
 **************/

BlockDwarfForm::BlockDwarfForm(Dwarf_Attribute d_attr)
    : DwarfForm(d_attr, EDwarfFormClass::BLOCK),
      m_dwBlock(nullptr)
{
    if (!isValid()) {
        return;
    }

    Dwarf_Block* d_dwBlock = nullptr;

    if (dwarf_formblock(d_attr, &d_dwBlock, nullptr) != DW_DLV_OK) {
        setValidity(false);
        return;
    }

    m_dwBlock.reset(new DwarfBlock(d_dwBlock));
}


std::string
BlockDwarfForm::getValueAsString()
{
    if (isValid()) {
        return m_dwBlock->getRawHexString();
    }
    else {
        return "";
    }
}

/******************************************************************************/
DwarfBlock::DwarfBlock(Dwarf_Block* dwBlock)
    : m_blockData(nullptr),
      m_blockLen(0)
{
    assert(dwBlock != nullptr);
    assert(dwBlock->bl_data != nullptr);
    assert(dwBlock->bl_len > 0);

    m_blockLen = dwBlock->bl_len;

    // Allocate memory
    m_blockData.reset(new blockdata_t(m_blockLen));
    assert(m_blockData.get() != nullptr);

    // Copy buffer
    std::memcpy(m_blockData.get()->data(), dwBlock->bl_data, m_blockLen);
}


std::shared_ptr<DwarfBlock::blockdata_t>
DwarfBlock::getDataPtr()
{
    return std::shared_ptr<blockdata_t>(m_blockData);
}


uint64_t
DwarfBlock::getLength()
{
    return m_blockLen;
}


std::string
DwarfBlock::getRawHexString()
{
    // Return the byte vector as hex string
    std::stringstream ss;

    ss << std::hex << std::setfill('0');

    for (uint64_t i=0; i<m_blockLen; i++)
    {
        // Cast it to unsigned, else ss outputs rubbish
        const blockdata_t* data = m_blockData.get();
        ss << std::setw(2) << (unsigned)((*data)[i]) << " ";
    }

    return ss.str();
}

/******************************************************************************/

/****************
 * Exprloc Form *
 ****************/

ExprlocDwarfForm::ExprlocDwarfForm(Dwarf_Attribute d_attr)
    : DwarfForm(d_attr, EDwarfFormClass::EXPRLOC),
      m_dwBlock(nullptr)
{
    if (!isValid()) {
        return;
    }

    Dwarf_Block d_dwBlock;

    if (dwarf_formexprloc(d_attr, &d_dwBlock.bl_len, &d_dwBlock.bl_data, nullptr)
        != DW_DLV_OK)
    {
        setValidity(false);
        return;
    }

    m_dwBlock.reset(new DwarfBlock(&d_dwBlock));
}


std::string
ExprlocDwarfForm::getValueAsString()
{
    return "Found Exprloc FORM." + m_dwBlock->getRawHexString();
}
