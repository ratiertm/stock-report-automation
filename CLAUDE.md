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
| 데이터 수집 (Phase 3) | Python Playwright (headless) | 서버 자동 수집 (예정) |
| PDF 파싱 | Python pdfplumber | 텍스트/테이블 추출 |
| ORM | SQLAlchemy 2.0 + Alembic | 모델 정의, 마이그레이션 |
| DB | PostgreSQL | 정규화 저장 (7 테이블) |
| 설정 | pydantic-settings | .env 기반 환경 설정 |
| 상위 프로젝트 (예정) | Elixir/Phoenix | 컨텍스트, API, Oban 통합 |

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

## 모듈 구조 (Python)

```
app/
├── __init__.py
├── main.py                        # ★ FastAPI 앱 엔트리포인트
├── config.py                      # pydantic-settings (DATABASE_URL, PDF_STORAGE_PATH 등)
├── database.py                    # SQLAlchemy engine, SessionLocal, Base
├── models/                        # SQLAlchemy ORM 모델 (10 테이블)
│   ├── __init__.py                # 전체 모델 re-export
│   ├── stock_profile.py           # 종목 기본정보
│   ├── stock_report.py            # 리포트 메타 (zacks_rank_label 포함)
│   ├── stock_financial.py         # 분기/연간 재무 데이터
│   ├── stock_balance_sheet.py     # 대차대조표
│   ├── stock_key_stat.py          # 핵심 통계 (quality_ranking, oper_eps 포함)
│   ├── stock_peer.py              # 피어 그룹 비교
│   ├── stock_analyst_note.py      # 애널리스트 리서치 노트
│   ├── watchlist.py               # Watchlist + WatchlistItem
│   └── alert.py                   # Alert (변경 알림 로그)
├── schemas/
│   └── stock.py                   # ★ Pydantic 응답 스키마
├── api/
│   ├── stocks.py                  # ★ REST API 라우터 (7개 엔드포인트)
│   ├── watchlist.py               # ★ Watchlist + Fetch API (6개 엔드포인트)
│   └── content.py                 # ★ Content + Alert API (5개 엔드포인트)
├── crud/
│   ├── stock.py                   # UPSERT 로직 (upsert_profile, upsert_report, ...)
│   └── watchlist.py               # Watchlist CRUD (add/remove/list/fetch_targets)
├── parsers/
│   └── __init__.py                # CFRAParser, ZacksParser re-export
└── services/
    ├── parser_service.py          # parse_and_store(): PDF 파싱 → DB 저장 오케스트레이터
    ├── fetcher_service.py         # Playwright PDF 다운로드 (fetch_pdf, batch_fetch)
    ├── scheduler.py               # APScheduler 정기 수집 (daily_fetch_job)
    ├── content_service.py         # 콘텐츠 변수 맵 + 변경 감지 (to_content_vars, detect_changes)
    └── alert_service.py           # 알림 생성 + 이메일 발송 (check_and_alert, send_email_alerts)

alembic/
├── env.py
└── versions/
    ├── b7c84913beb1_initial_7_tables.py
    └── 75ef54aaed55_add_missing_parser_fields.py
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

## 핵심 CRUD 함수 (app/crud/stock.py)

```python
# UPSERT 함수 — 유니크 제약 기반 INSERT ON CONFLICT UPDATE
upsert_profile(session, data)          # (ticker, exchange) 유니크
upsert_report(session, profile_id, data, pdf_path)  # (profile_id, source, report_date) 유니크
upsert_financial(session, profile_id, data)  # (profile_id, year, quarter, is_estimate) 유니크
upsert_key_stats(session, report_id, data)   # (stock_report_id) 유니크
save_peers(session, report_id, peers_list)   # DELETE + INSERT
save_analyst_notes(session, profile_id, source, notes)  # INSERT

# 조회 헬퍼
get_profile_by_ticker(session, ticker)
get_latest_reports(session, profile_id)
get_financials(session, profile_id)
get_all_profiles(session)
```

### 파싱 → DB 저장 (app/services/parser_service.py)

```python
from app.database import SessionLocal
from app.services.parser_service import parse_and_store

session = SessionLocal()
result = parse_and_store("pltr.pdf", "CFRA", session)
# → {"status": "success", "ticker": "PLTR", "source": "CFRA",
#    "records_saved": {"profile": 1, "report": 1, "financials": 30, ...}}
session.close()
```

### REST API (19개 엔드포인트)

```
서버 실행: uvicorn app.main:app --port 8000
Swagger UI: http://localhost:8000/docs

# Stocks API (app/api/stocks.py)
GET  /api/stocks                      # 전체 종목 목록
GET  /api/stocks/{ticker}             # 프로필 + 최신 리포트
GET  /api/stocks/{ticker}/financials  # 재무 데이터 (?period=annual|quarterly|all)
GET  /api/stocks/{ticker}/compare     # CFRA vs Zacks 비교
GET  /api/stocks/{ticker}/bundle      # 콘텐츠 변수 맵 (upside_pct 포함)
GET  /api/stocks/{ticker}/notes       # 애널리스트 노트
POST /api/parse                       # PDF 업로드 → 파싱 → DB (multipart: file + source)

# Watchlist + Fetch API (app/api/watchlist.py)
GET  /api/watchlist                   # 워치리스트 조회
POST /api/watchlist/add               # 티커 추가 (body: ticker, sources)
POST /api/watchlist/remove            # 티커 제거
POST /api/fetch/{ticker}              # 단일 PDF 다운로드 (Playwright)
POST /api/fetch-watchlist             # 워치리스트 일괄 다운로드 + 파싱
POST /api/parse-local/{ticker}        # 로컬 PDF 파싱 (?source=CFRA)

# Content + Alert API (app/api/content.py)
GET  /api/content/{ticker}            # 블로그/뉴스레터용 콘텐츠 변수 맵 (30+ 필드)
GET  /api/diff/{ticker}               # 등급/목표가 변경 감지 (latest vs previous)
POST /api/alerts/check                # 워치리스트 변경 감지 → 알림 생성
GET  /api/alerts                      # 미발송 알림 목록
POST /api/alerts/send                 # 이메일 알림 발송

GET  /health                          # 헬스체크
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
stock-report-automation/
├── CLAUDE.md                          ← 이 파일 (Claude Code 프로젝트 가이드)
├── README.md                          ← 프로젝트 개요 + 진행 상황
├── PRD-stock-report-hub.md            ← 제품 요구사항 정의서
├── ROADMAP.md                         ← 로드맵
├── stock-report-db-design.md          ← DB 스키마 상세 설계
├── stock-report-automation.md         ← 자동화 아키텍처 설계
│
├── app/                               ← ★ Python 애플리케이션 (FastAPI)
│   ├── main.py                        ← FastAPI 엔트리포인트
│   ├── config.py                      ← pydantic-settings (.env 기반)
│   ├── database.py                    ← SQLAlchemy engine, SessionLocal, Base
│   ├── models/                        ← ORM 모델 (v1: 10 테이블, v2: 13 테이블)
│   ├── schemas/                       ← Pydantic 응답 스키마
│   ├── api/                           ← REST API 라우터 (stocks, watchlist, content, auth)
│   ├── crud/                          ← UPSERT 로직 (stock.py, watchlist.py, api_key.py)
│   ├── parsers/__init__.py            ← 파서 re-export (CFRA/Zacks × Regex/LLM)
│   └── services/                      ← 비즈니스 로직
│       ├── parser_service.py          ← PDF → DB 오케스트레이터 (LLM default, regex fallback)
│       ├── fetcher_service.py         ← Playwright PDF 다운로드
│       ├── content_service.py         ← 콘텐츠 변수 맵 + 변경 감지
│       ├── alert_service.py           ← 알림 생성 + 이메일 발송
│       └── scheduler.py              ← APScheduler 정기 수집
│
├── cfra_parser.py                     ← CFRA Regex 파서 (pdfplumber 기반)
├── zacks_parser.py                    ← Zacks Regex 파서 (pdfplumber 기반)
├── llm_parser.py                      ← ★ LLM 파서 (Claude API, PDF 직접 전송)
├── validate_all.py                    ← Regex 파서 검증 스크립트
│
├── batch_llm_parse.py                 ← ★ 배치 파싱 스크립트 (inventory 기반, resumable)
├── build_pdf_inventory.py             ← PDF 인벤토리 생성 (storage 스캔 → JSON)
│
├── alembic/                           ← DB 마이그레이션
│   └── versions/                      ← 마이그레이션 파일들
│
├── storage/                           ← PDF 저장소 (gitignored)
│   └── pdfs/
│       ├── 2026-03-02/                ← 날짜별 다운로드 폴더
│       ├── 2026-03-03/
│       ├── 2026-03-05/                ← (239 PDFs)
│       ├── 2026-03-06/                ← (206 PDFs)
│       ├── 2026-03-07/                ← (159 PDFs)
│       ├── 2026-03-08/                ← (392 PDFs)
│       └── legacy/                    ← 초기 샘플 PDF 11개
│
├── scripts/                           ← 유틸리티 스크립트
│   ├── stealth_download_r*.py         ← Fidelity 포털 PDF 다운로드 (iteration 1~5)
│   ├── batch_download.py              ← 배치 다운로드
│   ├── test_llm_parser.py             ← LLM 파서 테스트
│   ├── run_*_test*.py                 ← 각종 테스트 스크립트
│   └── tickers_*.txt                  ← 티커 목록 (S&P 500, NASDAQ 100, 전체)
│
├── logs/                              ← 배치 실행 로그 (gitignored)
├── docs/                              ← bkit PDCA 문서 + 리포트
│   ├── 01-plan/                       ← Plan 문서
│   ├── 02-design/                     ← Design 명세
│   ├── reports/                       ← 파서 정확도 리포트, 세션 로그
│   └── database-architecture-review.md
├── priv/python/                       ← Elixir 연동용 CLI 래퍼
│
├── pdf_inventory.json                 ← PDF 인벤토리 (gitignored, regenerable)
├── bkit.config.json                   ← bkit PDCA 설정
├── alembic.ini                        ← Alembic 설정
├── requirements.txt                   ← Python 의존성
├── docker-compose.yml                 ← PostgreSQL Docker 설정
└── .env                               ← 환경변수 (gitignored)
```

---

## Python 파서 모듈 (검증 완료, DB 연동 완료)

### 의존성

- Python 3.10+, pdfplumber, sqlalchemy, psycopg, alembic, pydantic-settings
- 설치: `pip install pdfplumber sqlalchemy[asyncio] psycopg alembic pydantic-settings`

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

### CLI 래퍼 (priv/python/parse_report.py)

```bash
# 단일 PDF 파싱 + JSON 출력
python priv/python/parse_report.py --source cfra --file pltr.pdf

# Elixir 상위 프로젝트에서 호출 시:
{output, 0} = System.cmd("python3", ["priv/python/parse_report.py", "--source", source, "--file", pdf_path])
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
2. **파서 참조**: `cfra_parser.py`, `zacks_parser.py`의 출력 구조를 기준으로 ORM 모델/CRUD 코드 생성
3. **소스별 파서 분리**: CFRA/Zacks 파서는 별도 모듈, 공통 인터페이스(`parse(pdf_path)`)로 통일
4. **UPSERT 패턴**: 동일 종목+소스+날짜 리포트는 덮어쓰기 (유니크 제약 기반, `INSERT ON CONFLICT DO UPDATE`)
5. **멀티테넌시**: 모든 테이블에 `organization_id` 컬럼 포함
6. **환경변수**: DB URL, PDF 경로 등은 `.env` + `pydantic-settings`로 관리
7. **마이그레이션**: 스키마 변경 시 Alembic으로 마이그레이션 생성 (`alembic revision --autogenerate`)
8. **PDF 샘플 참조**: 파서 개발 시 9개 PDF 파일을 실제 테스트 데이터로 활용
9. **검증 스크립트**: `validate_all.py`로 파서 수정 후 회귀 테스트 실행
10. **CRUD ↔ 파서 동기화**: 파서 출력 필드 추가 시 `app/crud/stock.py` 매핑도 함께 업데이트

---

## 현재 상태

### 데이터 현황 (2026-03-10)

| 항목 | 수량 |
|------|------|
| PDF 수집 | 1,017개 (CFRA 511 + Zacks 506) |
| 유니크 티커 | 513개 |
| DB 적재 완료 | 466개 (238 profiles, 466 reports) |
| DB 미적재 | 551개 (3/7, 3/8 다운로드분) |
| 파서 | LLM (Claude API, default) + Regex (pdfplumber, fallback) |

### 완료된 Phase

- ✅ **Phase 1** (MVP): Regex 파서 2종 개발, 정확도 100% (170항목)
- ✅ **Phase 2** (데이터 품질): UPSERT 멱등성, Balance Sheet/Analyst Notes 연결
- ✅ **Phase 3** (자동 수집): Watchlist + Playwright fetcher + APScheduler
- ✅ **Phase 4** (콘텐츠): content_service, alert_service, 19개 API 엔드포인트
- ✅ **Phase 5** (LLM 파서): Claude API 기반 PDF 직접 파싱, regex fallback 자동 전환
- ✅ **Phase 6** (대량 수집): stealth_download (r1~r5), 1,017 PDF 수집 완료
- ✅ **Phase 7** (배치 적재): batch_llm_parse.py, pdf_inventory.json 기반 resumable 파싱

### 주요 배치 스크립트

```bash
# PDF 인벤토리 재생성 (storage/pdfs/ 스캔 → pdf_inventory.json)
python build_pdf_inventory.py

# 미적재 PDF 일괄 파싱 → DB (resumable, inventory 자동 업데이트)
python batch_llm_parse.py [--limit N] [--source CFRA|Zacks] [--date 2026-03-07] [--dry-run]
```

### 전체 API 엔드포인트 (19개)

Phase 1-4 전체 API는 위의 "REST API (19개 엔드포인트)" 섹션 참조.
