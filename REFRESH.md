# CV+ML Paper Atlas — 갱신 가이드

## 사이트
- **GitHub Pages**: https://gisbi-kim.github.io/cvmlpaper-atlas/
- **GitHub Repo**: https://github.com/gisbi-kim/cvmlpaper-atlas

## 대용량 데이터 파일 (GitHub Release v1.0.0)
- `all_dblp.json` (39MB) — DBLP 원본 수집 데이터
- `all_enriched.json` (81MB) — S2 enrichment 완료 데이터
- 다운로드: https://github.com/gisbi-kim/cvmlpaper-atlas/releases/tag/v1.0.0

## 파이프라인 (전체 재실행 순서)

```bash
# 1. DBLP 수집 (2~4시간)
python step1_dblp.py

# 2. Semantic Scholar 보강 (15~30분, Phase 2 포함 시 수시간)
python step2_s2.py --skip-phase2   # 빠른 버전 (DOI만)
# python step2_s2.py               # 전체 (DOI없는 구논문 제목검색 포함)

# 3. Excel 생성
python step3_excel.py

# 4. HTML 생성 (순서 상관없음)
python _make_all_html.py           # explorer.html
python _make_by_year_html.py       # by_year.html
python _make_coauthor_network.py   # coauthor_network.html  (pip install igraph 권장)
python _make_index_html.py         # index.html
python _make_xlsx_preview.py       # dataset_preview.html
python _split_by_venue.py          # by_venue/*.xlsx
```

## 최신 연도만 빠르게 갱신

```bash
python refresh_recent.py --years 2    # 최근 2년 재수집
python step2_s2.py --skip-phase2
python step3_excel.py
python _make_all_html.py
python _make_index_html.py
```

## GitHub 업데이트

```bash
git add *.html *.xlsx by_venue/
git commit -m "Update: YYYY-MM-DD citation refresh"
git push

# 대용량 데이터 새 버전 릴리즈
gh release create vX.Y --title "Data vX.Y — YYYY-MM-DD" all_dblp.json all_enriched.json
```

## 현재 데이터 현황 (2026-04-28)

| 항목 | 값 |
|------|-----|
| 전체 논문 | 111,939편 |
| 학회 | CVPR / ICCV / ECCV / NeurIPS / ICML / ICLR / 3DV |
| 연도 범위 | 1980 ~ 2025 |
| 초록 있음 | 32,998편 (29.4%) |
| 인용수 있음 | 52,255편 (46.6%) |
| 공저자 노드 | 14,342명 (7편+ 기준) |
| 공저자 엣지 | 49,106쌍 (3회+ 협업) |
