"""index.html 랜딩 페이지 생성

실행: python _make_index_html.py
출력: index.html
"""
import json
import os
from datetime import datetime
import pandas as pd

from _venues import VENUES_CFG, VENUE_LABELS

XLSX = 'cvml_atlas_all.xlsx'

try:
    AS_OF = datetime.fromtimestamp(os.path.getmtime('all_enriched.json')).date().isoformat()
except OSError:
    AS_OF = datetime.now().date().isoformat()

# stats
df_sum = pd.read_excel(XLSX, sheet_name='summary')
stats  = dict(zip(df_sum['Field'].astype(str), df_sum['Value'].astype(str)))
total  = stats.get('Total papers', '?')
yr_range = stats.get('Year range', '?')
with_abs = stats.get('With abstract', '?')

df_piv = pd.read_excel(XLSX, sheet_name='by_year_pivot')
df_piv['year'] = df_piv['year'].astype(int)
for v in VENUE_LABELS:
    if v not in df_piv.columns:
        df_piv[v] = 0
    df_piv[v] = df_piv[v].fillna(0).astype(int)
df_piv['total'] = df_piv[VENUE_LABELS].sum(axis=1)
rows = [[int(r['year'])] + [int(r[v]) for v in VENUE_LABELS]
        for r in df_piv.sort_values('year').to_dict('records')]

venue_totals = {v: int(df_piv[v].sum()) for v in VENUE_LABELS}

chart_labels   = json.dumps([r[0] for r in rows])
chart_datasets = json.dumps([
    {'label': v['label'],
     'data': [r[i+1] for r in rows],
     'backgroundColor': v['color'] + 'cc',
     'stack': 'a'}
    for i, v in enumerate(VENUES_CFG)
])

VENUE_CARDS = ''.join(f"""
  <a class="vcard" href="by_venue/{v['label']}.xlsx" style="border-top:3px solid {v['color']}">
    <div class="vnum">{venue_totals.get(v['label'], 0):,}</div>
    <div class="vname">{v['label']}</div>
    <div class="vsince">{v['since']}~</div>
  </a>""" for v in VENUES_CFG)

HTML = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>CV+ML Paper Atlas</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js"></script>
<style>
* {{ box-sizing: border-box; }}
body {{ font-family: -apple-system,"Segoe UI",sans-serif; margin:0; background:#f7f8fa; color:#222; }}
header {{ background:#fff; border-bottom:1px solid #e5e5e5; padding:24px 32px 20px; }}
header h1 {{ font-size:26px; margin:0 0 6px; }}
header .sub {{ color:#666; font-size:14px; }}
.content {{ max-width:1100px; margin:28px auto; padding:0 24px; }}
.stat-row {{ display:flex; gap:20px; flex-wrap:wrap; margin-bottom:24px; }}
.stat-box {{ background:#fff; border:1px solid #e5e5e5; border-radius:8px; padding:14px 20px; flex:1; min-width:150px; }}
.stat-box .n {{ font-size:26px; font-weight:700; font-variant-numeric:tabular-nums; margin-bottom:2px; }}
.stat-box .l {{ color:#888; font-size:13px; }}
.section {{ background:#fff; border:1px solid #e5e5e5; border-radius:8px; padding:18px 20px; margin-bottom:20px; }}
.section h2 {{ font-size:15px; margin:0 0 14px; color:#333; }}
canvas {{ max-height:320px; }}
.venue-grid {{ display:grid; grid-template-columns:repeat(auto-fill,minmax(110px,1fr)); gap:10px; margin-bottom:4px; }}
.vcard {{ background:#fafafa; border:1px solid #e5e5e5; border-radius:8px; padding:10px 12px; text-decoration:none; color:#222; display:block; transition:background 0.15s; }}
.vcard:hover {{ background:#f0f7ff; }}
.vnum {{ font-size:18px; font-weight:700; font-variant-numeric:tabular-nums; }}
.vname {{ font-weight:600; font-size:13px; margin:2px 0 1px; }}
.vsince {{ font-size:11px; color:#999; }}
.nav-grid {{ display:grid; grid-template-columns:repeat(auto-fill,minmax(220px,1fr)); gap:12px; }}
.nav-card {{ background:#fff; border:1px solid #e5e5e5; border-radius:8px; padding:16px 18px; text-decoration:none; color:#222; display:flex; flex-direction:column; gap:4px; transition:box-shadow 0.15s; }}
.nav-card:hover {{ box-shadow:0 4px 16px rgba(0,0,0,0.08); border-color:#bbb; }}
.nav-card .icon {{ font-size:24px; }}
.nav-card .nc-title {{ font-size:14px; font-weight:600; }}
.nav-card .nc-desc {{ font-size:12px; color:#888; }}
footer {{ text-align:center; padding:24px; color:#bbb; font-size:12px; }}
footer a {{ color:#bbb; }}
</style>
</head>
<body>
<header>
  <h1>CV+ML Paper Atlas</h1>
  <div class="sub">40+ years of Computer Vision &amp; Machine Learning research &nbsp;·&nbsp; Citations as of {AS_OF}</div>
</header>
<div class="content">

  <div class="stat-row">
    <div class="stat-box"><div class="n">{total}</div><div class="l">Total papers</div></div>
    <div class="stat-box"><div class="n">8</div><div class="l">Venues</div></div>
    <div class="stat-box"><div class="n">{yr_range}</div><div class="l">Year range</div></div>
    <div class="stat-box"><div class="n">{with_abs.split()[0] if with_abs != '?' else '?'}</div><div class="l">With abstract</div></div>
  </div>

  <div class="section">
    <h2>🗂 Navigate</h2>
    <div class="nav-grid">
      <a class="nav-card" href="explorer.html">
        <div class="icon">🔍</div>
        <div class="nc-title">Paper Explorer</div>
        <div class="nc-desc">Filter, sort, search all papers by title, author, year, citations</div>
      </a>
      <a class="nav-card" href="by_year.html">
        <div class="icon">📈</div>
        <div class="nc-title">Publications by Year</div>
        <div class="nc-desc">Stacked chart + table of paper counts per venue per year</div>
      </a>
      <a class="nav-card" href="coauthor_network.html">
        <div class="icon">🕸</div>
        <div class="nc-title">Co-author Network</div>
        <div class="nc-desc">Interactive d3-force graph of {total}+ researchers</div>
      </a>
      <a class="nav-card" href="dataset_preview.html">
        <div class="icon">📄</div>
        <div class="nc-title">Dataset Preview</div>
        <div class="nc-desc">Browse all Excel sheets before downloading</div>
      </a>
      <a class="nav-card" href="cvml_atlas_all.xlsx">
        <div class="icon">⬇</div>
        <div class="nc-title">Download Excel</div>
        <div class="nc-desc">Full dataset: summary, pivot, top-cited, all papers</div>
      </a>
    </div>
  </div>

  <div class="section">
    <h2>📈 Publications per year</h2>
    <canvas id="chart"></canvas>
  </div>

  <div class="section">
    <h2>🏛 Venues <span style="font-size:12px;color:#999;font-weight:400;">(click to download per-venue xlsx)</span></h2>
    <div class="venue-grid">{VENUE_CARDS}
    </div>
  </div>

</div>
<footer>
  CV+ML Paper Atlas · Data: <a href="https://dblp.org">DBLP</a> + <a href="https://www.semanticscholar.org">Semantic Scholar</a>
</footer>
<script>
new Chart(document.getElementById('chart'), {{
  type: 'bar',
  data: {{
    labels: {chart_labels},
    datasets: {chart_datasets},
  }},
  options: {{
    responsive: true, animation: false,
    plugins: {{ legend: {{ position:'top', labels:{{ boxWidth:12, font:{{ size:11 }} }} }} }},
    scales: {{
      x: {{ stacked:true, ticks:{{ maxRotation:45, font:{{ size:10 }} }} }},
      y: {{ stacked:true, ticks:{{ font:{{ size:10 }} }} }},
    }},
  }},
}});
</script>
</body>
</html>"""

with open('index.html', 'w', encoding='utf-8') as f:
    f.write(HTML)
print(f"index.html 생성 완료")
