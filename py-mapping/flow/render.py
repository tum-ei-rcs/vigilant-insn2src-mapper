import networkx as nx
import tempfile
import logging
import subprocess
import os.path
import uuid
import os
import re


log = logging.getLogger(__name__)


# only the following attrs are interpreted for layout; others are shown verbatim
LAYOUT_ATTRS = ('color', 'fontcolor', 'style', 'shape', 'fillcolor', 'constraint')
CSSNAME = "graphstyle.css"
JSNAME = "graphstyle.js"


class GraphCluster(object):
    """
    Sets of graph nodes that belong together. Possibly hierarchical

    Note: If hierarchy is used, then the children's nodes shall not be included in a parent
    """
    def __init__(self, name, visible=True, topnode=None, botnode=None):
        self.name = name
        self.children = []  # list of clusters contained in this one. Used to nest graphs.
        self.parent = None
        self.nodes = set()
        self.visible = visible
        self.topnode = topnode  # =entry
        self.botnote = botnode  # =exit
        self.relatives = []  # list of clusters related to this one. Used to draw edges between.
        self.color = 'blue'
        self._node2cluster = dict()
        self._scope_name = None

    def empty(self):
        return len(self.children) == 0 and len(self.nodes) == 0

    def add_node(self, n):
        self.nodes.add(n)

    def add_nodes(self, nlist):
        self.nodes |= set(nlist)

    def add_relative(self, cluster):
        assert isinstance(cluster, GraphCluster)
        self.relatives.append(cluster)

    def add_child(self, cluster):
        assert isinstance(cluster, GraphCluster)
        self.children.append(cluster)
        cluster.parent = self

    def analyze(self):
        self._build_node2cluster()

    def contained_nodes(self):
        """return list of nodes, including children"""
        cnodes = set()
        for c in self.children:
            cnodes |= c.contained_nodes()
        return self.nodes | cnodes

    def get_scope_name(self):
        if self._scope_name is None:
            scope = []
            c = self
            while True:
                scope.append(c.name)
                c = c.parent
                if c is None:
                    break
            self._scope_name = ".".join(reversed(scope))
        return self._scope_name

    def _build_node2cluster(self, force=False):
        """builds lookup dictionary that maps node id to cluster instance"""
        if not self._node2cluster or force:
            nodes_children = set()
            for c in self.children:
                c._build_node2cluster()
                nodes_children |= c.nodes
                self._node2cluster.update(c._node2cluster)
            self._node2cluster.update({n: self for n in self.nodes if n not in nodes_children})

    def cluster_of_node(self, n):
        """
        Searches for n in self and its children, and returns the innermost
        instance containing it
        """
        if not self._node2cluster:
            self._build_node2cluster()
        return self._node2cluster.get(n, None)

    def check_cluster(self):
        """children must be disjoint sets from me"""
        for c in self.children:
            assert not (c.nodes & self.nodes), "{} intersects {}".format(c.nodes, self.nodes)
            c.check_cluster()
        return True  # isn't reached when assert kicks in


def _make_classical_id(something):
    """make a traditional identifier"""
    return re.sub(r'[^a-zA-Z_0-9]', '', str(something))


def _make_dot_id(something):
    """make a DOT identifier, which can be anything as long as quoted"""
    return '"{}"'.format(something)


def _dot_code_node(G, n, attrs, lbls, target, clusterhead, interactive):
    """Write code for a single graph node"""

    def _write_verbatim(key, val):
        if not interactive:
            vstr = '<TR><TD align="right" colspan="2">' + \
                   '<FONT FACE="courier" POINT-SIZE="10" color="blue">{}: </FONT>'.format(key) + \
                   '<FONT FACE="courier" POINT-SIZE="12">{}</FONT>'.format(val) + \
                   '</TD></TR>\n'
        else:
            vstr = '{}: {}'.format(key, val)
        return vstr

    def select_shape():
        return 'box' if attrs_verb and not interactive else 'oval'

    if lbls is not None:
        lbl = lbls[n]
    else:
        lbl = G.nodes[n].get('label', None)
        if lbl is None:
            lbl = str(n)

    attrs_verb = []
    attrs_layout = []
    if attrs:
        for a in attrs:
            if a in G.nodes[n].keys():
                v = G.nodes[n][a]
                if a in LAYOUT_ATTRS:
                    attrs_layout.append(_dot_code_attr(a, v))
                else:
                    attrs_verb.append(_write_verbatim(a, v))

    shape = select_shape()
    tmpStr = '{} [shape={},margin=0,'.format(_make_dot_id(n), shape)

    if 'calls' in G.nodes[n]:
        tmpStr += 'xlabel="{}",'.format(G.nodes[n]['calls'])
        tmpStr += 'penwidth="2",'

    if attrs_layout:
        tmpStr += ",".join(attrs_layout) + ","

    if attrs_verb:
        if interactive:
            if clusterhead:
                tmpStr += 'target="other",'
                lbl += '\n(+)'
            tmpStr += 'label="{}",'.format(lbl)
            tmpStr += 'tooltip="{}"'.format(", ".join(attrs_verb))
        else:
            tmpStr += 'label=<<TABLE border="0" cellborder="0" cellpadding="0">'
            tmpStr += '<TR><TD colspan="2" border="1" sides="b">'
            tmpStr += lbl
            tmpStr += '</TD></TR> \n'
            tmpStr += "".join(attrs_verb)
            tmpStr += '</TABLE>>'
    else:
        if clusterhead:
            tmpStr += 'target="other",'
            lbl += '\n(+)'
        tmpStr += 'label="{}"'.format(lbl)

    if interactive and target is not None:
        tmpStr += ',URL="{}"'.format(target)

    tmpStr += "];\n"
    return tmpStr


def _dot_code_attr(k, v):
    """returns no trailing commas"""
    if isinstance(v, dict):
        ostr = [_dot_code_attr(k1, v1) for k1, v1 in v.iteritems()]
        ostr = ", ".join(ostr)
    else:
        ostr = "{} = {}".format(k, v)
    return ostr


def _dot_code_edge(G, e, attrs, lbls, interactive, target=None):
    assert isinstance(e, tuple)
    # --

    def _write_verbatim(key, val):
        if not interactive:
            pass
        vstr = "{}: {}".format(key, val)
        return vstr

    # edge itself name
    tmpStr = '{} -> {} '.format(_make_dot_id(e[0]), _make_dot_id(e[1]))

    # attributes
    edata = G.get_edge_data(e[0], e[1])
    attrs_verb = []
    attrs_layout = []
    if attrs:
        for a in attrs:
            if a in edata:
                v = edata[a]
                if a in LAYOUT_ATTRS:
                    attrs_layout.append(_dot_code_attr(a, v))
                else:
                    attrs_verb.append(_write_verbatim(a, v))

    inner = ""  # the stiff between "[" and "]"
    if attrs_layout:
        inner += ",".join(attrs_layout)
    if interactive and target is not None:
        if inner and inner[-1] != ',':
            inner += ","
        inner += 'URL="{}"'.format(target)

    # label it
    if lbls is not None:
        lbl = lbls.get(e, None)
    else:
        lbl = G.edges[e].get('label', None)

    if lbl is not None:
        if inner and inner[-1] != ',':
            inner += ","
        # XXX! we use xlabel instead of label, to avoid that dot has to consider them
        # as placement constraints. Because if it does, then it becomes horribly slow.
        inner += 'xlabel="{}",'.format(lbl)

    if inner.endswith(","):
        inner = inner[:-1]
    if inner:
        tmpStr += "[{}]".format(inner)

    tmpStr += ';\n'
    # --
    return tmpStr


def _dot_code_edges(G, edges, cluster=None, attrs=None, lbls=None, interactive=False):
    outStr = ""
    for e in edges:
        edge_src_cluster = cluster.cluster_of_node(e[0]).get_scope_name() if cluster else None
        outStr += _dot_code_edge(G=G, e=e, attrs=attrs, lbls=lbls, target=edge_src_cluster,
                                 interactive=interactive)
    return outStr


def _dot_code_nodes(G, nodes, cluster=None, attrs=None, lbls=None, interactive=False):
    outStr = ""
    for n in nodes:
        if n in G.nodes:
            scopename = cluster.get_scope_name() if cluster is not None else None
            clusterhead = cluster.topnode == n
            outStr += _dot_code_node(G=G, n=n, attrs=attrs, lbls=lbls, target=scopename,
                                     clusterhead=clusterhead, interactive=interactive)
        else:
            log.debug("Ignored unknown node in rendering: {}".format(n))
    return outStr


def _get_cluster_dummynode_id(c):
    """each cluster has an invisible dummy node. This returns its name"""
    assert isinstance(c, GraphCluster)
    # --
    cid = '{}_DUMMYnode'.format(c.name)
    return _make_dot_id(cid)


def _get_cluster_id(cluster):
    assert isinstance(cluster, GraphCluster)
    cid = "cluster_{}".format(_make_classical_id(cluster.name))
    return _make_dot_id(cid)


def _dot_code_subgraph(G, cluster, attrs=None, lbls=None, interactive=False):
    """writes only nodes, recursive to create clusters."""
    assert isinstance(cluster, GraphCluster)

    def add_dummy_node(sn):
        """needed to connect two subgraphs with edges"""
        return '{} [shape=point,style=invis,URL="{}"];\n'.format(
            _get_cluster_dummynode_id(cluster), sn)

    # --
    if cluster.visible:
        cname = _get_cluster_id(cluster)
    else:
        cname = ''
    outStr = "subgraph {} {{\n".format(cname)
    outStr += ' label="{}";\n'.format(cluster.name)
    outStr += ' color={};\n'.format(cluster.color)
    outStr += ' fontcolor={};\n'.format(cluster.color)
    if cluster.topnode is not None:
        outStr += _dot_code_rank("min", cluster.topnode)

    scopename = cluster.get_scope_name()
    outStr += _dot_code_nodes(G, cluster.nodes, cluster, attrs=attrs, lbls=lbls,
                              interactive=interactive)
    outStr += add_dummy_node(scopename)
    for c in cluster.children:
        outStr += _dot_code_subgraph(G, c, attrs=attrs, lbls=lbls, interactive=interactive)

    outStr += "\n}\n"
    return outStr


def _dot_code_subgraph_edges(G, cluster, interactive=False):
    """Edges between subgraphs, as well as additional edges for interactive mode"""

    def dot_code_subgraph_edge(u, v):
        return "{} -> {} ".format(_get_cluster_dummynode_id(u), _get_cluster_dummynode_id(v)) + \
               '[ltail={},lhead={},constraint=false,color={},URL="{}"];\n'.format(
                   _get_cluster_id(u), _get_cluster_id(v), u.color, cluster.get_scope_name())

    def dot_code_collapse_edge(u, v):
        return "{} -> {} ".format(_make_dot_id(u), _make_dot_id(v)) + \
               '[constraint=false,color=orange,URL="not_{}"];\n'.format(cluster.get_scope_name())

    outStr = ""
    # children
    for c in cluster.children:
        outStr += _dot_code_subgraph_edges(G, c, interactive)
    # myself
    for r in cluster.relatives:
        outStr += dot_code_subgraph_edge(cluster, r)
    if interactive and cluster.topnode is not None:
        # all edges leaving subgraph must be copied to the topnode, to support collapse
        collapse_edges = [(cluster.topnode, v) for (_, v, d) in
                          G.out_edges(nbunch=cluster.nodes, data=True)
                          if 'virtual' not in d and v not in cluster.contained_nodes()]
        for u, v in collapse_edges:
            outStr += dot_code_collapse_edge(u, v)
    # --
    return outStr


def _dot_code_rank(which, nodes):
    rstr = '{{ rank={}; '.format(which)
    if isinstance(nodes, (list, set, tuple)):
        rstr += "; ".join([_make_dot_id(t) for t in nodes])
    else:
        rstr += _make_dot_id(nodes)
    rstr += "};\n"
    return rstr


def _dot_code_graph(G, gname=None, clusters=None, topnode=None, botnode=None,
                    attrs=None, lbls=None, interactive=False):
    """return string with graphviz/dot code"""
    # --
    intname = _make_classical_id(gname) if gname else 'g'
    outStr = ' digraph {} {{ \n'.format(intname)
    outStr += 'compound=true;\n'
    outStr += 'forcelabels=true;\n'
    # outStr += 'concentrate=true;\n'
    glbl = gname + " (interactive)".format(gname) if interactive else gname
    outStr += 'label = "{}";\n'.format(glbl)
    outStr += 'labelloc = "t";\n'
    outStr += 'stylesheet = "{}";\n'.format(CSSNAME)
    outStr += 'graph [pad="1.0", nodesep=".5", ranksep="0.5"];\n'

    if topnode is not None:
        outStr += _dot_code_rank('min', topnode)
    if botnode is not None:
        outStr += _dot_code_rank('max', botnode)

    # wrap everything into a top-level cluster to ease processing
    tl_cluster = GraphCluster("__TOPLEVEL_GRAPH", visible=False, topnode=topnode)
    if clusters is not None:
        for c in clusters:
            tl_cluster.add_child(c)
    unclustered_nodes = set(G.nodes) - set(tl_cluster.contained_nodes())
    tl_cluster.add_nodes(unclustered_nodes)

    tl_cluster.analyze()
    outStr += _dot_code_subgraph(G=G, cluster=tl_cluster, attrs=attrs, lbls=lbls,
                                 interactive=interactive)

    # all edges
    outStr += _dot_code_edges(G, G.edges, cluster=tl_cluster, attrs=attrs, lbls=lbls,
                              interactive=interactive)
    outStr += _dot_code_subgraph_edges(G, tl_cluster, interactive=interactive)

    # done
    outStr += '\n}\n'
    return outStr


def write_javascript(fpath):
    """Write a js file to support interactive graphs"""
    js = """
function ignoreHandler() { return false; }    

function toggleObjList(objs, except, on) {
    for (var i = 0; i < objs.length; i++) {
      if (objs[i] != except) {
          if (on) {
              objs[i].classList.remove("hide");
          } else {
              objs[i].classList.add("hide");
          }
      } else {
          if (on) {
              objs[i].classList.remove("collapsed");
          } else {
              objs[i].classList.add("collapsed");
          }
      }
    }
}

function getObjectContainingLink(l) { return l.parentNode.parentNode; }

function toggleCluster(clustername, except, on) {
  /* toggle visibility of a single cluster */  
  // collect all nodes from the same cluster
  objs = Array.prototype.slice.call(document.querySelectorAll('a[cluster="' + clustername + '"]'));
  objs = objs.map(getObjectContainingLink);
  // add the cluster frame itself
  cluster_basename = "cluster_" + clustername.split(".").pop();
  clusters = Array.prototype.slice.call(document.getElementsByClassName("cluster"), 0);
  cluster = clusters.filter(function(x) {
      tt = x.getElementsByTagName('title');
      if (tt) {
          t = tt[0];
          if (t.innerHTML == cluster_basename) return true;
      }
      return false;
  });
  // hide/unhide stuff
  if (cluster.length > 0) {
      if (on) {
         cluster[0].classList.remove("hide");
      } else {
         cluster[0].classList.add("hide");
      }
  }
  toggleObjList(objs, except, on);
  // handle collapsed edges
  eds = Array.prototype.slice.call(document.querySelectorAll('a[cluster="not_'+ clustername +'"]'));
  eds = eds.map(getObjectContainingLink);
  // except == null && on -> make subgraph visible -> edge off
  // except != null && on -> make subgraph visible -> edge off
  // except == null && off -> make subgraph entirely invisible -> edge off
  // eccept != null && off -> make part of subgraph invisible -> edge on
  ed_on = (except != null) && !on;
  toggleObjList(eds, null, ed_on);
}

function clickHandler(){
  clustername = this.getAttribute("cluster");
  clickedNode = getObjectContainingLink(this);
  on = (clickedNode.classList.contains('collapsed')) ? true : false;
  // toggle all subclusters
  subs = document.querySelectorAll('a[cluster][target="other"]');
  for (var i = 0; i < subs.length; i++) {
      subcluster = subs[i].getAttribute("cluster");
      if (subcluster != clustername && subcluster.startsWith(clustername)) 
        toggleCluster(subcluster, null, on);
  }
  // ... and the clicked one
  toggleCluster(clustername, clickedNode, on);
  return false; // avoid load/scroll
}

// intercept links to toggle cluster visibility
var links = Array.prototype.slice.call(document.getElementsByTagName('a'));
for (var numLinks = links.length, i=0; i<numLinks; i++){
    links[i].setAttribute('cluster', links[i].getAttribute('xlink:href'));
    if (links[i].getAttribute('target') == null) {
        links[i].onclick = ignoreHandler;  // body nodes are silent
    } else {
        links[i].onclick = clickHandler;  // topnode is clickable  
    }
}

// handle collapsed-view edges: make initially invisible
collapse_edges = links.filter(function(x) { return x.getAttribute("cluster").startsWith("not_"); });
collapse_edges = collapse_edges.map(getObjectContainingLink);
toggleObjList(collapse_edges, null, false);
"""
    with open(fpath, 'w') as fp:
        fp.write(js)


def write_stylesheet(fpath):
    """Write a CSS file to decorate the graph"""

    css = """   
.node-highlight { stroke: blue; opacity: 1;}
.hide { display: none;}
"""
    with open(fpath, 'w') as fp:
        fp.write(css)


def _render_dot(dot_code, outdir=None, name=None, prefix=None, outType='svg',
                keepfiles=False, interactive=False):
    """Call graphviz/dot to generate a picture"""

    def inject_javascript(fsvg, fjs):
        """inject javascript reference (FIXME: make platform-independent w/o sed)"""
        needle = '</svg[^>]*>'
        repl = '<script xlink:href="{}" type="text/javascript" />'.format(fjs)
        sedcmd = ['sed', '-i', r's#\({}\)#{}\n\1#g'.format(needle, repl), fsvg]
        ret = subprocess.call(sedcmd)
        if ret != 0:
            log.warning('Failed to patch svg file {} for interactive mode'.format(fsvg))

    with tempfile.NamedTemporaryFile(mode='w', delete=False) as fp:
        fp.write(dot_code)
        dotPath = os.path.realpath(fp.name)

    if outdir is None:
        outdir = tempfile.tempdir
    if name is None:
        name = str(uuid.uuid1().hex)
    if prefix is not None:
        name = ''.join([prefix, '_', name])
    assert (os.path.isdir(outdir))

    outPath = os.path.join(outdir, '.'.join([name, outType]))
    log.info("Graph rendered at: {}".format(os.path.realpath(outPath)))

    # Invoke dot
    subprocess.call(['dot', '-T' + outType, dotPath, '-o', outPath])
    if not keepfiles:
        os.remove(dotPath)

    # write CSS and JS files
    if interactive:
        csspath = os.path.join(outdir, CSSNAME)
        if not os.path.isfile(csspath):  # or True:  # FIXME: remove second clause (just for dev)
            write_stylesheet(csspath)
        if outType == 'svg':
            jspath = os.path.join(outdir, JSNAME)
            inject_javascript(outPath, os.path.basename(jspath))
            if not os.path.isfile(jspath):  # or True:  # FIXME: remove second clause (just for dev)
                write_javascript(jspath)


def render_graph(G, dir=None, name=None, prefix=None, outType='svg', interactive=False,
                 attrs=None, lbls=None, topnode=None, botnode=None, clusters=None, keepfiles=False):
    """
    Renders a single graph.

    :param G the graph to render
    :param dir output directory
    :param name of the graph
    :param prefix used for file name
    :param outType select target format
    :param interactive if True, some output formats (svg) support mouse over effects etc
    :param attrs tuple or list of attributes to be forwarded from G to dot
    :param lbls tuple or list of attributes to be forwarded from G to dot
    :param topnode node ID or list of IDs that are the entries. Used as drawing hint
    :param botnode like topnode, but for bottom
    :param clusters to draw subgraphs/clusters
    :param keepfiles if True, intermediate (dot) files are not deleted
    """
    assert isinstance(G, nx.DiGraph)
    # --
    if clusters is not None:
        assert isinstance(clusters, list) and isinstance(clusters[0], GraphCluster)
    # --
    outStr = _dot_code_graph(G, gname=name, attrs=attrs, lbls=lbls, interactive=interactive,
                             topnode=topnode, botnode=botnode, clusters=clusters)
    _render_dot(outStr, dir, name, prefix, outType, keepfiles, interactive=interactive)
