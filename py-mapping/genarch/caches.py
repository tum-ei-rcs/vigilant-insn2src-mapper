#
# Generic cache models
#
import logging
import math
import copy
import xml.etree.ElementTree as XET
import fparser
import fparser.control_flow


log = logging.getLogger(__name__)


#################
# constants
#################
KNOWN_CLASSES = ('first-miss', 'always-miss', 'always-hit')  # all others are consid. unclassified


####################
# GLOBALS
####################
load_offset = 0  # address where instructions begin (LOAD address; for AVR null)


####################
# HELPERS
####################

def _power_of_two(val):
    return val != 0 and ((val & val - 1) == 0)


#####################
# DATA STRUCTURES
#####################

class BasicBlock(object):

    def __init__(self, ID, flow):
        self.ID = ID
        self.instance_id = 0
        self.instances = 0
        self.flow = flow
        self.lblocks = []  # in order of execution
        self.original = self  # I am the original

    def copy(self):
        assert self.original == self, "can only copy the original"
        cpy = copy.copy(self)
        self.instances += 1
        cpy.instance_id = self.instances
        return cpy

    def __str__(self):
        fname = self.flow.name if self.flow else ""
        inst = "'{}".format(self.instance_id) if self.instance_id > 0 else ""
        return "{}.bb{}{}".format(fname, self.ID, inst)

    def __repr__(self):
        return str(self)


class LBlock(object):
    def __init__(self, bb, addr, block, cset):
        assert isinstance(bb, BasicBlock)
        self.bb = bb
        self.addr = addr
        self.block = block
        self.cset = cset
        self.classification = 'unknown'
        self.context = None  # some classifiers need a context. E.g, first-miss (w.r.t. which BB?)
        self.needs_model = True
        self.comment = ''

    def __str__(self):
        return "lblock 0x{:x}".format(self.addr)

    def __repr__(self):
        return str(self)


class LBlockSet(object):
    def __init__(self, ID):
        self.ID = ID
        self.needs_model = True
        self.lblocks = set()

    def __str__(self):
        return "LBset {}: {}".format(self.ID, self.lblocks)

    def __repr__(self):
        return str(self)


class CacheConfig(object):
    """Holds information about a HW cache"""
    def __init__(self, configfile):
        self.policy = 'LRU'
        self.miss_penalty = 10
        self.lines = 0
        self.line_size = 0
        self.sets = 0
        self.size = 0
        self.assoc = 0
        self.rawconfig = None
        # --
        self._read_cache_config(configfile)

    def __str__(self):
        ss = "total={}B, lines={}, linesize={}B".format(self.size, self.lines, self.line_size)
        ss += ", assoc={}, sets={}, policy={}".format(self.assoc, self.sets, self.policy)
        ss += ", miss penalty={}".format(self.miss_penalty)
        ss += ", raw config={}".format(self.rawconfig)
        return ss

    def dump_config(self):
        log.info(str(self))

    def _read_cache_config(self, fcache):
        """read cache settings from file (compatible to OTAWA cache description)"""
        cconfig = dict(replace='LRU', block_bits=4, row_bits=5, way_bits=1, miss_penalty=5)

        def read_item(node, iname, conv):
            tmp = node.find(iname).text
            if tmp is None:
                raise ValueError
            cconfig[iname] = conv(tmp)

        ##################
        # read from file
        ##################
        try:
            xroot = XET.parse(fcache).getroot()
            assert xroot.tag == "cache-config", "unknown file format for cache config"
            icache = xroot.find('icache')
            read_item(icache, 'replace', str)
            read_item(icache, 'block_bits', int)
            read_item(icache, 'row_bits', int)
            read_item(icache, 'way_bits', int)
            read_item(icache, 'miss_penalty', int)

        except XET.ParseError as e:
            # noinspection PyUnresolvedReferences
            log.error("Failed loding cache config. Parse error at line {} col {}".format
                      (e.position[0], e.position[1]))
            exit(1)
        except ValueError:
            log.error("Unknown value in cache config")
            exit(1)
        except IOError as e:
            log.error("Failed loading cache config: {}".format(e.strerror))
            exit(1)

        # compute some more useful variables from thebits
        self.rawconfig = cconfig
        self.miss_penalty = cconfig['miss_penalty']
        self.policy = cconfig['replace']
        self.lines = pow(2, cconfig['way_bits'] + cconfig['row_bits'])
        self.line_size = pow(2, cconfig['block_bits'])
        self.assoc = pow(2, cconfig['way_bits'])

        log.debug("Loaded cache config: {}".format(cconfig))

        ##################
        # checks
        ##################
        assert 1 <= self.assoc <= self.lines, "associativity must be in 1...lines"
        assert 0 == self.lines % self.assoc, \
            "number of lines not divisible by associativity"
        assert _power_of_two(self.line_size), "line size is not a power of two"

        ####################
        # convenience props
        ####################
        self.offsetbits = int(math.log(self.line_size, 2))
        self.size = self.lines * self.line_size
        self.sets = self.lines / self.assoc


####################
# CACHE MODELS
####################

class Cache(object):
    """Abstract Base"""
    def __init__(self, configfile):
        self.cache_config = CacheConfig(configfile)

    def get_cache_config(self):
        return self.cache_config

    ###########################
    # provided methods:
    ###########################

    def setof(self, addr):
        """returns the cache set to which this address belongs to"""
        return (self.blockof(addr) >> self.cache_config.offsetbits) % self.cache_config.sets

    def blockof(self, addr):
        """returns the block number in the cache for a given instruction address

        Equivalent do address (rel. to text start) and flooring to first byte in cache line
        """
        global load_offset
        return ((addr - load_offset) >> self.cache_config.offsetbits) \
            << self.cache_config.offsetbits


class ICache(Cache):
    """instruction cache model"""
    def __init__(self, configfile, approx_unclassified=True):
        super(ICache, self).__init__(configfile)
        self.lbsets = None
        self.approx_unclassified = approx_unclassified

    def get_lbsets(self):
        """
        Get all line-blocks, arranged by cache set
        :return: dict containing cache sets, each value is a list of l-blocks in the set,
        each with additional data on the BB it belongs to.
        """
        return self.lbsets

    ########################
    # abstract methods
    ########################

    def classify_lbsets(self, ext_results):
        """
        Assert invariants on cache state; some we do ourselves, others from optional external input
        :param ext_results: optional external information
        """
        def decorate_trivial_first_miss():
            """
            Trivial first-miss classification (fewer L-blocks than associativity)
            Interestingly, OTAWA wcet analyzer does not check for this.
            """
            blocks = {l.block for l in lbset.lblocks}
            if len(blocks) <= self.cache_config.assoc:
                for l in lbset.lblocks:
                    # even if the block is FM, the l-block could already be classified from ext info
                    if l.classification not in KNOWN_CLASSES:
                        l.classification = 'first-miss'
                        l.context = None
                        log.debug("L-block {:x} in {}.{} is trivally 'first-miss'".format
                                  (l.addr, l.bb.flow.name, l.bb.ID))

        def decorate_with_external():
            """get external classification, if any"""
            def get_bb_by_ID(f, bbid):
                for onebb in f.basicblocks:
                    if onebb.ID == bbid:
                        return onebb
                return None

            def get_classification(onelb):
                ext_lb = ext_results['lblocks'].get(onelb.addr, None)
                if ext_lb and 'classification' in ext_lb:
                    return ext_lb['classification'], ext_lb['context']
                return None, None

            for lb in lbset.lblocks:
                found = False
                lbcls, lbctx = get_classification(lb)
                if lbcls:
                    found = True
                    lb.classification = lbcls
                    lb.context = lbctx
                else:
                    """
                    Since we split our BBs af fcn calls, we create new ones that external
                    analyzers might not have. As a consequence, we create some additional
                    L-blocks for which there is no classification. However, this can be
                    solved. If the BB of the L-block is a call and it is the first one, 
                    then we have this case.
                    """
                    callees = lb.bb.flow.get_func_calls(lb.bb.ID)
                    preds = list(lb.bb.flow.digraph.predecessors(lb.bb.ID))
                    isfirst = lb == lb.bb.lblocks[0]
                    if callees and isfirst and len(preds) == 1:
                        """
                        If the immediately preceding l-block (=last l-block in unique predecing 
                        BB) is in the same cache line, then it's always hit. Otherwise we must
                        assume.
                        """
                        log.debug("L-block for split fcn call {} of {}".format
                                  (lb, lb.bb))
                        # last lblock in pred is the one
                        bb_pre = get_bb_by_ID(lb.bb.flow, preds[0])
                        if bb_pre:
                            lb_pre = bb_pre.lblocks[-1]
                            if lb_pre.block == lb.block:
                                found = True
                                lb.classification = 'always-hit'
                        else:
                            log.warning("Failed to find preceding l-block for split-bb")
                if not found:
                    log.warning("External info present but lacking {} of {}".format(lb, lb.bb))

        def identify_unneeded_models():
            """we can only drop the model for entire sets on some conditions.
            If all l-blocks in a set are classified, we don't need to model accesses.
            If some l-blocks in a set are unclassified, we can either be pessimistic about them,
            or we can forget the classification of the others and model the entire set. Depends in
            user flags.
            """

            def approx_unclassified():
                for lbl in lbset.lblocks:
                    if lbl.classification not in KNOWN_CLASSES:
                        lbl.classification = 'always-miss'
                        lbl.comment = 'approx'
                        log.warning('Approximating access to unclassified {} in {}.{} as {}'.format
                                    (lbl, lbl.bb.flow.name, lbl.bb, lbl.classification))

            # mark sets that do not need explicit tracking
            set_classified = all([lb.classification in KNOWN_CLASSES for lb in lbset.lblocks])
            if set_classified:
                lbset.needs_model = False
            else:
                if self.approx_unclassified:
                    approx_unclassified()
                    lbset.needs_model = False
                else:
                    lbset.needs_model = True

            # mark l-blocks that do not need explicit tracking (first miss needs a model)
            LB_NO_MODEL = ('always-miss', 'always-hit')
            for lb in lbset.lblocks:
                if lb.classification in LB_NO_MODEL:
                    lb.needs_model = False

        have_ext_class = ext_results and 'lblocks' in ext_results
        for lbset in self.lbsets:
            if have_ext_class:
                decorate_with_external()
            decorate_trivial_first_miss()
            identify_unneeded_models()
            log.debug("Set {} (model={}): {}".format(lbset.ID, lbset.needs_model,
                                                     ["{:x}: {}".format
                                                         (lbb.block, lbb.classification)
                                                      for lbb in lbset.lblocks]))

    def compute_lbsets(self, cfgs):
        """
        Determine L-blocks and group them into cache sets.

        :param cfgs:
        """
        assert isinstance(cfgs, list)
        # --

        def init_lbsets():
            """based on cache config, create cache sets:

            Each set is considered a fully-associative cache, with the number of lines equivalent to
            the associativity. If direct-mapped cache, then we have as many sets as lines.
            If A-assoc cache, then we have [lines/A] sets, each with A lines.
            """
            assert 0 == self.cache_config.lines % self.cache_config.assoc, \
                "invalid cache config"
            sets = [LBlockSet(ID=a) for a in xrange(self.cache_config.sets)]
            return sets

        def add_lblocks(bFlow, binbb):
            """for a given BB 'n', compute all L-blocks and sort them into cache sets

            l-blocks are subvisions of BBs, such that l-blocks do not cross cache line boundaries
            """

            def make_lblock(bbobj, addr):
                """
                send each insn of BB n in here to
                if necessary, create new L-block for this insn
                """
                # we don't need offset and length, because cache lines are always loaded as whole
                return LBlock(bbobj, addr=addr, block=self.blockof(addr),
                              cset=self.lbsets[self.setof(addr)])

            # iterate over insn and create l-blocks. XXX: important: in instruction order
            last_set = None
            for instaddr, inst in bFlow.instructions(binbb.ID):
                # XXX: this assumes no unaligned access for instructions, which is true on ARM
                cur_set = self.setof(instaddr)
                if cur_set != last_set:  # l-blocks change together with cache set
                    lbs = self.lbsets[cur_set]  # the cache set of this L-block
                    log.debug("New L-Block for {}.b{}: addr={:x}, block={:x} set={}".format
                              (bFlow.name, binbb.ID, instaddr, self.blockof(instaddr),
                               cur_set))
                    lb = make_lblock(bbb, instaddr)
                    bbb.lblocks.append(lb)
                    lbs.lblocks.add(lb)
                    last_set = cur_set

        self.lbsets = init_lbsets()  # create n/A empty cache sets, which will hold l-blocks
        for g in cfgs:
            assert isinstance(g, fparser.control_flow.BinaryControlFlow)
            for bbb in g.basicblocks:
                add_lblocks(g, bbb)
        # --
        assert isinstance(self.lbsets, list)  # of LBlockSet
