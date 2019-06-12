from fparser import dwarf
from flow import render
import logging
import coloredlogs


# Set up logging
logging.basicConfig()
coloredlogs.install(level='DEBUG', fmt='[%(levelname)s] <%(name)s> %(message)s')
log = logging.getLogger()

# Main
dwData = dwarf.DwarfData('./test/benchmarks/maxleaf/debug.json')

# Render subprogram tree
subprogTreeNodes = [node for node in dwData._dieTree.nodes if dwData._dieTree.nodes[node]['tag'] in
                    ['DW_TAG_compile_unit', 'DW_TAG_subprogram', 'DW_TAG_inlined_subroutine',
                     'DW_TAG_lexical_block']]
subprogTreeNodes += [0]
finalNodes = [0]
subprogTree = dwData._dieTree.subgraph(subprogTreeNodes)

for node in subprogTree.nodes:
    die = subprogTree.nodes[node]
    if die['tag'] == 'DW_TAG_compile_unit' and subprogTree.out_degree(node) == 0:
        continue

    finalNodes.append(node)

finalTree = subprogTree.subgraph(finalNodes)
render.render_graph(finalTree, name='subprog_tree', attrs=['tag', 'attrs'])
