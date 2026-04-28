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
paper_year_min  = 9999
paper_year_max  = 0

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
    if y > 0:
        if y < paper_year_min:
            paper_year_min = y
        if y > paper_year_max:
            paper_year_max = y
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
author_top_papers = collections.defaultdict(list)  # name -> [(cites, title, year)]

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
        author_top_papers[a].append((cites, title, year))

# Keep only top 3 most-cited papers per author
for a in author_top_papers:
    author_top_papers[a] = sorted(author_top_papers[a], reverse=True)[:3]

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
    top_paps = [{'t': t, 'y': y, 'c': c}
                for c, t, y in author_top_papers.get(a, [])]
    nodes.append({
        'id': i, 'name': a, 'label': a,
        'papers': per_author[a],
        'last_year': author_max_year.get(a, 0),
        'dominant_venue': dominant_venue(a),
        'cluster': cl,
        'color': CLUSTER_COLORS[cl],
        'cv_papers': cv,
        'ml_papers': ml,
        'cv_ratio': round(cv / tot, 2) if tot else 1.0,
        'total_citations': author_cites[a],
        'top': top_paps,
        'x': 0.0, 'y': 0.0,
    })

print(f"Cluster breakdown: {dict(cluster_counts)}")

edges_out = []
for (a, b), cnt in valid_edges:
    ai, bi = node_idx.get(a), node_idx.get(b)
    if ai is None or bi is None:
        continue
    edges_out.append({
        'source': ai, 'target': bi,
        'weight': cnt,
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
    'built_at': datetime.now(timezone.utc).isoformat(),
    'min_author_papers': MIN_AUTHOR_PAPERS,
    'min_edge_collabs': MIN_EDGE_COLLABS,
    'node_count': len(nodes),
    'edge_count': len(edges_out),
    'nodes': len(nodes),
    'edges': len(edges_out),
    'cluster_counts': dict(cluster_counts),
    'venues': list(VENUE_LABELS.values()) if isinstance(VENUE_LABELS, dict) else list(VENUE_LABELS),
    'paper_year_min': paper_year_min if paper_year_min < 9999 else 0,
    'paper_year_max': paper_year_max,
}
out_data = {'nodes': nodes, 'edges': edges_out, 'meta': meta}
with open(OUT_JSON, 'w', encoding='utf-8') as f:
    json.dump(out_data, f, ensure_ascii=False)
print(f"Saved {OUT_JSON}: {len(nodes)} nodes, {len(edges_out)} edges")

# ── HTML (slim shell — loads data via fetch) ──────────────────────────────────
HTML = """\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Co-authorship network — CV+ML Paper Atlas</title>
<script src="https://d3js.org/d3.v7.min.js"></script>
<style>
  * { box-sizing: border-box; }
  html, body { margin: 0; padding: 0; height: 100%; font-family: -apple-system, "Segoe UI", sans-serif; background: #0f1117; color: #e5e7eb; overflow: hidden; }
  canvas { display: block; background: #0f1117; }
  .panel {
    position: fixed; background: rgba(17, 24, 39, 0.92); color: #e5e7eb;
    border: 1px solid #374151; border-radius: 8px; padding: 12px 14px;
    font-size: 12.5px; backdrop-filter: blur(6px);
  }
  #info { top: 14px; left: 14px; max-width: 320px; max-height: calc(100vh - 28px); overflow-y: auto; }
  #info h1 { font-size: 15px; margin: 0 0 6px; font-weight: 600; color: #f3f4f6; }
  #info .home { display: block; font-size: 11px; letter-spacing: 0.3px; color: #6b7280; text-decoration: none; margin-bottom: 4px; }
  #info .home:hover { color: #38bdf8; }
  #info .meta { color: #9ca3af; font-size: 11px; margin-bottom: 8px; line-height: 1.6; }
  #info .meta .count  { color: #e5e7eb; font-size: 12.5px; font-weight: 600; line-height: 1.35; }
  #info .meta .params { color: #6b7280; font-size: 10.5px; margin-top: 2px; }
  #info .meta .scope  { margin-top: 6px; padding-top: 6px; border-top: 1px solid #2a2f3a; font-size: 10.5px; line-height: 1.55; color: #9ca3af; }
  #info .meta .scope .k { color: #6b7280; margin-right: 5px; }
  #info .controls { display: flex; gap: 6px; flex-wrap: wrap; margin-top: 4px; }
  #info button, #info select, #info input {
    font-size: 11px; padding: 4px 8px; background: #1f2937; color: #e5e7eb;
    border: 1px solid #374151; border-radius: 4px; cursor: pointer;
  }
  #info button:hover { background: #374151; }
  #selected { margin-top: 10px; padding-top: 8px; border-top: 1px solid #374151; min-height: 28px; }
  #selected .name { font-weight: 600; color: #38bdf8; font-size: 13px; }
  #selected .stat { color: #9ca3af; font-size: 11px; margin-top: 2px; }
  #search {
    width: 100%; padding: 5px 8px; font-size: 12px;
    background: #1f2937; color: #e5e7eb; border: 1px solid #374151;
    border-radius: 4px; outline: none;
  }
  #search:focus { border-color: #38bdf8; }
  #results { margin-top: 6px; max-height: 260px; overflow-y: auto; }
  .result-item {
    padding: 4px 8px; cursor: pointer; display: flex;
    justify-content: space-between; gap: 8px;
    border-radius: 3px; font-size: 12px;
  }
  .result-item:hover { background: #374151; }
  .result-item .count { color: #9ca3af; font-variant-numeric: tabular-nums; }
  .result-item.unconn { opacity: 0.5; }
  .result-item.unconn:hover { background: #2a1f1f; }
  .toggle-small {
    width: 100%; text-align: left;
    font-size: 12px; padding: 5px 8px;
    background: #1f2937; color: #e5e7eb;
    border: 1px solid #374151; border-radius: 4px; cursor: pointer;
  }
  .toggle-small:hover { background: #2d3748; }
  #hubs-list { max-height: 280px; overflow-y: auto; margin-top: 4px; }
  .hub-item {
    padding: 4px 6px; cursor: pointer; display: flex;
    align-items: baseline; gap: 6px; border-radius: 3px; font-size: 12px;
  }
  .hub-item:hover { background: #374151; }
  .hub-item .rank { color: #6b7280; font-size: 10px; min-width: 22px; text-align: right; }
  .hub-item .name { flex: 1; }
  .hub-item .count { color: #9ca3af; font-variant-numeric: tabular-nums; font-size: 11px; }
  #comms-list { max-height: 320px; overflow-y: auto; margin-top: 4px; }
  .comm-item {
    padding: 5px 6px 5px 8px; cursor: pointer; border-left: 3px solid transparent;
    border-radius: 2px; margin-bottom: 2px; font-size: 11.5px; line-height: 1.35;
  }
  .comm-item:hover { background: #374151; }
  .comm-item.sel { background: #1e3a5f; outline: 1px solid #38bdf8; }
  .comm-item .hd { display: flex; align-items: baseline; gap: 6px; }
  .comm-item .name { flex: 1; color: #e5e7eb; font-weight: 500; }
  .comm-item .count { color: #9ca3af; font-variant-numeric: tabular-nums; font-size: 10.5px; }
  .comm-item .kw { color: #9ca3af; font-size: 10px; margin-top: 2px; }
  #legend { bottom: 14px; right: 14px; font-size: 11px; color: #9ca3af; max-width: 420px; }
  #tooltip {
    position: fixed; background: #1f2937; color: #e5e7eb; padding: 8px 10px;
    border-radius: 4px; font-size: 12px; pointer-events: none;
    display: none; z-index: 100; max-width: 320px;
    box-shadow: 0 4px 14px rgba(0, 0, 0, 0.5);
    border: 1px solid #374151;
  }
  #tooltip .tt-name { font-weight: 600; color: #f3f4f6; }
  #tooltip .tt-stat { color: #9ca3af; font-size: 11px; margin: 2px 0 5px; }
  #tooltip .tt-top { font-size: 11px; color: #cbd5e1; line-height: 1.55; margin-top: 6px; padding-top: 6px; border-top: 1px solid #374151; }
  #tooltip .tt-top b { color: #fcd34d; font-weight: 500; }
  #tooltip .tt-top .pap { display: block; margin-left: 2px; }
  #tooltip .tt-top .mc { color: #9ca3af; }
  #tooltip .tt-co { font-size: 11px; color: #cbd5e1; line-height: 1.55; margin-top: 6px; padding-top: 6px; border-top: 1px solid #374151; }
  #tooltip .tt-co b { color: #38bdf8; font-weight: 500; }
  #tooltip .tt-comm { font-size: 11px; color: #cbd5e1; line-height: 1.55; margin-top: 6px; padding-top: 6px; border-top: 1px solid #374151; }
  #tooltip .tt-comm .kw { color: #9ca3af; }
  .slider-row { display: flex; align-items: center; gap: 8px; margin-top: 6px; }
  .slider-row input[type="range"] { flex: 1; }
  .slider-row .val { font-variant-numeric: tabular-nums; min-width: 22px; text-align: right; color: #9ca3af; }
</style>
</head>
<body>
<canvas id="net"></canvas>
<div class="panel" id="info">
  <a href="index.html" class="home">← CV+ML Paper Atlas</a>
  <h1>Co-authorship network</h1>
  <div class="meta" id="meta-text"></div>
  <div class="slider-row">
    <span style="font-size:11px;">Edge threshold</span>
    <input type="range" id="edge-slider" min="2" max="30" value="5">
    <span class="val" id="edge-val">5</span>
  </div>
  <div class="slider-row">
    <span style="font-size:11px;">Layout spread</span>
    <input type="range" id="sparsity-slider" min="1" max="10" step="0.5" value="5">
    <span class="val" id="sparsity-val">5</span>
  </div>
  <div class="slider-row" style="gap: 10px;">
    <span style="font-size:11px;">Color</span>
    <label style="font-size:11px;display:inline-flex;align-items:center;gap:4px;cursor:pointer;"><input type="radio" name="cmode" value="community" checked>community</label>
    <label style="font-size:11px;display:inline-flex;align-items:center;gap:4px;cursor:pointer;"><input type="radio" name="cmode" value="year">year</label>
  </div>
  <div class="controls">
    <button id="restart">Restart</button>
    <button id="freeze">Freeze</button>
    <button id="center">Center</button>
  </div>
  <div style="margin-top: 10px;">
    <input type="text" id="search" placeholder="Search author name…" autocomplete="off">
    <div id="results"></div>
  </div>
  <div style="margin-top: 10px;">
    <button id="btn-hubs" class="toggle-small">▸ Top 100 hubs (most co-authors)</button>
    <div id="hubs-list" style="display:none;"></div>
  </div>
  <div style="margin-top: 10px;">
    <button id="btn-comms" class="toggle-small">▸ Communities</button>
    <div id="comms-panel" style="display:none;">
      <div id="comms-summary" style="font-size:11px; color:#9ca3af; margin: 6px 0 3px;"></div>
      <canvas id="comms-hist" width="300" height="78" style="display:block; width:100%; max-width:300px;"></canvas>
      <div id="comms-list" style="max-height:260px; overflow-y:auto; margin-top:6px;"></div>
    </div>
  </div>
  <div style="margin-top: 8px; font-size: 12px;">
    <label style="display: inline-flex; align-items: center; gap: 6px; cursor: pointer;">
      <input type="checkbox" id="show-degrees">
      Show 2nd/3rd degree connections
    </label>
    <div id="tier-legend" style="display:none; margin-top: 4px; font-size: 11px; color: #9ca3af;">
      <span style="color:#34d399;">● 1st</span>
      <span style="color:#818cf8; margin-left: 10px;">● 2nd</span>
      <span style="color:#f59e0b; margin-left: 10px;">● 3rd</span>
    </div>
  </div>
  <div id="selected"></div>
</div>
<div class="panel" id="legend">
  <div id="legend-year" style="display: none; align-items: center; gap: 8px; margin-bottom: 3px;">
    <span style="color:#cbd5e1;">Node color = author's most recent year</span>
    <span id="year-min" style="color:#9ca3af; font-variant-numeric: tabular-nums;">—</span>
    <canvas id="color-bar" width="140" height="8" style="border-radius: 2px; display: block;"></canvas>
    <span id="year-max" style="color:#9ca3af; font-variant-numeric: tabular-nums;">—</span>
  </div>
  <div id="legend-comm" style="color:#cbd5e1; margin-bottom: 3px;">
    Node color = research community · <span id="comm-count" style="color:#e5e7eb;">—</span> communities detected via Leiden · hover a node for topic
  </div>
  <div style="color:#9ca3af;">Node size = # papers · Edge thickness = # co-authored papers</div>
  <div style="color:#6b7280; margin-top: 2px;">Drag to pan · wheel to zoom · click node to pin · drag node to reposition</div>
</div>
<div id="tooltip">
  <div class="tt-name" id="tt-name"></div>
  <div class="tt-stat" id="tt-stat"></div>
  <div class="tt-comm" id="tt-comm"></div>
  <div class="tt-top" id="tt-top"></div>
  <div class="tt-co" id="tt-co"></div>
</div>

<script>
const canvas = document.getElementById('net');
const ctx = canvas.getContext('2d');
let width = canvas.width = window.innerWidth;
let height = canvas.height = window.innerHeight;

const metaEl = document.getElementById('meta-text');
metaEl.innerHTML = '<div class="count">Loading…</div><div class="params">fetching coauthor_network.json</div>';

(async function boot() {
let DATA;
try {
  const res = await fetch('coauthor_network.json');
  if (!res.ok) throw new Error('HTTP ' + res.status);
  DATA = await res.json();
} catch (err) {
  metaEl.innerHTML = '<div class="count" style="color:#f87171;">Failed to load</div>'
    + '<div class="params">' + (err.message || err) + '</div>'
    + '<div class="params" style="margin-top:4px;color:#6b7280;">Local preview requires an HTTP server (e.g. <code>python -m http.server</code>).</div>';
  return;
}
const META = DATA.meta;

{
  const venueStr = (META.venues && META.venues.length) ? META.venues.join(' / ') : '—';
  const yearStr = (META.paper_year_min && META.paper_year_max)
    ? `${META.paper_year_min}–${META.paper_year_max}` : '—';
  metaEl.innerHTML =
    `<div class="count">${META.nodes.toLocaleString()} authors · ${META.edges.toLocaleString()} co-author pairs</div>`
    + `<div class="params">(≥ ${META.min_author_papers} papers, ≥ ${META.min_edge_collabs} collabs)</div>`
    + `<div class="scope">`
    +   `<div><span class="k">Papers</span>${venueStr}</div>`
    +   `<div><span class="k">Years</span>${yearStr}</div>`
    +   `<div><span class="k">Built</span>${META.built_at || '—'}</div>`
    + `</div>`;
}

const INITIAL_EDGE_THRESHOLD = 5;
const allNodes = DATA.nodes;
const allEdges = DATA.edges;
const nodeById = new Map(allNodes.map(n => [n.id, n]));

let edges = allEdges.filter(d => d.weight >= INITIAL_EDGE_THRESHOLD).map(d => ({ ...d }));
const usedIdsInit = new Set();
edges.forEach(e => { usedIdsInit.add(e.source); usedIdsInit.add(e.target); });
let nodes = allNodes.filter(n => usedIdsInit.has(n.id));
edges.forEach(e => { e.source = nodeById.get(e.source); e.target = nodeById.get(e.target); });

const years = nodes.map(n => n.last_year).filter(y => y > 0);
const yMin = Math.min(...years), yMax = Math.max(...years);
const colorScale = d3.scaleSequential(d3.interpolateInferno).domain([yMin - 5, yMax]);

const communityPalette = new Map();
const communityInfo = new Map();
if (META.communities) {
  for (const c of META.communities) {
    communityPalette.set(c.id, c.color);
    communityInfo.set(c.id, c);
  }
  const ccEl = document.getElementById('comm-count');
  if (ccEl) ccEl.textContent = META.communities.length;
}
const hasCommunities = communityPalette.size > 0;

let colorMode = hasCommunities ? 'community' : 'year';
let selectedCommunity = null;
function nodeColor(n) {
  if (selectedCommunity != null && n.community !== selectedCommunity) {
    return 'rgba(100, 100, 105, 0.22)';
  }
  if (colorMode === 'community') {
    const c = communityPalette.get(n.community);
    return c || '#555';
  }
  return n.last_year > 0 ? colorScale(n.last_year) : '#888';
}
function applyColorMode(mode) {
  colorMode = mode;
  const ly = document.getElementById('legend-year');
  const lc = document.getElementById('legend-comm');
  if (ly) ly.style.display = (mode === 'year') ? 'flex' : 'none';
  if (lc) lc.style.display = (mode === 'community' && hasCommunities) ? 'block' : 'none';
  draw();
}

(function drawLegend() {
  const cb = document.getElementById('color-bar');
  const cbCtx = cb.getContext('2d');
  const grad = cbCtx.createLinearGradient(0, 0, cb.width, 0);
  const steps = 20;
  for (let i = 0; i <= steps; i++) {
    const t = i / steps;
    grad.addColorStop(t, colorScale(yMin - 5 + (yMax - (yMin - 5)) * t));
  }
  cbCtx.fillStyle = grad;
  cbCtx.fillRect(0, 0, cb.width, cb.height);
  document.getElementById('year-min').textContent = yMin;
  document.getElementById('year-max').textContent = yMax;
})();

const rScale = d3.scaleSqrt()
  .domain([d3.min(nodes, d => d.papers), d3.max(nodes, d => d.papers)])
  .range([2, 14]);
const eScale = d3.scaleLog()
  .domain([META.min_edge_collabs, d3.max(edges, d => d.weight) || 10])
  .range([0.3, 3]);

let adjacency = new Map();
let nodeDegree = new Map();
function buildAdjacency() {
  adjacency.clear();
  nodeDegree.clear();
  for (const n of nodes) { adjacency.set(n, []); nodeDegree.set(n, 0); }
  for (const e of edges) {
    adjacency.get(e.source).push(e.target);
    adjacency.get(e.target).push(e.source);
    nodeDegree.set(e.source, (nodeDegree.get(e.source) || 0) + 1);
    nodeDegree.set(e.target, (nodeDegree.get(e.target) || 0) + 1);
  }
}
buildAdjacency();

let showDegrees = false;
let edgeTier = new Map();

function recomputeEdgeTiers() {
  edgeTier.clear();
  if (!selectedNode) return;
  const maxHop = showDegrees ? 3 : 1;
  const dist = new Map();
  dist.set(selectedNode, 0);
  const queue = [selectedNode];
  while (queue.length) {
    const n = queue.shift();
    const d = dist.get(n);
    if (d >= maxHop) continue;
    for (const other of (adjacency.get(n) || [])) {
      if (dist.has(other)) continue;
      dist.set(other, d + 1);
      queue.push(other);
    }
  }
  for (const e of edges) {
    const ds = dist.get(e.source), dt = dist.get(e.target);
    if (ds === undefined || dt === undefined) continue;
    const tier = Math.max(ds, dt);
    if (tier >= 1 && tier <= 3) edgeTier.set(e, tier);
  }
}

let sparsity = 5;
const CHARGE_BASE = -14;
const LINK_BASE = 30;
const LINK_WEIGHT_INV = 70;

function linkDistance(d) {
  return LINK_BASE + LINK_WEIGHT_INV / d.weight * Math.sqrt(sparsity);
}

function chargeStrength(d) {
  const deg = nodeDegree.get(d) || 0;
  return CHARGE_BASE * sparsity * (1 + Math.sqrt(deg) * 0.35);
}

let simulation = d3.forceSimulation(nodes)
  .force('link', d3.forceLink(edges).id(d => d.id).distance(linkDistance).strength(0.35))
  .force('charge', d3.forceManyBody().strength(chargeStrength))
  .force('center', d3.forceCenter(width / 2, height / 2).strength(0.05))
  .force('collide', d3.forceCollide().radius(d => rScale(d.papers) + 2))
  .on('tick', draw);

function applySparsity(s) {
  sparsity = s;
  simulation.force('charge').strength(chargeStrength);
  simulation.force('link').distance(linkDistance);
  simulation.alpha(0.4).restart();
}

let transform = d3.zoomIdentity;
const zoom = d3.zoom().scaleExtent([0.02, 8]).on('zoom', (e) => {
  transform = e.transform;
  draw();
});
d3.select(canvas).call(zoom);

function draw() {
  ctx.save();
  ctx.clearRect(0, 0, width, height);
  ctx.translate(transform.x, transform.y);
  ctx.scale(transform.k, transform.k);

  ctx.lineCap = 'round';
  const wMult = Math.max(1, 1 / transform.k);
  const TIER_STYLE = {
    1: { color: '#34d399', alpha: 1.0,  w: 2.4 },
    2: { color: '#818cf8', alpha: 0.85, w: 1.5 },
    3: { color: '#f59e0b', alpha: 0.45, w: 0.9 },
  };
  if (!selectedNode && selectedCommunity != null) {
    ctx.strokeStyle = 'rgba(156, 163, 175, 0.06)';
    for (const e of edges) {
      if (e.source.community === selectedCommunity && e.target.community === selectedCommunity) continue;
      ctx.beginPath();
      ctx.lineWidth = eScale(e.weight) * wMult;
      ctx.moveTo(e.source.x, e.source.y);
      ctx.lineTo(e.target.x, e.target.y);
      ctx.stroke();
    }
    ctx.strokeStyle = 'rgba(156, 163, 175, 0.55)';
    for (const e of edges) {
      if (!(e.source.community === selectedCommunity && e.target.community === selectedCommunity)) continue;
      ctx.beginPath();
      ctx.lineWidth = eScale(e.weight) * wMult;
      ctx.moveTo(e.source.x, e.source.y);
      ctx.lineTo(e.target.x, e.target.y);
      ctx.stroke();
    }
  } else if (!selectedNode) {
    ctx.strokeStyle = 'rgba(156, 163, 175, 0.35)';
    for (const e of edges) {
      ctx.beginPath();
      ctx.lineWidth = eScale(e.weight) * wMult;
      ctx.moveTo(e.source.x, e.source.y);
      ctx.lineTo(e.target.x, e.target.y);
      ctx.stroke();
    }
  } else {
    ctx.strokeStyle = 'rgba(156, 163, 175, 0.15)';
    for (const e of edges) {
      if (edgeTier.has(e)) continue;
      ctx.beginPath();
      ctx.lineWidth = eScale(e.weight) * wMult;
      ctx.moveTo(e.source.x, e.source.y);
      ctx.lineTo(e.target.x, e.target.y);
      ctx.stroke();
    }
    for (const tier of [3, 2, 1]) {
      const s = TIER_STYLE[tier];
      ctx.globalAlpha = s.alpha;
      ctx.strokeStyle = s.color;
      for (const e of edges) {
        if (edgeTier.get(e) !== tier) continue;
        ctx.beginPath();
        ctx.lineWidth = eScale(e.weight) * s.w * wMult;
        ctx.moveTo(e.source.x, e.source.y);
        ctx.lineTo(e.target.x, e.target.y);
        ctx.stroke();
      }
    }
    ctx.globalAlpha = 1;
  }

  const nodeMult = Math.min(8, Math.pow(Math.max(1 / transform.k, 1), 0.75));
  for (const n of nodes) {
    ctx.beginPath();
    ctx.arc(n.x, n.y, rScale(n.papers) * nodeMult, 0, Math.PI * 2);
    ctx.fillStyle = nodeColor(n);
    ctx.fill();
    if (n === selectedNode) {
      ctx.strokeStyle = '#38bdf8';
      ctx.lineWidth = 2 / transform.k;
      ctx.stroke();
    }
  }

  if (transform.k > 0.25) {
    const fontPx = Math.max(9, 11 / transform.k);
    ctx.font = `${fontPx}px -apple-system, sans-serif`;
    ctx.fillStyle = 'rgba(229, 231, 235, 0.9)';
    ctx.textAlign = 'center';
    ctx.textBaseline = 'top';
    let minPapers;
    if      (transform.k >= 2.0) minPapers = 0;
    else if (transform.k >= 1.2) minPapers = 8;
    else if (transform.k >= 0.8) minPapers = 20;
    else if (transform.k >= 0.5) minPapers = 40;
    else                         minPapers = 80;
    for (const n of nodes) {
      if (n.papers < minPapers && n !== selectedNode) continue;
      const r = rScale(n.papers) * nodeMult;
      ctx.fillText(n.label, n.x, n.y + r + 2);
    }
  } else if (selectedNode) {
    ctx.font = `${11 / transform.k}px -apple-system, sans-serif`;
    ctx.fillStyle = '#38bdf8';
    ctx.textAlign = 'center';
    ctx.textBaseline = 'top';
    const r = rScale(selectedNode.papers) * nodeMult;
    ctx.fillText(selectedNode.label, selectedNode.x, selectedNode.y + r + 2);
  }
  ctx.restore();
}

let selectedNode = null;

function nodeAtScreen(sx, sy) {
  const x = (sx - transform.x) / transform.k;
  const y = (sy - transform.y) / transform.k;
  const nodeMult = Math.min(8, Math.pow(Math.max(1 / transform.k, 1), 0.75));
  for (let i = nodes.length - 1; i >= 0; i--) {
    const n = nodes[i];
    const r = rScale(n.papers) * nodeMult + 1.5 / transform.k;
    if ((n.x - x) ** 2 + (n.y - y) ** 2 < r * r) return n;
  }
  return null;
}

const tipEl = document.getElementById('tooltip');
const ttName = document.getElementById('tt-name');
const ttStat = document.getElementById('tt-stat');
const ttComm = document.getElementById('tt-comm');
const ttTop = document.getElementById('tt-top');
const ttCo = document.getElementById('tt-co');

function escHtml(s) {
  return String(s).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
}

function collectCoauthors(n) {
  const co = [];
  for (const e of edges) {
    const other = e.source === n ? e.target : (e.target === n ? e.source : null);
    if (other) co.push({ name: other.label, w: e.weight });
  }
  co.sort((a, b) => b.w - a.w);
  return co;
}

canvas.addEventListener('mousemove', (e) => {
  const n = nodeAtScreen(e.clientX, e.clientY);
  if (n) {
    canvas.style.cursor = 'pointer';
    ttName.textContent = n.label;
    ttStat.textContent = `${n.papers} papers · last active ${n.last_year}`;
    if (n.community != null && communityInfo.has(n.community)) {
      const ci = communityInfo.get(n.community);
      const topA = (ci.top_authors || []).slice(0, 3).map(escHtml).join(', ');
      const words = (ci.label_words || []).map(escHtml).join(' · ');
      const title = ci.misc ? 'Misc cluster' : `Community ${ci.id}`;
      const note = ci.misc
        ? ' <span class="kw">(many small labs, &lt; 10 each)</span>'
        : ` <span class="kw">(${ci.size} members)</span>`;
      ttComm.innerHTML = `<b style="color:${ci.color}">${title}</b>` + note
        + (words ? `<br><span class="kw">keywords:</span> ${words}` : '')
        + (topA ? `<br><span class="kw">hubs:</span> ${topA}` : '');
      ttComm.style.display = '';
    } else {
      ttComm.style.display = 'none';
    }
    if (n.top && n.top.length) {
      ttTop.innerHTML = '<b>Top cited papers:</b>'
        + n.top.map(p =>
            `<span class="pap">• ${escHtml(p.t)} <span class="mc">(${p.y}, ${p.c.toLocaleString()} cites)</span></span>`
          ).join('');
      ttTop.style.display = '';
    } else {
      ttTop.style.display = 'none';
    }
    const co = collectCoauthors(n);
    if (co.length) {
      const top = co.slice(0, 10);
      ttCo.innerHTML = `<b>Co-authors (${co.length}):</b> `
        + top.map(c => `${escHtml(c.name)} (${c.w})`).join(', ')
        + (co.length > 10 ? `, … +${co.length - 10} more` : '');
      ttCo.style.display = '';
    } else {
      ttCo.style.display = 'none';
    }
    let x = e.clientX + 12, y = e.clientY + 12;
    const w = tipEl.offsetWidth || 320, h = tipEl.offsetHeight || 80;
    if (x + w > window.innerWidth - 8)  x = e.clientX - w - 12;
    if (y + h > window.innerHeight - 8) y = e.clientY - h - 12;
    tipEl.style.left = x + 'px';
    tipEl.style.top = y + 'px';
    tipEl.style.display = 'block';
  } else {
    canvas.style.cursor = 'grab';
    tipEl.style.display = 'none';
  }
});
canvas.addEventListener('mouseleave', () => { tipEl.style.display = 'none'; });

function updateSelectedPanel(n) {
  const box = document.getElementById('selected');
  if (!n) { box.innerHTML = ''; return; }
  const neighbors = edges.filter(x => x.source === n || x.target === n).length;
  box.innerHTML = `<div class="name">${n.label}</div>`
    + `<div class="stat">${n.papers} papers · ${neighbors} co-authors in view · last ${n.last_year}</div>`;
}

function centerOnNode(n, scale = 1.8) {
  selectedNode = n;
  updateSelectedPanel(n);
  recomputeEdgeTiers();
  const tx = width / 2 - n.x * scale;
  const ty = height / 2 - n.y * scale;
  d3.select(canvas).transition().duration(500)
    .call(zoom.transform, d3.zoomIdentity.translate(tx, ty).scale(scale));
}

canvas.addEventListener('click', (e) => {
  const n = nodeAtScreen(e.clientX, e.clientY);
  selectedNode = n;
  if (selectedCommunity != null) {
    selectedCommunity = null;
    if (commsList) {
      commsList.querySelectorAll('.comm-item.sel').forEach(el => el.classList.remove('sel'));
    }
  }
  updateSelectedPanel(n);
  recomputeEdgeTiers();
  draw();
});

const searchInput = document.getElementById('search');
const resultsDiv = document.getElementById('results');

searchInput.addEventListener('input', (e) => {
  const q = e.target.value.trim().toLowerCase();
  if (!q) { resultsDiv.innerHTML = ''; return; }
  const visibleIds = new Set(nodes.map(n => n.id));
  const matches = allNodes
    .filter(n => n.label.toLowerCase().includes(q))
    .sort((a, b) => b.papers - a.papers)
    .slice(0, 25);
  if (matches.length === 0) {
    resultsDiv.innerHTML = '<div style="color:#888; padding:4px 8px; font-size:12px;">No matches</div>';
    return;
  }
  resultsDiv.innerHTML = matches.map(n => {
    const connected = visibleIds.has(n.id);
    const cls = connected ? 'result-item' : 'result-item unconn';
    const title = connected ? '' : ' title="Not in current view — try lowering edge threshold"';
    return `<div class="${cls}" data-id="${n.id}"${title}>`
      + `<span>${n.label}</span><span class="count">${n.papers}</span></div>`;
  }).join('');
});

searchInput.addEventListener('keyup', (e) => {
  if (e.key === 'Enter') {
    const first = resultsDiv.querySelector('.result-item');
    if (first) first.click();
  }
});

resultsDiv.addEventListener('click', (e) => {
  const item = e.target.closest('.result-item');
  if (!item) return;
  const id = parseInt(item.dataset.id);
  const node = nodes.find(n => n.id === id);
  if (!node) {
    alert('This author is not in the current view. Lower the edge threshold to include them.');
    return;
  }
  centerOnNode(node);
});

const btnHubs = document.getElementById('btn-hubs');
const hubsList = document.getElementById('hubs-list');

function populateHubs() {
  const degree = new Map();
  const weighted = new Map();
  for (const n of nodes) { degree.set(n.id, 0); weighted.set(n.id, 0); }
  for (const e of edges) {
    degree.set(e.source.id, degree.get(e.source.id) + 1);
    degree.set(e.target.id, degree.get(e.target.id) + 1);
    weighted.set(e.source.id, weighted.get(e.source.id) + e.weight);
    weighted.set(e.target.id, weighted.get(e.target.id) + e.weight);
  }
  const ranked = nodes.slice()
    .sort((a, b) => degree.get(b.id) - degree.get(a.id))
    .slice(0, 100);
  hubsList.innerHTML = ranked.map((n, i) =>
    `<div class="hub-item" data-id="${n.id}" title="${weighted.get(n.id)} total collaborations">`
    + `<span class="rank">${i + 1}</span>`
    + `<span class="name">${n.label}</span>`
    + `<span class="count">${degree.get(n.id)}</span>`
    + `</div>`
  ).join('');
}

btnHubs.addEventListener('click', () => {
  const show = hubsList.style.display === 'none';
  if (show) {
    populateHubs();
    hubsList.style.display = 'block';
    btnHubs.textContent = '▾ Top 100 hubs (most co-authors)';
  } else {
    hubsList.style.display = 'none';
    btnHubs.textContent = '▸ Top 100 hubs (most co-authors)';
  }
});

hubsList.addEventListener('click', (e) => {
  const item = e.target.closest('.hub-item');
  if (!item) return;
  const id = parseInt(item.dataset.id);
  const node = nodes.find(n => n.id === id);
  if (node) centerOnNode(node);
});

const btnComms = document.getElementById('btn-comms');
const commsPanel = document.getElementById('comms-panel');
const commsList = document.getElementById('comms-list');
const commsSummary = document.getElementById('comms-summary');
const commsHist = document.getElementById('comms-hist');
const commsBaseLabel = `Communities${META.communities ? ' (' + META.communities.length + ')' : ''}`;
btnComms.textContent = '▸ ' + commsBaseLabel;

const HIST_BINS = [
  { lo:  10, hi:  20,      label: '10-19' },
  { lo:  20, hi:  50,      label: '20-49' },
  { lo:  50, hi: 100,      label: '50-99' },
  { lo: 100, hi: 200,      label: '100-199' },
  { lo: 200, hi: 300,      label: '200-299' },
  { lo: 300, hi: 400,      label: '300-399' },
  { lo: 400, hi: 500,      label: '400-499' },
  { lo: 500, hi: 600,      label: '500-599' },
  { lo: 600, hi: Infinity, label: '600+' },
];

function drawCommsHist() {
  const hctx = commsHist.getContext('2d');
  const W = commsHist.width, H = commsHist.height;
  hctx.clearRect(0, 0, W, H);
  const bins = HIST_BINS.map(b => ({ ...b, count: 0 }));
  for (const c of META.communities || []) {
    if (c.misc) continue;
    for (const b of bins) {
      if (c.size >= b.lo && c.size < b.hi) { b.count++; break; }
    }
  }
  const maxCount = Math.max(1, ...bins.map(b => b.count));
  const topPad = 14, bottomPad = 20, leftPad = 2, rightPad = 2, gap = 2;
  const chartH = H - topPad - bottomPad;
  const totalGaps = (bins.length - 1) * gap;
  const barW = Math.floor((W - leftPad - rightPad - totalGaps) / bins.length);
  hctx.textBaseline = 'alphabetic';
  bins.forEach((b, i) => {
    const x = leftPad + i * (barW + gap);
    const h = b.count > 0 ? Math.max(2, (b.count / maxCount) * chartH) : 0;
    const t = i / (bins.length - 1);
    const light = 55 - t * 28;
    hctx.fillStyle = `hsl(210, 40%, ${light}%)`;
    hctx.fillRect(x, topPad + chartH - h, barW, h);
    if (b.count > 0) {
      hctx.font = '9.5px -apple-system, "Segoe UI", sans-serif';
      hctx.fillStyle = '#e5e7eb';
      hctx.textAlign = 'center';
      hctx.fillText(String(b.count), x + barW / 2, topPad + chartH - h - 3);
    }
    hctx.font = '8.5px -apple-system, "Segoe UI", sans-serif';
    hctx.fillStyle = '#9ca3af';
    hctx.textAlign = 'center';
    hctx.fillText(b.label, x + barW / 2, H - 5);
  });
}

function populateComms() {
  const named = (META.communities || []).filter(c => !c.misc);
  const sizes = named.map(c => c.size).sort((a, b) => a - b);
  const med = sizes.length ? sizes[Math.floor(sizes.length / 2)] : 0;
  const miscC = (META.communities || []).find(c => c.misc);
  commsSummary.innerHTML =
    `${named.length} communities · sizes ${sizes[0] || 0}–${sizes[sizes.length - 1] || 0}`
    + ` · median ${med}`
    + (miscC ? ` · +${miscC.size.toLocaleString()} in misc` : '')
    + `<div style="color:#6b7280; font-size:10px; margin-top:3px;">counts show <b style="color:#9ca3af;">visible in current view</b> / <b style="color:#9ca3af;">total in community</b> — lower the edge slider to reveal more.</div>`;
  drawCommsHist();

  const visibleByComm = new Map();
  for (const n of nodes) {
    if (n.community != null) {
      visibleByComm.set(n.community, (visibleByComm.get(n.community) || 0) + 1);
    }
  }

  const rows = [];
  (META.communities || []).forEach((c) => {
    const hub = (c.top_authors && c.top_authors[0]) || '—';
    const title = c.misc ? 'Misc cluster' : `#${c.id} · ${hub}`;
    const kw = (c.label_words || []).slice(0, 4).join(' · ');
    const note = c.misc
      ? '<div class="kw">many small labs, &lt; 10 members each</div>'
      : (kw ? `<div class="kw">${escHtml(kw)}</div>` : '');
    const selCls = (selectedCommunity === c.id) ? ' sel' : '';
    const vis = visibleByComm.get(c.id) || 0;
    const countStr = `${vis.toLocaleString()} / ${c.size.toLocaleString()}`;
    rows.push(
      `<div class="comm-item${selCls}" data-cid="${c.id}" style="border-left-color:${c.color};" `
      + `title="${vis} of ${c.size} currently visible at edge threshold ${slider ? slider.value : ''}">`
      + `<div class="hd"><span class="name">${escHtml(title)}</span>`
      + `<span class="count">${countStr}</span></div>`
      + note
      + `</div>`
    );
  });
  commsList.innerHTML = rows.join('');
}

btnComms.addEventListener('click', () => {
  const show = commsPanel.style.display === 'none';
  if (show) {
    populateComms();
    commsPanel.style.display = 'block';
    btnComms.textContent = '▾ ' + commsBaseLabel;
  } else {
    commsPanel.style.display = 'none';
    btnComms.textContent = '▸ ' + commsBaseLabel;
  }
});

commsList.addEventListener('click', (e) => {
  const item = e.target.closest('.comm-item');
  if (!item) return;
  const cid = parseInt(item.dataset.cid);
  if (selectedCommunity === cid) {
    selectedCommunity = null;
    item.classList.remove('sel');
    selectedNode = null;
    updateSelectedPanel(null);
    recomputeEdgeTiers();
    draw();
    return;
  }
  selectedCommunity = cid;
  commsList.querySelectorAll('.comm-item.sel').forEach(el => el.classList.remove('sel'));
  item.classList.add('sel');
  const c = communityInfo.get(cid);
  const hubLabel = c && c.top_authors && c.top_authors[0];
  const target = hubLabel ? nodes.find(n => n.label === hubLabel) : null;
  selectedNode = null;
  updateSelectedPanel(null);
  edgeTier.clear();
  if (target) {
    const scale = 1.8;
    const tx = width / 2 - target.x * scale;
    const ty = height / 2 - target.y * scale;
    d3.select(canvas).transition().duration(500)
      .call(zoom.transform, d3.zoomIdentity.translate(tx, ty).scale(scale));
  }
  draw();
});

d3.select(canvas).call(d3.drag()
  .container(canvas)
  .subject((event) => nodeAtScreen(event.sourceEvent.clientX, event.sourceEvent.clientY))
  .filter((event) => nodeAtScreen(event.clientX, event.clientY))
  .on('start', (event) => { if (!event.active) simulation.alphaTarget(0.3).restart(); event.subject.fx = event.subject.x; event.subject.fy = event.subject.y; })
  .on('drag', (event) => { event.subject.fx = (event.x - transform.x) / transform.k; event.subject.fy = (event.y - transform.y) / transform.k; })
  .on('end', (event) => { if (!event.active) simulation.alphaTarget(0); event.subject.fx = null; event.subject.fy = null; })
);

const INITIAL_SPARSITY = 5;
let frozen = false;

function fullReset() {
  selectedNode = null;
  selectedCommunity = null;
  frozen = false;
  showDegrees = false;
  document.getElementById('show-degrees').checked = false;
  document.getElementById('tier-legend').style.display = 'none';
  document.getElementById('selected').innerHTML = '';
  edgeTier.clear();

  searchInput.value = '';
  resultsDiv.innerHTML = '';
  hubsList.style.display = 'none';
  btnHubs.textContent = '▸ Top 100 hubs (most co-authors)';

  slider.value = INITIAL_EDGE_THRESHOLD;
  sliderVal.textContent = INITIAL_EDGE_THRESHOLD;
  sparsitySlider.value = INITIAL_SPARSITY;
  sparsityVal.textContent = INITIAL_SPARSITY;
  sparsity = INITIAL_SPARSITY;

  edges = allEdges.filter(d => d.weight >= INITIAL_EDGE_THRESHOLD).map(d => ({ source: d.source, target: d.target, weight: d.weight }));
  const usedNow = new Set();
  edges.forEach(e => { usedNow.add(e.source); usedNow.add(e.target); });
  nodes = allNodes.filter(n => usedNow.has(n.id));
  edges.forEach(e => {
    if (typeof e.source !== 'object') e.source = nodeById.get(e.source);
    if (typeof e.target !== 'object') e.target = nodeById.get(e.target);
  });

  for (const n of nodes) {
    n.fx = null; n.fy = null;
    n.x = width / 2 + (Math.random() - 0.5) * 200;
    n.y = height / 2 + (Math.random() - 0.5) * 200;
    n.vx = 0; n.vy = 0;
  }

  buildAdjacency();
  simulation.nodes(nodes);
  simulation.force('link').links(edges).distance(linkDistance);
  simulation.force('charge').strength(CHARGE_BASE * sparsity);
  simulation.force('center', d3.forceCenter(width / 2, height / 2));
  simulation.alpha(1).restart();

  d3.select(canvas).transition().duration(450)
    .call(zoom.transform, d3.zoomIdentity);

  document.getElementById('freeze').textContent = 'Freeze';
}

document.getElementById('restart').onclick = fullReset;
document.getElementById('freeze').onclick = () => {
  frozen = !frozen;
  if (frozen) { simulation.stop(); document.getElementById('freeze').textContent = 'Resume'; }
  else { simulation.alpha(0.3).restart(); document.getElementById('freeze').textContent = 'Freeze'; }
};
document.getElementById('center').onclick = () => {
  d3.select(canvas).transition().duration(400).call(zoom.transform, d3.zoomIdentity);
};

const slider = document.getElementById('edge-slider');
const sliderVal = document.getElementById('edge-val');
slider.oninput = (e) => {
  const th = parseInt(e.target.value);
  sliderVal.textContent = th;
  edges = allEdges.filter(d => d.weight >= th).map(d => ({ ...d }));
  edges.forEach(e => {
    e.source = nodeById.get(typeof e.source === 'object' ? e.source.id : e.source);
    e.target = nodeById.get(typeof e.target === 'object' ? e.target.id : e.target);
  });
  const used = new Set();
  edges.forEach(e => { used.add(e.source.id); used.add(e.target.id); });
  nodes = allNodes.filter(n => used.has(n.id));
  nodes.forEach(n => { n.x = nodeById.get(n.id).x; n.y = nodeById.get(n.id).y; });
  simulation.nodes(nodes);
  simulation.force('link').links(edges);
  simulation.alpha(0.4).restart();
  buildAdjacency();
  recomputeEdgeTiers();
  if (hubsList.style.display === 'block') populateHubs();
  if (commsPanel && commsPanel.style.display !== 'none') populateComms();
};

document.getElementById('show-degrees').addEventListener('change', (e) => {
  showDegrees = e.target.checked;
  document.getElementById('tier-legend').style.display = showDegrees ? 'block' : 'none';
  recomputeEdgeTiers();
  draw();
});

const sparsitySlider = document.getElementById('sparsity-slider');
const sparsityVal = document.getElementById('sparsity-val');
sparsitySlider.oninput = (e) => {
  const s = parseFloat(e.target.value);
  sparsityVal.textContent = s;
  applySparsity(s);
};

window.addEventListener('resize', () => {
  width = canvas.width = window.innerWidth;
  height = canvas.height = window.innerHeight;
  simulation.force('center', d3.forceCenter(width / 2, height / 2));
  simulation.alpha(0.3).restart();
});

document.querySelectorAll('input[name="cmode"]').forEach(r => {
  r.checked = (r.value === colorMode);
  r.addEventListener('change', (e) => { if (e.target.checked) applyColorMode(e.target.value); });
});
applyColorMode(colorMode);
})();
</script>
</body>
</html>"""

with open(OUT_HTML, 'w', encoding='utf-8') as f:
    f.write(HTML)
print(f"Saved {OUT_HTML}")
