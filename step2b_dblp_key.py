"""Step 2b: DOI 없는 논문을 DBLP key로 S2 보강

S2 batch endpoint는 DOI 외에 DBLP:<key> 형식도 지원.
Phase 1(DOI)에서 놓친 NeurIPS/ICML/ICLR 논문 대부분을 3분 내 처리.

실행: python step2b_dblp_key.py
"""
import json
import time
import requests
from _checkpoint import load_checkpoint, save_checkpoint

INPUT    = "all_enriched.json"
OUT_FILE = "all_enriched.json"

S2_BASE    = "https://api.semanticscholar.org/graph/v1"
FIELDS     = "title,abstract,citationCount,externalIds,year"
BATCH_SIZE = 500
HEADERS    = {"User-Agent": "cvml-paper-atlas/1.0 (gisbi.kim@gmail.com)"}


def fetch_batch(ids):
    url = f"{S2_BASE}/paper/batch"
    for attempt in range(4):
        try:
            r = requests.post(url, json={"ids": ids},
                              params={"fields": FIELDS},
                              headers=HEADERS, timeout=60)
            if r.status_code == 200:
                return r.json()
            elif r.status_code == 429:
                wait = 60 * (attempt + 1)
                print(f"  rate limited, waiting {wait}s...")
                time.sleep(wait)
            else:
                print(f"  HTTP {r.status_code}, retry {attempt+1}")
                time.sleep(10)
        except Exception as e:
            print(f"  error: {e}, retry {attempt+1}")
            time.sleep(15 * (attempt + 1))
    return [None] * len(ids)


def main():
    with open(INPUT, encoding="utf-8") as f:
        papers = json.load(f)
    print(f"Total papers: {len(papers)}")

    # DOI 없고, abstract/citation도 없는 논문만 대상
    targets = [
        (i, p) for i, p in enumerate(papers)
        if not (p.get("doi") or "").strip()
        and not p.get("abstract")
        and p.get("dblp_key")
    ]
    print(f"No-DOI papers with dblp_key (no abstract yet): {len(targets)}")

    enriched = load_checkpoint()

    updated = 0
    for batch_start in range(0, len(targets), BATCH_SIZE):
        batch = targets[batch_start:batch_start + BATCH_SIZE]
        ids   = [f"DBLP:{p['dblp_key']}" for _, p in batch]
        results = fetch_batch(ids)

        found = 0
        for (idx, paper), s2 in zip(batch, results):
            if not s2:
                continue
            key = f"dblp:{paper['dblp_key']}"
            if s2.get("abstract") and not paper.get("abstract"):
                paper["abstract"] = s2["abstract"]
                updated += 1
            if s2.get("citationCount") and not paper.get("cited_by_count"):
                paper["cited_by_count"] = s2["citationCount"]
            enriched[key] = {
                "abstract": s2.get("abstract") or "",
                "cited_by_count": s2.get("citationCount") or 0,
                "s2_id": s2.get("paperId") or "",
            }
            found += 1

        done = batch_start + len(batch)
        print(f"  [{done}/{len(targets)}] found {found}/{len(batch)}, abstract hits so far: {updated}")

        if (batch_start // BATCH_SIZE) % 5 == 4:
            save_checkpoint(enriched)

        time.sleep(1.1)

    save_checkpoint(enriched)

    with open(OUT_FILE, "w", encoding="utf-8") as f:
        json.dump(papers, f, ensure_ascii=False)

    with_abstract = sum(1 for p in papers if p.get("abstract"))
    with_cite     = sum(1 for p in papers if p.get("cited_by_count"))
    print(f"\n=== DONE ===")
    print(f"Abstracts added this run: {updated}")
    print(f"Total with abstract: {with_abstract} ({100*with_abstract/len(papers):.1f}%)")
    print(f"Total with citations: {with_cite} ({100*with_cite/len(papers):.1f}%)")


if __name__ == "__main__":
    main()
