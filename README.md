# CV+ML Paper Atlas

A comprehensive bibliography of Computer Vision and Machine Learning research —
**111,939 papers** across 7 major venues, spanning 1987–2025, enriched with
citation counts and abstracts from Semantic Scholar.

## 🌐 Live Site

**https://gisbi-kim.github.io/cvmlpaper-atlas/**

| Page | Description |
|------|-------------|
| [Paper Explorer](https://gisbi-kim.github.io/cvmlpaper-atlas/explorer.html) | Filter, sort, and search all papers by title, author, year, citations |
| [Publications by Year](https://gisbi-kim.github.io/cvmlpaper-atlas/by_year.html) | Stacked bar chart + table of paper counts per venue per year |
| [Co-author Network](https://gisbi-kim.github.io/cvmlpaper-atlas/coauthor_network.html) | Interactive graph of 14,000+ researchers (pre-baked FR layout) |
| [Dataset Preview](https://gisbi-kim.github.io/cvmlpaper-atlas/dataset_preview.html) | Browse all Excel sheets before downloading |

## 📊 Dataset Summary

| Venue | Papers | Since |
|-------|-------:|-------|
| CVPR  | 31,548 | 1983 |
| NeurIPS | 25,165 | 1987 |
| ICML  | 17,032 | 1980 |
| ICCV  | 12,564 | 1987 |
| ICLR  | 12,253 | 2013 |
| ECCV  | 11,760 | 1990 |
| 3DV   |  1,617 | 1999 |
| **Total** | **111,939** | |

- **Citation coverage**: 52,255 papers (46.6%) · Total 7.4M citations
- **Abstract coverage**: 32,973 papers (29.5%) — via Semantic Scholar DOI lookup
- **Co-author network**: 14,342 researchers · 49,106 collaboration pairs
- **Citations as of**: 2026-04-28

## ⬇️ Download

- **Full Excel dataset** (all venues, 5 sheets): [`cvml_atlas_all.xlsx`](https://gisbi-kim.github.io/cvmlpaper-atlas/cvml_atlas_all.xlsx) — 31 MB
- **Per-venue Excel**: [`by_venue/CVPR.xlsx`](https://gisbi-kim.github.io/cvmlpaper-atlas/by_venue/CVPR.xlsx), `ICCV.xlsx`, `ECCV.xlsx`, `NeurIPS.xlsx`, `ICML.xlsx`, `ICLR.xlsx`, `3DV.xlsx`
- **Raw JSON data** (for pipeline re-runs): [Release v1.0.0](https://github.com/gisbi-kim/cvmlpaper-atlas/releases/tag/v1.0.0)
  - `all_dblp.json` (39 MB) — DBLP raw collection
  - `all_enriched.json` (81 MB) — S2-enriched with abstracts + citations

## 🗂 Venue Coverage

**3DV lineage** (merged into single `3DV` label):
- 3DIM (1999–2009) · 3DIMPVT (2011–2012) · 3DV (2013–present)

## 🛠 Pipeline

Data collected from [DBLP](https://dblp.org), enriched via [Semantic Scholar](https://www.semanticscholar.org).

```
step1_dblp.py          →  all_dblp.json        (112k papers from DBLP)
step2_s2.py            →  all_enriched.json    (+ abstracts & citations via S2 batch API)
step3_excel.py         →  cvml_atlas_all.xlsx
_make_all_html.py      →  explorer.html
_make_by_year_html.py  →  by_year.html
_make_coauthor_network.py  →  coauthor_network.html
_make_index_html.py    →  index.html
_split_by_venue.py     →  by_venue/*.xlsx
```

See [`REFRESH.md`](REFRESH.md) for update instructions and pipeline details.

## 📝 Citation

If you use this dataset, please cite the original sources:

- **DBLP**: Ley, M. (2002). The DBLP computer science bibliography. *SPIRE*.
- **Semantic Scholar**: Lo et al. (2020). S2ORC: The Semantic Scholar Open Research Corpus. *ACL*.
