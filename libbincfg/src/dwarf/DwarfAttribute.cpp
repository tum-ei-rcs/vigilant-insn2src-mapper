#include "bincfg/dwarf/DwarfAttribute.hpp"
#include <algorithm>
#include <sstream>


using Log = bcfg::Log;


/******************************************************************************/

/*************
 * DwarfAttr *
 *************/
DwarfAttr::DwarfAttr(Dwarf_Attribute d_attr)
    : m_type(0),
      m_form(nullptr),
      m_isValid(false)
{
    do {
        if (dwarf_whatattr(d_attr, &m_type, nullptr) != DW_DLV_OK) {
            break;
        }

        m_form.reset(Dwarf::createDwarfForm(d_attr));
        if (m_form.get() == nullptr) {
            break;
        }
        if (!m_form->isValid()) {
            break;
        }

        m_isValid = true;
    } while (false);
}


bool
DwarfAttr::isValid() const
{
    return m_isValid;
}


std::string
DwarfAttr::getValueAsString() const
{
    return m_form->getValueAsString();
}


Dwarf_Half
DwarfAttr::getType() const
{
    return m_type;
}


bool operator< (const DwarfAttr& lhs, const DwarfAttr& rhs)
{
    return lhs.m_type < rhs.m_type;
}


/****************
 * LocDwarfAttr *
 ****************/
LocDwarfAttr::LocDwarfAttr(Dwarf_Debug d_debug, Dwarf_Attribute d_attr)
    : DwarfAttr(d_attr)
{
    if(!m_isValid) {
        return;
    }

    do {
        Dwarf_Loc_Head_c d_loclistHead;
        Dwarf_Unsigned   d_loclistCount;

        if (dwarf_get_loclist_c(d_attr, &d_loclistHead, &d_loclistCount, nullptr)
            != DW_DLV_OK)
        {
            m_isValid = false;
            break;
        }

        if (d_loclistCount < 1) {
            break;
        }
        else {
            m_locEntries.reserve(d_loclistCount);
        }

        bool errorStatus = false;
        for (uint64_t i = 0; i < d_loclistCount; ++i)
        {
            DwarfLocEntry dwLocEntry = DwarfLocEntry(d_loclistHead, i);
            
            if (!dwLocEntry.isValid()) {
                errorStatus = true;
                break;
            }

            m_locEntries.push_back(std::move(dwLocEntry));
        }

        if (errorStatus) {
            m_isValid = false;
            break;
        }
    } while (false);
}


std::string
LocDwarfAttr::getValueAsString() const
{
    std::stringstream ss;
    const std::string empty("NO_ENTRIES");

    if (m_locEntries.empty()) {
        return empty;
    }

    for (const DwarfLocEntry& locEntry: m_locEntries)
    {
        ss << locEntry.getEntryAsString() << ";";
    }

    return ss.str();
}

/******************************************************************************/

/******************************************************************************/

RangeDwarfAttr::RangeDwarfAttr(Dwarf_Debug d_debug, Dwarf_Attribute d_attr)
    : DwarfAttr(d_attr)
{
    if(!m_isValid) {
        return;
    }

    bool status = false;
    do {
        if (m_form->getFormClass() != EDwarfFormClass::CONSTANT &&
            m_form->getFormClass() != EDwarfFormClass::REFERENCE)
        {
            Log::log() << "Invalid form class for DW_AT_ranges attribute."
                       << ELogLevel::LOG_ERROR;
            break;
        }
        
        // Dwarf_Off is the same as Dwarf_Unsigned
        Dwarf_Off      d_rangeOffset;
        Dwarf_Die      d_die         = nullptr;
        Dwarf_Ranges*  d_ranges      = nullptr;
        Dwarf_Signed   d_rangeCount  = 0;
        Dwarf_Unsigned d_byteCount   = 0;

        // Get offset from base class, cast the dwarf form to ConstantDwarfForm
        if (m_form->getFormClass() == EDwarfFormClass::CONSTANT) {
            ConstantDwarfForm* cdwForm = dynamic_cast<ConstantDwarfForm*>(m_form.get());
            if (cdwForm == nullptr) {
                Log::log() << "Invalid form cast for DW_AT_ranges attribute."
                        << ELogLevel::LOG_ERROR;
                break;
            }
            d_rangeOffset = cdwForm->getUnsigned();
        }

        if (m_form->getFormClass() == EDwarfFormClass::REFERENCE) {
            GlobalRefDwarfForm* rdwForm = dynamic_cast<GlobalRefDwarfForm*>(m_form.get());
            if (rdwForm == nullptr) {
                Log::log() << "Invalid form cast for DW_AT_ranges attribute."
                           << ELogLevel::LOG_ERROR;
                break;
            }
            d_rangeOffset = rdwForm->getOffset();
        }

        // Get ranges
        int result = dwarf_get_ranges_a(d_debug, d_rangeOffset, d_die,
                                        &d_ranges, &d_rangeCount,
                                        &d_byteCount, nullptr);
        if (result != DW_DLV_OK) {
            Log::log() << "Could not read ranges for DW_AT_ranges attribute"
                       << ELogLevel::LOG_ERROR;
            break;
        }

        m_rangeEntries = std::vector<RangeEntry>(d_rangeCount);

        for (int i = 0; i < d_rangeCount; ++i)
        {
            RangeEntry& rEntry = m_rangeEntries[i];
            
            rEntry.low  = d_ranges[i].dwr_addr1;
            rEntry.high = d_ranges[i].dwr_addr2;
        }

        // Deallocate here, since we have a pointer to Dwarf_Debug instance.
        dwarf_ranges_dealloc(d_debug, d_ranges, d_rangeCount);

        status = true;
    } while (false);

    m_isValid = status;
}


std::string
RangeDwarfAttr::getValueAsString() const
{
    std::stringstream ss;
    const std::string empty = "NO_ENTRIES";

    if (m_rangeEntries.empty()) {
        return empty;
    }

    for (auto& entry: m_rangeEntries) {
        ss << "[" << entry.getEntryAsString() << "];";
    }

    return ss.str();
}


/******************************************************************************/
/**
 * 
 * @fixme Add the remaining OP's.
 * @fixme Use switch, group conditions with the same body together.
 */
std::string
DwarfOperator::getOpAsString() const
{
    std::stringstream ss;
    const std::string opName(Dwarf::getOpType(d_atom));
    const std::string notImpl("NOT_IMPLEMENTED");

    assert(ss.str() != "UNKNOWN_OP");

    auto output_0 = [&]() {
        ss << opName;
    };
    
    auto outputu = [&]() {
        ss << opName << d_operand1;
    };

    auto output_u = [&]() {
        ss << opName << ":" << d_operand1;
    };

    auto output_s = [&]() {
        ss << opName << ":" << (Dwarf_Signed)d_operand1;
    };

    auto outputu_s = [&]() {
        ss << opName << d_operand1 << ":" << (Dwarf_Signed)d_operand2;
    };

    do {
        // DW_OP_addr; DW_OP_piece
        if ( (d_atom == DW_OP_addr) ||
             (d_atom == DW_OP_piece) )
        {
            output_u();
            break;
        }
        
        // DW_OP_breg<n>, n=0,..,31; DW_OP_fbreg
        if ( (d_atom >= DW_OP_breg0 && d_atom <= DW_OP_breg31) ||
             (d_atom == DW_OP_fbreg) )
        {
            output_s();
            break;
        }

        // DW_OP_reg; DW_OP_lit
        if ( (d_atom >= DW_OP_reg0 && d_atom <= DW_OP_reg31) ||
             (d_atom >= DW_OP_lit0 && d_atom <= DW_OP_lit31) )
        {
            output_0();
            break;
        }

        // DW_OP_regx
        if (d_atom == DW_OP_regx) {
            outputu();
            break;
        }

        // DW_OP_bregx has two operands
        if (d_atom == DW_OP_bregx) {
            outputu_s();
            break;
        }
    } while (false);

    if (ss.str() == "") {
        return notImpl;
    }
    else {
        return ss.str();
    }
}

/******************************************************************************/

DwarfLocEntry::DwarfLocEntry(Dwarf_Loc_Head_c d_loclistHead, Dwarf_Unsigned index)
    : m_isValid(false)
{
    DwarfLocDescEntry lde;
            
    if (dwarf_get_locdesc_entry_c(d_loclistHead, index,
            &lde.d_lleVal, &lde.d_lowPc, &lde.d_highPc, &lde.d_loclistCount,
            &lde.d_locEntry, &lde.d_loclistSource, &lde.d_exprOffset,
            &lde.d_locdescOffset, nullptr)
        != DW_DLV_OK)
    {
        return;
    }

    m_operators = std::vector<DwarfOperator>(lde.d_loclistCount);

    bool errorStatus = false;
    for (uint64_t i = 0; i < lde.d_loclistCount; ++i)
    {
        DwarfOperator& dwo = m_operators[i];

        if (dwarf_get_location_op_value_c(lde.d_locEntry, i,
                &dwo.d_atom, &dwo.d_operand1, &dwo.d_operand2, &dwo.d_operand3,
                &dwo.d_offsetBranch, nullptr)
            != DW_DLV_OK)
        {
            errorStatus = true;
            break;
        }
    }

    if (!errorStatus) {
        m_isValid = true;
    }
}


bool
DwarfLocEntry::isValid() const
{
    return m_isValid;
}


const std::vector<DwarfOperator>&
DwarfLocEntry::getOperators() const
{
    return m_operators;
}


std::string
DwarfLocEntry::getEntryAsString() const
{
    std::stringstream ss;

    ss << "[";

    for (const DwarfOperator& dwOp: m_operators)
    {
        ss << dwOp.getOpAsString() << ",";
    }

    ss << "]";

    return ss.str();
}

/******************************************************************************/



/******************************************************************************/

/**************************
 * DIE Attribute Handling *
 **************************/

using DieAttrValidator = std::function<bool(const AttrSet&)>;
using DAInstance       = std::function<DwarfAttr*(Dwarf_Debug, Dwarf_Attribute)>;

static bool validateDieAttrs(Dwarf_Die d_inDie, const AttrSet& attrSet);
static bool subprogramDieValidator(const AttrSet& attrSet);
static bool inlinedsubDieValidator(const AttrSet& attrSet);

static const std::map<Dwarf_Half, DieAttrValidator> s_dieValidatorMap {
    {DW_TAG_subprogram,         subprogramDieValidator},
    {DW_TAG_inlined_subroutine, inlinedsubDieValidator}
};

static const std::map<Dwarf_Half, DAInstance> s_attrInstanceMap {
    #define DINST(a,b) {DW_AT_##a, [](Dwarf_Debug d_debug, Dwarf_Attribute d_attr){\
        return new b(d_debug, d_attr);}},

    DINST(location, LocDwarfAttr)
    DINST(ranges,   RangeDwarfAttr)

    #undef DINST
};

static DwarfAttr* readAttribute(Dwarf_Debug d_debug, Dwarf_Attribute d_attr,
                                bool& status);
static bool       hasAttributes(Dwarf_Half d_attrType, const AttrSet& attrSet1,
                                const AttrSet& attrSet2);


/**
 * 
 * @return Returns false if either validation failed or an error occurred in
 *         libdwarf.
 */
static bool
validateDieAttrs(Dwarf_Die d_inDie, const AttrSet& attrSet)
{
    // Get DIE tag
    Dwarf_Half d_tagValue;
    if (dwarf_tag(d_inDie, &d_tagValue, nullptr) != DW_DLV_OK) {
        Log::log() << "Could not get tag value"
                   << ELogLevel::LOG_ERROR;
        return false;
    }

    // Get DIE validator
    auto it = s_dieValidatorMap.find(d_tagValue);
    if (it != s_dieValidatorMap.end()) {
        return it->second(attrSet);
    }
    else {
        return true;
    }
}


static bool
subprogramDieValidator(const AttrSet& attrSet)
{
    return true;
}

static bool
inlinedsubDieValidator(const AttrSet& attrSet)
{
    return true;
}


/**
 * @brief Reads the given Dwarf_Attr instance.
 *
 * 
 * @note DwarfAttr is invalidated in case an error occurrs while reading the
 *       attribute.
 */
static DwarfAttr*
readAttribute(Dwarf_Debug d_debug, Dwarf_Attribute d_attr, bool& status)
{
    Dwarf_Half attrType;

    if (dwarf_whatattr(d_attr, &attrType, nullptr) != DW_DLV_OK) {
        status = false;
        Log::log() << "dwarf_whatattr failed."
                   << ELogLevel::LOG_ERROR;
    }
    else {
        status = true;
    }

    auto it = s_attrInstanceMap.find(attrType);
    if (it != s_attrInstanceMap.end()) {
        return it->second(d_debug, d_attr);
    }
    else {
        return new DwarfAttr(d_attr);
    }
}


static bool
hasAttributes(Dwarf_Half d_attrType, const AttrSet& attrSet1, const AttrSet& attrSet2)
{
    return false;
}


/**
 * @brief Reads the attributes of the given Dwarf_Die.
 * 
 *
 * @note An attribute is not added to the set if an error occurs in libdwarf
 *       (readAttribute() scope) or it possesses an invalid DwarfForm.
 * 
 * @note status is set to false if either DIE validation failed or an 
 *       internal libdwarf error occurred in this function (local scope).
 */
AttrSet
Dwarf::getAttributes(Dwarf_Debug d_debug, Dwarf_Die d_inDie, bool& status)
{
    AttrSet dwAttrs;

    bool _status = false;

    do {
        Dwarf_Attribute* d_attrs;
        Dwarf_Signed     d_attrCount;
        Dwarf_Off        d_dieOffset;

        if (dwarf_dieoffset(d_inDie, &d_dieOffset, nullptr) != DW_DLV_OK) {
            Log::log() << "Error getting DIE offset"
                       << ELogLevel::LOG_ERROR;
            break;
        }

        if (dwarf_attrlist(d_inDie, &d_attrs, &d_attrCount, nullptr) != DW_DLV_OK) {
            Log::log() << "Error getting attribute list."
                       << ELogLevel::LOG_ERROR;
            break;       
        }

        AttrSet::iterator lastIt = dwAttrs.end();

        for (int i = 0; i < d_attrCount; ++i)
        {
            // readAttribute is a factory method
            bool       readStatus = false;
            DwarfAttr* dwAttrPtr  = readAttribute(d_debug, d_attrs[i], readStatus);

            // Log error (libdwarf func failed) and continue, don't add to set. 
            if (!readStatus) {
                Log::log() << "Error while reading attribute in DIE @0x" << std::hex
                           << d_dieOffset << "."
                           << ELogLevel::LOG_ERROR;
                delete dwAttrPtr;
                continue;
            }

            // Either an internal libdwarf error occurred or this attribute has
            // an invalid DwarfForm.
            if (!dwAttrPtr->isValid()) {
                Log::log() << "Could not read attribute "
                           << Dwarf::getAttrType(dwAttrPtr->getType())
                           << " in DIE @0x" << std::hex << d_dieOffset
                           << ELogLevel::LOG_ERROR;
                delete dwAttrPtr;
                continue;
            }

            lastIt = dwAttrs.insert(lastIt, AttrUniquePtr(dwAttrPtr));
        }

        // Validate DIE
        bool isValidDie = validateDieAttrs(d_inDie, dwAttrs);
        if (!isValidDie) {
            Log::log() << "Could not validate attributes for DIE @0x" << std::hex
                       << d_dieOffset << "."
                       << ELogLevel::LOG_WARNING;
        }

        if (isValidDie) {
            _status = true;
        }
    } while (false);

    status = _status;
    return dwAttrs;
}
/******************************************************************************/


static const std::map<Dwarf_Half, const std::string> s_attrStrings {
    #define ASTR(a) {DW_AT_##a, "DW_AT_" #a},

        ASTR(sibling) 
        ASTR(location) 
        ASTR(name) 
        ASTR(ordering) 
        ASTR(subscr_data) 
        ASTR(byte_size) 
        ASTR(bit_offset) 
        ASTR(bit_size) 
        ASTR(element_list) 
        ASTR(stmt_list) 
        ASTR(low_pc) 
        ASTR(high_pc) 
        ASTR(language) 
        ASTR(member) 
        ASTR(discr) 
        ASTR(discr_value) 
        ASTR(visibility) 
        ASTR(import) 
        ASTR(string_length) 
        ASTR(common_reference) 
        ASTR(comp_dir) 
        ASTR(const_value) 
        ASTR(containing_type) 
        ASTR(default_value) 
        ASTR(inline) 
        ASTR(is_optional) 
        ASTR(lower_bound) 
        ASTR(producer) 
        ASTR(prototyped) 
        ASTR(return_addr) 
        ASTR(start_scope) 
        ASTR(bit_stride) 
        ASTR(stride_size) 
        ASTR(upper_bound) 
        ASTR(abstract_origin) 
        ASTR(accessibility) 
        ASTR(address_class) 
        ASTR(artificial) 
        ASTR(base_types) 
        ASTR(calling_convention) 
        ASTR(count) 
        ASTR(data_member_location) 
        ASTR(decl_column) 
        ASTR(decl_file) 
        ASTR(decl_line) 
        ASTR(declaration) 
        ASTR(discr_list) 
        ASTR(encoding) 
        ASTR(external) 
        ASTR(frame_base) 
        ASTR(friend) 
        ASTR(identifier_case) 
        ASTR(macro_info) 
        ASTR(namelist_item) 
        ASTR(priority) 
        ASTR(segment) 
        ASTR(specification) 
        ASTR(static_link) 
        ASTR(type) 
        ASTR(use_location) 
        ASTR(variable_parameter) 
        ASTR(virtuality) 
        ASTR(vtable_elem_location) 
        ASTR(allocated) 
        ASTR(associated) 
        ASTR(data_location) 
        ASTR(byte_stride) 
        ASTR(stride) 
        ASTR(entry_pc) 
        ASTR(use_UTF8) 
        ASTR(extension) 
        ASTR(ranges) 
        ASTR(trampoline) 
        ASTR(call_column) 
        ASTR(call_file) 
        ASTR(call_line) 
        ASTR(description) 
        ASTR(binary_scale) 
        ASTR(decimal_scale) 
        ASTR(small) 
        ASTR(decimal_sign) 
        ASTR(digit_count) 
        ASTR(picture_string) 
        ASTR(mutable) 
        ASTR(threads_scaled) 
        ASTR(explicit) 
        ASTR(object_pointer) 
        ASTR(endianity) 
        ASTR(elemental) 
        ASTR(pure) 
        ASTR(recursive) 
        ASTR(signature) 
        ASTR(main_subprogram) 
        ASTR(data_bit_offset) 
        ASTR(const_expr) 
        ASTR(enum_class) 
        ASTR(linkage_name) 
        ASTR(string_length_bit_size) 
        ASTR(string_length_byte_size) 
        ASTR(rank) 
        ASTR(str_offsets_base) 
        ASTR(addr_base) 
        ASTR(rnglists_base) 
        ASTR(dwo_id) 
        ASTR(dwo_name) 
        ASTR(reference) 
        ASTR(rvalue_reference) 
        ASTR(macros) 
        ASTR(call_all_calls) 
        ASTR(call_all_source_calls) 
        ASTR(call_all_tail_calls) 
        ASTR(call_return_pc) 
        ASTR(call_value) 
        ASTR(call_origin) 
        ASTR(call_parameter) 
        ASTR(call_pc) 
        ASTR(call_tail_call) 
        ASTR(call_target) 
        ASTR(call_target_clobbered) 
        ASTR(call_data_location) 
        ASTR(call_data_value) 
        ASTR(noreturn) 
        ASTR(alignment) 
        ASTR(export_symbols) 
        ASTR(deleted) 
        ASTR(defaulted) 
        ASTR(loclists_base) 
        ASTR(HP_block_index) 
        ASTR(lo_user) 
        ASTR(MIPS_fde) 
        ASTR(MIPS_loop_begin) 
        ASTR(MIPS_tail_loop_begin) 
        ASTR(MIPS_epilog_begin) 
        ASTR(MIPS_loop_unroll_factor) 
        ASTR(MIPS_software_pipeline_depth) 
        ASTR(MIPS_linkage_name) 
        ASTR(MIPS_stride) 
        ASTR(MIPS_abstract_name) 
        ASTR(MIPS_clone_origin) 
        ASTR(MIPS_has_inlines) 
        ASTR(MIPS_stride_byte) 
        ASTR(MIPS_stride_elem) 
        ASTR(MIPS_ptr_dopetype) 
        ASTR(MIPS_allocatable_dopetype) 
        ASTR(MIPS_assumed_shape_dopetype) 
        ASTR(MIPS_assumed_size) 
        ASTR(HP_unmodifiable) 
        ASTR(HP_actuals_stmt_list) 
        ASTR(HP_proc_per_section) 
        ASTR(HP_raw_data_ptr) 
        ASTR(HP_pass_by_reference) 
        ASTR(HP_opt_level) 
        ASTR(HP_prof_version_id) 
        ASTR(HP_opt_flags) 
        ASTR(HP_cold_region_low_pc) 
        ASTR(HP_cold_region_high_pc) 
        ASTR(HP_all_variables_modifiable) 
        ASTR(HP_linkage_name) 
        ASTR(HP_prof_flags) 
        ASTR(CPQ_discontig_ranges) 
        ASTR(CPQ_semantic_events) 
        ASTR(CPQ_split_lifetimes_var) 
        ASTR(CPQ_split_lifetimes_rtn) 
        ASTR(CPQ_prologue_length) 
        ASTR(INTEL_other_endian) 
        ASTR(sf_names) 
        ASTR(src_info) 
        ASTR(mac_info) 
        ASTR(src_coords) 
        ASTR(body_begin) 
        ASTR(body_end) 
        ASTR(GNU_vector) 
        ASTR(GNU_guarded_by) 
        ASTR(GNU_pt_guarded_by) 
        ASTR(GNU_guarded) 
        ASTR(GNU_pt_guarded) 
        ASTR(GNU_locks_excluded) 
        ASTR(GNU_exclusive_locks_required) 
        ASTR(GNU_shared_locks_required) 
        ASTR(GNU_odr_signature) 
        ASTR(GNU_template_name) 
        ASTR(GNU_call_site_value) 
        ASTR(GNU_call_site_data_value) 
        ASTR(GNU_call_site_target) 
        ASTR(GNU_call_site_target_clobbered) 
        ASTR(GNU_tail_call) 
        ASTR(GNU_all_tail_call_sites) 
        ASTR(GNU_all_call_sites) 
        ASTR(GNU_all_source_call_sites) 
        ASTR(GNU_macros) 
        ASTR(GNU_dwo_name) 
        ASTR(GNU_dwo_id) 
        ASTR(GNU_ranges_base) 
        ASTR(GNU_addr_base) 
        ASTR(GNU_pubnames) 
        ASTR(GNU_pubtypes) 
        ASTR(GNU_discriminator) 
        ASTR(GNU_numerator) 
        ASTR(GNU_denominator) 
        ASTR(GNU_bias) 
        ASTR(ALTIUM_loclist) 
        ASTR(SUN_template) 
        ASTR(VMS_rtnbeg_pd_address) 
        ASTR(SUN_alignment) 
        ASTR(SUN_vtable) 
        ASTR(SUN_count_guarantee) 
        ASTR(SUN_command_line) 
        ASTR(SUN_vbase) 
        ASTR(SUN_compile_options) 
        ASTR(SUN_language) 
        ASTR(SUN_browser_file) 
        ASTR(SUN_vtable_abi) 
        ASTR(SUN_func_offsets) 
        ASTR(SUN_cf_kind) 
        ASTR(SUN_vtable_index) 
        ASTR(SUN_omp_tpriv_addr) 
        ASTR(SUN_omp_child_func) 
        ASTR(SUN_func_offset) 
        ASTR(SUN_memop_type_ref) 
        ASTR(SUN_profile_id) 
        ASTR(SUN_memop_signature) 
        ASTR(SUN_obj_dir) 
        ASTR(SUN_obj_file) 
        ASTR(SUN_original_name) 
        ASTR(SUN_hwcprof_signature) 
        ASTR(SUN_amd64_parmdump) 
        ASTR(SUN_part_link_name) 
        ASTR(SUN_link_name) 
        ASTR(SUN_pass_with_const) 
        ASTR(SUN_return_with_const) 
        ASTR(SUN_import_by_name) 
        ASTR(SUN_f90_pointer) 
        ASTR(SUN_pass_by_ref) 
        ASTR(SUN_f90_allocatable) 
        ASTR(SUN_f90_assumed_shape_array) 
        ASTR(SUN_c_vla) 
        ASTR(SUN_return_value_ptr) 
        ASTR(SUN_dtor_start) 
        ASTR(SUN_dtor_length) 
        ASTR(SUN_dtor_state_initial) 
        ASTR(SUN_dtor_state_final) 
        ASTR(SUN_dtor_state_deltas) 
        ASTR(SUN_import_by_lname) 
        ASTR(SUN_f90_use_only) 
        ASTR(SUN_namelist_spec) 
        ASTR(SUN_is_omp_child_func) 
        ASTR(SUN_fortran_main_alias) 
        ASTR(SUN_fortran_based) 
        ASTR(use_GNAT_descriptive_type) 
        ASTR(GNAT_descriptive_type) 
        ASTR(upc_threads_scaled) 
        ASTR(PGI_lbase) 
        ASTR(PGI_soffset) 
        ASTR(PGI_lstride) 
        ASTR(APPLE_optimized) 
        ASTR(APPLE_flags) 
        ASTR(APPLE_isa) 
        ASTR(APPLE_block) 
        ASTR(APPLE_major_runtime_vers) 
        ASTR(APPLE_runtime_class) 
        ASTR(APPLE_omit_frame_ptr) 
        ASTR(APPLE_closure) 
        ASTR(APPLE_major_runtime_vers) 
        ASTR(APPLE_runtime_class) 
        ASTR(hi_user)

    #undef ASTR
};


const std::string&
Dwarf::getAttrType(Dwarf_Half attrType)
{
    static const std::string unknownType = "UNKNOWN_ATTRIBUTE";

    auto it = s_attrStrings.find(attrType);
    if (it != s_attrStrings.end()) {
        return it->second;
    }
    else {
        return unknownType;
    }
}