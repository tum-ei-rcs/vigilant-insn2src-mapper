
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
