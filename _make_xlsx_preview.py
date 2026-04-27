"""dataset_preview.html 생성 — xlsx 각 시트의 미리보기 페이지

실행: python _make_xlsx_preview.py
출력: dataset_preview.html
"""
from __future__ import annotations
import html
import os
from datetime import datetime
import pandas as pd

XLSX = 'cvml_atlas_all.xlsx'
OUT  = 'dataset_preview.html'

ROW_LIMITS: dict[str, int | None] = {
    'summary':        None,
    'by_year_pivot':  None,
    'by_year_detail': 30,
    'top_cited_100':  30,
    'papers':         30,
}
CELL_MAX = 200


def _cell(v) -> str:
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return '<span class="null">—</span>'
    s = str(v)
    if len(s) > CELL_MAX:
        s = s[:CELL_MAX].rstrip() + '…'
    return html.escape(s)


def _render_sheet(name: str, df: pd.DataFrame, limit: int | None) -> str:
    total = len(df)
    shown = df if limit is None else df.head(limit)
    head  = ''.join(f'<th>{html.escape(str(c))}</th>' for c in shown.columns)
    rows  = ''.join(
        '<tr>' + ''.join(f'<td>{_cell(v)}</td>' for v in r) + '</tr>'
        for _, r in shown.iterrows()
    )
    trailer = ''
    if limit and total > limit:
        trailer = (f'<div class="more">+ {total-limit:,} more rows — '
                   f'download the xlsx to see all {total:,}.</div>')
    return f'''
<section id="sheet-{html.escape(name)}">
  <h2>{html.escape(name)}
    <span class="ncol">{len(shown.columns)} cols</span>
    <span class="nrow">{total:,} rows{f" · first {len(shown):,} shown" if limit and total > limit else ""}</span>
  </h2>
  <div class="scroll"><table><thead><tr>{head}</tr></thead><tbody>{rows}</tbody></table></div>
  {trailer}
</section>'''


as_of   = datetime.fromtimestamp(os.path.getmtime(XLSX)).date().isoformat()
file_mb = os.path.getsize(XLSX) / 1024 / 1024

sections, toc = [], []
for name, limit in ROW_LIMITS.items():
    df = pd.read_excel(XLSX, sheet_name=name)
    sections.append(_render_sheet(name, df, limit))
    toc.append(f'<a href="#sheet-{html.escape(name)}">{html.escape(name)}</a>')

out_html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Dataset Preview — CV+ML Paper Atlas</title>
<style>
* {{ box-sizing: border-box; }}
body {{ font-family: -apple-system,"Segoe UI",sans-serif; margin:24px; background:#fafafa; color:#222; max-width:1400px; }}
.brand {{ font-size:12px; color:#888; margin-bottom:4px; }}
.brand a {{ color:inherit; text-decoration:none; font-weight:600; }}
h1 {{ font-size:22px; margin:0 0 6px; }}
.meta {{ color:#666; font-size:13px; margin-bottom:20px; }}
.meta a {{ color:#1f77b4; }}
nav.toc {{ display:flex; gap:12px; flex-wrap:wrap; margin-bottom:24px; font-size:13px; }}
nav.toc a {{ color:#1f77b4; text-decoration:none; padding:4px 10px; border:1px solid #dde; border-radius:4px; }}
nav.toc a:hover {{ background:#f0f7ff; }}
section {{ margin-bottom:32px; }}
h2 {{ font-size:15px; margin:0 0 8px; display:flex; align-items:center; gap:10px; }}
.ncol,.nrow {{ font-size:11px; color:#888; font-weight:400; background:#f4f4f4; padding:2px 7px; border-radius:10px; }}
.scroll {{ overflow-x:auto; border:1px solid #e5e5e5; border-radius:6px; }}
table {{ border-collapse:collapse; font-size:12px; width:100%; }}
th,td {{ border-bottom:1px solid #eee; padding:5px 10px; white-space:nowrap; text-align:left; }}
th {{ background:#f7f7f7; font-weight:600; position:sticky; top:0; z-index:1; }}
tr:hover td {{ background:#fafeff; }}
.null {{ color:#ccc; }}
.more {{ margin-top:8px; font-size:12px; color:#888; font-style:italic; }}
nav.top {{ margin-bottom:14px; font-size:13px; }}
nav.top a {{ color:#1f77b4; text-decoration:none; margin-right:14px; }}
nav.top a:hover {{ text-decoration:underline; }}
</style>
</head>
<body>
<div class="brand"><a href="index.html">CV+ML Paper Atlas</a></div>
<h1>Dataset Preview</h1>
<div class="meta">
  <b>{html.escape(XLSX)}</b> &nbsp;·&nbsp; {file_mb:.1f} MB &nbsp;·&nbsp; generated {as_of}
  &nbsp;·&nbsp; <a href="{html.escape(XLSX)}">⬇ Download</a>
</div>
<nav class="top">
  <a href="index.html">← Home</a>
  <a href="explorer.html">Paper Explorer</a>
  <a href="by_year.html">By Year</a>
  <a href="coauthor_network.html">Co-author Network</a>
</nav>
<nav class="toc">{''.join(toc)}</nav>
{''.join(sections)}
</body>
</html>"""

with open(OUT, 'w', encoding='utf-8') as f:
    f.write(out_html)
print(f"{OUT} 생성 완료 ({file_mb:.1f} MB xlsx)")
