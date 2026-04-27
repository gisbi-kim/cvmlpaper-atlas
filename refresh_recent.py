"""최신 연도만 빠르게 갱신하는 스크립트.

전체 step1~step3를 다시 돌리지 않고 최근 N년치만 재수집 → 기존 데이터에 병합.

실행:
    python refresh_recent.py            # 최근 2년 갱신
    python refresh_recent.py --years 3  # 최근 3년 갱신
"""
import argparse
import json
import os
import time
from datetime import datetime

import requests
from urllib.parse import quote

from step1_dblp import fetch_dblp_year, CORE_VENUES

OUT_DIR = 'dblp_raw'
MAIN_JSON = 'all_dblp.json'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--years', type=int, default=2, help='최근 몇 년을 재수집할지')
    args = ap.parse_args()

    current_year = datetime.now().year
    refresh_years = list(range(current_year - args.years + 1, current_year + 1))
    print(f"Refreshing years: {refresh_years}")

    # 기존 데이터 로드
    if os.path.exists(MAIN_JSON):
        with open(MAIN_JSON, encoding='utf-8') as f:
            all_papers = json.load(f)
        print(f"Existing papers: {len(all_papers)}")
        # 갱신할 연도의 기존 데이터 제거
        all_papers = [p for p in all_papers if int(p.get('year', 0)) not in refresh_years]
        print(f"After removing refresh years: {len(all_papers)}")
    else:
        all_papers = []

    new_papers = []
    for key, stream, label, _, vq in CORE_VENUES:
        for year in refresh_years:
            fpath = f"{OUT_DIR}/{key}_{year}.json"
            # 캐시 파일 삭제 (강제 재수집)
            if os.path.exists(fpath):
                os.remove(fpath)

            print(f"  {label} {year}: fetching...", flush=True)
            papers = fetch_dblp_year(stream, label, year, venue_query=vq)
            print(f"    got {len(papers)} papers")

            with open(fpath, 'w', encoding='utf-8') as f:
                json.dump(papers, f, ensure_ascii=False)

            new_papers.extend(papers)
            time.sleep(2)

    all_papers.extend(new_papers)
    with open(MAIN_JSON, 'w', encoding='utf-8') as f:
        json.dump(all_papers, f, ensure_ascii=False)

    print(f"\n=== DONE: {len(all_papers)} total papers (+{len(new_papers)} new) ===")
    print("Next: python step2_s2.py  →  python step3_excel.py  →  python _make_all_html.py")


if __name__ == '__main__':
    main()
