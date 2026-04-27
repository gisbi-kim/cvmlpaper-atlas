"""
Step 3: 최종 엑셀 파일 생성

실행: python step3_excel.py
"""
import json
import html
import os
import re
from datetime import datetime
import pandas as pd

from _clean import is_front_matter, is_translated_dup

INPUT = "all_enriched.json"

try:
    AS_OF = datetime.fromtimestamp(os.path.getmtime(INPUT)).date().isoformat()
except OSError:
    AS_OF = datetime.now().date().isoformat()
print(f"Citations as of: {AS_OF}")

OUT_XLSX = "cvml_atlas_all.xlsx"

# DOI 중복 시 venue 우선순위 (conference prestige 순)
VENUE_LABELS = ['CVPR', 'ICCV', 'ECCV', '3DV', 'NeurIPS', 'ICML', 'ICLR']
VENUE_PRIORITY = {v: i for i, v in enumerate(VENUE_LABELS)}

with open(INPUT, encoding='utf-8') as f:
    papers = json.load(f)

df = pd.DataFrame(papers)

cols = ['venue', 'year', 'title', 'authors', 'abstract', 'cited_by_count',
        'concepts', 'doi', 'ee', 'pages', 'dblp_key', 'openalex_id']
df = df[[c for c in cols if c in df.columns]]

# --- 정제 ---
for col in ['title', 'authors']:
    df[col] = df[col].fillna('').astype(str).map(html.unescape)

_dblp_suffix = re.compile(r'\s+\d{4}$')
def _clean_authors(s):
    return '; '.join(_dblp_suffix.sub('', a.strip()) for a in str(s).split(';') if a.strip())
df['authors'] = df['authors'].map(_clean_authors)

df['title'] = df['title'].str.rstrip('.').str.strip()

before = len(df)
df = df[df['authors'].str.strip() != ''].reset_index(drop=True)
print(f"proceedings 표제 행 제거: {before - len(df)}개")

before = len(df)
df = df[~df['title'].map(is_front_matter)].reset_index(drop=True)
print(f"front-matter 제거: {before - len(df)}개")

before = len(df)
df = df[~df['title'].map(is_translated_dup)].reset_index(drop=True)
print(f"비영어 번역본 제거: {before - len(df)}개")

df['doi'] = df['doi'].fillna('').astype(str).str.strip()
doi_less = (df['doi'] == '').sum()
print(f"DOI-less 행 (유지): {doi_less}개")

# DOI 정규화
df['doi'] = df['doi'].str.lower()
df['doi'] = df['doi'].str.replace(r'^https?://doi\.org/', '', regex=True)

# DOI 기반 중복 제거
before = len(df)
with_doi = df[df['doi'] != ''].copy()
without_doi = df[df['doi'] == ''].copy()
with_doi['_priority'] = with_doi['venue'].map(VENUE_PRIORITY).fillna(99).astype(int)
with_doi = with_doi.sort_values(['doi', '_priority'])
venues_per_doi = with_doi.groupby('doi')['venue'].apply(
    lambda s: '; '.join(sorted(set(s), key=lambda v: VENUE_PRIORITY.get(v, 99)))
)
with_doi = with_doi.drop_duplicates(subset=['doi'], keep='first').drop(columns=['_priority'])
with_doi['venues_all'] = with_doi['doi'].map(venues_per_doi)
without_doi['venues_all'] = without_doi['venue']
df = pd.concat([with_doi, without_doi], ignore_index=True)
print(f"DOI 중복 제거: {before} → {len(df)} ({before - len(df)}건 병합)")

# 제목+연도 within-venue dedup
def _norm_title(s):
    return re.sub(r'[^a-z0-9]', '', str(s).lower())

before = len(df)
df['_tn'] = df['title'].map(_norm_title)
short_mask = df['_tn'].str.len() < 20
dedup_pool = df[~short_mask].copy()
keep_asis = df[short_mask].copy()
dedup_pool['_priority'] = dedup_pool['venue'].map(VENUE_PRIORITY).fillna(99).astype(int)
dedup_pool = dedup_pool.sort_values(['_tn', 'year', 'venue', '_priority'])
dedup_pool = dedup_pool.drop_duplicates(subset=['_tn', 'year', 'venue'], keep='first').drop(columns=['_priority'])
df = pd.concat([dedup_pool, keep_asis], ignore_index=True).drop(columns=['_tn'])
print(f"제목+연도 dedup: {before} → {len(df)} ({before - len(df)}건 병합)")

df['year'] = pd.to_numeric(df['year'], errors='coerce').fillna(0).astype(int)
df = df.sort_values(['year', 'venue', 'title'], ascending=[False, True, True])

print(f"\nTotal rows: {len(df)}")
print(f"\nVenue counts:")
print(df['venue'].value_counts())
print(f"\nYear range: {df['year'].min()} ~ {df['year'].max()}")

# --- 통계 시트 ---
cited_num = pd.to_numeric(df['cited_by_count'], errors='coerce')
stats_df = df.assign(
    _has_doi=df['doi'].astype(bool),
    _has_abs=df['abstract'].astype(str).str.len() > 0,
    _cited=cited_num,
)
by_year = stats_df.groupby(['year', 'venue']).agg(
    papers=('title', 'count'),
    with_doi=('_has_doi', 'sum'),
    with_abstract=('_has_abs', 'sum'),
    total_citations=('_cited', 'sum'),
    mean_citations=('_cited', 'mean'),
).reset_index()
by_year['abstract_coverage_%'] = (100 * by_year['with_abstract'] / by_year['papers']).round(1)
by_year['mean_citations'] = by_year['mean_citations'].round(1)
by_year = by_year.sort_values(['year', 'venue'], ascending=[False, True])

pivot = stats_df.pivot_table(index='year', columns='venue', values='title',
                              aggfunc='count', fill_value=0)
pivot['total'] = pivot.sum(axis=1)
pivot = pivot.sort_index(ascending=False).reset_index()

total = len(df)
summary_rows = [
    ('Citations as of', AS_OF),
    ('Total papers', total),
]
seen_venues = set(df['venue'].astype(str).unique())
ordered = [v for v in VENUE_LABELS if v in seen_venues]
extras = sorted(v for v in seen_venues if v and v not in VENUE_PRIORITY)
for v in ordered + extras:
    summary_rows.append((v, int((df['venue'] == v).sum())))
summary_rows += [
    ('Year range', f"{df['year'].min()} ~ {df['year'].max()}"),
    ('With DOI', f"{int(df['doi'].astype(bool).sum())} ({100*df['doi'].astype(bool).mean():.1f}%)"),
    ('With abstract', f"{int((df['abstract'].astype(str).str.len() > 0).sum())} ({100*(df['abstract'].astype(str).str.len() > 0).mean():.1f}%)"),
    ('Total citations', int(cited_num.fillna(0).sum())),
    ('Mean citations', round(cited_num.mean(), 1)),
    ('Median citations', int(cited_num.median()) if cited_num.notna().any() else 0),
]
summary_df = pd.DataFrame(summary_rows, columns=['Field', 'Value'])

top_cited = df.copy()
top_cited['cited_num'] = cited_num
top_cited = top_cited.dropna(subset=['cited_num']).nlargest(100, 'cited_num')
top_cited = top_cited[['venue', 'year', 'title', 'authors', 'cited_num', 'doi']].rename(
    columns={'cited_num': 'cited_by_count'})

try:
    for col in ['abstract', 'title', 'authors']:
        if col in df.columns:
            df[col] = df[col].astype(str).str[:32000]
    top_cited['title'] = top_cited['title'].astype(str).str[:32000]
    top_cited['authors'] = top_cited['authors'].astype(str).str[:32000]

    with pd.ExcelWriter(OUT_XLSX, engine='openpyxl') as writer:
        summary_df.to_excel(writer, sheet_name='summary', index=False)
        pivot.to_excel(writer, sheet_name='by_year_pivot', index=False)
        by_year.to_excel(writer, sheet_name='by_year_detail', index=False)
        top_cited.to_excel(writer, sheet_name='top_cited_100', index=False)
        df.to_excel(writer, sheet_name='papers', index=False)
    print(f"\nXLSX saved: {OUT_XLSX}")
except Exception as e:
    print(f"XLSX 생성 실패: {e}")
    print("해결: pip install openpyxl")
