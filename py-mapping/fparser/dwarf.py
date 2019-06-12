import logging
import json
import re
import networkx as nx
from sortedcontainers import SortedDict


log = logging.getLogger(__name__)
SUBROUTINE = ('DW_TAG_inlined_subroutine', 'DW_TAG_subprogram')


class DwarfData(object):
    """
    Loads dwarf data from the given file.

    Data:
        - DIEs: Apart from attributes, it also contains DIE offset as well as
                parent DIE offset in order to build a tree. 
        - LineInfoMap: Instruction address to LineInfoEntry
        - LineInfoEntries: Map of entries containing line info

    TODO: - Include DW_TAG_formal_parameter?
    """

    def __init__(self, path):
        self._dwData = None
        self._dieTree = None
        self._subDies = None
        self._subprograms = None
        self._inlSubroutines = {}
        self._dwLineMap = None

        # Read dwarf data.
        self._read_data(path)
        assert self._validate_data(), "Invalid dwarf data."

        # Process dwarf data.
        self._build_die_tree()
        self._find_subprograms()
        self._find_inlined_subroutines()

        # Save LineInfoMap as SortedDict
        self._dwLineMap = SortedDict({int(k): int(v)
                                      for k, v in self._dwData['LineInfoMap'].iteritems()})

    def get_dw_lines(self, ranges):
        """
        Return dwarf lines that belong to given instruction address ranges
        Args
            ranges : List of ranges to retrieve dwarf line entries for

        Return
            dwLines : Dict of DwarfLine entries referenced in given range list
        """
        dwLineIndices = []
        for r in ranges:
            for dwl_i in self._dwLineMap.irange(minimum=r[0], maximum=r[1]):
                dwLineIndices.append(self._dwLineMap[dwl_i])

        dwLines = {i: self._dwData['LineInfoEntries'][str(i)] for i in set(dwLineIndices)}
        return dwLines

    def get_line_info(self, ranges):
        """
        Returns line info for the given address ranges.

        Args:
            ranges : list of address ranges

        Return:
            Returns dict containing the following elements:
                - begin : Begin Line
                - end   : End Line
                - max   : Min Line
                - min   : Max Line
            
            where each element is a dict: {l, c, d} where:
                - l : line
                - c : column
                - d : discriminator
            
            * All values are integers.
        """
        assert isinstance(ranges, list)

        l_info = {
            'begin': {},
            'end': {},
            'max': {},
            'min': {}
        }

        def get_lcd(dwlIndex):
            dwl = self._dwData['LineInfoEntries'].get(str(dwlIndex), None)
            if dwl is None:
                assert False, "Invalid dwLine index."
            return {
                'l': int(dwl['LineNumber']),
                'c': int(dwl['LineOffset']),
                'd': int(dwl['Discriminator'])
            }

        l_info['begin'] = get_lcd(self._dwLineMap[ranges[0][0]])
        l_info['end'] = get_lcd(self._dwLineMap[ranges[-1][-1]])

        minLine = None
        maxLine = None
        for r in ranges:
            for dwl_i in self._dwLineMap.irange(minimum=r[0], maximum=r[1]):
                dwlIndex = self._dwLineMap[dwl_i]
                lcd = get_lcd(dwlIndex)
                if minLine is None and maxLine is None:
                    minLine = lcd
                    maxLine = lcd
                    continue

                # Max
                if lcd['l'] > maxLine['l']:
                    maxLine = lcd
                elif lcd['l'] == maxLine['l']:
                    if lcd['c'] > maxLine['c']:
                        maxLine = lcd
                    elif lcd['c'] == maxLine['c']:
                        if lcd['d'] > maxLine['d']:
                            maxLine = lcd

                # Same for min...
                if lcd['l'] < minLine['l']:
                    minLine = lcd
                elif lcd['l'] == minLine['l']:
                    if lcd['c'] < minLine['c']:
                        minLine = lcd
                    elif lcd['c'] == minLine['c']:
                        if lcd['d'] < minLine['d']:
                            minLine = lcd

        # Update min/max
        l_info['max'] = maxLine
        l_info['min'] = minLine

        return l_info

    def get_subprograms(self):
        """
        Get subprogram dict.

        Return:
            Dict keyed by subprogram low_pc (serving as entry point) with values
            of the following form: {name, dieOffset}.
        """
        return self._subprograms

    def get_subprogram_file(self, dieOffset):
        """
        Returns the file associated with the given subprogram DIE.

        Args:
            dieOffset: Offset of subprogram DIE.

        Return:
            Tuple (comp_dir, filename).

        FIXME:
            Return the actual file. The source file table must be exported in JSON 
            (it is already parsed from the elf object). For now, the file path
            of parent CU is returned instead.
        """
        assert dieOffset in self._subDies, "Invalid subprogram DIE offset."

        # Get parent DIE (CU)
        cuDie = list(self._dieTree.predecessors(dieOffset))
        assert len(cuDie) == 1, "Invalid DIE tree."
        cuDie = cuDie[0]

        # Get the source file table associated with this CU. Use DW_AT_decl_file
        # index for retrieving the actual file.

        # FIXME: Return the actual file.
        cuDieAttrs = self._dieTree.nodes[cuDie]['attrs']
        return cuDieAttrs['DW_AT_comp_dir'], cuDieAttrs['DW_AT_name']

    def get_inlined_subroutines(self, subDieOffset):
        """
        Returns a list of inlined subroutines for the given subprogram DIE offset.

        Args:
            subDieOffset: Valid subprogram DIE offset.

        Note:
          ** high_pc points at first byte after last instruction

        Return:
            List of inlined subroutines of the form {dieOffset, low_pc, high_pc}.
            Returns an empty list if given subprogram does not contain inlined
            subroutines.
        """
        assert subDieOffset in self._subDies
        return self._inlSubroutines.get(subDieOffset, [])

    def get_local_variables(self, subDieOffset):
        """
        Returns local variables given a subroutine DIE offset. The subroutine DIE
        may be a normal subroutine or an abstract instance root entry (part of 
        self._subDies).
        
        Note:
            SP register hardcoded for avr (fbreg28).
        
        Args:
            subDieOffset: Offset of subprogram DIE containing variables.
        
        Return:
            A dict keyed by variable offset in stack, with values of the form
            {name, byteSize}.
        """

        def get_locs(chDie):
            rx = re.compile(r'\[([^\]]+)\];')
            return rx.findall(chDie['attrs']['DW_AT_location'])

        def get_ops(loc):
            assert loc[-1] == ','
            return loc.split(',')[:-1]

        assert subDieOffset in self._subDies, \
            "Invalid subprogram DIE offset."

        localVars = {}

        for s in self._dieTree.successors(subDieOffset):
            chDie = self._dieTree.nodes[s]
            if chDie['tag'] != 'DW_TAG_variable':
                continue
            if not {'DW_AT_name', 'DW_AT_location', 'DW_AT_type'} <= set(chDie['attrs'].keys()):
                continue

            locs = get_locs(chDie)
            name = chDie['attrs']['DW_AT_name']

            if len(locs) == 1:
                ops = get_ops(locs[0])
                if len(ops) == 1:
                    o = ops[0].split(':')
                    if len(o) == 2:
                        k = o[0]
                        v = o[1]
                    else:
                        continue

                    if k != 'DW_OP_breg28':
                        continue

                    # Get base type
                    typeDieOffset = int(chDie['attrs']['DW_AT_type'])
                    if not self._dieTree.has_node(typeDieOffset):
                        continue
                    bs = self._get_type_byte_size(typeDieOffset)
                    localVars[v] = {'name': name, 'byteSize': bs}

        return localVars

    def _get_type_byte_size(self, die):
        """Decodes byte size for a DIE with tag DW_TAG_base_type."""
        if not self._dieTree.has_node(die):
            assert False, "Invalid DIE offset."

        die = self._dieTree.nodes[die]
        assert die['tag'] == 'DW_TAG_base_type'
        assert 'DW_AT_byte_size' in die['attrs'].keys()

        return self._decode_dwarf_constant(die['attrs']['DW_AT_byte_size'])[1]

    def _decode_dwarf_constant(self, attr):
        """
        Decodes a dwarf constant of the form S_{}_U_{}, returning signed, unsigned.
        
        Args:
            attr: Attribute (string) of the form S_{}_U_{}.

        Return:
            Tuple (s, u), signed and unsigned respectively.
        """
        m = re.search(r'S_([+\-0-9]+)_U_([+\-0-9]+)', attr)
        assert m is not None

        s = int(m.group(1))
        u = int(m.group(2))
        assert u >= 0
        return s, u

    def _find_inlined_subroutines(self):
        """
        Scans subtrees with roots in self._subDies for DIEs with tag 
        'DW_AT_inlined_subroutine'. Only inlined subroutines which
        have low_pc, high_pc are processed here. Nested inlining is not
        supported.
        
        Note:
            Inlined subroutine DIEs are marked in self._inlSubroutines. This
            dict is keyed by subprogram DIE offset, where each value is a list 
            of inlined subroutines of the form {dieOffset, low_pc, high_pc}.
        
        Return:
            Void
        """

        def add_inl(die, node, subp):
            """
            Add the inlined subroutine to self._inlSubroutines. 'Decode' high_pc
            if it represents an offset.
            
            Args:
                die:  Die offset.
                node: Die node is self._dieTree.
                subp: Offset of subprogram DIE containing inlined node.
            
            Return:
                Void.
            """
            assert subp in self._subDies

            # Get range
            lo_pc = int(node['attrs']['DW_AT_low_pc'])

            if node['attrs']['DW_AT_high_pc'][0] == 'S':
                # Decode dwarf constant
                _, off = self._decode_dwarf_constant(node['attrs']['DW_AT_high_pc'])
                hi_pc = lo_pc + off
            else:
                hi_pc = int(node['attrs']['DW_AT_high_pc'])

            # Update self._inlSubroutines
            if subp not in self._inlSubroutines:
                self._inlSubroutines[subp] = []

            self._inlSubroutines[subp].append({
                'dieOffset': die,
                'low_pc': lo_pc,
                'high_pc': hi_pc
            })

        def get_surrounding_sub(dnode):
            """Walk up the tree and return next surrounding subroutine
            Not necessarily the direct parent. There may be lexical scopes and other stuff.
            """
            n = dnode
            try:
                while n:
                    n = next(iter(self._dieTree.predecessors(n)))
                    dd = self._dieTree.nodes[n]
                    if 'tag' in dd and dd['tag'] in SUBROUTINE:
                        return n
            except StopIteration:
                pass
            return None

        def get_sub_details(doff):
            """Return dict with details of subroutine. If die is inlined, go to abstract origin"""
            assert int(doff) in self._dieTree.nodes, "DWARF data incomplete"
            # --
            dd = self._dieTree.nodes[int(doff)]
            assert dd['tag'] in SUBROUTINE, "not a subprogram"
            if dd['tag'] == "DW_TAG_inlined_subroutine":
                return get_sub_details(dd['attrs']['DW_AT_abstract_origin'])
            return dd['attrs']

        def test_die(die, subp):
            """
            Test if die is an inlined node, add it to self._inlSubroutines.

            Note:
                - Nested inlining not supported.
                - DW_AT_ranges not supported.

            Args:
                die:  Die offset.
                subp: Subprogram die offset.

            Returns:
                Void.
            """
            dNode = self._dieTree.nodes[die]
            if dNode['tag'] == 'DW_TAG_inlined_subroutine':
                inlined_into = int(get_surrounding_sub(die))
                abstract_orig = int(dNode['attrs']['DW_AT_abstract_origin'])
                assert inlined_into is not None, "Inlined sub without surrounding sub"
                sub_into = get_sub_details(inlined_into)
                sub_myself = get_sub_details(abstract_orig)
                log.info("Sub '{}' (die +{:x}) was inlined into '{}' (die +{:x})".format
                         (sub_myself['DW_AT_name'], die, sub_into['DW_AT_name'], inlined_into))

                if self._dieTree.node[inlined_into]['tag'] == 'DW_TAG_inlined_subroutine':
                    raise NotImplementedError("nested inlining @die offset {:x}".format(die))

                # Check if it contains DW_AT_ranges
                if 'DW_AT_ranges' in dNode['attrs']:
                    raise NotImplementedError("Inlined subroutine not in contiguous range.")

                assert {'DW_AT_low_pc', 'DW_AT_high_pc'} <= set(dNode['attrs'].keys()), \
                    "Incorrect inlined subroutine DIE @0d{}".format(die)

                # Add inlined subroutine
                add_inl(die, dNode, subp)

        def find_children(subt, root):
            """Search the subtree rooted by subp recursively."""
            for ch in self._dieTree.successors(subt):
                test_die(ch, root)
                find_children(ch, root)

        for s in self._subDies:
            find_children(s, s)
        if self._inlSubroutines:
            log.warning("Support for inlining is experimental!")

    def _find_subprograms(self):
        """
        Finds subprograms that have debug info, notes them in self._subprograms.

        
        NOTE: Only subprogram DIEs that are direct children of CU DIEs are
              processed here (as it should be).

        NOTE: Only subprogram DIEs that have low_pc, high_pc are processed here.
              DIEs with an DW_AT_ranges are skipped here (non-contiguous case).
              To be completed later... (FIXME).

           ** It is assumed that low_pc represents the entry point of the 
              subprogram. If this is not the case, then the Executable class will
              simply assume that this subroutine does not possess debug info 
              (mismatch between entry point as symbol address in json data and
               the low_pc address here).
        -----

        NOTE: Subprogram DIEs that are abstract instance root entries are 
              are not added to self._subprograms, but are noted in self._subDies.
              This happens for subprograms that are always inlined, so that there
              is no external symbol left.
        
        NOTE: It can happen that a subprogram DIE (DW_TAG_subprogram) which is
              not a concrete out-of-line instance (see below) may be missing 
              a DW_AT_name or DW_AT_low_pc attribute. Example (memmove in maxleaf).
        -----

        NOTE: DIEs with DW_TAG_subprogram which have an DW_AT_abstract_origin
              attribute represent a concrete out-of-line instance of an
              inlinable subroutine.
        """
        self._subDies = []
        self._subprograms = {}

        # Walk the tree, only traverse CU's that have DW_AT_comp_dir and
        # DW_AT_name attributes.
        #
        # FIXME: Process all CU's after fixing self.get_subprogram_file()
        cuDies = self._dieTree.successors(0)
        for cu in cuDies:
            cuAttrs = self._dieTree.nodes[cu]['attrs']
            if not {'DW_AT_name', 'DW_AT_comp_dir'} <= set(cuAttrs.keys()):
                continue

            # Find subprogram DIE's that are children of current CU DIE
            for s in self._dieTree.successors(cu):
                die = self._dieTree.nodes[s]

                if die['tag'] != 'DW_TAG_subprogram':
                    continue

                # Check if it has an abstract origin attribute -> concrete 
                # out of line instance.
                if 'DW_AT_abstract_origin' in die['attrs']:
                    # log.debug("Skipping subprog DIE @0d{}, concrete out-of-line
                    # instance".format(s))
                    continue

                # Don't process abstract instance root entries here but note 
                # them in self._subDies.
                if 'DW_AT_inline' in die['attrs']:
                    log.debug("Subprog DIE @0d{} is an abstract instance root entry.".format(s))
                    self._subDies.append(s)
                    continue

                if not {'DW_AT_low_pc'} <= set(die['attrs'].keys()):
                    # a declaration
                    continue

                if 'DW_AT_ranges' in die['attrs']:
                    log.error("Skipping subprogram DIE @0d{}, contains DW_AT_ranges.".format(s))
                    continue

                self._subprograms.update({int(die['attrs']['DW_AT_low_pc']):
                                          {'name': die['attrs']['DW_AT_name'], 'dieOffset': s}})
                self._subDies.append(s)

    def _build_die_tree(self):
        """
        Builds the die tree as nx.DiGraph. Children of the root node are 
        Compilation Unit DIE's found in .debug_info section. Each node has
        the following attributes:
            - tag   : DW_TAG_*
            - attrs : DW_AT_*

        Note:
            Nodes are keyed by DIE offset, the root node having offset 0.
        """

        dieTree = nx.DiGraph()
        dieTree.add_node(0, tag='root')

        for die in self._dwData['DIEs']:
            assert die['Offset'] != 0, "Invalid DIE."
            # Add node
            dieTree.add_node(die['Offset'], tag=die['Tag'], attrs=die['Attributes'])
            # Add edge to parent
            dieTree.add_edge(die['ParentOffset'], die['Offset'])

        # Check if graph is indeed a tree, raise an error if not.
        assert nx.is_tree(dieTree), "Invalid DIE tree."

        self._dieTree = dieTree

    def _read_data(self, path):
        with open(path, 'r') as fp:
            self._dwData = json.load(fp)

    def _validate_data(self):
        status = False
        while True:
            if not {'Type', 'Data'} <= set(self._dwData.keys()):
                break
            if self._dwData['Type'] != 'DebugInfo':
                break
            if not {'DIEs', 'LineInfoEntries', 'LineInfoMap'} <= \
                    set(self._dwData['Data'].keys()):
                break
            if len(self._dwData['Data']['DIEs']) < 1:
                log.error("Empty DIE map.")
                break

            self._dwData = self._dwData['Data']
            status = True
            break
        return status
