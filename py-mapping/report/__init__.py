#
# Methods and format for output reports
#
import logging
import networkx as nx
import types
import json
import os
import tempfile
import pickle
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


def write_report(reportdata, name):
    """generic report, intended to have a quick and dirty dump that is half-way human-readable"""
    export_path = os.path.join(tempfile.tempdir, name + ".json")
    with open(export_path, "w") as json_out:
        json.dump(reportdata, json_out, indent=4, cls=JsonReportEncoder)


def write_mapping_annotations(fname_or_file, outmap, cache_model=None):
    """
    Write proprietary mapping format that can be understood by cbb-analyzer
    Also computes the instruction cycles per source-BB according to the mapping.
    """
    assert isinstance(outmap, gm.HierarchicalGraphMap)
    # --
    outmap.consistency_check()
    flatmap = outmap.flatten()
    bFlow = flatmap.graph_A.get_original_cflow()
    sFlow = flatmap.graph_B.get_original_cflow()
    assert isinstance(bFlow, cf.BinaryControlFlow)
    assert isinstance(sFlow, cf.SourceControlFlow)

    #############
    # invert map (we want src->bin)
    #############
    global_mapping_dict = dict()
    for n_b, n_s in flatmap.get_map().iteritems():
        if n_s not in global_mapping_dict:
            global_mapping_dict[n_s] = [n_b]
        else:
            global_mapping_dict[n_s] += [n_b]

    ############
    # write CSV
    ############
    out_string = "# Source_BB; Line_Col; [BinaryBB]+; ExecTime [, [fcall]+]; CacheModelFunc\n"
    for n_s, list_n_b in global_mapping_dict.items():
        lcd_beg = sFlow.get_line_info(n_s)['begin']
        total_time = 0
        f_calls = []

        # accumulate instruction time of binary BBs
        for n in list_n_b:
            assert n in bFlow.digraph.nodes
            exec_count = flatmap.exec_count[n]
            if exec_count.hi > 1:
                log.debug("it happens")
            if exec_count.hi < 0:
                # FIXME: can come from annotatins. Allow user to provide a time instead of repeat
                raise NotImplementedError("invalid execution count for BB{}".format(n))
            if cache_model is None:
                # otherwise contained in cache model already
                total_time += exec_count.hi * bFlow.get_block_time(n)
            f_calls += bFlow.get_func_calls(n) * exec_count.hi  # list repetition

        # add extra time from function calls not analyzed here
        timing_string = str(total_time)
        if len(f_calls) > 0:
            timing_string += "," + ",".join(f_calls)

        out_string += "{}; {}; {}; {}".format\
            (n_s, "l{}c{}".format(lcd_beg['l'], lcd_beg['c']),
             ",".join(str(bb) for bb in list_n_b),
             timing_string)

        # each src BB might have a function modeling caching behavior; give its name here
        if cache_model:
            model_func = cache_model.get(n_s, None)
            if model_func:
                out_string += "; {}".format(model_func)
        out_string += "\n"

    if isinstance(fname_or_file, file):
        fname_or_file.write('[{},{}]\n'.format(sFlow.file, sFlow.name))
        fname_or_file.write(out_string)
    else:
        with open(fname_or_file, 'w') as newfile:
            newfile.write('[{},{}]\n'.format(sFlow.file, sFlow.name))
            newfile.write(out_string)
        log.info("Mapping written to {}".format(newfile))


def write_mapping_pickle(filename, outmap):
    """dumps everything into pickle file, to be read by other Python processors"""
    assert isinstance(outmap, gm.HierarchicalGraphMap)
    with open(filename, 'w') as f:
        pickle.dump(outmap, f)


def write_mapping(outmap, bFlow, sFlow):
    filename = os.path.join(tempfile.tempdir, "mapping_" + bFlow.name)
    write_mapping_annotations(filename + ".csv", outmap=outmap)
    write_mapping_pickle(filename + ".pickle", outmap)


def write(bFlow, sFlow, reportdata, mapping):
    write_report(reportdata, bFlow.name)
    write_mapping(outmap=mapping, bFlow=bFlow, sFlow=sFlow)
