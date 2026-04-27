"""특정 venue 서브셋만 수집하는 병렬 수집용 스크립트.

사용법:
    python _collect_subset.py iccv
    python _collect_subset.py eccv_3dv
    python _collect_subset.py ml
"""
import sys, json, time, os
from step1_dblp import fetch_dblp_year, OUT_DIR

SUBSETS = {
    'iccv': [
        ('iccv', 'conf/iccv', 'ICCV', range(1987, 2026)),
    ],
    'eccv_3dv': [
        ('eccv',    'conf/eccv',    'ECCV', range(1990, 2025)),
        ('3dv',     'conf/3dv',     '3DV',  range(2013, 2026)),
        ('3dimpvt', 'conf/3dimpvt', '3DV',  range(2011, 2013)),
        ('3dim',    'conf/3dim',    '3DV',  range(1999, 2010)),
    ],
    'ml': [
        ('neurips', 'conf/nips', 'NeurIPS', range(1987, 2026)),
        ('icml',    'conf/icml', 'ICML',    range(1980, 2026)),
        ('iclr',    'conf/iclr', 'ICLR',    range(2013, 2026)),
    ],
}

subset_name = sys.argv[1] if len(sys.argv) > 1 else 'iccv'
venues = SUBSETS[subset_name]

jobs = [(key, stream, label, y)
        for key, stream, label, years in venues
        for y in years]

papers = []
for i, (key, stream, label, year) in enumerate(jobs):
    fpath = f"{OUT_DIR}/{key}_{year}.json"
    if os.path.exists(fpath) and os.path.getsize(fpath) > 2:
        with open(fpath, encoding='utf-8') as f:
            p = json.load(f)
        if p:
            print(f"[{i+1}/{len(jobs)}] {label} {year}: cached ({len(p)})")
        papers.extend(p)
        continue
    print(f"[{i+1}/{len(jobs)}] {label} {year}: fetching...", flush=True)
    p = fetch_dblp_year(stream, label, year)
    print(f"    got {len(p)} papers")
    with open(fpath, 'w', encoding='utf-8') as f:
        json.dump(p, f, ensure_ascii=False)
    papers.extend(p)
    time.sleep(2)

out = f"all_dblp_{subset_name}.json"
with open(out, 'w', encoding='utf-8') as f:
    json.dump(papers, f, ensure_ascii=False)

by_venue = {}
for p in papers:
    v = p['venue']
    by_venue[v] = by_venue.get(v, 0) + 1
print(f"\n=== {subset_name.upper()} DONE: {len(papers)} papers ===")
for v, cnt in sorted(by_venue.items(), key=lambda x: -x[1]):
    print(f"  {v}: {cnt:,}")
