"""
Step 1: DBLP에서 CV+ML 8개 venue 전체 논문 메타데이터 수집
- 연도별로 수집하여 dblp_raw/ 폴더에 JSON으로 저장 (체크포인트)
- 중단되어도 이미 받은 연도는 스킵
- 최종 all_dblp.json 합본 생성

실행:
    python step1_dblp.py              # core 8 venues
    python step1_dblp.py --test       # CVPR 2020-2024만 빠르게 테스트

예상 소요: 2~4시간 (연결 속도 따라)
"""
import argparse
import requests
import time
import json
import os
from urllib.parse import quote

DBLP_BASE = "https://dblp.org/search/publ/api"
OUT_DIR = "dblp_raw"
os.makedirs(OUT_DIR, exist_ok=True)


def fetch_dblp_year(stream, venue_label, year, venue_query=None):
    """DBLP에서 한 stream·연도 논문 전부 수집.
    venue_query: if set, use 'venue:NAME year:Y:' instead of 'stream:S: year:Y:'
                 (needed for 3DV/3DIMPVT where stream: returns 0)
    """
    results = []
    offset = 0
    batch_size = 1000  # DBLP 최대

    while True:
        if venue_query:
            query = f"venue:{venue_query} year:{year}:"
        else:
            query = f"stream:{stream}: year:{year}:"
        url = f"{DBLP_BASE}?q={quote(query)}&format=json&h={batch_size}&f={offset}"

        HEADERS = {'User-Agent': 'cvml-paper-atlas/1.0 (research; gisbi.kim@gmail.com)'}
        r = None
        for attempt in range(5):
            try:
                r = requests.get(url, timeout=60, headers=HEADERS)
                if r.status_code == 200:
                    break
                elif r.status_code == 429:
                    wait = 60 * (attempt + 1)
                    print(f"    rate limited, waiting {wait}s...")
                    time.sleep(wait)
                else:
                    print(f"    HTTP {r.status_code}, retry {attempt+1}")
                    time.sleep(10)
            except Exception as e:
                wait = 15 * (attempt + 1)
                print(f"    error {e}, retry {attempt+1}, waiting {wait}s")
                time.sleep(wait)

        if r is None or r.status_code != 200:
            print(f"    FAILED {venue_label} {year}")
            return results

        data = r.json()
        hits = data.get('result', {}).get('hits', {})
        total = int(hits.get('@total', 0))

        if total == 0:
            return results

        hit_list = hits.get('hit', [])
        if not hit_list:
            break

        for h in hit_list:
            info = h.get('info', {})
            authors_data = info.get('authors', {}).get('author', [])
            if isinstance(authors_data, dict):
                authors_data = [authors_data]
            authors = [a.get('text', '') for a in authors_data]

            results.append({
                'venue': venue_label,
                'year': str(info.get('year', year)),
                'title': info.get('title', ''),
                'authors': '; '.join(authors),
                'doi': info.get('doi', '').lower() if info.get('doi') else '',
                'ee': info.get('ee', ''),
                'pages': info.get('pages', ''),
                'dblp_key': info.get('key', ''),
            })

        offset += len(hit_list)
        if offset >= total or len(hit_list) < batch_size:
            break
        time.sleep(1)

    return results


# (cache_key, dblp_stream, venue_label, year_range, venue_query_override)
#
# 3DV 계보:
#   3DIM  (1999~2009, 격년) → conf/3dim  (stream: works)
#   3DIMPVT (2011~2012)    → venue:3DIMPVT (stream:conf/3dimpvt: returns 0)
#   3DV   (2013~현재)      → venue:3DV    (stream:conf/3dv: returns 0)
#
# ECCV는 짝수 해만, ICCV는 홀수 해만 개최하지만 전체 범위를 넣어도
# DBLP가 없는 해는 0건으로 반환하므로 캐시만 남고 실데이터엔 영향 없음.

CORE_VENUES = [
    # (cache_key, dblp_stream, venue_label, year_range, venue_query_override)
    # CV conferences
    ('cvpr',     'conf/cvpr',     'CVPR',    range(1983, 2026), None),
    ('iccv',     'conf/iccv',     'ICCV',    range(1987, 2026), None),
    ('eccv',     'conf/eccv',     'ECCV',    range(1990, 2025), None),
    # ML conferences
    ('neurips',  'conf/nips',     'NeurIPS', range(1987, 2026), None),
    ('icml',     'conf/icml',     'ICML',    range(1980, 2026), None),
    ('iclr',     'conf/iclr',     'ICLR',    range(2013, 2026), None),
    # 3D Vision (계보 통합) — stream: broken for 3dv/3dimpvt, use venue: instead
    ('3dv',      'conf/3dv',      '3DV',     range(2013, 2026), '3DV'),
    ('3dimpvt',  'conf/3dimpvt',  '3DV',     range(2011, 2013), '3DIMPVT'),
    ('3dim',     'conf/3dim',     '3DV',     range(1999, 2010), None),
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--test', action='store_true',
                    help='CVPR 2020-2024만 빠르게 테스트')
    args = ap.parse_args()

    if args.test:
        venues_config = [('cvpr', 'conf/cvpr', 'CVPR', range(2020, 2025), None)]
    else:
        venues_config = CORE_VENUES

    jobs = []
    for key, stream, label, years, vq in venues_config:
        for y in years:
            jobs.append((key, stream, label, y, vq))

    all_papers = []
    for i, (key, stream, label, year, vq) in enumerate(jobs):
        fpath = f"{OUT_DIR}/{key}_{year}.json"

        if os.path.exists(fpath) and os.path.getsize(fpath) > 2:
            with open(fpath, encoding='utf-8') as f:
                papers = json.load(f)
            if papers:
                print(f"[{i+1}/{len(jobs)}] {label} {year}: cached ({len(papers)})")
            all_papers.extend(papers)
            continue

        print(f"[{i+1}/{len(jobs)}] {label} {year}: fetching...", flush=True)
        papers = fetch_dblp_year(stream, label, year, venue_query=vq)
        print(f"    got {len(papers)} papers")

        with open(fpath, 'w', encoding='utf-8') as f:
            json.dump(papers, f, ensure_ascii=False)

        all_papers.extend(papers)
        time.sleep(2)

    with open('all_dblp.json', 'w', encoding='utf-8') as f:
        json.dump(all_papers, f, ensure_ascii=False)

    print(f"\n=== TOTAL: {len(all_papers)} papers ===")
    by_venue = {}
    for p in all_papers:
        v = p['venue']
        by_venue[v] = by_venue.get(v, 0) + 1
    for v, cnt in sorted(by_venue.items(), key=lambda x: -x[1]):
        print(f"  {v}: {cnt:,}")
    with_doi = sum(1 for p in all_papers if p.get('doi'))
    print(f"With DOI: {with_doi} ({100*with_doi/max(len(all_papers),1):.1f}%)")


if __name__ == '__main__':
    main()
