#
# Methods and format for output reports
#
import logging
import networkx as nx
import types
import json
import os
import tempfile
import mapping.graphmap as gm
import fparser.control_flow as cf
import flow.transformer as ft


log = logging.getLogger(__name__)


class JsonReportEncoder(json.JSONEncoder):
    """
    Provide serialization for objects that json doesn't understand by default,
    in a way that is desirable for the report.
    """

    def default(self, obj):
        IGNORE = (nx.Graph, cf.ControlFlow, ft.TransformedFlowGraph)
        IGNORE += (types.InstanceType,)  # ignore old-style classes
        if isinstance(obj, IGNORE):
            as_string = str(obj)
            if isinstance(obj, types.InstanceType) and hasattr(obj, '__class__'):
                as_string += " ({})".format(obj.__class__)
            log.debug("Object {} has been omitted in report".format(as_string))
            return as_string
        elif hasattr(obj, '__dict__'):
            return obj.__dict__
        elif isinstance(obj, (list, dict, str, unicode, int, float, bool, type(None))):
            return json.JSONEncoder.default(self, obj)
        elif isinstance(obj, (set,)):
            return list(obj)
        else:
            log.debug("JSON: serialization of {} is missing.".format(type(obj)))
            return str(obj)


def _write_json(reportdata, name):
    """generic report, intended to have a quick and dirty dump that is half-way human-readable"""
    export_path = os.path.join(tempfile.tempdir, name + ".json")
    with open(export_path, "w") as json_out:
        json.dump(reportdata, json_out, indent=4, cls=JsonReportEncoder)


def _write_csv(outmap, reportdata, annot_func, bFlow, sFlow):
    """
    Proprietary mapping format that can be understood by cbb-analyzer
    FIXME: this is slow
    FIXME: remove reportdata at all. Need to communicate skipped loops in another way.
    """
    assert isinstance(outmap, gm.HierarchicalGraphMap)
    assert isinstance(bFlow, cf.BinaryControlFlow)
    assert isinstance(sFlow, cf.SourceControlFlow)
    # --
    global_mapping_dict = dict()
    flatmap = outmap.flatten()

    # invert and skip some. We need src->bin
    for n_b, n_s in flatmap.get_map().iteritems():
        if n_b > reportdata["max_bin_id"]:
            continue  # FIXME: is this necessary?
        if n_s not in global_mapping_dict:
            global_mapping_dict[n_s] = [n_b]
        else:
            global_mapping_dict[n_s] += [n_b]

    ##################
    # Calc extra time for low-level loops (skipped binary loops with annotations)
    ##################
    extra_ll_time = dict()  # Keyed by source node id
    for n_s in global_mapping_dict.keys():
        extra_ll_time[n_s] = 0

    skipped_b_loops = reportdata["matched_loops"]["skipped_bin_loops"]
    skipped_b_r_ids = reportdata["matched_loops"]["skipped_bin_r_ids"]
    if len(skipped_b_loops) > 0:
        assert annot_func is not None, \
            "Please provide information for low-level loops."

        assert len(annot_func['loops']) == len(skipped_b_loops), \
            "Missing loop information for function {}".format(bFlow.name)

        loop_info = bFlow.get_loop_info()
        for b_loop in skipped_b_loops:
            bloop = annot_func['loops'][str(b_loop)]
            loop_cycles = int(bloop['repeats'])

            # 1. Get all binary loop blocks (head+body)
            loop_header = loop_info.lookup_node(b_loop)
            assert loop_header is not None, "Invalid loop node {}".format(b_loop)

            b_loop_blocks = [loop_header] + list(loop_info.get_body_nodes(loop_header))

            # 2. Find which source block n_s this low-level loop is mapped to
            b_loop_region_id = skipped_b_r_ids[b_loop]
            n_s = flatmap.get_map().get(b_loop_region_id, None)
            assert n_s is not None, \
                "Could not find source block for loop region {}".format(b_loop_region_id)

            # apparently skipped nodes are otherwise missing in dict. FIXME: should be in mapping.
            global_mapping_dict[n_s] += b_loop_blocks

            # 3. Calc total loop exec time
            extra_time = 0
            if 'time' in bloop:
                extra_time = int(bloop['time'])
                time_mode = 'user'
            else:
                time_mode = 'estimate'
                for b_node in b_loop_blocks:
                    # FIXME: this assumes ALL BBs in loop execute.
                    extra_time += loop_cycles * bFlow._blockTimes[b_node]

            # 4. Save extra exec time for n_s
            extra_ll_time[n_s] += extra_time

            log.info("Loop region {} for loop header {} is mapped to source basic block {}. ".
                     format(b_loop_region_id, loop_header, n_s) +
                     "Loop time ({}): {}".format(time_mode, extra_time))
            # log.info("Extra time for low-level loop {}: {}".format(b_loop, extra_time))

            # Export mapping as csv
    out_string = ""
    out_string += "# Source_BB; Line_Col; [BinaryBB]+; ExecTime [, [fcall]+]\n"

    ############
    # write CSV
    ############
    smax = sFlow.get_max_id()  # nodes with higher numbers are not in the original graph
    bmax = bFlow.get_max_id()
    for n_s, list_n_b in global_mapping_dict.items():
        if n_s > smax:
            continue
        lcd_beg = sFlow.get_line_info(n_s)['begin']
        total_time = 0
        f_calls = []

        for n in list_n_b:
            if n > bmax:
                continue
            assert n in bFlow.digraph.nodes
            total_time += bFlow._blockTimes[n]
            f_calls += bFlow.get_func_calls(n)

        # Add extra time from low-level loops, not present in list_n_b
        if extra_ll_time[n_s] > 0:
            log.debug("Source block {} has low-level loops, extra time added: {}".format
                      (n_s, extra_ll_time[n_s]))
            total_time += extra_ll_time[n_s]

        timing_string = str(total_time)
        if len(f_calls) > 0:
            timing_string = timing_string + "," + ",".join(f_calls)

        out_string += "{}; {}; {}; {}\n".format(
            n_s,
            "l{}c{}".format(lcd_beg['l'], lcd_beg['c']),
            ",".join(str(bb) for bb in list_n_b),
            timing_string
        )
    export_path_csv = os.path.join(tempfile.tempdir, "mapping_" + bFlow.name + ".csv")
    with open(export_path_csv, 'w') as out_file:
        out_file.write(out_string)
    log.info("Mapping written to {}".format(export_path_csv))
    # --


def write(bFlow, sFlow, reportdata, mapping, annot_func):
    """Write report to files for a CFG pair"""

    _write_json(reportdata, bFlow.name)
    _write_csv(outmap=mapping, reportdata=reportdata,
               annot_func=annot_func, bFlow=bFlow, sFlow=sFlow)
