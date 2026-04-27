"""공저자 네트워크 생성 — CV / ML 클러스터 색상 구분 (pre-baked layout)

위치는 빌드 시 계산. 브라우저에서 시뮬레이션 없이 즉시 렌더링.
슬라이더는 display 토글만 하므로 실시간 반응.

출력:
  - coauthor_network.json
  - coauthor_network.html

실행: python _make_coauthor_network.py
빠른 레이아웃을 원하면: pip install igraph
"""
import collections
import html as htmllib
import json
import math
import os
import random as _rand
import re
from datetime import datetime, timezone
from itertools import combinations

from _clean import is_front_matter, is_translated_dup
from _venues import VENUE_COLORS, VENUE_LABELS, CV_VENUES, ML_VENUES, CLUSTER_COLORS

INPUT    = 'all_enriched.json'
OUT_JSON = 'coauthor_network.json'
OUT_HTML = 'coauthor_network.html'

MIN_AUTHOR_PAPERS = 7    # 5→7 로 올려서 노드 수 감소
MIN_EDGE_COLLABS  = 3
DEFAULT_EDGE_VIEW = 5
CLUSTER_THRESHOLD = 0.65
LAYOUT_SCALE      = 5000  # 좌표 범위: ±5000

_dblp = re.compile(r'\s+\d{4}$')
def clean_author(s):
    return _dblp.sub('', htmllib.unescape(s)).strip()

with open(INPUT, encoding='utf-8') as f:
    papers = json.load(f)

per_author      = collections.Counter()
author_max_year = {}
paper_authors   = []

for p in papers:
    a_str = (p.get('authors') or '').strip()
    if not a_str:
        continue
    raw_title = htmllib.unescape((p.get('title') or '').strip()).rstrip('.').strip()
    if is_front_matter(raw_title) or is_translated_dup(raw_title):
        continue
    authors = [clean_author(a) for a in a_str.split(';')]
    authors = [a for a in authors if a]
    if not authors:
        continue
    try:
        y = int(p.get('year') or 0)
    except (ValueError, TypeError):
        y = 0
    try:
        cites = int(p.get('cited_by_count') or 0)
    except (ValueError, TypeError):
        cites = 0
    venue = p.get('venue', '')
    for a in authors:
        per_author[a] += 1
        if y > author_max_year.get(a, 0):
            author_max_year[a] = y
    paper_authors.append((authors, y, raw_title, cites, venue))

print(f"Papers processed: {len(paper_authors)}")
print(f"Unique authors (raw): {len(per_author)}")

valid_authors = {a for a, cnt in per_author.items() if cnt >= MIN_AUTHOR_PAPERS}
print(f"Authors with {MIN_AUTHOR_PAPERS}+ papers: {len(valid_authors)}")

edge_counts    = collections.Counter()
edge_venues    = collections.defaultdict(collections.Counter)
edge_top_paper = {}

for authors, year, title, cites, venue in paper_authors:
    valid = [a for a in authors if a in valid_authors]
    for a, b in combinations(sorted(valid), 2):
        key = (a, b)
        edge_counts[key] += 1
        edge_venues[key][venue] += 1
        if cites > edge_top_paper.get(key, (0,))[0]:
            edge_top_paper[key] = (cites, title, year)

valid_edges = [(k, v) for k, v in edge_counts.items() if v >= MIN_EDGE_COLLABS]
print(f"Edges with {MIN_EDGE_COLLABS}+ collabs: {len(valid_edges)}")

edge_authors = set()
for (a, b), _ in valid_edges:
    edge_authors.add(a)
    edge_authors.add(b)

author_cv_cnt   = collections.Counter()
author_ml_cnt   = collections.Counter()
author_cites    = collections.defaultdict(int)
author_venue_ct = collections.defaultdict(collections.Counter)

for authors, year, title, cites, venue in paper_authors:
    for a in authors:
        if a not in edge_authors:
            continue
        author_cites[a] += cites
        author_venue_ct[a][venue] += 1
        if venue in CV_VENUES:
            author_cv_cnt[a] += 1
        elif venue in ML_VENUES:
            author_ml_cnt[a] += 1

def author_cluster(a):
    cv = author_cv_cnt[a]
    ml = author_ml_cnt[a]
    total = cv + ml
    if total == 0:
        return 'CV'
    cv_ratio = cv / total
    if cv_ratio >= CLUSTER_THRESHOLD:
        return 'CV'
    elif cv_ratio <= (1 - CLUSTER_THRESHOLD):
        return 'ML'
    return 'Mixed'

def dominant_venue(a):
    vc = author_venue_ct[a]
    return vc.most_common(1)[0][0] if vc else ''

nodes    = []
node_idx = {}
cluster_counts = collections.Counter()

for i, a in enumerate(sorted(edge_authors)):
    node_idx[a] = i
    cl = author_cluster(a)
    cluster_counts[cl] += 1
    cv  = author_cv_cnt[a]
    ml  = author_ml_cnt[a]
    tot = cv + ml
    nodes.append({
        'id': i, 'name': a,
        'papers': per_author[a],
        'last_year': author_max_year.get(a, 0),
        'dominant_venue': dominant_venue(a),
        'cluster': cl,
        'color': CLUSTER_COLORS[cl],
        'cv_papers': cv,
        'ml_papers': ml,
        'cv_ratio': round(cv / tot, 2) if tot else 1.0,
        'total_citations': author_cites[a],
        'x': 0.0, 'y': 0.0,
    })

print(f"Cluster breakdown: {dict(cluster_counts)}")

edges_out = []
for (a, b), cnt in valid_edges:
    ai, bi = node_idx.get(a), node_idx.get(b)
    if ai is None or bi is None:
        continue
    top = edge_top_paper.get((a, b), (0, '', 0))
    ev  = edge_venues.get((a, b), {})
    ca, cb = nodes[ai]['cluster'], nodes[bi]['cluster']
    edge_color = (CLUSTER_COLORS['Mixed'] if ca != cb
                  else CLUSTER_COLORS.get(ca, '#555'))
    edges_out.append({
        'source': ai, 'target': bi,
        'weight': cnt,
        'color': edge_color,
        'top_paper_cites': top[0],
        'top_paper_title': top[1],
        'top_paper_year': top[2],
        'venues': dict(ev),
    })

# ── Pre-baked layout ─────────────────────────────────────────────────────────
def _compute_layout(nodes, edges_out):
    n = len(nodes)
    if not n:
        return
    print(f"Computing layout ({n} nodes, {len(edges_out)} edges)...")

    # igraph: fastest (C implementation)
    try:
        import igraph as ig
        g = ig.Graph(n=n)
        g.add_edges([(e['source'], e['target']) for e in edges_out])
        weights = [float(e['weight']) for e in edges_out]
        lyt = g.layout_fruchterman_reingold(niter=300, weights=weights)
        xs = [p[0] for p in lyt.coords]
        ys = [p[1] for p in lyt.coords]
        xr = max(xs) - min(xs) or 1
        yr = max(ys) - min(ys) or 1
        xmn, ymn = min(xs), min(ys)
        for i, nd in enumerate(nodes):
            nd['x'] = round((xs[i] - xmn) / xr * 2 * LAYOUT_SCALE - LAYOUT_SCALE, 1)
            nd['y'] = round((ys[i] - ymn) / yr * 2 * LAYOUT_SCALE - LAYOUT_SCALE, 1)
        print("  igraph Fruchterman-Reingold done")
        return
    except ImportError:
        pass

    # networkx: slower but no extra deps beyond common scipy stack
    try:
        import networkx as nx
        G = nx.Graph()
        G.add_nodes_from(range(n))
        G.add_edges_from([(e['source'], e['target']) for e in edges_out])
        k = 2.0 / n ** 0.5
        pos = nx.spring_layout(G, k=k, iterations=50, seed=42, scale=LAYOUT_SCALE)
        for nd in nodes:
            p = pos.get(nd['id'], (0.0, 0.0))
            nd['x'] = round(float(p[0]), 1)
            nd['y'] = round(float(p[1]), 1)
        print("  networkx spring_layout done")
        return
    except ImportError:
        pass

    # Cluster-based fallback: no deps, decent CV/ML visual separation
    _rand.seed(42)
    centers = {'CV': (-2800.0, 0.0), 'ML': (2800.0, 0.0), 'Mixed': (0.0, 2200.0)}
    for nd in nodes:
        cx, cy = centers.get(nd['cluster'], (0.0, 0.0))
        angle = _rand.uniform(0, 2 * math.pi)
        r = _rand.uniform(100, LAYOUT_SCALE * 0.65)
        nd['x'] = round(cx + r * math.cos(angle), 1)
        nd['y'] = round(cy + r * math.sin(angle), 1)
    print("  cluster-based fallback done  (pip install igraph for better layout)")

_compute_layout(nodes, edges_out)

# ── Save JSON ────────────────────────────────────────────────────────────────
meta = {
    'generated': datetime.now(timezone.utc).isoformat(),
    'min_author_papers': MIN_AUTHOR_PAPERS,
    'min_edge_collabs': MIN_EDGE_COLLABS,
    'node_count': len(nodes),
    'edge_count': len(edges_out),
    'cluster_counts': dict(cluster_counts),
}
out_data = {'nodes': nodes, 'edges': edges_out, 'meta': meta}
with open(OUT_JSON, 'w', encoding='utf-8') as f:
    json.dump(out_data, f, ensure_ascii=False)
print(f"Saved {OUT_JSON}: {len(nodes)} nodes, {len(edges_out)} edges")

# ── HTML ─────────────────────────────────────────────────────────────────────
data_js           = json.dumps(out_data, ensure_ascii=False)
cluster_colors_js = json.dumps(CLUSTER_COLORS, ensure_ascii=False)
venue_colors_js   = json.dumps(VENUE_COLORS,   ensure_ascii=False)

HTML = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>CV+ML Co-author Network</title>
<style>
* {{ box-sizing: border-box; margin:0; padding:0; }}
body {{ font-family: -apple-system,"Segoe UI",sans-serif; background:#111; color:#eee; overflow:hidden; }}

#controls {{
  position:fixed; top:12px; left:12px; z-index:10;
  background:rgba(18,18,18,0.92); border:1px solid #333;
  padding:14px 16px; border-radius:10px; font-size:13px; width:240px;
}}
#controls h2 {{ margin:0 0 12px; font-size:15px; color:#fff; }}
#controls label {{ display:block; margin:8px 0 2px; color:#aaa; font-size:12px; }}
#controls input[type=range] {{ width:100%; accent-color:#9467bd; }}
.val {{ color:#fff; font-weight:600; }}
#legend {{ margin-top:14px; padding-top:12px; border-top:1px solid #333; }}
#legend h3 {{ margin:0 0 8px; font-size:12px; color:#999; text-transform:uppercase; letter-spacing:0.5px; }}
.legend-row {{ display:flex; align-items:center; gap:8px; margin:5px 0; font-size:12px; color:#ccc; }}
.legend-dot {{ width:12px; height:12px; border-radius:50%; flex-shrink:0; }}
.legend-count {{ color:#666; font-size:11px; margin-left:auto; }}
#color-by {{
  margin-top:10px; display:flex; border:1px solid #444; border-radius:6px; overflow:hidden;
}}
#color-by button {{
  flex:1; padding:5px 0; font-size:12px; border:none; cursor:pointer;
  background:#222; color:#888; transition:background 0.15s;
}}
#color-by button.active {{ background:#9467bd; color:#fff; }}
#stats {{ margin-top:10px; font-size:11px; color:#666; line-height:1.6; }}
#info {{
  position:fixed; bottom:16px; left:12px; z-index:10;
  background:rgba(18,18,18,0.92); border:1px solid #333;
  padding:12px 14px; border-radius:10px; font-size:12px;
  max-width:260px; display:none;
}}
#info .name {{ font-size:14px; font-weight:600; margin-bottom:6px; color:#fff; }}
#info .cluster-badge {{
  display:inline-block; padding:2px 8px; border-radius:10px;
  font-size:11px; font-weight:600; margin-bottom:8px;
}}
#info .row {{ display:flex; justify-content:space-between; color:#aaa; margin:3px 0; }}
#info .row b {{ color:#eee; }}
.close-btn {{ float:right; cursor:pointer; color:#666; font-size:14px; margin-top:-2px; }}
.close-btn:hover {{ color:#fff; }}
canvas {{ display:block; cursor:grab; }}
canvas.panning {{ cursor:grabbing; }}
</style>
</head>
<body>
<div id="controls">
  <h2>CV+ML Co-author Network</h2>
  <label>Min collaborations: <span class="val" id="edge-val">{DEFAULT_EDGE_VIEW}</span></label>
  <input type="range" id="edge-slider" min="{MIN_EDGE_COLLABS}" max="20" value="{DEFAULT_EDGE_VIEW}">
  <label>Node size by:</label>
  <select id="size-by" style="width:100%;padding:4px;background:#222;color:#eee;border:1px solid #444;border-radius:4px;">
    <option value="papers">Paper count</option>
    <option value="citations">Total citations</option>
  </select>
  <label style="margin-top:10px;">Color by:</label>
  <div id="color-by">
    <button class="active" onclick="setColorMode('cluster')">CV / ML Cluster</button>
    <button onclick="setColorMode('venue')">Dominant Venue</button>
  </div>
  <div id="legend">
    <h3>Cluster</h3>
    <div class="legend-row">
      <div class="legend-dot" style="background:#1f77b4"></div>
      CV <small style="color:#666">(CVPR·ICCV·ECCV·3DV)</small>
      <span class="legend-count" id="cnt-cv">-</span>
    </div>
    <div class="legend-row">
      <div class="legend-dot" style="background:#d62728"></div>
      ML <small style="color:#666">(NeurIPS·ICML·ICLR)</small>
      <span class="legend-count" id="cnt-ml">-</span>
    </div>
    <div class="legend-row">
      <div class="legend-dot" style="background:#9467bd"></div>
      Mixed <span class="legend-count" id="cnt-mix">-</span>
    </div>
  </div>
  <div id="stats"></div>
</div>

<div id="info">
  <span class="close-btn" onclick="document.getElementById('info').style.display='none'">✕</span>
  <div class="name" id="info-name"></div>
  <div class="cluster-badge" id="info-badge"></div>
  <div class="row"><span>Papers</span><b id="info-papers"></b></div>
  <div class="row"><span>CV papers</span><b id="info-cv"></b></div>
  <div class="row"><span>ML papers</span><b id="info-ml"></b></div>
  <div class="row"><span>Citations</span><b id="info-cites"></b></div>
  <div class="row"><span>Dominant venue</span><b id="info-venue"></b></div>
  <div class="row"><span>Last active</span><b id="info-year"></b></div>
</div>

<canvas id="canvas"></canvas>

<script>
const DATA           = {data_js};
const CLUSTER_COLORS = {cluster_colors_js};
const VENUE_COLORS   = {venue_colors_js};
const DEF_EDGE       = {DEFAULT_EDGE_VIEW};
const MIN_EDGE       = {MIN_EDGE_COLLABS};

// Legend counts
const cc = DATA.meta.cluster_counts || {{}};
document.getElementById('cnt-cv').textContent  = (cc.CV    || 0).toLocaleString();
document.getElementById('cnt-ml').textContent  = (cc.ML    || 0).toLocaleString();
document.getElementById('cnt-mix').textContent = (cc.Mixed || 0).toLocaleString();

// ── Canvas setup ─────────────────────────────────────────────────────────────
const canvas = document.getElementById('canvas');
const ctx    = canvas.getContext('2d');
function resize() {{
  canvas.width  = window.innerWidth;
  canvas.height = window.innerHeight;
  draw();
}}
window.addEventListener('resize', resize);
canvas.width  = window.innerWidth;
canvas.height = window.innerHeight;
const W = () => canvas.width, H = () => canvas.height;

// ── Node data setup ───────────────────────────────────────────────────────────
const nodeById = {{}};
DATA.nodes.forEach(n => {{
  n.px = n.x || 0;
  n.py = n.y || 0;
  nodeById[n.id] = n;
}});

// Per-node edge list for drag updates
const nodeEdgeList = {{}};
DATA.edges.forEach(e => {{
  (nodeEdgeList[e.source] = nodeEdgeList[e.source] || []).push(e);
  (nodeEdgeList[e.target] = nodeEdgeList[e.target] || []).push(e);
}});

// ── Initial viewport transform ────────────────────────────────────────────────
const allPX = DATA.nodes.map(n => n.px);
const allPY = DATA.nodes.map(n => n.py);
const gxMin = allPX.reduce((a,b) => Math.min(a,b),  Infinity);
const gxMax = allPX.reduce((a,b) => Math.max(a,b), -Infinity);
const gyMin = allPY.reduce((a,b) => Math.min(a,b),  Infinity);
const gyMax = allPY.reduce((a,b) => Math.max(a,b), -Infinity);
let scale = Math.min(
  W() * 0.78 / Math.max(gxMax - gxMin, 1),
  H() * 0.78 / Math.max(gyMax - gyMin, 1)
);
let tx = W()/2 - (gxMin + gxMax)/2 * scale;
let ty = H()/2 - (gyMin + gyMax)/2 * scale;

// ── State ─────────────────────────────────────────────────────────────────────
let colorMode    = 'cluster';
let sizeMode     = 'papers';
let edgeThreshold = DEF_EDGE;
let visEdges     = [], visNodes = [], visNodeSet = new Set();
let hoveredNode  = null;
let selectedNode = null;
let dragNode     = null, dragOffGX = 0, dragOffGY = 0;
let isPanning    = false, panSX = 0, panSY = 0;
let rafId        = null;

// ── Helpers ───────────────────────────────────────────────────────────────────
function nodeColor(n) {{
  return colorMode === 'venue'
    ? (VENUE_COLORS[n.dominant_venue] || '#aaa')
    : (CLUSTER_COLORS[n.cluster]      || '#aaa');
}}
function nodeR(n) {{
  return sizeMode === 'citations'
    ? Math.max(2, Math.sqrt(n.total_citations / 80 + 1) * 3.5)
    : Math.max(2, Math.sqrt(n.papers) * 4.5);
}}
function edgeCol(e) {{
  return colorMode === 'venue' ? '#555' : (e.color || '#555');
}}
function s2g(sx, sy) {{   // screen → graph coords
  return [(sx - tx) / scale, (sy - ty) / scale];
}}

// ── Filter ────────────────────────────────────────────────────────────────────
function applyFilter() {{
  visEdges   = DATA.edges.filter(e => e.weight >= edgeThreshold);
  visNodeSet = new Set();
  visEdges.forEach(e => {{ visNodeSet.add(e.source); visNodeSet.add(e.target); }});
  visNodes   = DATA.nodes.filter(n => visNodeSet.has(n.id));

  const cvN  = visNodes.filter(n => n.cluster === 'CV').length;
  const mlN  = visNodes.filter(n => n.cluster === 'ML').length;
  const mixN = visNodes.length - cvN - mlN;
  document.getElementById('stats').innerHTML =
    `${{visNodes.length.toLocaleString()}} researchers · ${{visEdges.length.toLocaleString()}} pairs<br>` +
    `<span style="color:#1f77b4">CV: ${{cvN}}</span> &nbsp;` +
    `<span style="color:#d62728">ML: ${{mlN}}</span> &nbsp;` +
    `<span style="color:#9467bd">Mixed: ${{mixN}}</span>`;
  requestDraw();
}}

// ── Draw (full Canvas, batched by color) ──────────────────────────────────────
function requestDraw() {{
  if (!rafId) rafId = requestAnimationFrame(() => {{ rafId = null; draw(); }});
}}

function draw() {{
  const w = W(), h = H();
  ctx.clearRect(0, 0, w, h);
  ctx.save();
  ctx.translate(tx, ty);
  ctx.scale(scale, scale);

  // ── Edges: group by color → minimal strokeStyle changes ──────────────────
  const edgeGroups = {{}};
  for (const e of visEdges) {{
    const c = edgeCol(e);
    (edgeGroups[c] = edgeGroups[c] || []).push(e);
  }}
  ctx.globalAlpha = 0.32;
  ctx.lineWidth   = 1 / scale;
  for (const [col, edges] of Object.entries(edgeGroups)) {{
    ctx.strokeStyle = col;
    ctx.beginPath();
    for (const e of edges) {{
      const s = nodeById[e.source], t = nodeById[e.target];
      ctx.moveTo(s.px, s.py);
      ctx.lineTo(t.px, t.py);
    }}
    ctx.stroke();
  }}

  // ── Nodes: fill batched by color ─────────────────────────────────────────
  const nodeGroups = {{}};
  for (const n of visNodes) {{
    const c = nodeColor(n);
    (nodeGroups[c] = nodeGroups[c] || []).push(n);
  }}
  ctx.globalAlpha = 0.88;
  for (const [col, nodes] of Object.entries(nodeGroups)) {{
    ctx.fillStyle = col;
    ctx.beginPath();
    for (const n of nodes) {{
      const r = nodeR(n);
      ctx.moveTo(n.px + r, n.py);
      ctx.arc(n.px, n.py, r, 0, Math.PI * 2);
    }}
    ctx.fill();
  }}

  // ── Node outlines: single batched stroke ──────────────────────────────────
  ctx.globalAlpha  = 0.5;
  ctx.strokeStyle  = '#111';
  ctx.lineWidth    = 1.5 / scale;
  ctx.beginPath();
  for (const n of visNodes) {{
    const r = nodeR(n);
    ctx.moveTo(n.px + r, n.py);
    ctx.arc(n.px, n.py, r, 0, Math.PI * 2);
  }}
  ctx.stroke();

  // ── Hovered / selected node ring + label ─────────────────────────────────
  const highlight = hoveredNode || selectedNode;
  if (highlight && visNodeSet.has(highlight.id)) {{
    const r = nodeR(highlight);
    ctx.globalAlpha  = 1;
    ctx.strokeStyle  = '#fff';
    ctx.lineWidth    = 2.5 / scale;
    ctx.beginPath();
    ctx.arc(highlight.px, highlight.py, r + 4/scale, 0, Math.PI * 2);
    ctx.stroke();
    // name label
    const fs = Math.max(10, 12/scale);
    ctx.font      = `600 ${{fs}}px -apple-system,sans-serif`;
    ctx.fillStyle = '#fff';
    ctx.textAlign = 'center';
    ctx.shadowColor = '#000'; ctx.shadowBlur = 4/scale;
    ctx.fillText(highlight.name, highlight.px, highlight.py - r - 5/scale);
    ctx.shadowBlur = 0;
  }}

  // ── LOD labels: show at high zoom for prolific authors ────────────────────
  if (scale > 0.22) {{
    const minP  = Math.max(25, 70 / scale);
    const alpha = Math.min(1, (scale - 0.22) * 5);
    const fs    = Math.max(8, 10 / scale);
    ctx.globalAlpha = alpha * 0.75;
    ctx.fillStyle   = '#bbb';
    ctx.font        = `${{fs}}px -apple-system,sans-serif`;
    ctx.textAlign   = 'center';
    for (const n of visNodes) {{
      if (n.papers >= minP && n !== highlight) {{
        ctx.fillText(n.name, n.px, n.py - nodeR(n) - 3/scale);
      }}
    }}
  }}

  ctx.restore();
}}

// ── Hit detection ─────────────────────────────────────────────────────────────
function findNode(sx, sy) {{
  const [gx, gy] = s2g(sx, sy);
  const hit = 5 / scale;
  let best = null, bestD2 = Infinity;
  for (const n of visNodes) {{
    const r = nodeR(n) + hit;
    const dx = n.px - gx, dy = n.py - gy, d2 = dx*dx + dy*dy;
    if (d2 < r*r && d2 < bestD2) {{ best = n; bestD2 = d2; }}
  }}
  return best;
}}

// ── Mouse events ──────────────────────────────────────────────────────────────
canvas.addEventListener('mousedown', e => {{
  const r = canvas.getBoundingClientRect();
  const sx = e.clientX - r.left, sy = e.clientY - r.top;
  const node = findNode(sx, sy);
  if (node) {{
    dragNode = node;
    const [gx, gy] = s2g(sx, sy);
    dragOffGX = node.px - gx;
    dragOffGY = node.py - gy;
  }} else {{
    isPanning = true;
    panSX = e.clientX - tx;
    panSY = e.clientY - ty;
    canvas.classList.add('panning');
  }}
  e.preventDefault();
}});

canvas.addEventListener('mousemove', e => {{
  const r = canvas.getBoundingClientRect();
  const sx = e.clientX - r.left, sy = e.clientY - r.top;

  if (dragNode) {{
    const [gx, gy] = s2g(sx, sy);
    dragNode.px = gx + dragOffGX;
    dragNode.py = gy + dragOffGY;
    requestDraw();
    return;
  }}
  if (isPanning) {{
    tx = e.clientX - panSX;
    ty = e.clientY - panSY;
    requestDraw();
    return;
  }}
  // Hover
  const node = findNode(sx, sy);
  if (node !== hoveredNode) {{
    hoveredNode = node;
    canvas.style.cursor = node ? 'pointer' : 'grab';
    requestDraw();
  }}
}});

canvas.addEventListener('mouseup', e => {{
  if (!dragNode && !isPanning) {{   // it was a click
    const r = canvas.getBoundingClientRect();
    const node = findNode(e.clientX - r.left, e.clientY - r.top);
    if (node) {{ selectedNode = node; showInfo(node); }}
    else {{ selectedNode = null; document.getElementById('info').style.display='none'; }}
    requestDraw();
  }}
  dragNode  = null;
  isPanning = false;
  canvas.classList.remove('panning');
}});

canvas.addEventListener('mouseleave', () => {{
  hoveredNode = null;
  dragNode    = null;
  isPanning   = false;
  canvas.classList.remove('panning');
  requestDraw();
}});

canvas.addEventListener('wheel', e => {{
  e.preventDefault();
  const r   = canvas.getBoundingClientRect();
  const sx  = e.clientX - r.left, sy = e.clientY - r.top;
  const fac = e.deltaY < 0 ? 1.15 : 1/1.15;
  const ns  = Math.max(0.01, Math.min(15, scale * fac));
  tx = sx - (sx - tx) * ns / scale;
  ty = sy - (sy - ty) * ns / scale;
  scale = ns;
  requestDraw();
}}, {{ passive: false }});

// ── Controls ──────────────────────────────────────────────────────────────────
document.getElementById('edge-slider').addEventListener('input', e => {{
  edgeThreshold = +e.target.value;
  document.getElementById('edge-val').textContent = edgeThreshold;
  applyFilter();
}});
document.getElementById('size-by').addEventListener('change', e => {{
  sizeMode = e.target.value;
  requestDraw();
}});
function setColorMode(mode) {{
  colorMode = mode;
  document.querySelectorAll('#color-by button').forEach(b =>
    b.classList.toggle('active', b.textContent.includes(mode==='cluster'?'Cluster':'Venue'))
  );
  requestDraw();
}}

// ── Info panel ────────────────────────────────────────────────────────────────
function showInfo(d) {{
  document.getElementById('info').style.display = 'block';
  document.getElementById('info-name').textContent = d.name;
  const badge = document.getElementById('info-badge');
  badge.textContent      = d.cluster;
  badge.style.background = CLUSTER_COLORS[d.cluster] + '33';
  badge.style.color      = CLUSTER_COLORS[d.cluster];
  badge.style.border     = `1px solid ${{CLUSTER_COLORS[d.cluster]}}55`;
  document.getElementById('info-papers').textContent = d.papers.toLocaleString();
  document.getElementById('info-cv').textContent     = d.cv_papers + (d.cv_ratio < 1 ? ` (${{Math.round(d.cv_ratio*100)}}%)` : '');
  document.getElementById('info-ml').textContent     = d.ml_papers;
  document.getElementById('info-cites').textContent  = d.total_citations.toLocaleString();
  document.getElementById('info-venue').textContent  = d.dominant_venue || '—';
  document.getElementById('info-year').textContent   = d.last_year || '—';
}}

// ── Init ──────────────────────────────────────────────────────────────────────
applyFilter();
</script>
</body>
</html>"""

with open(OUT_HTML, 'w', encoding='utf-8') as f:
    f.write(HTML)
print(f"Saved {OUT_HTML}")
