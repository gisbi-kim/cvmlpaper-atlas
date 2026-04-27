"""
Step 2 (S2 version): Semantic Scholar API로 초록/인용수 보강
- /paper/batch endpoint: 500개 DOI 한 번에 처리 (OpenAlex 50개 대비 10x)
- 제목 검색으로 DOI 없는 논문도 커버
- 체크포인트로 중단 재개 가능

실행: python step2_s2.py
예상 소요: 15~30분 (112k편 기준)
"""
import requests
import time
import json
import os

from _checkpoint import load_checkpoint, save_checkpoint

INPUT = "all_dblp.json"
OUT_FILE = "all_enriched.json"

S2_BASE = "https://api.semanticscholar.org/graph/v1"
FIELDS = "title,abstract,citationCount,externalIds,year"
BATCH_SIZE = 500
HEADERS = {"User-Agent": "cvml-paper-atlas/1.0 (gisbi.kim@gmail.com)"}


def fetch_batch_by_doi(dois):
    """S2 batch endpoint: 최대 500개 DOI 한 번에."""
    ids = [f"DOI:{d}" for d in dois]
    url = f"{S2_BASE}/paper/batch"
    params = {"fields": FIELDS}
    for attempt in range(4):
        try:
            r = requests.post(url, json={"ids": ids}, params=params,
                              headers=HEADERS, timeout=60)
            if r.status_code == 200:
                return r.json()  # list, same order as ids (null if not found)
            elif r.status_code == 429:
                wait = 60 * (attempt + 1)
                print(f"    S2 rate limited, waiting {wait}s...")
                time.sleep(wait)
            elif r.status_code == 400:
                print(f"    S2 400 bad request on batch, skipping")
                return [None] * len(dois)
            else:
                print(f"    S2 HTTP {r.status_code}, retry {attempt+1}")
                time.sleep(10)
        except Exception as e:
            wait = 15 * (attempt + 1)
            print(f"    S2 error: {e}, retry {attempt+1}, waiting {wait}s")
            time.sleep(wait)
    return [None] * len(dois)


def fetch_by_title(title, year=None):
    """제목으로 S2 검색 — DOI 없는 논문용."""
    params = {"query": title[:200], "fields": FIELDS, "limit": 3}
    for attempt in range(3):
        try:
            r = requests.get(f"{S2_BASE}/paper/search", params=params,
                             headers=HEADERS, timeout=30)
            if r.status_code == 200:
                for res in r.json().get("data", []):
                    # 제목 앞부분 매칭 + 연도 ±1 허용
                    def _norm(s):
                        return ''.join(c for c in str(s).lower() if c.isalnum())
                    if _norm(res.get("title", ""))[:30] == _norm(title)[:30]:
                        if year and res.get("year") and abs(int(res["year"]) - int(year)) > 1:
                            continue
                        return res
                return None
            elif r.status_code == 429:
                wait = 60 * (attempt + 1)
                print(f"    S2 title rate limited, waiting {wait}s...")
                time.sleep(wait)
            else:
                time.sleep(5)
        except Exception as e:
            print(f"    S2 title error: {e}")
            time.sleep(5)
    return None


def extract_s2(s2_data):
    if not s2_data:
        return {}
    return {
        "abstract": s2_data.get("abstract") or "",
        "cited_by_count": s2_data.get("citationCount") or 0,
        "concepts": "",
        "openalex_id": "",
        "s2_id": s2_data.get("paperId") or "",
    }


def main(skip_phase2=False):
    with open(INPUT, encoding="utf-8") as f:
        papers = json.load(f)
    print(f"Total papers: {len(papers)}")

    doi_to_idx = {}
    nodoi_idxs = []
    for i, p in enumerate(papers):
        doi = (p.get("doi") or "").strip().lower()
        if doi.startswith("https://doi.org/"):
            doi = doi[len("https://doi.org/"):]
        if doi:
            doi_to_idx[doi] = i
        else:
            nodoi_idxs.append(i)

    print(f"With DOI: {len(doi_to_idx)}  |  No DOI: {len(nodoi_idxs)}")

    enriched = load_checkpoint()
    processed_dois = set(enriched.keys())
    print(f"Checkpoint: {len(processed_dois)} already processed")

    # ── Phase 1: DOI batch lookup ──
    all_dois = [d for d in doi_to_idx if d not in processed_dois]
    print(f"Phase 1: {len(all_dois)} DOIs to fetch via S2 batch")

    for i in range(0, len(all_dois), BATCH_SIZE):
        batch_dois = all_dois[i:i + BATCH_SIZE]
        results = fetch_batch_by_doi(batch_dois)

        found = 0
        for doi, s2 in zip(batch_dois, results):
            enriched[doi] = extract_s2(s2)
            if s2:
                found += 1

        done = i + len(batch_dois)
        print(f"  [{done}/{len(all_dois)}] found {found}/{len(batch_dois)}")

        batch_num = i // BATCH_SIZE
        if batch_num % 5 == 4:
            save_checkpoint(enriched)
            print(f"    checkpoint saved ({len(enriched)} entries)")

        time.sleep(1.1)  # S2 polite rate: ~1 req/s

    save_checkpoint(enriched)
    print(f"Phase 1 done. Checkpoint: {len(enriched)}")

    # ── Phase 2: title search for no-DOI papers ──
    if skip_phase2:
        print("\nPhase 2: skipped (--skip-phase2)")
    else:
        nodoi_missing = [i for i in nodoi_idxs
                         if not papers[i].get("abstract")]
        print(f"\nPhase 2: title search for {len(nodoi_missing)} no-DOI papers")

        title_updated = 0
        for n, idx in enumerate(nodoi_missing):
            p = papers[idx]
            title = (p.get("title") or "").strip()
            if not title or len(title) < 10:
                continue
            s2 = fetch_by_title(title, p.get("year"))
            if s2 and s2.get("abstract"):
                p["abstract"] = s2["abstract"]
                if s2.get("citationCount"):
                    p["cited_by_count"] = s2["citationCount"]
                title_updated += 1
            if (n + 1) % 200 == 0:
                print(f"  [{n+1}/{len(nodoi_missing)}] title hits so far: {title_updated}")
            time.sleep(0.5)

        print(f"Phase 2 done. Title hits: {title_updated}")

    # ── Merge enrichment into papers ──
    for p in papers:
        doi = (p.get("doi") or "").strip().lower()
        if doi.startswith("https://doi.org/"):
            doi = doi[len("https://doi.org/"):]
        e = enriched.get(doi, {})
        if e.get("abstract") and not p.get("abstract"):
            p["abstract"] = e["abstract"]
        if e.get("cited_by_count") and not p.get("cited_by_count"):
            p["cited_by_count"] = e["cited_by_count"]
        if e.get("s2_id") and not p.get("openalex_id"):
            p["openalex_id"] = e["s2_id"]

    with open(OUT_FILE, "w", encoding="utf-8") as f:
        json.dump(papers, f, ensure_ascii=False)

    with_abstract = sum(1 for p in papers if p.get("abstract"))
    with_cite = sum(1 for p in papers if p.get("cited_by_count"))
    print(f"\n=== DONE ===")
    print(f"Total: {len(papers)}")
    print(f"With abstract: {with_abstract} ({100*with_abstract/len(papers):.1f}%)")
    print(f"With citations: {with_cite} ({100*with_cite/len(papers):.1f}%)")


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--skip-phase2", action="store_true")
    args = ap.parse_args()
    main(skip_phase2=args.skip_phase2)
