# PDF 파싱 검증 리포트 (DB 스키마 적합성)

## 테스트 일시: 2026-02-28 (초판) → 2026-03-01 (최종 업데이트)

> **목적**: DB 스키마 7개 테이블이 실제 PDF 데이터를 수용할 수 있는지 검증
> **파서 정확도 검증**은 별도 문서 참조: `parser-accuracy-report.md`

---

## 1. 테스트 대상

| # | 파일 | 소스 | 종목 | 섹터 | 페이지 |
|---|------|------|------|------|--------|
| 1 | pltr.pdf | CFRA | PLTR | IT/App Software | 9p |
| 2 | MSFT-CFRA.pdf | CFRA | MSFT | IT/Systems Software | 9p |
| 3 | JNJ-CFRA.pdf | CFRA | JNJ | Healthcare/Pharma | 9p |
| 4 | JPM-CFRA.pdf | CFRA | JPM | Financials/Banks | 9p |
| 5 | PG-CFRA.pdf | CFRA | PG | Consumer Staples | 9p |
| 6 | DHR.pdf | Zacks | DHR | Healthcare/Medical | 8p |
| 7 | AAPL-Zacks.pdf | Zacks | AAPL | IT/Computers | 9p |
| 8 | MSFT-Zacks.pdf | Zacks | MSFT | IT/Software | 10p |
| 9 | JPM-Zacks.pdf | Zacks | JPM | Financials/Banks | 10p |

---

## 2. 파싱 방법론

- **도구**: pdfplumber 0.11.9
- **테이블 추출**: `page.extract_tables()` — CFRA 8~13개/문서, Zacks 1개/문서
- **핵심 결론**: 두 소스 모두 **텍스트 기반 정규식 파싱**이 핵심. 테이블 추출은 보조적.

---

## 3. DB 스키마 적합성 검증 결과

### 3-1. stock_profiles — ✅ 적합 (수정 불필요)

- CFRA: ticker, exchange, GICS sector/sub-industry, investment_style 추출 가능
- Zacks: ticker, company_name, industry 추출 가능
- 기존 설계 컬럼으로 충분

### 3-2. stock_reports — ✅ 적합 (수정 불필요)

기존 설계에 trailing_pe, beta, yield 등은 이미 `stock_key_stats` 테이블에서 커버.
초판에서 "7개 컬럼 추가 권장"했으나, **stock_key_stats 테이블에 이미 해당 컬럼 존재** 확인 → 추가 불필요.

| 컬럼 | CFRA | Zacks | 상태 |
|------|------|-------|------|
| source | ✅ | ✅ | 적합 |
| report_date | ✅ | ✅ | 적합 |
| recommendation | ✅ STRONG BUY~SELL | ✅ Neutral/Outperform/Underperform | 적합 |
| stars_rating | ✅ « 개수 파싱 | N/A | 적합 |
| zacks_rank | N/A | ✅ `(1-5) 3-Hold` → rank=3 | 적합 |
| style_scores | N/A | ✅ jsonb | 적합 |
| target_price / current_price | ✅ | ✅ | 적합 |
| highlights | ✅ | N/A | 적합 |
| reasons_to_buy / reasons_to_sell | N/A | ✅ | 적합 |
| investment_rationale | ✅ | N/A | 적합 |
| business_summary | ✅ | ✅ | 적합 |
| sub_industry_outlook | ✅ | N/A | 적합 |
| last_earnings_summary | N/A | ✅ | 적합 |
| outlook | N/A | ✅ | 적합 |

### 3-3. stock_financials — ✅ 적합 (수정 불필요)

- CFRA: Revenue 6년치 × 5기간 = 30 레코드/파일 추출 성공
- `is_estimate` boolean — 설계 시점에 이미 포함되어 있었음 ✅
- `period_type` (quarterly/annual), `fiscal_year`, `fiscal_quarter` 구조 적합

### 3-4. stock_balance_sheets — ✅ 적합 (파서 P2)

- CFRA 3~4페이지에 Balance Sheet 텍스트 존재 확인
- DB 컬럼 구조는 적합, 파서 추출 로직은 P2에서 개발

### 3-5. stock_key_stats — ✅ 적합 (수정 불필요)

- CFRA: 8+ 지표 추출 (P/E, beta, market_cap, yield, 52wk range 등)
- Zacks: valuation multiples, forward P/E, PEG 등 추출 가능
- 기존 설계 컬럼으로 충분

### 3-6. stock_peers — ✅ 적합 (수정 불필요)

- Zacks: Industry Comparison + Top Peers에서 7~8개 피어 추출 성공
- CFRA: Peer Group 테이블 존재, P2에서 파서 개발

### 3-7. stock_analyst_notes — ✅ 적합 (수정 불필요)

- CFRA: "Analysis prepared by..." 패턴으로 시계열 추출 가능
- 기존 설계 컬럼 (published_at, analyst_name, stock_price_at_note) 적합

---

## 4. 발견된 이슈 및 해결 현황

| # | 이슈 | 발견 시점 | 해결 상태 |
|---|------|----------|----------|
| 1 | Zacks Rank 정규식 버그 (`rank=1, label=5`) | 초판 | ✅ 수정 완료 (`cfra_parser.py`) |
| 2 | CFRA symbol 파싱 (exchange 추출 → ticker 추출) | 초판 | ✅ 수정 완료 |
| 3 | CFRA sub_industry 텍스트 넘침 (JPM) | 초판 | ✅ 수정 완료 |
| 4 | stock_reports에 7개 컬럼 추가 권장 | 초판 | ❌ 불필요 — stock_key_stats에서 이미 커버 |
| 5 | stock_financials에 is_estimate 추가 권장 | 초판 | ❌ 불필요 — 설계 시점에 이미 포함 |

---

## 5. 최종 결론

1. **DB 스키마 7개 테이블 — 수정 없이 적합** (초판에서 권장했던 컬럼 추가는 재검토 결과 불필요)
2. **pdfplumber 테이블 추출은 보조적** — 핵심은 텍스트 정규식 파싱
3. **CFRA와 Zacks의 구조가 상당히 다름** — 소스별 전용 파서 필수
4. **9개 PDF × 4개 섹터로 검증** — 추가 섹터 (Energy, Utilities 등)는 필요시 별도 수집
5. **파서 개발 완료 후 정확도 100% 달성** → `parser-accuracy-report.md` 참조
