"""
Merges all dblp_raw/*.json shard files into all_dblp.json.
Also deduplicates by (venue, year, dblp_key).

Usage:
    python _merge_dblp.py

Run AFTER all _collect_subset.py processes (and step1_dblp.py) finish.
"""
import json, os, glob
from step1_dblp import OUT_DIR

seen = set()
papers = []

files = sorted(glob.glob(f"{OUT_DIR}/*.json"))
print(f"Reading {len(files)} shard files from {OUT_DIR}/...")

for fpath in files:
    size = os.path.getsize(fpath)
    if size <= 2:
        continue  # empty / failed fetch
    with open(fpath, encoding='utf-8') as f:
        try:
            shard = json.load(f)
        except json.JSONDecodeError:
            print(f"  SKIP (bad json): {fpath}")
            continue
    for p in shard:
        key = p.get('dblp_key') or f"{p.get('venue')}|{p.get('year')}|{p.get('title','')[:60]}"
        if key not in seen:
            seen.add(key)
            papers.append(p)

with open('all_dblp.json', 'w', encoding='utf-8') as f:
    json.dump(papers, f, ensure_ascii=False)

print(f"\n=== MERGED: {len(papers)} unique papers → all_dblp.json ===")
by_venue = {}
for p in papers:
    v = p['venue']
    by_venue[v] = by_venue.get(v, 0) + 1
for v, cnt in sorted(by_venue.items(), key=lambda x: -x[1]):
    print(f"  {v}: {cnt:,}")

with_doi = sum(1 for p in papers if p.get('doi'))
print(f"\nWith DOI: {with_doi} ({100*with_doi/max(len(papers),1):.1f}%)")
print(f"Year range: {min(int(p.get('year',0)) for p in papers if p.get('year'))} "
      f"~ {max(int(p.get('year',0)) for p in papers if p.get('year'))}")
