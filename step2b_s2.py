"""
Step 2b: Semantic Scholar로 OpenAlex 누락분 보강
- abstract 없는 논문을 제목+저자로 S2 API 검색
- DOI 있으면 DOI로 직접 조회 (더 정확)
- 초록·인용수 업데이트

실행: python step2b_s2.py
예상 소요: 1~3시간 (누락 건 수에 따라)
"""
import requests
import time
import json
import os
import re

INPUT = "all_enriched.json"
OUT_FILE = "all_enriched.json"

S2_BASE = "https://api.semanticscholar.org/graph/v1"
FIELDS = "title,abstract,citationCount,externalIds,year"
HEADERS = {"User-Agent": "cvml-paper-atlas/1.0 (gisbi.kim@gmail.com)"}


def _clean_title(t):
    return re.sub(r'[^a-z0-9 ]', ' ', str(t).lower()).strip()


def fetch_by_doi(doi):
    url = f"{S2_BASE}/paper/DOI:{doi}"
    try:
        r = requests.get(url, params={"fields": FIELDS}, headers=HEADERS, timeout=30)
        if r.status_code == 200:
            return r.json()
        elif r.status_code == 429:
            print("      S2 rate limited, waiting 120s...")
            time.sleep(120)
    except Exception as e:
        print(f"      S2 DOI error: {e}")
    return None


def fetch_by_title(title, year=None):
    params = {
        "query": title[:200],
        "fields": FIELDS,
        "limit": 3,
    }
    try:
        r = requests.get(f"{S2_BASE}/paper/search", params=params,
                         headers=HEADERS, timeout=30)
        if r.status_code == 200:
            results = r.json().get("data", [])
            for res in results:
                # fuzzy match: check title similarity and year
                res_title = _clean_title(res.get("title", ""))
                query_title = _clean_title(title)
                if res_title[:40] == query_title[:40]:
                    if year and res.get("year") and abs(int(res["year"]) - int(year)) > 1:
                        continue
                    return res
        elif r.status_code == 429:
            print("      S2 rate limited, waiting 120s...")
            time.sleep(120)
    except Exception as e:
        print(f"      S2 title search error: {e}")
    return None


def apply_s2(paper, s2_data):
    if not s2_data:
        return False
    changed = False
    if not paper.get("abstract") and s2_data.get("abstract"):
        paper["abstract"] = s2_data["abstract"]
        changed = True
    s2_cite = s2_data.get("citationCount")
    if s2_cite is not None:
        existing = paper.get("cited_by_count")
        if not existing or (isinstance(s2_cite, int) and s2_cite > int(existing or 0)):
            paper["cited_by_count"] = s2_cite
            changed = True
    if not paper.get("openalex_id"):
        eids = s2_data.get("externalIds", {}) or {}
        if eids.get("DOI"):
            paper["doi"] = paper.get("doi") or eids["DOI"].lower()
    return changed


def main():
    with open(INPUT, encoding="utf-8") as f:
        papers = json.load(f)
    print(f"Total papers: {len(papers)}")

    missing_abstract = [p for p in papers if not p.get("abstract")]
    print(f"Missing abstract: {len(missing_abstract)}")

    updated = 0
    doi_hits = 0
    title_hits = 0

    for i, p in enumerate(missing_abstract):
        doi = (p.get("doi") or "").strip().lower()
        title = (p.get("title") or "").strip()
        year = p.get("year")

        s2 = None
        if doi:
            s2 = fetch_by_doi(doi)
            if s2:
                doi_hits += 1
            time.sleep(0.5)

        if not s2 and title:
            s2 = fetch_by_title(title, year)
            if s2:
                title_hits += 1
            time.sleep(0.5)

        if apply_s2(p, s2):
            updated += 1

        if (i + 1) % 100 == 0:
            print(f"  [{i+1}/{len(missing_abstract)}] updated={updated} "
                  f"(doi={doi_hits} title={title_hits})")
            # save incrementally every 500
            if (i + 1) % 500 == 0:
                with open(OUT_FILE, "w", encoding="utf-8") as f:
                    json.dump(papers, f, ensure_ascii=False)
                print(f"    saved checkpoint")

    with open(OUT_FILE, "w", encoding="utf-8") as f:
        json.dump(papers, f, ensure_ascii=False)

    with_abstract = sum(1 for p in papers if p.get("abstract"))
    print(f"\n=== S2 MOP-UP DONE ===")
    print(f"Updated: {updated} (doi={doi_hits} title={title_hits})")
    print(f"With abstract now: {with_abstract} ({100*with_abstract/len(papers):.1f}%)")


if __name__ == "__main__":
    main()
