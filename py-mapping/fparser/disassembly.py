import logging
import re
from sortedcontainers import SortedDict


log = logging.getLogger(__name__)


class Instructions:
    def __init__(self, insns):
        assert len(insns) > 0, "Empty instruction list."

        self._insnMap = SortedDict({i['Addr']:
                                    {
                                        'Mnem': i['Mnem'],
                                        'Operands': i['Op'],
                                        'Target': i['Target']
                                    } for i in insns})

    def get_instructions(self, addr_range):
        """
        Returns a list of instructions contained in the given address range.
        
        Note:
            - Each insn is a dict, possible keys:  'Mnem','Operands','Target'
        """
        assert isinstance(addr_range, tuple), "Invalid address range: {}".format(addr_range)
        ar_begin = addr_range[0]
        ar_end = addr_range[1]

        insnRange = self._insnMap.irange(minimum=ar_begin, maximum=ar_end)
        # for k,v in self._insnMap.items():
        #    log.debug("{}: {}".format(k,v))
        # log.debug("insnRange: {}".format(list(insnRange)))
    
        return [self._insnMap[i_addr] for i_addr in insnRange]

    def get_next_insn_address(self, addr):
        """
        Returns the next valid instruction address.

        Note:
            Addr may or may not be a valid instruction address.

        Args:
            addr: Current address.

        Return:
            Returns the next valid address, or None if addr is the very last
            address.
        """
        i = self._insnMap.bisect_left(addr)
        c_key = self._insnMap.iloc[i]
        # assert c_key == addr, "Address not in map."

        if i == len(self._insnMap) - 1:
            return None

        return self._insnMap.values()[i+1]
    
    def get_prev_insn_addres(self, addr):
        """
        Returns the previous valid instruction address.

        Note:
            Addr may or may not be a valid instruction address.

        Args:
            addr: Address to start search.

        Return:
            Returns the previous valid address, or None if add is the very first
            address.
        """
        i = self._insnMap.bisect_left(addr)
        c_key = self._insnMap.iloc[i]
        # FIXME: possibly incomplete

    def get_var_accesses(self, addrRanges, stackOffsets):
        """
        Return varReads, varWrites found in instructions specified by
        addrRanges @ the given stack frame offsets.

        param: - stackOffsets {offset:length}

        FIXME: Move validOffsets from here.
        """

        varReads = []
        varWrites = []
        varReadOffsets = []
        varWriteOffsets = []
        srx = re.compile(r'Y\+(\d+)')

        validOffsets = {}
        for key in stackOffsets.keys():
            validOffsets.update({
                o: key for o in xrange(key, key+stackOffsets[key])
            })

        def check_var_rw(addr):
            i = self._insnMap[addr]
            if len(i['Operands']) != 2:
                return
            # Write
            m = srx.search(i['Operands'][0])
            if m is not None:
                o = int(m.group(1))
                if o in validOffsets:
                    varWriteOffsets.append(o)
                else:
                    varWriteOffsets.append(None)
                return
            # Read
            m = srx.search(i['Operands'][1])
            if m is not None:
                o = int(m.group(1))
                if o in validOffsets:
                    varReadOffsets.append(o)
                else:
                    varReadOffsets.append(None)
                return

        for ar in addrRanges:
            insnRange = self._insnMap.irange(minimum=ar[0], maximum=ar[1])
            for i in insnRange:
                check_var_rw(i)
            pass

        # Filter None values
        varWriteOffsets = filter(lambda a: a is not None, varWriteOffsets)
        varReadOffsets = filter(lambda a: a is not None, varReadOffsets)
        
        def count_consecutive_occurrences(i, offsets):
            assert i < len(offsets)
            status = False

            initOff = validOffsets[offsets[i]]
            length = stackOffsets[initOff]

            if i + length > len(offsets):
                # Partial read for last variable in offsets.
                return i+length, initOff, False
                
            count = 0
            for j in xrange(i, i+length):
                if validOffsets[offsets[j]] == initOff:  # + length:
                    count += 1
                else:
                    break
            if count == length:
                status = True
                return i+length, initOff, status
            else:
                return i+1, initOff, status

        i = 0
        while i < len(varReadOffsets):
            i, initOff, status = count_consecutive_occurrences(i, varReadOffsets)
            # Byte operations (e.g. var & 0xEF)
            if status is False:
                log.debug("Partial read for variable starting @ offset: {}".format(initOff))
            varReads.append(initOff)

        i = 0
        while i < len(varWriteOffsets):
            i, initOff, status = count_consecutive_occurrences(i, varWriteOffsets)
            assert status, "Partial write."
            varWrites.append(initOff)

        return varReads, varWrites


class Symbols:
    def __init__(self, symbols):
        assert len(symbols) > 0, "Empty symbols list."

        self.symbols = {s['Addr']: s['Symbol'] for s in symbols}
        self.symbols_i = {s['Symbol']: s['Addr'] for s in symbols}
