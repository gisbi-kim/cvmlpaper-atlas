"""연도별 논문 편수 시각화 HTML 생성

실행: python _make_by_year_html.py
출력: by_year.html
"""
import json
import os
import re
from datetime import datetime
import pandas as pd

from _venues import VENUES_CFG, VENUE_LABELS

TITLE_STR = 'CV+ML Papers by Year'

try:
    AS_OF = datetime.fromtimestamp(os.path.getmtime('all_enriched.json')).date().isoformat()
except OSError:
    AS_OF = datetime.now().date().isoformat()

XLSX = 'cvml_atlas_all.xlsx'
df = pd.read_excel(XLSX, sheet_name='by_year_pivot')
df['year'] = df['year'].astype(int)
for v in VENUE_LABELS:
    if v not in df.columns:
        df[v] = 0
    df[v] = df[v].fillna(0).astype(int)
df['total'] = df[VENUE_LABELS].sum(axis=1)
df = df.sort_values('year').reset_index(drop=True)

rows = [[int(r['year'])] + [int(r[v]) for v in VENUE_LABELS]
        for r in df.to_dict('records')]
totals = {v: int(df[v].sum()) for v in VENUE_LABELS}
grand_total = sum(totals.values())
peak_row = df.loc[df['total'].idxmax()]
peak_year, peak_total = int(peak_row['year']), int(peak_row['total'])

def _class_key(label):
    return re.sub(r'[^A-Za-z0-9]', '', label).upper()

CARD_BORDER_CSS = ''.join(
    f'  .card.v-{v["id"]} {{ border-top: 3px solid {v["color"]}; }}\n'
    for v in VENUES_CFG
)
CELL_TEXT_CSS = ''.join(
    f'  td.c-{v["id"]} {{ color: {v["color"]}; font-variant-numeric: tabular-nums; }}\n'
    for v in VENUES_CFG
)
SUMMARY_CARDS = ''.join(
    f'  <div class="card v-{v["id"]}"><div class="num">{totals[v["label"]]:,}</div>'
    f'<div class="label">{v["label"]} ({v["since"]}~)</div></div>\n'
    for v in VENUES_CFG
)
TABLE_HEAD = ''.join(f'<th class="c-{v["id"]}">{v["label"]}</th>' for v in VENUES_CFG)
TABLE_ROWS = ''.join(
    '<tr><td class="yr">{}</td>{}<td class="total">{:,}</td></tr>'.format(
        r[0],
        ''.join(f'<td class="c-{v["id"]}">{r[i+1] if r[i+1] else ""}</td>'
                for i, v in enumerate(VENUES_CFG)),
        sum(r[1:]),
    )
    for r in reversed(rows)
)

CHART_DATASETS = json.dumps([
    {
        'label': v['label'],
        'data': [int(df.loc[df['year']==r[0], v['label']].iloc[0]) if r[0] in df['year'].values else 0
                 for r in rows],
        'backgroundColor': v['color'] + 'cc',
        'stack': 'a',
    }
    for v in VENUES_CFG
], ensure_ascii=False)
CHART_LABELS = json.dumps([r[0] for r in rows])

HTML = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>{TITLE_STR}</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js"></script>
<style>
* {{ box-sizing: border-box; }}
body {{ font-family: -apple-system,"Segoe UI",sans-serif; margin:20px; background:#fafafa; color:#222; }}
.brand {{ font-size:12px; color:#888; margin-bottom:4px; }}
.brand a {{ color:inherit; text-decoration:none; font-weight:600; }}
.brand a:hover {{ color:#1f77b4; }}
h1 {{ font-size:22px; margin:0 0 4px; }}
.sub {{ color:#666; font-size:13px; margin-bottom:16px; }}
.summary {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(110px,1fr)); gap:10px; margin-bottom:16px; }}
.card {{ background:#fff; border:1px solid #e5e5e5; border-radius:8px; padding:10px 14px; }}
.card .num {{ font-size:18px; font-weight:600; font-variant-numeric:tabular-nums; }}
.card .label {{ color:#666; font-size:11px; margin-top:2px; }}
.card.total-card .num {{ font-size:22px; }}
.wrap {{ background:#fff; border:1px solid #e5e5e5; border-radius:8px; padding:14px 16px; margin-bottom:16px; }}
h2 {{ font-size:14px; margin:0 0 10px; color:#333; }}
canvas {{ max-height:380px; }}
table {{ width:100%; border-collapse:collapse; font-size:12px; }}
th,td {{ border-bottom:1px solid #eee; padding:5px 8px; text-align:right; }}
th {{ background:#f4f4f4; font-weight:600; font-size:11px; }}
td.yr {{ text-align:left; font-weight:600; color:#333; }}
td.total {{ font-weight:700; color:#222; }}
{CARD_BORDER_CSS}
{CELL_TEXT_CSS}
nav {{ margin-bottom:12px; font-size:13px; }}
nav a {{ color:#1f77b4; text-decoration:none; margin-right:14px; }}
nav a:hover {{ text-decoration:underline; }}
</style>
</head>
<body>
<div class="brand"><a href="index.html">CV+ML Paper Atlas</a></div>
<h1>{TITLE_STR}</h1>
<div class="sub">Citations as of {AS_OF} &nbsp;·&nbsp; Peak year: <b>{peak_year}</b> ({peak_total:,} papers)</div>

<nav>
  <a href="index.html">← Home</a>
  <a href="explorer.html">Paper Explorer</a>
  <a href="coauthor_network.html">Co-author Network</a>
  <a href="dataset_preview.html">Dataset Preview</a>
</nav>

<div class="summary">
  <div class="card total-card" style="border-top:3px solid #222;">
    <div class="num">{grand_total:,}</div>
    <div class="label">Total papers</div>
  </div>
{SUMMARY_CARDS}</div>

<div class="wrap">
  <h2>📈 Publications per year (stacked)</h2>
  <canvas id="chart-stacked"></canvas>
</div>

<div class="wrap">
  <h2>📊 Year-by-year table</h2>
  <table>
    <thead><tr><th style="text-align:left">Year</th>{TABLE_HEAD}<th>Total</th></tr></thead>
    <tbody>{TABLE_ROWS}</tbody>
  </table>
</div>

<script>
new Chart(document.getElementById('chart-stacked'), {{
  type: 'bar',
  data: {{
    labels: {CHART_LABELS},
    datasets: {CHART_DATASETS},
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

with open('by_year.html', 'w', encoding='utf-8') as f:
    f.write(HTML)
print(f"by_year.html 생성 완료 ({grand_total:,} papers, {len(rows)} years)")
