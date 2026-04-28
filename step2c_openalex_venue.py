"""Step 2c: OpenAlex 학회별 대량 수집으로 NeurIPS/ICML/ICLR 인용수·초록 보강

전략: title search가 아니라 source(학회) + year 필터로 전체를 가져와서
title 정규화 매칭 → 우리 레코드에 병합.

- 200편/페이지, ~10 req/s (비인증) → 전 venues 합계 5분 이내 완료
- OpenAlex abstract_inverted_index → 원문 복원

실행: python step2c_openalex_venue.py
"""
import json
import re
import time
import requests
from collections import defaultdict

INPUT    = "all_enriched.json"
OUT_FILE = "all_enriched.json"

OA_BASE  = "https://api.openalex.org"
HEADERS  = {"User-Agent": "cvml-paper-atlas/1.0 (mailto:gisbi.kim@gmail.com)"}
PER_PAGE = 200
SLEEP    = 0.12  # 8 req/s, 폴라이트

# OpenAlex 학회 display_name 검색어 → 우리 venue 라벨 매핑
VENUE_SOURCES = {
    "NeurIPS": ["Neural Information Processing Systems", "NeurIPS", "NIPS"],
    "ICML":    ["International Conference on Machine Learning", "ICML"],
    "ICLR":    ["International Conference on Learning Representations", "ICLR"],
}
# 우리 데이터에서 보강할 대상 venues
TARGET_VENUES = set(VENUE_SOURCES.keys())


def _norm(s: str) -> str:
    """소문자 + 알파뉴메릭만 남김 → 타이틀 비교용"""
    return re.sub(r'[^a-z0-9]', '', str(s).lower())


def reconstruct_abstract(inv_idx) -> str:
    """OpenAlex abstract_inverted_index → 문자열"""
    if not inv_idx:
        return ""
    pos_word = {}
    for word, positions in inv_idx.items():
        for p in positions:
            pos_word[p] = word
    return " ".join(pos_word[i] for i in sorted(pos_word))


def find_oa_source_id(venue_label: str, search_terms: list[str]) -> str | None:
    """OpenAlex source ID 검색"""
    for term in search_terms:
        url = f"{OA_BASE}/sources"
        params = {"filter": f"display_name.search:{term}", "per-page": 5}
        try:
            r = requests.get(url, params=params, headers=HEADERS, timeout=30)
            if r.status_code != 200:
                continue
            results = r.json().get("results", [])
            for src in results:
                name = src.get("display_name", "")
                # 이름이 충분히 유사하면 채택
                if _norm(term)[:8] in _norm(name) or _norm(name)[:8] in _norm(term):
                    print(f"  [{venue_label}] source: '{name}' → {src['id']}")
                    return src["id"]
        except Exception as e:
            print(f"  source lookup error: {e}")
        time.sleep(SLEEP)
    return None


def fetch_works_by_source_year(source_id: str, year: int) -> list[dict]:
    """특정 source + year의 전체 works 페이지네이션"""
    works = []
    cursor = "*"
    flt = f"primary_location.source.id:{source_id},publication_year:{year}"
    sel = "title,publication_year,cited_by_count,abstract_inverted_index"
    while True:
        params = {
            "filter": flt,
            "select": sel,
            "per-page": PER_PAGE,
            "cursor": cursor,
        }
        try:
            r = requests.get(f"{OA_BASE}/works", params=params,
                             headers=HEADERS, timeout=60)
            if r.status_code == 429:
                print("    OA rate limited, sleeping 30s...")
                time.sleep(30)
                continue
            if r.status_code != 200:
                break
            data = r.json()
            batch = data.get("results", [])
            works.extend(batch)
            next_cursor = data.get("meta", {}).get("next_cursor")
            if not next_cursor or not batch:
                break
            cursor = next_cursor
            time.sleep(SLEEP)
        except Exception as e:
            print(f"    fetch error: {e}")
            break
    return works


def main():
    with open(INPUT, encoding="utf-8") as f:
        papers = json.load(f)
    print(f"Loaded {len(papers)} papers")

    # 대상 papers: DOI 없고, abstract 없는 target venues
    target_papers = [
        (i, p) for i, p in enumerate(papers)
        if p.get("venue") in TARGET_VENUES
        and not (p.get("doi") or "").strip()
        and not p.get("abstract")
    ]
    print(f"Target (no-DOI, no-abstract) in NeurIPS/ICML/ICLR: {len(target_papers)}")

    # title norm → (idx, paper) 빠른 조회
    by_venue_year_title: dict[str, dict[int, dict[str, tuple]]] = defaultdict(lambda: defaultdict(dict))
    for idx, p in target_papers:
        v   = p["venue"]
        yr  = int(p.get("year") or 0)
        nt  = _norm(p.get("title") or "")
        if nt:
            by_venue_year_title[v][yr][nt] = (idx, p)

    total_updated = 0

    for our_venue, search_terms in VENUE_SOURCES.items():
        print(f"\n=== {our_venue} ===")
        source_id = find_oa_source_id(our_venue, search_terms)
        if not source_id:
            print(f"  Could not find OA source for {our_venue}, skipping")
            continue

        years_needed = sorted(by_venue_year_title[our_venue].keys())
        venue_updated = 0

        for yr in years_needed:
            if yr <= 0:
                continue
            title_map = by_venue_year_title[our_venue][yr]
            if not title_map:
                continue

            works = fetch_works_by_source_year(source_id, yr)
            matched = 0
            for w in works:
                nt = _norm(w.get("title") or "")
                if not nt:
                    continue
                # 정확 매칭 우선
                hit = title_map.get(nt)
                # 앞 40자 매칭 (축약 타이틀 처리)
                if not hit:
                    nt40 = nt[:40]
                    for k, v in title_map.items():
                        if k[:40] == nt40:
                            hit = v
                            break
                if not hit:
                    continue
                idx, paper = hit
                abstract = reconstruct_abstract(w.get("abstract_inverted_index"))
                cites    = w.get("cited_by_count") or 0
                changed  = False
                if abstract and not paper.get("abstract"):
                    papers[idx]["abstract"] = abstract
                    changed = True
                if cites and not paper.get("cited_by_count"):
                    papers[idx]["cited_by_count"] = cites
                    changed = True
                if changed:
                    matched += 1
                    venue_updated += 1
                    total_updated += 1

            if works:
                print(f"  {yr}: {len(works)} OA works → {matched} matched/updated")
            time.sleep(SLEEP)

        print(f"  {our_venue} total updated: {venue_updated}")

    with open(OUT_FILE, "w", encoding="utf-8") as f:
        json.dump(papers, f, ensure_ascii=False)

    with_abstract = sum(1 for p in papers if p.get("abstract"))
    with_cite     = sum(1 for p in papers if p.get("cited_by_count"))
    print(f"\n=== DONE ===")
    print(f"Updated this run: {total_updated}")
    print(f"Total with abstract: {with_abstract} ({100*with_abstract/len(papers):.1f}%)")
    print(f"Total with citations: {with_cite} ({100*with_cite/len(papers):.1f}%)")


if __name__ == "__main__":
    main()
