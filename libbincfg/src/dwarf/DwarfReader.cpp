#include "bincfg/dwarf/DwarfReader.hpp"
#include <set>

const std::string DwarfReader::m_logIdentifier { "[DwarfReader] " };

DwarfReader::DwarfReader()
{
}

/**
 * @brief: Returns a DwarfData object containing debugging information. For the
 *         time being, only CU's in debug_info are processed.
 *
 * @todo: Inspect some elf file containing dwarf regions that overlap with
 *        one another.
 *
 * @note: Experimental two-level line tables are not supported.
 *
 * @note: Always check the validity of the returned DwarfData object.
 *
 * @fixme: Status handling for readAddressRanges, readSourceFiles.
 */
std::shared_ptr<DwarfData>
DwarfReader::readDwarfData(const std::string& elfPath)
{
    DwarfData* debugData = new DwarfData();
    bool status = true;

    do {
        // Open file
        FILE* elfFd { fopen(elfPath.c_str(), "r") };
        if (elfFd == nullptr) {
            Log::log() << m_logIdentifier << "Cannot open file: "
                       << elfPath
                       << ELogLevel::LOG_ERROR;

            status = false;
            break;
        }

        // Get Dwarf_Debug
        Dwarf_Debug d_debug = dwarfInit(elfFd, status);
        if (!status) break;

        Log::log() << m_logIdentifier << "File contains dwarf data: "
                   << elfPath
                   << ELogLevel::LOG_INFO;

        // Read CU headers in debug_info
        auto cuDies = readCompilationUnits(d_debug, true);

        if (!cuDies.empty()) {
            // Read address ranges
            readAddressRanges(d_debug, debugData);

            // Read source file names, update debugData
            readSourceFiles(d_debug, cuDies, debugData);

            // Read line information, update debugData
            status = readLineNumbers(cuDies, debugData);

            // Read subprograms, including inlined ones
            status &= buildDieTree(d_debug, cuDies, debugData);
        }
        else {
            status = false;
        }

        // Call dwarf_finish() and close file
        dwarfFinish(d_debug);
        fclose(elfFd);
    } while (false);

    debugData->setValidFlag(status);
    //debugData->printDwarfLines();
    return std::shared_ptr<DwarfData>(debugData);
}

/**
 * @note: When initStatus is set to false, either an error occurred during
 *        initialization or the file does not contain dwarf data.
 *
 * @note: No need to call dwarfFinish when the returned initStatus is false.
 */
Dwarf_Debug
DwarfReader::dwarfInit(FILE* elfFd, bool& initStatus)
{
    Dwarf_Debug  d_debug = nullptr;
    Dwarf_Error  d_error = nullptr;

    // Supply a Dwarf_Error, otherwise libdwarf will call abort
    // in case Dwarf_Debug isn't set up (NULL) and an error occurs during init.
    int result = dwarf_init(fileno(elfFd),
                            DW_DLC_READ,
                            &DwarfReader::dwarfErrorHandler,
                            nullptr,
                            &d_debug,
                            &d_error);

    if (result != DW_DLV_OK) {
        initStatus = false;

        Log::log() << m_logIdentifier << "dwarfInit() failed -- bad or no debug data"
                   << ELogLevel::LOG_DEBUG;
        // Deallocate only the error descriptor, dwarf_object_init_b takes care
        // of the rest. We need not call this function, since it simply returns
        // in our case.
        dwarf_dealloc(d_debug, d_error, DW_DLA_ERROR);

        if (d_debug == nullptr && d_error != nullptr) {
            dwarfErrorHandler(d_error, nullptr);

            // Free the leaking error.
            if (d_error->er_static_alloc == DE_MALLOC) {
                free(d_error);
            }
        }
    }
    else {
        // Error descriptor deallocated when calling dwarf_finish().
        initStatus = true;
    }

    return d_debug;
}


bool
DwarfReader::dwarfFinish(Dwarf_Debug d_debug)
{
    Dwarf_Error  d_error = nullptr;

    int result = dwarf_finish(d_debug, &d_error);
    if (result != DW_DLV_OK) {
        Log::log() << m_logIdentifier << "Dwarf finish failed."
                   << ELogLevel::LOG_ERROR;

        // Errors allocated during dwarf_finish will leak, must be freed manually.
        if (d_debug == nullptr && d_error != nullptr) {
            dwarfErrorHandler(d_error, nullptr);

            if (d_error->er_static_alloc == DE_MALLOC) {
                free(d_error);
            }
        }

        return false;
    }

    return true;
}


/**
 *
 * @note: This is invoked only if d_debug is not NULL when error handling is
 *        performed in libdwarf (_dwarf_error()). Allocated Dwarf_Error's
 *        tied to a Dwarf_Debug will get deallocated in dwarf_finish().
 *
 * @note: If Dwarf_Error in _dwarf_error() is not NULL, this will not be
 *        called.
 *
 * @note: In the case when Dwarf_Error is statically allocated, a call to
 *        dwarf_dealloc is harmless. This case does not arise here, refer
 *        to _dwarf_error() implementation in dwarf_error.c
 *
 * @note: If error is NULL, will print "Dwarf_Error is NULL" with error code 0.
 */
void
DwarfReader::dwarfErrorHandler(Dwarf_Error error, Dwarf_Ptr errarg)
{
    Log::log() << m_logIdentifier << "Error detected: 0x" << std::hex
               << dwarf_errno(error) << " " << dwarf_errmsg(error)
               << ELogLevel::LOG_ERROR;
}


/**
 * @brief: Returns a vector of Compilation Unit DIE's found in debug_info or
 *         debug_types.
 *
 * @note: All CU headers are processed sequentially.
 *
 * @note: Subsequent calls to next_cu_header after it has returned DW_DLV_NO_ENTRY
 *        will repeat the cycle.
 *
 * @info: The offset returned from dwarf_dieoffset() given a CU die is
 *        section-relative.
 */
std::vector<Dwarf_Die>
DwarfReader::readCompilationUnits(Dwarf_Debug d_debug, bool d_isInfo)
{
    std::vector<Dwarf_Die> cuDies;

    while (true) {
        // Get the next compilation unit (cu pointer will be updated
        // internally in d_debug). Always provide non NULL pointers
        // for the following arguments: next_cu_header.
        Dwarf_Unsigned d_nextCuHeader = 0;
        int result = dwarf_next_cu_header_d(d_debug, d_isInfo,
                                            nullptr, nullptr,
                                            nullptr, nullptr,
                                            nullptr, nullptr,
                                            nullptr, nullptr,
                                            &d_nextCuHeader, nullptr,
                                            nullptr);

        if (result == DW_DLV_ERROR) {
            break;
        }
        else if (result == DW_DLV_NO_ENTRY) {
            // There are no more compilation unit headers, we are done.
            break;
        }

        // A CU will have a single sibling, pass a NULL die to get the CU die.
        Dwarf_Die d_noDie = nullptr;
        Dwarf_Die d_cuDie = nullptr;

        result = dwarf_siblingof_b(d_debug, d_noDie, d_isInfo,
                                   &d_cuDie, nullptr);

        if (result == DW_DLV_ERROR || result == DW_DLV_NO_ENTRY) {
            break;
        }

        // CU die's will be deallocated in dwarf_finish().
        cuDies.push_back(d_cuDie);
    }

    if (cuDies.empty()) {
        Log::log() << m_logIdentifier << "An error occurred while reading"
                   << " compilation unit headers."
                   << ELogLevel::LOG_ERROR;
    }

    return cuDies;
}

/**
 * @brief: Reads source file names for all given CU's, updates DwarfData
 *         accordingly.
 *
 *
 * @note: Returns false if no source file was retrieved for at least one CU.
 */
bool
DwarfReader::readSourceFiles(Dwarf_Debug d_debug,
                             const std::vector<Dwarf_Die>& cuDies,
                             DwarfData* debugData)
{
    std::size_t errorCount = 0;
    auto cleanUp = [&d_debug](char** d_srcFiles)
    {
        // Harmless if d_srcFiles is NULL, simply returns.
        dwarf_dealloc(d_debug, d_srcFiles, DW_DLA_LIST);
    };

    for (Dwarf_Die d_cuDie : cuDies)
    {
        char**         d_srcFiles = nullptr;
        Dwarf_Signed   d_srcCount = 0;
        Dwarf_Unsigned d_dieOffset = 0;

        // Get CU Die offset first (section relative).
        int result = dwarf_dieoffset(d_cuDie, & d_dieOffset, nullptr);
        if (result != DW_DLV_OK) {
            Log::log() << m_logIdentifier << "Could not get CU die offset."
                       << ELogLevel::LOG_ERROR;
            errorCount++;
            continue;
        }

        result = dwarf_srcfiles(d_cuDie, &d_srcFiles, &d_srcCount, nullptr);
        if (result != DW_DLV_OK) {
            Log::log() << m_logIdentifier << "Error getting source files"
                       << " for CU @0x" << std::hex << d_dieOffset << "."
                       << ELogLevel::LOG_ERROR;
            errorCount++;
            cleanUp(d_srcFiles);
            continue;
        }

        // Copy strings individually, deallocate d_srcFiles[i].
        std::vector<std::string> srcFiles;
        srcFiles.reserve(d_srcCount);

        for (int i = 0; i < d_srcCount; i++)
        {
            std::string currSrcFile;
            // Copy the current source file string
            if (d_srcFiles[i] != nullptr) {
                currSrcFile = d_srcFiles[i];
            }
            else {
                Log::log() << m_logIdentifier << "Returned string points to NULL."
                           << ELogLevel::LOG_DEBUG;
            }

            // currSrcFile will be empty after moving it. Call clear to return
            // it to a known state if reusing the same string in loop.
            std::cout << "SrcFile: " << currSrcFile << std::endl;
            srcFiles.push_back(std::move(currSrcFile));

            // Deallocate the char* string
            dwarf_dealloc(d_debug, d_srcFiles[i], DW_DLA_STRING);
        }

        // Move the source file vector to DwarfData, srcFiles will be in
        // unknown state afterwards.
        debugData->addSourceFiles(std::move(srcFiles), d_dieOffset);

        // Clean up
        cleanUp(d_srcFiles);
    }

    if (errorCount == cuDies.size()) {
        return false;
    }

    return true;
}


/**
 * @brief: Reads line number information for all given CU dies, updates
 *         debugData accordingly. Only single line tables are processed.
 *
 * @note: Returns false if no line information was retrieved for at least one
 *        CU.
 *
 * @note: For the time being, we process only CU dies found in dwarf_info. The
 *        offset retrieved from dwarf_dieoffset is section-relative, so it
 *        is safe to use this offset as a unique key for identifying a CU. If we
 *        intend to implement processing CU dies found in dwarf_types section,
 *        either another way of keying CU's globally must be thought of or
 *        DwarfData must be changed to handle this. dwarf_get_die_infotypes_flag
 *        sets a flag indicating whether a given DIE is part of debug_info or
 *        debug_types. This could be used to distinguish between sections so that
 *        a global "offset" can be calculated.
 */
bool
DwarfReader::readLineNumbers(const std::vector<Dwarf_Die>& cuDies,
                             DwarfData* debugData)
{
    std::size_t errorCount = 0;
    auto cleanUp = [](Dwarf_Line_Context d_lineContext)
    {
        if (d_lineContext != nullptr) dwarf_srclines_dealloc_b(d_lineContext);
    };

    for (Dwarf_Die d_cuDie : cuDies)
    {
        Dwarf_Unsigned     d_version       = 0;
        Dwarf_Unsigned     d_dieOffset     = 0;
        Dwarf_Small        d_isSingleTable = 0;
        Dwarf_Line_Context d_lineContext   = nullptr;


        // Get CU Die offset first (section relative).
        int result = dwarf_dieoffset(d_cuDie, & d_dieOffset, nullptr);
        if (result != DW_DLV_OK) {
            Log::log() << m_logIdentifier << "Could not get CU die offset."
                       << ELogLevel::LOG_ERROR;
            errorCount++;
            continue;
        }

        // Get line context for the current CU Die
        result = dwarf_srclines_b(d_cuDie, &d_version, &d_isSingleTable,
                                  &d_lineContext, nullptr);

        if (result != DW_DLV_OK) {
            Log::log() << m_logIdentifier << "Error getting line context for"
                       << "CU @" << std::hex << d_dieOffset
                       << ELogLevel::LOG_ERROR;
            errorCount++;
            cleanUp(d_lineContext);
            continue;
        }

        // Only continue processing if the current CU contains a single line
        // table.
        if (d_isSingleTable != 1) {
            Log::log() << "CU @" << std::hex << d_dieOffset
                       << " does not contain a single line table."
                       << ELogLevel::LOG_DEBUG;
            errorCount++;
            cleanUp(d_lineContext);
            continue;
        }

        // Process line context, update debug data, cuId will be d_dieOffset.
        if (!processLineContext(d_lineContext, d_dieOffset, debugData)) {
            errorCount++;
        }
        cleanUp(d_lineContext);
    }

    // Return false if we don't have valid line info for at least one CU.
    if (errorCount == cuDies.size()) {
        return false;
    }
    return true;
}


bool
DwarfReader::processLineContext(Dwarf_Line_Context d_lineContext, uint64_t cuId,
                                DwarfData* debugData)
{
    std::size_t errorCount = 0;
    auto checkError = [&errorCount](int result) -> bool
    {
        if (result != DW_DLV_OK) {
            errorCount++;
            return false;
        }
        return true;
    };

    // Line buffer will be deallocated when dwarf_srclines_dealloc_b() is called.
    Dwarf_Line*  d_lineBuffer = nullptr;
    Dwarf_Signed d_lineCount  = 0;

    int result = dwarf_srclines_from_linecontext(d_lineContext, &d_lineBuffer,
                                                &d_lineCount, nullptr);

    if (result != DW_DLV_OK) {
        Log::log() << "Could not get lines from line context."
                   << ELogLevel::LOG_DEBUG;
        return false;
    }

    Log::log() << "CU has " << d_lineCount << " dwarf_line's."
               << ELogLevel::LOG_DEBUG;

    std::vector<DwarfLine> dwarfLines(d_lineCount);
    for (int i = 0; i < d_lineCount; i++)
    {
        DwarfLine& dl = dwarfLines[i];

        int result = dwarf_linebeginstatement(d_lineBuffer[i], &dl.d_isStmt, nullptr);
        if (!checkError(result)) continue;

        result = dwarf_lineendsequence(d_lineBuffer[i], &dl.d_isEndSequence, nullptr);
        if (!checkError(result)) continue;

        result = dwarf_lineno(d_lineBuffer[i], &dl.d_lineNumber, nullptr);
        if (!checkError(result)) continue;

        result = dwarf_lineoff_b(d_lineBuffer[i], &dl.d_lineOffset, nullptr);
        if (!checkError(result)) continue;

        result = dwarf_lineaddr(d_lineBuffer[i], &dl.d_lineAddress, nullptr);
        if (!checkError(result)) continue;

        result = dwarf_line_srcfileno(d_lineBuffer[i], &dl.d_fileIndex, nullptr);
        if (!checkError(result)) continue;

        // Always provide valid (not NULL) addresses for all arguments,
        // dwarf_prologue_end_etc does not check for NULL arguments.
        Dwarf_Bool     d_dummyBool;
        Dwarf_Unsigned d_dummyUI;
        result = dwarf_prologue_end_etc(d_lineBuffer[i], &d_dummyBool,
                                        &d_dummyBool, &d_dummyUI,
                                        &dl.d_discriminator, nullptr);
        if (!checkError(result)) continue;

        // Using cu die offset (section-relative) as ID.
        dl.cuId = cuId;
    }

    if (errorCount > 0) {
        Log::log() << m_logIdentifier << "Encountered " << errorCount
                   << " error(s) while processing line context."
                   << ELogLevel::LOG_WARNING;
        return false;
    }
    else {
        debugData->addDwarfLines(dwarfLines, cuId);
    }

    return true;
}

/**
 * @brief: Reads debug_aranges section, saves the found address ranges and their
 *         corresponding CU indices in DwarfData.
 *
 */
bool
DwarfReader::readAddressRanges(Dwarf_Debug d_debug, DwarfData* debugData)
{
    DwarfRange currRange;
    bool warningFlag = false;
    std::size_t totalCount = 0;

    Dwarf_Arange* d_aRanges    = nullptr;
    Dwarf_Signed  d_rangeCount = 0;

    int result = dwarf_get_aranges(d_debug, &d_aRanges, &d_rangeCount, nullptr);

    if (result == DW_DLV_OK)
    {
        Log::log() << m_logIdentifier << "Found " << d_rangeCount << " ranges in"
                   << " debug_aranges." << ELogLevel::LOG_DEBUG;

        for (int i = 0; i < d_rangeCount; i++)
        {
            Dwarf_Off d_cuOffset = 0;
            currRange = DwarfRange();

            dwarf_get_arange_info(d_aRanges[i], &currRange.d_start,
                                  &currRange.d_length, &d_cuOffset, nullptr);

            // Skip last range in CU (0x0 - 0x0, has length 0)
            if (currRange.d_length == 0) {
                continue;
            }

            // Use CU offset (section-relative) as ID
            currRange.cuId = d_cuOffset;

            // CU offset is relative to debug_info section
            bool status = debugData->addAddrRange(currRange);
            if (!status && !warningFlag) {
                Log::log() << m_logIdentifier << "Found overlapping address ranges"
                           << " in Dwarf debug data."
                           << ELogLevel::LOG_WARNING;

                warningFlag = true;
            }
            if (status) totalCount++;

            // Deallocate current range
            dwarf_dealloc(d_debug, d_aRanges[i], DW_DLA_ARANGE);
        }
    }

    dwarf_dealloc(d_debug, d_aRanges, DW_DLA_LIST);

    if (!totalCount) {
        return false;
    }
    else {
        return true;
    }
}


bool
DwarfReader::buildDieTree(Dwarf_Debug d_debug, const std::vector<Dwarf_Die>& cuDies,
                          DwarfData* debugData)
{
    std::size_t processedDies = 0;

    for (auto cuDie: cuDies) {
        Dwarf_Off dieOffset;
        if (dwarf_dieoffset(cuDie, &dieOffset, nullptr) != DW_DLV_OK) {
            Log::log() << "Error getting DIE offset."
                       << ELogLevel::LOG_ERROR;
            continue;
        }

        Log::log() << "Processing CU DIE @0x" << std::hex << dieOffset << "."
                   << ELogLevel::LOG_INFO;

        DwarfDie dwDie = DwarfDie(d_debug, cuDie, 0);

        if (!dwDie.isValid()) {
            Log::log() << "An error occurred while processing CU DIE @0x" << std::hex
                       << dieOffset << "."
                       << ELogLevel::LOG_ERROR;
            continue;
        }

        if (!debugData->addCuDie(std::move(dwDie))) {
            continue;
        }

        ++processedDies;
    }

    if (processedDies != cuDies.size()) {
        return false;
    }

    return true;
}
