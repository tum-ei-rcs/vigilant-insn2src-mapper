#include "bincfg/dwarf/DwarfDie.hpp"

using Log = bcfg::Log;

/**
 * @note To be deleted, for debugging only.
 */
static void
printDieAttributes(Dwarf_Off dieOff, AttrSet& dieAttrs,
                   Dwarf_Half tagValue)
{
    if (dieAttrs.size() == 0) {
        Log::log() << "DIE @0x" << std::hex << dieOff << " contains no "
                   << "decoded attributes."
                   << ELogLevel::LOG_DEBUG; 
        return;
    }

    Log::log() << "[0x" << std::hex << dieOff << "]<"
               << Dwarf::getTagType(tagValue) << ">:"
               << ELogLevel::LOG_DEBUG;

    for (auto& attr: dieAttrs)
    {
        Log::log() << "   <" << Dwarf::getAttrType(attr->getType()) << ">: "
                   << attr->getValueAsString()
                   << ELogLevel::LOG_DEBUG;
    }
}

/******************************************************************************/

/************
 * DwarfDie *
 ************/

DwarfDie::DwarfDie(Dwarf_Debug d_debug, Dwarf_Die d_inDie, Dwarf_Off parentOffset,
                   bool findChildren)
    : m_parentOffset(parentOffset),
      m_isValid(false),
      m_isInfo(false)
{
    do {
        // Which section does the DIE originate from (.debug_info or .debug_types)
        if (dwarf_get_die_infotypes_flag(d_inDie)) {
            m_isInfo = true;
        }

        // Get DIE version and offset size
        if (dwarf_get_version_of_die(d_inDie, &m_dieVersion, &m_dieOffsetSize)
            != DW_DLV_OK)
        {
            break;
        }

        // Read die offset
        if (dwarf_dieoffset(d_inDie, &m_dieOffset, nullptr) != DW_DLV_OK) {
            break;
        }

        // Read die tag value
        if (dwarf_tag(d_inDie, &m_tagValue, nullptr) != DW_DLV_OK) {
            Log::log() << "Cannot read die tag."
                       << ELogLevel::LOG_ERROR;
            break;
        }

        // Read attributes
        if (!readAttributes(d_debug, d_inDie)) {
            Log::log() << "Could not read attributes."
                       << ELogLevel::LOG_ERROR;
            break;
        }

        // Find die children, this will construct DwarfDies recursively
        if (findChildren) {
            if (!findDieChildren(d_debug, d_inDie)) {
                Log::log() << "Error while processing children of die @0x"
                           << std::hex << m_dieOffset << "."
                           << ELogLevel::LOG_ERROR;
                break;
            }
        }

        //printDieAttributes(m_dieOffset, m_attrs, m_tagValue);

        // Set validity
        m_isValid = true;
    } while (false);
}


bool
DwarfDie::readAttributes(Dwarf_Debug d_debug, Dwarf_Die d_inDie)
{
    bool status = false;
    m_attrs = Dwarf::getAttributes(d_debug, d_inDie, status);

    return status;
}


/**
 * @todo Implement dwarf_validate_die_sibling() to validate the depth-first
 *       tree walk.
 * 
 */
bool
DwarfDie::findDieChildren(Dwarf_Debug d_debug, Dwarf_Die d_inDie)
{
    Dwarf_Die currDie;
    Dwarf_Die currSib;
    bool      status = false;

    do {
        // Get the first child
        int result = dwarf_child(d_inDie, &currSib, nullptr);
        if (result != DW_DLV_OK) {
            if (result == DW_DLV_NO_ENTRY) {
                // No children found for the given DIE.
                status = true;
            }
            break;
        }

        // Get all siblings of the first child. Note that if we land here,
        // result is equal to DW_DLV_OK.
        while (result == DW_DLV_OK)
        {
            currDie = currSib;
            
            DwarfDie dwDie = DwarfDie(d_debug, currDie, m_dieOffset);
            if (!dwDie.isValid()) {
                Log::log() << "An error occurred while processing DIE @0x"
                           << std::hex << dwDie.getOffset()
                           << ELogLevel::LOG_ERROR;
                break;
            } 

            m_dieChildren.push_back(std::move(dwDie));
            result = dwarf_siblingof_b(d_debug, currDie, m_isInfo, &currSib, nullptr);
        }

        // Check result, if not equal to DW_DLV_NO_ENTRY, then an error has occurred.
        if (result == DW_DLV_NO_ENTRY) {
            status = true;
        }
    } while (false);

    return status;
}


const std::vector<DwarfDie>&
DwarfDie::getChildren() const
{
    return m_dieChildren;
}


const AttrSet&
DwarfDie::getAttributes() const
{
    return m_attrs;
}


Dwarf_Off
DwarfDie::getOffset() const
{
    return m_dieOffset;
}


Dwarf_Off
DwarfDie::getParentOffset() const
{
    return m_parentOffset;
}


Dwarf_Half
DwarfDie::getTagValue() const
{
    return m_tagValue;
}


Dwarf_Half
DwarfDie::getDieVersion() const
{
    return m_dieVersion;
}


Dwarf_Half
DwarfDie::getDieOffsetSize() const
{
    return m_dieOffsetSize;
}


bool
DwarfDie::isValid() const
{
    return m_isValid;
}

/******************************************************************************/

// grep from dwarf.h
static const std::map<Dwarf_Half, const std::string> s_tagStrings {
    #define TSTR(a) {DW_TAG_##a, "DW_TAG_" #a},

        TSTR(array_type) 
        TSTR(class_type) 
        TSTR(entry_point) 
        TSTR(enumeration_type) 
        TSTR(formal_parameter) 
        TSTR(imported_declaration) 
        TSTR(label) 
        TSTR(lexical_block) 
        TSTR(member) 
        TSTR(pointer_type) 
        TSTR(reference_type) 
        TSTR(compile_unit) 
        TSTR(string_type) 
        TSTR(structure_type) 
        TSTR(subroutine_type) 
        TSTR(typedef) 
        TSTR(union_type) 
        TSTR(unspecified_parameters) 
        TSTR(variant) 
        TSTR(common_block) 
        TSTR(common_inclusion) 
        TSTR(inheritance) 
        TSTR(inlined_subroutine) 
        TSTR(module) 
        TSTR(ptr_to_member_type) 
        TSTR(set_type) 
        TSTR(subrange_type) 
        TSTR(with_stmt) 
        TSTR(access_declaration) 
        TSTR(base_type) 
        TSTR(catch_block) 
        TSTR(const_type) 
        TSTR(constant) 
        TSTR(enumerator) 
        TSTR(file_type) 
        TSTR(friend) 
        TSTR(namelist) 
        TSTR(namelist_item) 
        TSTR(namelist_items) 
        TSTR(packed_type) 
        TSTR(subprogram) 
        TSTR(template_type_parameter) 
        TSTR(template_type_param) 
        TSTR(template_value_parameter) 
        TSTR(template_value_param) 
        TSTR(thrown_type) 
        TSTR(try_block) 
        TSTR(variant_part) 
        TSTR(variable) 
        TSTR(volatile_type) 
        TSTR(dwarf_procedure) 
        TSTR(restrict_type) 
        TSTR(interface_type) 
        TSTR(namespace) 
        TSTR(imported_module) 
        TSTR(unspecified_type) 
        TSTR(partial_unit) 
        TSTR(imported_unit) 
        TSTR(mutable_type) 
        TSTR(condition) 
        TSTR(shared_type) 
        TSTR(type_unit) 
        TSTR(rvalue_reference_type) 
        TSTR(template_alias) 
        TSTR(coarray_type) 
        TSTR(generic_subrange) 
        TSTR(dynamic_type) 
        TSTR(atomic_type) 
        TSTR(call_site) 
        TSTR(call_site_parameter) 
        TSTR(skeleton_unit) 
        TSTR(immutable_type) 
        TSTR(lo_user) 
        TSTR(MIPS_loop) 
        TSTR(HP_array_descriptor) 
        TSTR(format_label) 
        TSTR(function_template) 
        TSTR(class_template) 
        TSTR(GNU_BINCL) 
        TSTR(GNU_EINCL) 
        TSTR(GNU_template_template_parameter) 
        TSTR(GNU_template_template_param) 
        TSTR(GNU_template_parameter_pack) 
        TSTR(GNU_formal_parameter_pack) 
        TSTR(GNU_call_site) 
        TSTR(GNU_call_site_parameter) 
        TSTR(ALTIUM_circ_type) 
        TSTR(ALTIUM_mwa_circ_type) 
        TSTR(ALTIUM_rev_carry_type) 
        TSTR(ALTIUM_rom) 
        TSTR(upc_shared_type) 
        TSTR(upc_strict_type) 
        TSTR(upc_relaxed_type) 
        TSTR(PGI_kanji_type) 
        TSTR(PGI_interface_block) 
        TSTR(SUN_function_template) 
        TSTR(SUN_class_template) 
        TSTR(SUN_struct_template) 
        TSTR(SUN_union_template) 
        TSTR(SUN_indirect_inheritance) 
        TSTR(SUN_codeflags) 
        TSTR(SUN_memop_info) 
        TSTR(SUN_omp_child_func) 
        TSTR(SUN_rtti_descriptor) 
        TSTR(SUN_dtor_info) 
        TSTR(SUN_dtor) 
        TSTR(SUN_f90_interface) 
        TSTR(SUN_fortran_vax_structure) 
        TSTR(SUN_hi) 
        TSTR(hi_user)
 
    #undef TSTR
};


const std::string&
Dwarf::getTagType(Dwarf_Half tagType)
{
    static const std::string unknownType = "UNKNOWN_TAG";

    auto it = s_tagStrings.find(tagType);
    if (it != s_tagStrings.end()) {
        return it->second;
    }
    else {
        return unknownType;
    }
}


