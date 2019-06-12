import logging
from mapping.mapper import AbstractMapper
import graphmap as gm


log = logging.getLogger(__name__)


class SkipMapper(AbstractMapper):
    """
    Lumps all skipped subgraphs into where their head nodes are mapped
    """

    def __init__(self, input_hmap, bFlow, sFlow, bhFlow, shFlow, annot, do_render=False):
        assert input_hmap is not None
        super(SkipMapper, self).__init__(input_hmap, bFlow, sFlow, bhFlow, shFlow)
        self.annot = annot
        self.do_render = do_render

    def walk_subgraphs(self):
        pass

    def _map_subgraph(self, input_map, btfg, stfg):
        pass

    def _compute_mapping(self):

        def walk_map(omap, imap):
            """
            Dives into hierarchy, copies everything,
            and adds the skipped nodes to the mapping.
            """

            def get_exec_count(skipflow_head):
                """look up exec count of skipped nodes in user annotations"""

                def annot_check_line(user_line):
                    lInfo = self.bFlow.get_line_info(skipflow_head)
                    matching = lInfo['begin']['l'] <= user_line <= lInfo['end']['l'] or \
                        lInfo['min']['l'] <= user_line <= lInfo['max']['l']
                    assert matching, "User annotation mismatches line"

                def annot_check_addr(user_addr):
                    lranges = self.bFlow.get_addr_ranges(skipflow_head)
                    user_addr_dec = int(user_addr, 16)
                    for lo, hi in lranges:
                        matching = lo <= user_addr_dec <= hi
                        if matching:
                            return
                    assert False, "User annotation mismatches address"

                skipflow_name = "{}.{}".format(self.bFlow.name, skipflow_head)
                log.info("Looking for user annotation of subflow {}...".format(skipflow_name))
                assert self.annot, "No user annotations given"
                try:
                    skip_annot = self.annot['loops'][str(skipflow_head)]
                    log.info("Using annotation for skipped flow {}: {}".format
                             (skipflow_name, skip_annot))
                    if 'line' in skip_annot:
                        annot_check_line(skip_annot['line'])
                    if 'addr' in skip_annot:
                        annot_check_addr(skip_annot['addr'])
                except KeyError:
                    assert False, "Annotation for skipped subflow {} missing".format(skipflow_name)
                # --
                return int(skip_annot.get('repeats', -1))

            def handle_skipped():
                skipflow_head = ocm.mapping.graph_A.entryId
                surro = rcoll.get_loop_region_id(skipflow_head)
                try:
                    surro_maps_to = imap.mapping[surro]  # requires complete mapping
                    log.debug("Mapping skipped subflow '{}' to s{}".format(ocm.name, surro_maps_to))
                    # FIXME: this is pessimistic. Not all nodes may execute the same number o.t.
                    loop_iter = gm.ExecCountRange(0, get_exec_count(skipflow_head))
                    addmap = {n: surro_maps_to for n in ocm.mapping.unmapped()}
                    cntmap = {n: loop_iter for n in ocm.mapping.unmapped()}
                    ext = gm.GraphMap(None, None, addmap, dict_exec_count=cntmap)
                    ocm.mapping.add(ext)
                except KeyError:
                    log.warning("During mapping of {}: surrogate {} of subgraph{} is "
                                "unmapped".format(imap.name, surro, icm.name))

            log.debug("Checking subflow {} for skips...".format(imap.name))
            num = 0
            rcoll = imap.mapping.graph_A.get_region_collection()
            for icm in imap.children:
                ocm = gm.HierarchicalGraphMap(icm.name)
                ocm.skip = icm.skip
                ocm.is_precise = icm.is_precise and not ocm.skip
                ocm.mapping = icm.mapping.copy(rename='skip.map')
                omap.children.append(ocm)
                if ocm.skip:
                    handle_skipped()
                    num += 1
                else:
                    num += walk_map(ocm, icm)
            return num

        outmap = gm.HierarchicalGraphMap(self.input_hmap.name)
        outmap.mapping = self.input_hmap.mapping.copy(rename='skip.map')
        num_lumped = walk_map(outmap, self.input_hmap)
        log.info("Skip mapper lumped {} subflows within {}".format(num_lumped, outmap.name))
        # --
        return outmap, self.bhFlow, self.shFlow
