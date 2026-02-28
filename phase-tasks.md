# Stock Report Hub — Phase별 세부 기능 목록 (Claude Code용)

> **용도**: Claude Code에서 `/pdca plan {feature}` 또는 직접 구현 시 참조
> **생성일**: 2026-03-01
> **현재 상태**: Phase 0 완료 (파서 2종 + DB 설계 + 9 PDF 검증 100%)

---

## Phase 0: 사전 준비 ✅ DONE

| ID | 기능 | 상태 | 산출물 |
|----|------|------|--------|
| 0.1 | Fidelity Research 포털 구조 분석 | ✅ | stock-report-automation.md |
| 0.2 | Chrome MCP 검색 플로우 테스트 | ✅ | 세션 트랜스크립트 |
| 0.3 | DB 스키마 7테이블 설계 | ✅ | stock-report-db-design.md |
| 0.4 | 자동화 아키텍처 설계 (3방안) | ✅ | stock-report-automation.md |
| 0.5 | CFRA 파서 개발 + 검증 | ✅ | cfra_parser.py (26KB) |
| 0.6 | Zacks 파서 개발 + 검증 | ✅ | zacks_parser.py (18KB) |
| 0.7 | 검증 스크립트 + 100% 정확도 달성 | ✅ | validate_all.py, parser-accuracy-report.md |
| 0.8 | PRD 작성 | ✅ | PRD-stock-report-hub.md |

---

## Phase 1: 데이터 수집 엔진 (3/1 ~ 3/14)

**목표**: 티커 → PDF → 파싱 → DB 저장 End-to-End 동작

### 1-A. 인프라 셋업

```
Feature: python-env-setup
```

| # | 세부 기능 | bkit 명령 | 파일 | 수용 기준 |
|---|----------|----------|------|----------|
| 1 | Python venv 생성 (priv/python/) | `/pdca plan python-env-setup` | priv/python/requirements.txt | `pdfplumber` import 성공 |
| 2 | parse_report.py CLI 래퍼 | `/pdca do parse-report-cli` | priv/python/parse_report.py | `python parse_report.py <pdf> <source>` → JSON stdout |
| 3 | cfra_parser.py / zacks_parser.py 복사 | - | priv/python/parsers/ | 기존 파서 그대로 동작 |
| 4 | Elixir에서 System.cmd 호출 테스트 | - | test/market/parser_port_test.exs | `System.cmd("python3", [...])` → JSON 파싱 성공 |

**parse_report.py 인터페이스**:
```bash
# 입력
python3 priv/python/parse_report.py /path/to/pltr.pdf CFRA

# 출력 (JSON stdout)
{
  "profile": {...},
  "report": {...},
  "key_stats": {...},
  "financials": [...],
  "analyst_notes": [...],
  "peers": [...],
  "errors": [],
  "warnings": []
}
```

---

### 1-B. DB 마이그레이션

```
Feature: ecto-migrations
```

| # | 세부 기능 | 파일 | 수용 기준 |
|---|----------|------|----------|
| 1 | stock_profiles 테이블 생성 | priv/repo/migrations/xxx_create_stock_profiles.exs | ticker+exchange 유니크 제약 |
| 2 | stock_reports 테이블 생성 | priv/repo/migrations/xxx_create_stock_reports.exs | profile_id+source+report_date 유니크 |
| 3 | stock_financials 테이블 생성 | priv/repo/migrations/xxx_create_stock_financials.exs | profile_id+year+quarter+is_estimate 유니크 |
| 4 | stock_balance_sheets 테이블 생성 | priv/repo/migrations/xxx_create_stock_balance_sheets.exs | - |
| 5 | stock_key_stats 테이블 생성 | priv/repo/migrations/xxx_create_stock_key_stats.exs | report_id FK |
| 6 | stock_peers 테이블 생성 | priv/repo/migrations/xxx_create_stock_peers.exs | report_id FK |
| 7 | stock_analyst_notes 테이블 생성 | priv/repo/migrations/xxx_create_stock_analyst_notes.exs | - |
| 8 | 모든 테이블에 organization_id FK | 각 마이그레이션에 포함 | 멀티테넌시 지원 |

**핵심 규칙**:
- 모든 금액 필드: `:decimal` 타입
- 모든 테이블: `organization_id` FK + `timestamps()`
- `mix ecto.migrate` + `mix ecto.rollback` 양방향 동작

---

### 1-C. Ecto 스키마 (7개 모듈)

```
Feature: ecto-schemas
```

| # | 모듈 | 파일 | 주요 필드 |
|---|------|------|----------|
| 1 | StockProfile | lib/app/market/stock_profile.ex | ticker, company_name, exchange, sector, sub_industry, employees |
| 2 | StockReport | lib/app/market/stock_report.ex | source, recommendation, stars_rating, target_price, risk_assessment, highlights, investment_rationale |
| 3 | StockFinancial | lib/app/market/stock_financial.ex | fiscal_year, fiscal_quarter, period_type, is_estimate, revenue, eps, margins |
| 4 | StockBalanceSheet | lib/app/market/stock_balance_sheet.ex | total_assets, total_liabilities, long_term_debt, ratios |
| 5 | StockKeyStat | lib/app/market/stock_key_stat.ex | pe, peg, beta, market_cap, 52w_high/low, institutional_ownership |
| 6 | StockPeer | lib/app/market/stock_peer.ex | peer_ticker, peer_name, recommendation, rank, detailed_comparison (map) |
| 7 | StockAnalystNote | lib/app/market/stock_analyst_note.ex | source, published_at, analyst_name, content, stock_price_at_note |

**관계**:
```
StockProfile has_many :stock_reports, :stock_financials, :stock_balance_sheets, :stock_analyst_notes
StockReport has_many :stock_peers, has_one :stock_key_stat
```

---

### 1-D. 컨텍스트 모듈 (UPSERT 로직)

```
Feature: stock-reports-context
```

| # | 함수 | 파일 | 설명 |
|---|------|------|------|
| 1 | `upsert_from_parsed/2` | lib/app/market/stock_reports.ex | JSON → Ecto.Multi 원자적 UPSERT (7테이블) |
| 2 | `upsert_profile/2` | 위 파일 | ticker+exchange 기준 upsert |
| 3 | `upsert_report/3` | 위 파일 | profile_id+source+date 기준 upsert |
| 4 | `upsert_financials/2` | 위 파일 | year+quarter+is_estimate 기준 bulk upsert |
| 5 | `upsert_key_stats/2` | 위 파일 | report_id 기준 upsert |
| 6 | `upsert_peers/2` | 위 파일 | report_id 기준 delete + insert |
| 7 | `upsert_analyst_notes/2` | 위 파일 | profile_id+source+published_at 기준 |
| 8 | `get_latest_report/2` | 위 파일 | 최신 리포트 + preload |
| 9 | `list_financials/2` | 위 파일 | N년치 재무 데이터 조회 |
| 10 | `get_report_bundle/1` | 위 파일 | 통합 조회 (프로필+리포트+재무+통계+피어+노트) |

**수용 기준**: pltr.pdf 파싱 → upsert → DB 조회 → 원본 대조 일치

---

### 1-E. Oban 워커

```
Feature: oban-report-worker
```

| # | 워커 | 파일 | 큐 | 역할 |
|---|------|------|---|------|
| 1 | ReportParseWorker | lib/app/market/workers/report_parse_worker.ex | :reports | PDF경로+소스 → Python 호출 → JSON 파싱 → DB upsert |
| 2 | ReportFetchWorker | lib/app/market/workers/report_fetch_worker.ex | :report_fetch | 티커+소스 → PDF 다운로드 → ReportParseWorker 큐잉 |

**ReportParseWorker 흐름**:
```
Job args: %{"pdf_path" => "/data/pltr.pdf", "source" => "CFRA", "organization_id" => 1}
  → System.cmd("python3", ["priv/python/parse_report.py", pdf_path, source])
  → Jason.decode!(stdout)
  → StockReports.upsert_from_parsed(parsed, org_id)
  → :ok | {:error, reason}
```

**설정**:
```elixir
# Oban 큐 설정
queues: [reports: 5, report_fetch: 2]
# max_attempts: 3, priority: 2
```

---

### 1-F. 워치리스트

```
Feature: watchlist-crud
```

| # | 세부 기능 | 파일 | 수용 기준 |
|---|----------|------|----------|
| 1 | Watchlist 스키마 | lib/app/market/watchlist.ex | org_id, name, is_default |
| 2 | WatchlistItem 스키마 | lib/app/market/watchlist_item.ex | watchlist_id, stock_profile_id |
| 3 | 마이그레이션 | priv/repo/migrations/xxx_create_watchlists.exs | 최대 50종목 제약 |
| 4 | CRUD 함수 | lib/app/market/stock_reports.ex | add_to_watchlist/remove/list/get_tickers |
| 5 | 워치리스트 기반 일괄 수집 | lib/app/market/stock_reports.ex | `batch_fetch_watchlist/2` → N개 FetchWorker 큐잉 |

---

### 1-G. 통합 테스트

```
Feature: phase1-integration-test
```

| # | 테스트 | 수용 기준 |
|---|--------|----------|
| 1 | CFRA pltr.pdf → 7테이블 저장 | 숫자 필드 정확도 ≥ 98% |
| 2 | Zacks DHR.pdf → 7테이블 저장 | 숫자 필드 정확도 ≥ 98% |
| 3 | 9개 PDF 전체 파싱 + 저장 | 100% 성공률 |
| 4 | 동일 PDF 중복 실행 → UPSERT | 데이터 중복 없음 |
| 5 | validate_all.py 회귀 테스트 | 170개 항목 100% |

---

## Phase 2: 조회 UI + 비교 뷰 (3/15 ~ 3/28)

**목표**: 저장된 데이터를 웹에서 검색·조회·비교

### 2-A. 종목 검색

```
Feature: stock-search-page
```

| # | 세부 기능 | 파일 | 수용 기준 |
|---|----------|------|----------|
| 1 | 종목 검색 LiveView | lib/app_web/live/stock/search_live.ex | 티커/회사명 실시간 검색 |
| 2 | 자동완성 컴포넌트 | lib/app_web/components/stock_autocomplete.ex | 3글자 이상 입력 시 후보 표시 |
| 3 | 검색 결과 리스트 | 위 파일 | 종목명, 티커, 섹터, 최신 추천등급 표시 |
| 4 | 라우팅 | lib/app_web/router.ex | /stocks, /stocks/:ticker |

---

### 2-B. 종목 프로필 상세

```
Feature: stock-profile-page
```

| # | 세부 기능 | 파일 | 수용 기준 |
|---|----------|------|----------|
| 1 | 프로필 헤더 | lib/app_web/live/stock/show_live.ex | 회사명, 티커, 거래소, 섹터, 직원수 |
| 2 | 최신 리포트 요약 카드 | lib/app_web/components/report_summary_card.ex | 추천등급, 목표가, 현재가, 리스크, 별점 |
| 3 | 핵심 통계 패널 | lib/app_web/components/key_stats_panel.ex | PE, PEG, Beta, 시가총액, 52주 범위 |
| 4 | Highlights 섹션 | 위 LiveView | 리포트 highlights 텍스트 |
| 5 | Investment Rationale 섹션 | 위 LiveView | 투자 근거 텍스트 |

---

### 2-C. 재무 데이터 테이블

```
Feature: financial-data-table
```

| # | 세부 기능 | 파일 | 수용 기준 |
|---|----------|------|----------|
| 1 | 연간 재무 테이블 | lib/app_web/components/financial_table.ex | Revenue, EPS, 마진 8년치 |
| 2 | 분기 재무 테이블 | 위 파일 | 분기별 Revenue, EPS |
| 3 | Annual/Quarterly 토글 | 위 파일 | 탭 전환 |
| 4 | 추정치(E) 표시 | 위 파일 | is_estimate=true인 셀 시각 구분 |
| 5 | 애널리스트 노트 타임라인 | lib/app_web/components/analyst_notes.ex | 날짜별 노트, 주가 표시 |

---

### 2-D. 멀티소스 비교 뷰

```
Feature: multi-source-comparison
```

| # | 세부 기능 | 파일 | 수용 기준 |
|---|----------|------|----------|
| 1 | 비교 뷰 페이지 | lib/app_web/live/stock/compare_live.ex | CFRA vs Zacks 사이드바이사이드 |
| 2 | 추천등급 비교 | 위 파일 | 양쪽 등급 + 목표가 나란히 |
| 3 | 핵심 통계 비교 | 위 파일 | 동일 지표 양쪽 대조 (차이 하이라이트) |
| 4 | EPS 비교 | 위 파일 | CFRA EPS vs Zacks EPS (연도별) |
| 5 | 소스 선택 드롭다운 | 위 파일 | 2개 이상 소스 있을 때 선택 |

---

### 2-E. 워치리스트 대시보드

```
Feature: watchlist-dashboard
```

| # | 세부 기능 | 파일 | 수용 기준 |
|---|----------|------|----------|
| 1 | 대시보드 페이지 | lib/app_web/live/stock/dashboard_live.ex | 카드 뷰 전체 종목 |
| 2 | 종목 카드 컴포넌트 | lib/app_web/components/stock_card.ex | 티커, 추천등급, 목표가, 현재가, 업사이드 |
| 3 | 워치리스트 관리 UI | 위 LiveView | 종목 추가/삭제, 최대 50개 |
| 4 | 정렬/필터 | 위 LiveView | 섹터별, 등급별, 업사이드순 |
| 5 | 수집 트리거 버튼 | 위 LiveView | "전체 업데이트" 클릭 → batch_fetch |

---

### 2-F. 50종목 통합 테스트

| # | 테스트 | 수용 기준 |
|---|--------|----------|
| 1 | 50종목 일괄 수집 | 전체 성공률 ≥ 95% |
| 2 | 검색 → 프로필 → 리포트 → 재무 | 한 화면 정상 표시 |
| 3 | CFRA/Zacks 동일 종목 비교 뷰 | 사이드바이사이드 정상 |
| 4 | 대시보드 50종목 카드 렌더링 | 페이지 로드 < 3초 |

---

## Phase 3: 완전 자동화 + 안정화 (3/29 ~ 4/15)

**목표**: 사람 개입 없이 정기 수집 + 에러 복구 + 알림

### 3-A. Playwright Headless 수집

```
Feature: playwright-headless
```

| # | 세부 기능 | 파일 | 수용 기준 |
|---|----------|------|----------|
| 1 | Playwright 스크립트 | priv/python/fetch_report.py | Fidelity 포털 → PDF 다운로드 headless |
| 2 | 로그인/세션 관리 | 위 파일 | Public 포털이므로 로그인 불필요 |
| 3 | 딜레이 + 재시도 로직 | 위 파일 | 요청 간 5~10초, 최대 3회 재시도 |
| 4 | Elixir에서 System.cmd 호출 | lib/app/market/stock_report_fetcher.ex | `fetch_report(ticker, source)` → {:ok, pdf_path} |
| 5 | 에러 핸들링 | 위 파일 | rate limit, timeout, PDF 미존재 처리 |

---

### 3-B. Oban 정기 수집 스케줄러

```
Feature: oban-scheduler
```

| # | 세부 기능 | 파일 | 수용 기준 |
|---|----------|------|----------|
| 1 | ReportScheduleWorker | lib/app/market/workers/report_schedule_worker.ex | 워치리스트 전체 → FetchWorker 큐잉 |
| 2 | Cron 설정 (매일 7AM, 평일만) | config/config.exs | `"0 7 * * 1-5"` |
| 3 | 랜덤 딜레이 분산 | 위 워커 | `schedule_in: :rand.uniform(300)` |
| 4 | 수집 결과 로깅 | 위 워커 | 성공/실패 건수 기록 |

---

### 3-C. 변경 감지 + 알림

```
Feature: report-change-detection
```

| # | 세부 기능 | 파일 | 수용 기준 |
|---|----------|------|----------|
| 1 | 등급 변경 감지 | lib/app/market/stock_reports.ex | 이전 리포트 대비 recommendation diff |
| 2 | 목표가 변경 감지 | 위 파일 | target_price 변동률 계산 |
| 3 | 변경 이력 저장 | 마이그레이션 + 스키마 추가 | stock_report_changes 테이블 (선택) |
| 4 | 이메일 알림 | lib/app/market/workers/alert_worker.ex | 변경 감지 시 Oban → 이메일 발송 |
| 5 | UI 하이라이트 | 프로필 페이지 | 변경된 항목 배지/색상 표시 |

---

### 3-D. 콘텐츠 변수 맵

```
Feature: content-vars-map
```

| # | 세부 기능 | 파일 | 수용 기준 |
|---|----------|------|----------|
| 1 | `to_content_vars/1` | lib/app/market/stock_reports.ex | 티커 → 템플릿 변수 맵 반환 |
| 2 | upside_pct 계산 | 위 파일 | (target - current) / current * 100 |
| 3 | revenue_growth 계산 | 위 파일 | YoY 성장률 |
| 4 | ContentPost 연동 | content_posts 테이블 ALTER | stock_profile_id, stock_report_id FK 추가 |
| 5 | 통합 테스트 | test/ | `to_content_vars("PLTR")` → 모든 키 존재 |

---

### 3-E. PDF 아카이브

```
Feature: pdf-archive
```

| # | 세부 기능 | 파일 | 수용 기준 |
|---|----------|------|----------|
| 1 | 날짜별 폴더 저장 | lib/app/market/stock_report_fetcher.ex | /data/reports/2026-03-01/PLTR_CFRA.pdf |
| 2 | DB에 파일 경로 기록 | stock_reports 테이블 | pdf_path 컬럼 |
| 3 | 다운로드 엔드포인트 | lib/app_web/controllers/ | GET /stocks/:ticker/reports/:id/pdf |

---

### 3-F. 에러 핸들링 + 알림

```
Feature: error-handling
```

| # | 세부 기능 | 파일 | 수용 기준 |
|---|----------|------|----------|
| 1 | Oban 실패 알림 | lib/app/market/workers/ | 3회 재시도 후 실패 → 이메일 |
| 2 | 파싱 에러 로깅 | stock_reports 테이블 | parse_errors jsonb 컬럼 |
| 3 | 수집 대시보드 | LiveView 또는 로그 | 일별 성공/실패 현황 |

---

### 3-G. 1주 안정성 테스트

| # | 테스트 | 수용 기준 |
|---|--------|----------|
| 1 | 매일 7AM 자동 수집 5일 연속 | 성공률 ≥ 95% |
| 2 | 등급/목표가 변경 감지 | 변경 시 이메일 수신 |
| 3 | `to_content_vars("PLTR")` 호출 | 블로그 변수 맵 정상 반환 |
| 4 | 에러 복구 | Oban 재시도 후 정상 처리 |

---

## Phase 4: 확장 + SaaS 연동 (4/16~, 지속적)

### 4-A. 추가 소스 파서

```
Feature: argus-parser / sp-capitaliq-parser
```

| # | 세부 기능 | 수용 기준 |
|---|----------|----------|
| 1 | Argus 파서 (Python) | priv/python/parsers/argus_parser.py |
| 2 | S&P Capital IQ 파서 | priv/python/parsers/sp_parser.py |
| 3 | parse_report.py에 소스 라우팅 추가 | `ARGUS`, `SP` 소스 지원 |
| 4 | 파서별 검증 스크립트 | validate_all.py 확장 |

### 4-B. REST API

```
Feature: stock-rest-api
```

| # | 세부 기능 | 수용 기준 |
|---|----------|----------|
| 1 | GET /api/stocks/:ticker | JSON 프로필 + 최신 리포트 |
| 2 | GET /api/stocks/:ticker/financials | 재무 데이터 |
| 3 | GET /api/stocks/:ticker/compare | 멀티소스 비교 |
| 4 | API 인증 (Bearer token) | Pro+ 플랜 전용 |
| 5 | Rate limiting | 분당 60회 |

### 4-C. 웹훅 알림

```
Feature: webhook-notifications
```

| # | 세부 기능 | 수용 기준 |
|---|----------|----------|
| 1 | 웹훅 URL 등록 CRUD | org별 N개 URL |
| 2 | 새 리포트 이벤트 | report.created payload |
| 3 | 등급 변경 이벤트 | report.rating_changed payload |
| 4 | 재시도 + 실패 처리 | 3회 재시도, DLQ |

### 4-D. 콘텐츠 자동 생성

```
Feature: content-auto-generation
```

| # | 세부 기능 | 수용 기준 |
|---|----------|----------|
| 1 | 새 리포트 → 블로그 초안 자동 생성 | to_content_vars → 템플릿 → ContentPost |
| 2 | 배포 파이프라인 연결 | Distribution 모듈 연동 |
| 3 | 수동 승인 후 배포 | 자동 게시 OFF (기본) |

### 4-E. 종목 카드 임베드 위젯

```
Feature: stock-card-embed
```

| # | 세부 기능 | 수용 기준 |
|---|----------|----------|
| 1 | 임베드 가능한 HTML 위젯 | `<script src="embed.js" data-ticker="PLTR">` |
| 2 | 실시간 데이터 반영 | API에서 최신 데이터 |
| 3 | 커스텀 테마 | 라이트/다크 |

### 4-F. SaaS 티어 연동

```
Feature: saas-feature-gating
```

| # | 세부 기능 | 수용 기준 |
|---|----------|----------|
| 1 | Free: 5종목 워치리스트 | 제한 초과 시 업그레이드 안내 |
| 2 | Pro: 50종목 + 비교 뷰 | feature gate 동작 |
| 3 | Pro+: API + 웹훅 + 무제한 | 모든 기능 해제 |

---

## Claude Code 실행 순서 (권장)

### Week 1 (Phase 1-A ~ 1-E)

```bash
# Day 1: 인프라
/pdca plan python-env-setup
/pdca do python-env-setup
/pdca plan ecto-migrations
/pdca do ecto-migrations

# Day 2-3: 스키마 + 컨텍스트
/pdca plan ecto-schemas
/pdca do ecto-schemas
/pdca plan stock-reports-context
/pdca do stock-reports-context

# Day 4-5: Oban + 통합
/pdca plan oban-report-worker
/pdca do oban-report-worker
/pdca analyze phase1-integration
```

### Week 2 (Phase 1-F ~ 1-G)

```bash
/pdca plan watchlist-crud
/pdca do watchlist-crud
# Cowork: Chrome MCP 수집 테스트 + 일괄 수집
/pdca report phase1-completion
```

### Week 3-4 (Phase 2)

```bash
/pdca plan stock-search-page
/pdca plan stock-profile-page
/pdca plan financial-data-table
/pdca plan multi-source-comparison
/pdca plan watchlist-dashboard
# 순차 do → analyze → iterate
```

---

## 참조 문서

| 문서 | 경로 | 용도 |
|------|------|------|
| DB 스키마 설계 | stock-report-db-design.md | 테이블 구조, 관계, 매핑 예시 |
| 자동화 아키텍처 | stock-report-automation.md | 파이프라인, Oban, 코드 예시 |
| PRD | PRD-stock-report-hub.md | 요구사항, 수용 기준 |
| 로드맵 | ROADMAP.md | 일정, 의존성, 리스크 |
| 파서 정확도 | parser-accuracy-report.md | 170항목 검증 결과 |
| CFRA 파서 | cfra_parser.py | Python 파서 소스 |
| Zacks 파서 | zacks_parser.py | Python 파서 소스 |
| 검증 스크립트 | validate_all.py | 회귀 테스트 |
