# Stock Report Hub — Claude Code 프로젝트 가이드

## 프로젝트 개요

주식 리서치 리포트를 자동 수집·파싱·저장하여 **주식 정보 Hub**로 제공하는 시스템.
Fidelity Research 포털(CFRA, Zacks 등)에서 PDF 리포트를 가져와 구조화된 데이터로 변환하고,
이를 기반으로 콘텐츠 자동 생성, 종목 비교, 투자 인사이트를 제공한다.

### 핵심 가치

- **수집**: 멀티소스 리서치 리포트 자동 다운로드 (CFRA, Zacks, Argus, S&P 등)
- **정규화**: 소스마다 다른 포맷을 통합 DB 스키마로 정규화
- **활용**: 블로그, 뉴스레터, 분석글 자동 생성의 데이터 소스
- **비교**: 멀티소스 크로스체크 (CFRA vs Zacks 동일 종목 비교)

### 상위 프로젝트

Elixir SaaS MVP의 `market/` 모듈 하위에 통합 예정.
상위 프로젝트 가이드는 `~/Downloads/CLAUDE.md` 참조.

---

## 기술 스택

| 레이어 | 기술 | 용도 |
|--------|------|------|
| 데이터 수집 (Phase 1) | Chrome MCP (Claude Desktop) | 포털 브라우저 자동화 |
| 데이터 수집 (Phase 3) | Python Playwright (headless) | 서버 자동 수집 |
| PDF 파싱 | Python pdfplumber + tabula-py | 텍스트/테이블 추출 |
| DB | PostgreSQL + Ecto | 정규화 저장 |
| 백엔드 | Elixir/Phoenix | 컨텍스트, API, Oban |
| 스케줄링 | Oban Cron | 정기 수집/파싱 |

---

## 데이터 소스

| 소스 | 포털 | 레이팅 체계 | 리포트 형식 |
|------|------|-----------|-----------|
| CFRA | Fidelity Research | STARS 1~5 + Buy/Hold/Sell | 9페이지, 8년 재무제표, 리서치노트 시계열 |
| Zacks | Fidelity Research | Rank 1~5 + Style Scores(VGM) | 8페이지, 산업비교 40개 지표, Buy/Sell 근거 분리 |
| Argus | Fidelity Research | (확장 예정) | Company Report |
| S&P Capital IQ | Fidelity Research | (확장 예정) | Company Report |

### Fidelity Research 포털 접근

- URL: `https://public.fidelityresearch.com/nationalfinancialnet`
- 로그인: 불필요 (Public)
- 구조: iframe 기반 → 직접 접근 URL: `/NationalFinancialNet/MurielSiebert/PageContent`
- 검색 플로우: Firm 선택 → 티커 입력 → autocomplete 선택 → Search → 결과 클릭 → PDF

---

## DB 스키마 (7 테이블)

상세 설계: `stock-report-db-design.md` 참조.

| 테이블 | 설명 | 핵심 필드 |
|--------|------|----------|
| `stock_profiles` | 종목 기본 정보 | ticker, company_name, exchange, sector, segments |
| `stock_reports` | 리포트 메타 (1 리포트 = 1 row) | source, recommendation, target_price, highlights |
| `stock_financials` | 분기/연간 재무 데이터 | revenue, eps, margins, is_estimate |
| `stock_balance_sheets` | 대차대조표 | assets, liabilities, ratios |
| `stock_key_stats` | 핵심 통계 스냅샷 | PE, PEG, beta, market_cap, valuation_multiples |
| `stock_peers` | 피어 그룹 비교 | peer_ticker, rank, detailed_comparison |
| `stock_analyst_notes` | 애널리스트 리서치 노트 | published_at, action, target_price, content |

### 관계

```
stock_profiles (1) ──< (N) stock_reports
stock_profiles (1) ──< (N) stock_financials
stock_profiles (1) ──< (N) stock_balance_sheets
stock_profiles (1) ──< (N) stock_analyst_notes
stock_reports  (1) ──< (N) stock_peers
stock_reports  (1) ──< (1) stock_key_stats
```

### 유니크 제약

- `stock_profiles`: `(ticker, exchange)`
- `stock_reports`: `(stock_profile_id, source, report_date)`
- `stock_financials`: `(stock_profile_id, fiscal_year, fiscal_quarter, is_estimate)`

---

## 모듈 구조

```
lib/app_name/market/
├── stock_profile.ex           # Ecto 스키마: 종목 기본정보
├── stock_report.ex            # Ecto 스키마: 리포트 메타
├── stock_financial.ex         # Ecto 스키마: 재무 데이터
├── stock_balance_sheet.ex     # Ecto 스키마: 대차대조표
├── stock_key_stat.ex          # Ecto 스키마: 핵심 통계
├── stock_peer.ex              # Ecto 스키마: 피어 비교
├── stock_analyst_note.ex      # Ecto 스키마: 애널리스트 노트
├── stock_reports.ex           # 컨텍스트 (비즈니스 로직, 조회, 콘텐츠 변환)
├── stock_report_fetcher.ex    # 데이터 수집 오케스트레이터
├── stock_report_parser.ex     # PDF → 구조화 데이터 (소스별 위임)
├── parsers/
│   ├── cfra_parser.ex         # CFRA 포맷 전용 파서
│   └── zacks_parser.ex        # Zacks 포맷 전용 파서
└── workers/
    ├── report_fetch_worker.ex     # Oban: PDF 다운로드
    ├── report_parse_worker.ex     # Oban: PDF 파싱 + DB 저장
    └── report_schedule_worker.ex  # Oban: 정기 수집 (매일 7AM)
```

---

## 자동화 파이프라인

상세 설계: `stock-report-automation.md` 참조.

```
티커 목록 → 포털 검색 → PDF 다운로드 → 텍스트/테이블 추출 → 소스별 파서 → DB UPSERT
                                                                    ↓
                                                        콘텐츠 생성 파이프라인
                                                        (to_content_vars → Template → Post → Distribution)
```

### Phase별 구현 계획

| Phase | 방안 | 핵심 작업 | 소요 기간 |
|-------|------|----------|----------|
| 1 MVP | A (Chrome MCP) | 파서 개발 + 정확도 검증 | 1~2주 |
| 2 반자동 | A + DB 연결 | DB 저장 + 콘텐츠 파이프라인 | 1~2주 |
| 3 완전자동 | C (Playwright) | headless 스크립트 + Oban 스케줄러 | 2~3주 |
| 4 확장 | C → B 검토 | 추가 소스 파서 + UI + HTTP 전환 | 지속적 |

---

## 핵심 컨텍스트 함수

```elixir
# 콘텐츠 생성용 통합 조회
StockReports.get_report_bundle(ticker)
# → %{profile, report, financials, key_stats, peers, notes}

# 템플릿 변수 맵 생성
StockReports.to_content_vars(ticker)
# → %{company_name, ticker, recommendation, target_price, upside_pct, ...}

# 최신 리포트
StockReports.get_latest_report(ticker, source: "CFRA")

# 재무 데이터
StockReports.list_financials(ticker, years: 5, type: :annual)

# 피어 비교
StockReports.list_peers(report_id)
```

---

## 콘텐츠 활용 시나리오

| 콘텐츠 유형 | 참조 데이터 | 출력 |
|------------|-----------|------|
| 종목 분석 블로그 | profile + report + financials + peers | ContentPost → 블로그 |
| 실적 속보 | financials(분기) + analyst_notes | ContentPost → SNS |
| 비교 분석글 | 복수 종목 key_stats + peers 조인 | ContentPost → 뉴스레터 |
| 투자 인사이트 | report.rationale + sub_industry_outlook | ContentPost → 프리미엄 콘텐츠 |
| 종목 카드 | profile + report + key_stats | API → 프론트엔드 위젯 |

---

## 파일 구조

```
Stock_report_automation/
├── CLAUDE.md                      ← 이 파일 (Claude Code 프로젝트 가이드)
├── README.md                      ← 프로젝트 개요 + 진행 상황
├── bkit.config.json               ← ★ bkit (Vibecoding Kit) PDCA 설정
│
├── docs/                          ← bkit PDCA 문서 디렉토리
│   ├── 01-plan/features/          ← Plan 문서
│   ├── 02-design/features/        ← Design 명세
│   ├── 03-analysis/features/      ← Gap Analysis
│   ├── 04-report/features/        ← 완료 리포트
│   └── archive/                   ← 아카이브
│
├── stock-report-db-design.md      ← DB 스키마 상세 설계 (테이블, 인덱스, 매핑 예시)
├── stock-report-automation.md     ← 자동화 아키텍처 상세 설계 (포털 분석, 코드 설계)
├── parsing-validation-report.md   ← 이전 세션 파싱 검증 결과 (DB 스키마 적합성)
├── parser-accuracy-report.md      ← 파서 정확도 최종 리포트 (100% 달성)
│
├── cfra_parser.py                 ← ★ CFRA 파서 (Python, pdfplumber 기반)
├── zacks_parser.py                ← ★ Zacks 파서 (Python, pdfplumber 기반)
├── validate_all.py                ← 9개 PDF × 170항목 검증 스크립트
│
├── pltr.pdf                       ← CFRA 샘플 (Palantir, IT/App Software)
├── MSFT-CFRA.pdf                  ← CFRA (Microsoft, IT/Systems Software)
├── JNJ-CFRA.pdf                   ← CFRA (J&J, Healthcare/Pharma)
├── JPM-CFRA.pdf                   ← CFRA (JPMorgan, Financials/Banks)
├── PG-CFRA.pdf                    ← CFRA (P&G, Consumer Staples)
├── DHR.pdf                        ← Zacks 샘플 (Danaher, Healthcare/Medical)
├── AAPL-Zacks.pdf                 ← Zacks (Apple, IT/Computers)
├── MSFT-Zacks.pdf                 ← Zacks (Microsoft, IT/Software)
└── JPM-Zacks.pdf                  ← Zacks (JPMorgan, Financials/Banks)
```

---

## Python 파서 모듈 (검증 완료, Elixir 연동 대기)

### 의존성

- Python 3.10+, pdfplumber 0.11.9
- 설치: `pip install pdfplumber`

### cfra_parser.py — CFRA 리포트 파서

```python
from cfra_parser import parse_cfra
result = parse_cfra("pltr.pdf")
# result = {
#   "profile": {ticker, exchange, company_name, gics_sector, gics_sub_industry, investment_style},
#   "report": {source, report_date, recommendation, stars_rating, target_price, current_price,
#              analyst_name, risk_assessment, fair_value, volatility, technical_eval, insider_activity,
#              highlights, investment_rationale, business_summary, sub_industry_outlook},
#   "key_stats": {trailing_12m_pe, beta, market_cap_b, shares_outstanding_m, dividend_yield_pct,
#                 week_52_high, week_52_low, oper_eps_current_e, oper_eps_next_e, ...},
#   "financials": [{fiscal_year, fiscal_quarter, period_type, is_estimate, revenue, eps}, ...],
#   "analyst_notes": [{published_at, analyst_name, stock_price_at_note}, ...],
#   "errors": [], "warnings": []
# }
```

- 추출 범위: Revenue 6년치 × 5기간 = 30 레코드/파일, EPS 별도 merge 가능
- 텍스트 섹션 4종: highlights, investment_rationale, business_summary, sub_industry_outlook
- 멀티컬럼 레이아웃 대응 (Page 1 interleaved columns)

### zacks_parser.py — Zacks 리포트 파서

```python
from zacks_parser import parse_zacks
result = parse_zacks("DHR.pdf")
# result = {
#   "profile": {ticker, company_name, industry},
#   "report": {source, report_date, recommendation, prior_recommendation, zacks_rank,
#              zacks_rank_label, style_scores, target_price, current_price, industry_rank,
#              reasons_to_buy, reasons_to_sell, last_earnings_summary, outlook, business_summary},
#   "key_stats": {pe_forward_12m, peg_ratio, price_to_book, ev_ebitda, debt_equity, ...},
#   "financials": [],  # P2 예정
#   "peers": [{peer_ticker, peer_name, recommendation, rank}, ...],
#   "errors": [], "warnings": []
# }
```

- 텍스트 섹션 4종: reasons_to_buy, reasons_to_sell, last_earnings_summary, outlook
- Peers 7~8개 추출 (Industry Analysis + Top Peers)
- Style Scores: VGM, Value, Growth, Momentum 분리 추출

### 검증 결과 (validate_all.py)

- 9개 PDF × 170개 검증 항목 → **정확도 100%**
- CFRA 5종목 (PLTR, MSFT, JNJ, JPM, PG) × 4개 섹터 검증
- Zacks 4종목 (DHR, AAPL, MSFT, JPM) × 3개 섹터 검증
- 상세: `parser-accuracy-report.md` 참조

### DB 테이블 매핑 커버리지

| DB 테이블 | CFRA 파서 | Zacks 파서 | 상태 |
|-----------|----------|-----------|------|
| stock_profiles | ✅ ticker, exchange, GICS | ✅ ticker, company, industry | 완료 |
| stock_reports | ✅ 전체 텍스트 섹션 | ✅ 전체 텍스트 섹션 | 완료 |
| stock_financials | ✅ Revenue 30레코드 | ⏳ P2 | CFRA 완료 |
| stock_key_stats | ✅ 8+ 지표 | ⏳ 부분 | CFRA 완료 |
| stock_balance_sheets | ⏳ P2 | N/A | 예정 |
| stock_peers | N/A | ✅ 7~8개 | 완료 |
| stock_analyst_notes | ✅ 기본 | N/A | 상세화 P2 |

### Elixir 연동 방식 (추천: Python Port)

```elixir
# priv/python/parse_report.py — CLI 래퍼
# Usage: python3 parse_report.py --source cfra --file pltr.pdf
# Output: JSON to stdout

# Elixir에서 호출:
{output, 0} = System.cmd("python3", [
  "priv/python/parse_report.py",
  "--source", source,
  "--file", pdf_path
])
Jason.decode!(output)
```

---

## bkit (Vibecoding Kit) — PDCA 개발 워크플로우

### 개요

bkit은 Claude Code 플러그인으로, **PDCA (Plan-Do-Check-Act)** 방법론 기반 체계적 개발을 지원한다.
Context Engineering을 통해 AI 추론의 품질을 극대화하며, 9단계 개발 파이프라인 + 16개 AI 에이전트를 제공한다.

- **버전**: 1.5.8
- **리포지토리**: https://github.com/popup-studio-ai/bkit-claude-code
- **라이선스**: Apache 2.0

### 설치

```bash
# Claude Code에서 실행
/plugin marketplace add popup-studio-ai/bkit-claude-code
/plugin install bkit

# 요구사항: Claude Code v2.1.63+, Node.js v18+
```

### PDCA 명령어

```bash
/pdca plan {feature}      # Plan 문서 생성 (전략, 대안 탐색)
/pdca design {feature}    # Design 명세 생성
/pdca do {feature}        # 구현 가이드
/pdca analyze {feature}   # Gap Analysis (계획 vs 실제)
/pdca iterate {feature}   # 자동 수정 (최대 5회, 90% 임계값)
/pdca report {feature}    # 완료 리포트 생성
/pdca status              # 현재 PDCA 상태 확인
/pdca next                # 다음 단계 안내
```

### PDCA 문서 구조

```
docs/
├── 01-plan/features/          # Plan 문서
│   └── {feature}.plan.md
├── 02-design/features/        # Design 명세
│   └── {feature}.design.md
├── 03-analysis/features/      # Gap Analysis 결과
│   └── {feature}.analysis.md
├── 04-report/features/        # 완료 리포트
│   └── {feature}.report.md
└── archive/{date}/{feature}/  # 아카이브
```

### 프로젝트 설정

`bkit.config.json`에서 프로젝트별 커스터마이즈:
- `fileDetection.sourceExtensions`: `.ex`, `.exs`, `.heex`, `.py`, `.js`
- `fileDetection.excludePatterns`: `_build`, `deps`, `__pycache__` 등
- `pdca.matchRateThreshold`: 90 (Check 단계 통과 기준)
- `pdca.maxIterations`: 5 (자동 수정 최대 횟수)

### 이 프로젝트에서의 활용 예시

```bash
# Phase 2: Elixir 연동 개발
/pdca plan elixir-python-port      # Python Port 연동 전략
/pdca design ecto-migrations       # DB 마이그레이션 설계
/pdca do oban-workers              # Oban Worker 구현
/pdca analyze parser-integration   # 파서 통합 검증
/pdca report phase2-completion     # Phase 2 완료 리포트
```

### CTO-Led Agent Teams (선택사항)

```bash
export CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1
/pdca team {feature}               # 멀티 에이전트 병렬 PDCA
```

팀 구성: CTO Lead (opus), Frontend Architect (sonnet), Product Manager (sonnet), QA Strategist (sonnet), Security Architect (opus)

---

## 코드 생성 시 규칙

1. **레퍼런스 먼저**: 코드 작성 전 반드시 `stock-report-db-design.md`와 `stock-report-automation.md`를 읽고 시작
2. **파서 참조**: `cfra_parser.py`, `zacks_parser.py`의 출력 구조를 기준으로 Elixir 스키마/컨텍스트 코드 생성
3. **소스별 파서 분리**: CFRA/Zacks 파서는 별도 모듈, 공통 인터페이스(`parse/2`)로 통일
4. **UPSERT 패턴**: 동일 종목+소스+날짜 리포트는 덮어쓰기 (유니크 제약 기반)
5. **멀티테넌시**: 모든 테이블에 `organization_id` FK 포함
6. **Oban으로 부작용 분리**: PDF 다운로드, 파싱, 알림은 반드시 Oban 워커
7. **Python 의존성 격리**: pdfplumber/playwright는 `System.cmd`로 호출, venv 사용 권장
8. **환경변수**: API 키, 다운로드 경로 등은 `runtime.exs`에서 읽음
9. **PDF 샘플 참조**: 파서 개발 시 9개 PDF 파일을 실제 테스트 데이터로 활용
10. **검증 스크립트**: `validate_all.py`로 파서 수정 후 회귀 테스트 실행

---

## 현재 상태

- ✅ Fidelity Research 포털 구조 분석 완료
- ✅ Chrome MCP 검색 플로우 테스트 완료
- ✅ DB 스키마 7테이블 설계 완료 (CFRA + Zacks 호환)
- ✅ 자동화 아키텍처 3방안 설계 완료
- ✅ 9개 PDF 수집 완료 (CFRA 5 + Zacks 4, 4개 섹터)
- ✅ Python 파서 2종 개발 완료 (cfra_parser.py, zacks_parser.py)
- ✅ 정확도 검증 100% 달성 (170개 항목)
- ⬜ **다음 단계**: Elixir Python Port 연동 + Oban Worker + DB 마이그레이션

### 다음 단계 상세 (Claude Code 작업)

1. `priv/python/` 디렉토리에 파서 CLI 래퍼 생성 (parse_report.py)
2. Ecto 마이그레이션 7개 테이블 생성
3. Ecto 스키마 7개 모듈 구현
4. `stock_reports.ex` 컨텍스트 모듈 — UPSERT 로직
5. `report_parse_worker.ex` Oban 워커 — Python 파서 호출 + DB 저장
6. P2: EPS merge, Balance Sheet 파싱, Zacks Financials 추가
