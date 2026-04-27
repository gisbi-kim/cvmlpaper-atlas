"""전체 논문 시각화 HTML 생성 (venue-config driven, DOI dedup)

실행: python _make_all_html.py
출력: explorer.html
"""
import json
import html
import os
import re
from datetime import datetime
import pandas as pd

from _clean import is_front_matter, is_translated_dup
from _venues import VENUES_CFG, VENUE_PRIORITY, VENUE_LABELS, VENUE_COLORS, VENUE_IDS

TITLE_STR = 'CV+ML Paper Atlas'

try:
    AS_OF = datetime.fromtimestamp(os.path.getmtime('all_enriched.json')).date().isoformat()
except OSError:
    AS_OF = datetime.now().date().isoformat()

with open('all_enriched.json', encoding='utf-8') as f:
    papers = json.load(f)

df = pd.DataFrame(papers)
slim = df[['venue', 'year', 'title', 'authors', 'cited_by_count', 'doi', 'pages']].copy()
slim['title'] = (slim['title'].fillna('').astype(str).map(html.unescape)
                 .str.rstrip('.').str.strip().str[:300])
_dblp_suffix = re.compile(r'\s+\d{4}$')
def _clean_authors(s):
    return '; '.join(_dblp_suffix.sub('', a.strip()) for a in html.unescape(str(s)).split(';') if a.strip())
slim['authors'] = slim['authors'].fillna('').astype(str).map(_clean_authors).str[:300]
slim['doi'] = slim['doi'].fillna('').astype(str).str.strip().str.lower()
slim['doi'] = slim['doi'].str.replace(r'^https?://doi\.org/', '', regex=True)
slim['cited_by_count'] = pd.to_numeric(slim['cited_by_count'], errors='coerce').fillna(0).astype(int)
slim['year'] = pd.to_numeric(slim['year'], errors='coerce').fillna(0).astype(int)

_pg_range   = re.compile(r'^\s*(\d+)\s*[-–]\s*(\d+)\s*$')
_pg_single  = re.compile(r'^\s*(\d+)\s*$')
_pg_article = re.compile(r'^\s*\d+\s*:\s*(\d+)\s*[-–]\s*(\d+)\s*$')
def _page_count(p):
    if not p:
        return 0
    s = str(p).strip()
    m = _pg_article.match(s)
    if m:
        return max(0, int(m.group(2)) - int(m.group(1)) + 1)
    m = _pg_range.match(s)
    if m:
        a, b = int(m.group(1)), int(m.group(2))
        if b < a:
            sa, sb = str(a), str(b)
            if len(sb) < len(sa):
                b = int(sa[:len(sa)-len(sb)] + sb)
        return max(0, b - a + 1)
    if _pg_single.match(s):
        return 1
    return 0
def _clean_page_count(p, venue):
    n = _page_count(p)
    return n if 2 <= n <= 30 else 0  # CV/ML papers are typically 8-12 pages
slim['pages_n'] = [_clean_page_count(p, v) for v, p in zip(slim['venue'], slim['pages'].fillna('').astype(str))]

before = len(slim)
slim = slim[slim['authors'].str.strip() != ''].reset_index(drop=True)
slim = slim[~slim['title'].map(is_front_matter)].reset_index(drop=True)
slim = slim[~slim['title'].map(is_translated_dup)].reset_index(drop=True)
print(f"Cleaned: {before} → {len(slim)}")

before = len(slim)
with_doi = slim[slim['doi'] != ''].copy()
without_doi = slim[slim['doi'] == ''].copy()
with_doi['_pri'] = with_doi['venue'].map(VENUE_PRIORITY).fillna(99).astype(int)
with_doi = with_doi.sort_values(['doi', '_pri'])
venues_per_doi = with_doi.groupby('doi')['venue'].apply(
    lambda s: ','.join(sorted(set(s), key=lambda v: VENUE_PRIORITY.get(v, 99)))
)
with_doi = with_doi.drop_duplicates(subset=['doi'], keep='first').drop(columns=['_pri'])
with_doi['venues_all'] = with_doi['doi'].map(venues_per_doi)
without_doi['venues_all'] = without_doi['venue']
slim = pd.concat([with_doi, without_doi], ignore_index=True)
print(f"DOI dedup: {before} → {len(slim)}")

def _norm_title(s):
    return re.sub(r'[^a-z0-9]', '', str(s).lower())
before = len(slim)
slim['_tn'] = slim['title'].map(_norm_title)
short = slim['_tn'].str.len() < 20
pool = slim[~short].copy()
keep = slim[short].copy()
pool['_pri'] = pool['venue'].map(VENUE_PRIORITY).fillna(99).astype(int)
pool = pool.sort_values(['_tn', 'year', 'venue', '_pri'])
pool = pool.drop_duplicates(subset=['_tn', 'year', 'venue'], keep='first').drop(columns=['_pri'])
slim = pd.concat([pool, keep], ignore_index=True).drop(columns=['_tn'])
print(f"Title dedup: {before} → {len(slim)}")

arr = [[r['venue'], r['year'], r['title'], r['authors'],
        r['cited_by_count'], r['doi'], r['venues_all'], int(r['pages_n'])]
       for r in slim.to_dict('records')]

total = len(arr)
year_min = int(slim['year'].min())
year_max = int(slim['year'].max())

try:
    with open('word_book.json', encoding='utf-8') as f:
        wb = json.load(f)
    wb_vocab = wb['vocab']
    wb_papers_slim = {doi: idx_list[:15] for doi, idx_list in wb['papers'].items()}
    print(f"word_book: {len(wb_vocab):,} vocab")
except FileNotFoundError:
    print("warning: word_book.json not found — run _make_word_book.py first")
    wb_vocab = []
    wb_papers_slim = {}


def _class_key(label):
    return re.sub(r'[^A-Za-z0-9]', '', label).upper()


CARD_BORDER_CSS = ''.join(
    f'  .card.v-{v["id"]} {{ border-top: 3px solid {v["color"]}; }}\n'
    for v in VENUES_CFG
)
VENUE_TEXT_CSS = ''.join(
    f'  .venue-{_class_key(v["label"])} {{ color: {v["color"]}; font-weight: 600; }}\n'
    for v in VENUES_CFG
)
SUMMARY_CARDS = ''.join(
    f'  <div class="card v-{v["id"]} venue-card" data-venue-id="{v["id"]}" '
    f'title="Click to solo this venue">'
    f'<div class="num" id="c-{v["id"]}">-</div>'
    f'<div class="label">{v["label"]} ({v["since"]}~)</div></div>\n'
    for v in VENUES_CFG
)
FILTER_CHECKBOXES = ''.join(
    f'      <label><input type="checkbox" id="f-{v["id"]}" checked> '
    f'{v["label"]} <span class="since">({v["since"]}~)</span></label>\n'
    for v in VENUES_CFG
)

HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>__TITLE__</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/wordcloud@1.2.2/src/wordcloud2.js"></script>
<style>
* { box-sizing: border-box; }
body { font-family: -apple-system,"Segoe UI",sans-serif; margin: 20px; background:#fafafa; color:#222; }
h1 { font-size: 22px; margin: 0 0 4px; }
.sub { color:#666; font-size:13px; margin-bottom:16px; display:flex; justify-content:space-between; align-items:flex-start; gap:16px; flex-wrap:wrap; }
.stat-line { display:flex; gap:28px; font-size:13px; color:#555; margin:8px 0 14px; flex-wrap:wrap; }
.stat-line b { color:#222; font-size:16px; margin-left:6px; font-weight:700; }
.wrap { background:#fff; border:1px solid #e5e5e5; border-radius:8px; padding:14px 16px; margin-bottom:16px; }
h2 { font-size:14px; margin:0 0 10px; color:#333; }
canvas { max-height:340px; }
.summary { display:grid; grid-template-columns:repeat(auto-fit,minmax(120px,1fr)); gap:12px; margin-bottom:16px; }
.card { min-width:0; background:#fff; border:1px solid #e5e5e5; border-radius:8px; padding:10px 14px; }
.card .num { font-size:20px; font-weight:600; }
.card .label { color:#666; font-size:11px; margin-top:2px; }
.venue-card { cursor:pointer; transition:background 0.1s,transform 0.08s; }
.venue-card:hover { background:#fafafa; transform:translateY(-1px); }
.venue-card.solo { background:#f0f7ff; border-color:#1f77b4; }
.card.dim { opacity:0.45; }
.venue-filters { display:grid; grid-template-columns:repeat(auto-fill,minmax(135px,1fr)); gap:4px 14px; padding:8px 12px; margin-bottom:10px; background:#fafafa; border:1px solid #eee; border-radius:6px; }
.venue-filters label { font-size:13px; color:#444; display:inline-flex; align-items:center; gap:6px; cursor:pointer; }
.venue-filters label .since { color:#999; font-size:11px; }
__CARD_BORDER_CSS__
.controls { display:flex; gap:16px; align-items:center; flex-wrap:wrap; }
.controls label { font-size:13px; color:#555; display:inline-flex; align-items:center; gap:6px; }
.controls input[type="number"] { width:78px; padding:4px 6px; border:1px solid #ccc; border-radius:4px; font-size:13px; }
.controls input[type="text"] { padding:4px 8px; border:1px solid #ccc; border-radius:4px; font-size:13px; min-width:200px; }
.controls button { border:1px solid #ccc; background:#fff; padding:5px 12px; border-radius:4px; cursor:pointer; font-size:13px; }
.controls button:hover { background:#f4f4f4; }
.controls .reset { color:#c33; }
.result-info { font-size:12px; color:#666; margin:8px 0 10px; }
table { width:100%; border-collapse:collapse; font-size:12px; table-layout:fixed; }
th,td { border-bottom:1px solid #eee; padding:5px 8px; vertical-align:top; overflow:hidden; text-overflow:ellipsis; }
th { background:#f4f4f4; font-weight:600; text-align:left; cursor:pointer; user-select:none; white-space:nowrap; }
th:hover { background:#ebebeb; }
th.sorted { background:#e0ebf5; }
th .arrow { font-size:10px; color:#1f77b4; margin-left:4px; }
col.col-rank  { width:52px; }
col.col-venue { width:82px; }
col.col-year  { width:52px; }
col.col-pages { width:60px; }
col.col-cites { width:72px; }
col.col-title { width:auto; }
col.col-authors { width:220px; }
td.rank,td.cites,td.year,td.pages { text-align:right; font-variant-numeric:tabular-nums; }
td.pages { color:#888; font-size:12px; }
td.cites { font-weight:600; }
td.rank { color:#999; }
__VENUE_TEXT_CSS__
.venue-also { color:#888; font-weight:400; font-size:10px; }
td.authors { color:#555; font-size:11px; white-space:nowrap; }
.author-click { cursor:pointer; }
.author-click:hover { color:#1f77b4; text-decoration:underline; }
a { color:inherit; text-decoration:none; }
a:hover { text-decoration:underline; color:#1f77b4; }
a[data-doi] { border-bottom:1px dotted #bbb; }
a[data-doi]:hover { border-bottom:1px solid #1f77b4; text-decoration:none; }
#abstract-tooltip {
  position:fixed; display:none; background:#fff;
  border:1px solid #ccc; border-radius:6px;
  padding:12px 14px; max-width:500px; min-width:280px;
  box-shadow:0 6px 20px rgba(0,0,0,0.15);
  font-size:12.5px; line-height:1.55; color:#333;
  z-index:1000; pointer-events:none;
}
#abstract-tooltip .tt-title { font-weight:600; margin-bottom:6px; font-size:13px; }
#abstract-tooltip .tt-meta  { color:#888; font-size:11px; margin-bottom:8px; }
#abstract-tooltip .tt-body  { color:#444; }
#wc-overlay { display:none; position:fixed; inset:0; background:rgba(0,0,0,0.5); z-index:2000; align-items:center; justify-content:center; }
#wc-overlay.show { display:flex; }
#wc-box { background:#fff; border-radius:10px; padding:20px; max-width:90vw; max-height:90vh; overflow:auto; }
#wc-title { font-size:14px; font-weight:600; margin-bottom:10px; }
#wc-canvas { display:block; }
#wc-close { float:right; cursor:pointer; color:#999; font-size:18px; margin-top:-4px; }
</style>
</head>
<body>
<div class="brand" style="font-size:12px;color:#888;margin-bottom:4px;">
  <a href="https://github.com/gisbi-kim/cvml-paper-atlas" style="color:inherit;text-decoration:none;font-weight:600;">CV+ML Paper Atlas</a>
</div>
<h1>__TITLE__</h1>
<div class="sub">
  <span>40+ years of Computer Vision &amp; Machine Learning research — CVPR · ICCV · ECCV · NeurIPS · ICML · ICLR · AAAI · 3DV</span>
  <span style="font-size:11px;color:#aaa;">Citations as of __AS_OF__</span>
</div>
<div class="stat-line">
  <span>Total<b id="stat-total">-</b></span>
  <span>Shown<b id="stat-shown">-</b></span>
  <span>Year<b id="stat-yr">-</b></span>
  <span>Citations<b id="stat-cites">-</b></span>
</div>

<div class="summary">
__SUMMARY_CARDS__</div>

<div class="wrap">
  <h2>📈 Publications per year</h2>
  <canvas id="chart-timeline"></canvas>
</div>

<div class="wrap">
  <h2>🔍 Filter &amp; Search</h2>
  <div class="venue-filters" id="venue-filters">
__FILTER_CHECKBOXES__  </div>
  <div class="controls">
    <label>Year from <input type="number" id="yr-from" value="__YEAR_MIN__" min="__YEAR_MIN__" max="__YEAR_MAX__"></label>
    <label>to <input type="number" id="yr-to" value="__YEAR_MAX__" min="__YEAR_MIN__" max="__YEAR_MAX__"></label>
    <label>Min citations <input type="number" id="min-cites" value="0" min="0"></label>
    <label>Search <input type="text" id="search-box" placeholder="title / author…"></label>
    <button onclick="applyFilters()">Apply</button>
    <button class="reset" onclick="resetFilters()">Reset</button>
  </div>
  <div class="result-info" id="result-info"></div>
</div>

<div class="wrap">
  <h2>📄 Papers</h2>
  <table id="papers-table">
    <colgroup>
      <col class="col-rank"><col class="col-venue"><col class="col-year">
      <col class="col-cites"><col class="col-pages"><col class="col-title"><col class="col-authors">
    </colgroup>
    <thead>
      <tr>
        <th data-col="rank">#<span class="arrow"></span></th>
        <th data-col="venue">Venue<span class="arrow"></span></th>
        <th data-col="year">Year<span class="arrow"></span></th>
        <th data-col="cites">Cites<span class="arrow"></span></th>
        <th data-col="pages">Pages<span class="arrow"></span></th>
        <th data-col="title">Title<span class="arrow"></span></th>
        <th data-col="authors">Authors<span class="arrow"></span></th>
      </tr>
    </thead>
    <tbody id="papers-tbody"></tbody>
  </table>
  <div id="load-more-wrap" style="text-align:center;margin:12px 0;">
    <button id="load-more-btn" onclick="loadMore()" style="padding:6px 20px;">Load more…</button>
  </div>
</div>

<div id="abstract-tooltip">
  <div class="tt-title" id="tt-title"></div>
  <div class="tt-meta"  id="tt-meta"></div>
  <div class="tt-body"  id="tt-body"></div>
</div>

<div id="wc-overlay" onclick="closeWC()">
  <div id="wc-box" onclick="event.stopPropagation()">
    <span id="wc-close" onclick="closeWC()">✕</span>
    <div id="wc-title"></div>
    <canvas id="wc-canvas" width="600" height="360"></canvas>
  </div>
</div>

<script>
// ─── DATA ───────────────────────────────────────────────────────────────────
// [venue, year, title, authors, cited_by_count, doi, venues_all, pages_n]
const RAW = __RAW_JSON__;

const WB_VOCAB  = __WB_VOCAB__;
const WB_PAPERS = __WB_PAPERS__;

const VENUES_CFG = __VENUES_CFG_JSON__;
const VENUE_COLOR = Object.fromEntries(VENUES_CFG.map(v => [v.label, v.color]));
const VENUE_ID    = Object.fromEntries(VENUES_CFG.map(v => [v.label, v.id]));

const AS_OF   = "__AS_OF__";
const YEAR_MIN = __YEAR_MIN__;
const YEAR_MAX = __YEAR_MAX__;
const PAGE_SIZE = 200;

// ─── STATE ──────────────────────────────────────────────────────────────────
let filtered = [];
let displayed = 0;
let sortCol = 'cites';
let sortAsc = false;
let soloVenue = null;

// ─── HELPERS ────────────────────────────────────────────────────────────────
function venueClass(label) { return label.replace(/[^A-Za-z0-9]/g,'').toUpperCase(); }
function fmtNum(n) { return n == null ? '-' : n.toLocaleString(); }

function venueHtml(venue, venuesAll) {
  const cls = 'venue-' + venueClass(venue);
  const also = venuesAll && venuesAll !== venue
    ? `<span class="venue-also"> +${venuesAll.replace(venue,'').replace(',','').trim()}</span>` : '';
  return `<span class="${cls}">${venue}</span>${also}`;
}

// ─── FILTERING ──────────────────────────────────────────────────────────────
function getActiveVenues() {
  return VENUES_CFG.map(v => v.id).filter(id => {
    const el = document.getElementById('f-' + id);
    return el && el.checked;
  }).map(id => VENUES_CFG.find(v => v.id === id).label);
}

function applyFilters() {
  const yrFrom  = parseInt(document.getElementById('yr-from').value) || YEAR_MIN;
  const yrTo    = parseInt(document.getElementById('yr-to').value)   || YEAR_MAX;
  const minCite = parseInt(document.getElementById('min-cites').value) || 0;
  const q       = (document.getElementById('search-box').value || '').toLowerCase().trim();
  const active  = new Set(getActiveVenues());

  filtered = RAW.filter(r => {
    const [venue, year, title, authors, cites, doi, venuesAll, pages] = r;
    if (!active.has(venue)) return false;
    if (year < yrFrom || year > yrTo) return false;
    if (cites < minCite) return false;
    if (q && !title.toLowerCase().includes(q) && !authors.toLowerCase().includes(q)) return false;
    return true;
  });

  // sort
  const colIdx = {rank:null, venue:0, year:1, title:2, authors:3, cites:4, pages:7};
  const ci = colIdx[sortCol];
  if (ci !== null) {
    filtered.sort((a,b) => {
      const av = a[ci], bv = b[ci];
      if (typeof av === 'number') return sortAsc ? av-bv : bv-av;
      return sortAsc ? String(av).localeCompare(String(bv)) : String(bv).localeCompare(String(av));
    });
  }

  displayed = 0;
  document.getElementById('papers-tbody').innerHTML = '';
  loadMore();
  updateStats();
  updateCards(active);
  updateChart();
}

function resetFilters() {
  document.getElementById('yr-from').value  = YEAR_MIN;
  document.getElementById('yr-to').value    = YEAR_MAX;
  document.getElementById('min-cites').value = 0;
  document.getElementById('search-box').value = '';
  VENUES_CFG.forEach(v => {
    const el = document.getElementById('f-' + v.id);
    if (el) el.checked = true;
  });
  soloVenue = null;
  document.querySelectorAll('.venue-card').forEach(c => c.classList.remove('solo','dim'));
  applyFilters();
}

// ─── TABLE RENDER ───────────────────────────────────────────────────────────
function loadMore() {
  const tbody = document.getElementById('papers-tbody');
  const end   = Math.min(displayed + PAGE_SIZE, filtered.length);
  const frag  = document.createDocumentFragment();
  for (let i = displayed; i < end; i++) {
    const [venue, year, title, authors, cites, doi, venuesAll, pages] = filtered[i];
    const tr = document.createElement('tr');
    const doiUrl = doi ? `https://doi.org/${doi}` : null;
    const pg = pages > 0 ? pages + 'p' : '';
    tr.innerHTML = `
      <td class="rank">${(i+1).toLocaleString()}</td>
      <td>${venueHtml(venue, venuesAll)}</td>
      <td class="year">${year}</td>
      <td class="cites">${fmtNum(cites)}</td>
      <td class="pages">${pg}</td>
      <td>${doiUrl
        ? `<a data-doi="${doi}" href="${doiUrl}" target="_blank" rel="noopener">${title}</a>`
        : title}</td>
      <td class="authors">${authors.split(';').map(a =>
        `<span class="author-click" onclick="searchAuthor(this)">${a.trim()}</span>`
      ).join('; ')}</td>`;
    if (doi && WB_PAPERS[doi]) {
      tr.querySelector('a,td:nth-child(6)').addEventListener('mouseenter', e => showAbstract(e, i));
      tr.querySelector('a,td:nth-child(6)').addEventListener('mouseleave', hideAbstract);
    }
    frag.appendChild(tr);
  }
  tbody.appendChild(frag);
  displayed = end;
  document.getElementById('load-more-wrap').style.display =
    displayed < filtered.length ? 'block' : 'none';
}

// ─── ABSTRACT TOOLTIP ───────────────────────────────────────────────────────
let _tt = null;
function showAbstract(e, idx) {
  const [venue,year,title,authors,cites,doi] = filtered[idx];
  document.getElementById('tt-title').textContent = title;
  document.getElementById('tt-meta').textContent  = `${venue} ${year} · ${cites} citations`;
  // reconstruct a short preview from word_book
  const wordIdxs = WB_PAPERS[doi] || [];
  const preview  = wordIdxs.slice(0,20).map(([wi]) => WB_VOCAB[wi]).join(' ');
  document.getElementById('tt-body').textContent = preview ? `[keywords: ${preview}]` : '(no abstract)';
  const tt = document.getElementById('abstract-tooltip');
  tt.style.display = 'block';
  positionTT(e, tt);
  _tt = tt;
}
function hideAbstract() { if (_tt) _tt.style.display = 'none'; }
function positionTT(e, tt) {
  const margin = 14;
  let x = e.clientX + margin, y = e.clientY + margin;
  if (x + 500 > window.innerWidth) x = e.clientX - 500 - margin;
  if (y + 200 > window.innerHeight) y = e.clientY - 200 - margin;
  tt.style.left = x + 'px'; tt.style.top = y + 'px';
}

// ─── WORD CLOUD ─────────────────────────────────────────────────────────────
function showWC(doi, title) {
  const words = (WB_PAPERS[doi] || []).map(([wi, freq]) => [WB_VOCAB[wi], freq * 10]);
  if (!words.length) return;
  document.getElementById('wc-title').textContent = title;
  document.getElementById('wc-overlay').classList.add('show');
  WordCloud(document.getElementById('wc-canvas'), {
    list: words, gridSize: 8, weightFactor: 4,
    fontFamily: '-apple-system,sans-serif', color: 'random-dark',
    rotateRatio: 0.3, backgroundColor: '#fff',
  });
}
function closeWC() { document.getElementById('wc-overlay').classList.remove('show'); }

// ─── STATS ──────────────────────────────────────────────────────────────────
function updateStats() {
  const total = RAW.length;
  const shown = filtered.length;
  const years = filtered.map(r => r[1]);
  const yr = years.length ? `${Math.min(...years)}–${Math.max(...years)}` : '-';
  const cites = filtered.reduce((s, r) => s + (r[4]||0), 0);
  document.getElementById('stat-total').textContent = fmtNum(total);
  document.getElementById('stat-shown').textContent = fmtNum(shown);
  document.getElementById('stat-yr').textContent    = yr;
  document.getElementById('stat-cites').textContent = fmtNum(cites);
  document.getElementById('result-info').textContent =
    `Showing ${fmtNum(shown)} of ${fmtNum(total)} papers`;
}

function updateCards(active) {
  const counts = {};
  VENUES_CFG.forEach(v => counts[v.label] = 0);
  filtered.forEach(r => { if (counts[r[0]] !== undefined) counts[r[0]]++; });
  VENUES_CFG.forEach(v => {
    const el = document.getElementById('c-' + v.id);
    if (el) el.textContent = fmtNum(counts[v.label]);
    const card = document.querySelector(`.card.v-${v.id}`);
    if (card) card.classList.toggle('dim', !active.has(v.label));
  });
}

// ─── CHART ──────────────────────────────────────────────────────────────────
let chart = null;
function updateChart() {
  const years = Array.from(new Set(filtered.map(r => r[1]))).sort((a,b)=>a-b);
  const datasets = VENUES_CFG.map(v => {
    const data = years.map(y => filtered.filter(r => r[0]===v.label && r[1]===y).length);
    return { label: v.label, data, backgroundColor: v.color + 'cc', stack: 'a' };
  });
  if (chart) chart.destroy();
  chart = new Chart(document.getElementById('chart-timeline'), {
    type: 'bar',
    data: { labels: years, datasets },
    options: {
      responsive: true, animation: false,
      plugins: { legend: { position: 'top', labels: { boxWidth: 12, font: { size: 11 } } } },
      scales: {
        x: { stacked: true, ticks: { maxRotation: 0, font: { size: 10 } } },
        y: { stacked: true, ticks: { font: { size: 10 } } },
      },
    }
  });
}

// ─── SORT ───────────────────────────────────────────────────────────────────
document.querySelectorAll('th[data-col]').forEach(th => {
  th.addEventListener('click', () => {
    const col = th.dataset.col;
    if (sortCol === col) sortAsc = !sortAsc;
    else { sortCol = col; sortAsc = col === 'title' || col === 'authors' || col === 'venue'; }
    document.querySelectorAll('th').forEach(t => {
      t.classList.remove('sorted');
      t.querySelector('.arrow').textContent = '';
    });
    th.classList.add('sorted');
    th.querySelector('.arrow').textContent = sortAsc ? ' ▲' : ' ▼';
    applyFilters();
  });
});

// ─── VENUE SOLO ─────────────────────────────────────────────────────────────
document.querySelectorAll('.venue-card').forEach(card => {
  card.addEventListener('click', () => {
    const vid = card.dataset.venueId;
    if (soloVenue === vid) {
      soloVenue = null;
      VENUES_CFG.forEach(v => {
        const el = document.getElementById('f-' + v.id);
        if (el) el.checked = true;
      });
      document.querySelectorAll('.venue-card').forEach(c => c.classList.remove('solo','dim'));
    } else {
      soloVenue = vid;
      VENUES_CFG.forEach(v => {
        const el = document.getElementById('f-' + v.id);
        if (el) el.checked = v.id === vid;
      });
      document.querySelectorAll('.venue-card').forEach(c => {
        c.classList.toggle('solo', c.dataset.venueId === vid);
        c.classList.toggle('dim',  c.dataset.venueId !== vid);
      });
    }
    applyFilters();
  });
});

// ─── AUTHOR SEARCH ──────────────────────────────────────────────────────────
function searchAuthor(el) {
  document.getElementById('search-box').value = el.textContent.trim();
  applyFilters();
}

// ─── INIT ───────────────────────────────────────────────────────────────────
applyFilters();
document.getElementById('stat-total').textContent = fmtNum(RAW.length);
// set sort arrow
document.querySelector('th[data-col="cites"]').classList.add('sorted');
document.querySelector('th[data-col="cites"] .arrow').textContent = ' ▼';
</script>
</body>
</html>"""

# Fill in data
paper_data_json = json.dumps(arr, ensure_ascii=False)
wb_vocab_json   = json.dumps(wb_vocab, ensure_ascii=False)
wb_papers_json  = json.dumps(wb_papers_slim, ensure_ascii=False)
venues_cfg_json = json.dumps(VENUES_CFG, ensure_ascii=False)

out = (HTML
    .replace('__TITLE__',           TITLE_STR)
    .replace('__AS_OF__',           AS_OF)
    .replace('__YEAR_MIN__',        str(year_min))
    .replace('__YEAR_MAX__',        str(year_max))
    .replace('__RAW_JSON__',        paper_data_json)
    .replace('__WB_VOCAB__',        wb_vocab_json)
    .replace('__WB_PAPERS__',       wb_papers_json)
    .replace('__VENUES_CFG_JSON__', venues_cfg_json)
    .replace('__CARD_BORDER_CSS__', CARD_BORDER_CSS)
    .replace('__VENUE_TEXT_CSS__',  VENUE_TEXT_CSS)
    .replace('__SUMMARY_CARDS__',   SUMMARY_CARDS)
    .replace('__FILTER_CHECKBOXES__', FILTER_CHECKBOXES)
)

with open('explorer.html', 'w', encoding='utf-8') as f:
    f.write(out)

print(f"explorer.html 생성 완료 ({total:,} papers, {len(out)//1024} KB)")
