# Stock Report Database 설계안

## 개요

CFRA, Zacks 등 다양한 증권사 리서치 리포트 데이터를 PostgreSQL에 정규화 저장하여,
콘텐츠 자동 생성(블로그, 뉴스레터, 분석글) 시 참조 데이터로 활용하는 구조.

기존 `market/` 모듈(MarketIndicator, MarketReport, EarningsCalendar) 하위에
**StockReport 도메인**을 추가한다.

### 지원 리포트 소스

| 소스 | 포맷 특징 | 레이팅 체계 |
|------|----------|-----------|
| CFRA | STARS + 8년 재무제표 + 리서치노트 시계열 | STARS 1~5 + Buy/Hold/Sell |
| Zacks | Style Scores(VGM) + Buy/Sell 근거 분리 + 산업비교 40개 지표 | Rank 1~5 + Outperform/Neutral/Underperform |
| (확장 예정) | Morningstar, Bloomberg, S&P 등 | source 필드로 구분 |

---

## 1. 테이블 설계 (7개 테이블)

### 1-1. `stock_profiles` — 종목 기본 정보

| 컬럼 | 타입 | 설명 |
|------|------|------|
| id | bigserial PK | |
| ticker | varchar(10) | `PLTR` |
| company_name | varchar(255) | `Palantir Technologies Inc.` |
| exchange | varchar(50) | `NasdaqGS` |
| currency | varchar(10) | `USD` |
| gics_sector | varchar(100) | `Information Technology` |
| gics_sub_industry | varchar(100) | `Application Software` |
| industry | varchar(100) | `Medical Services` (Zacks 산업 분류) |
| domicile | varchar(100) | `Delaware` |
| founded_year | integer | `2003` |
| employees | integer | `4,429` |
| website | varchar(255) | `www.palantir.com` |
| description | text | 회사 개요 요약 |
| segments | jsonb | `[{"name": "Diagnostics", "pct": 40.5}, ...]` (Zacks 사업부 비중) |
| geo_breakdown | jsonb | `[{"region": "North America", "pct": 43.1}, ...]` |
| officers | jsonb | `[{"name": "A. C. Karp", "title": "CEO"}, ...]` |
| board_members | jsonb | `["A. C. Karp", "P. A. Thiel", ...]` |
| index_memberships | varchar[] | `{"S&P 500"}` |
| organization_id | bigint FK | 멀티테넌시 |
| inserted_at / updated_at | timestamps | |

**유니크 제약**: `(ticker, exchange)`

---

### 1-2. `stock_reports` — 리포트 메타 (1 리포트 = 1 row)

| 컬럼 | 타입 | 설명 |
|------|------|------|
| id | bigserial PK | |
| stock_profile_id | bigint FK | stock_profiles 참조 |
| source | varchar(50) | `CFRA`, `Morningstar`, `Bloomberg` 등 |
| report_date | date | `2026-02-21` |
| analyst_name | varchar(100) | `Janice Quek` |
| recommendation | varchar(20) | `Buy`, `Hold`, `Neutral`, `Underperform` 등 (통합) |
| prior_recommendation | varchar(20) | `Underperform` (Zacks: 이전 추천) |
| stars_rating | integer | 1~5 (CFRA STARS) |
| zacks_rank | integer | 1~5 (Zacks Rank: 1=Strong Buy ~ 5=Strong Sell) |
| style_scores | jsonb | `{"value":"D","growth":"D","momentum":"B","vgm":"C"}` (Zacks) |
| target_price | decimal(12,2) | `203.00` |
| current_price | decimal(12,2) | `135.24` (리포트 기준일 종가) |
| price_date | date | `2026-02-20` |
| risk_assessment | varchar(20) | `LOW`, `MEDIUM`, `HIGH` |
| fair_value | decimal(12,2) | `89.94` |
| fair_value_rank | integer | 1~5 |
| volatility | varchar(20) | `LOW`, `AVERAGE`, `HIGH` |
| technical_eval | varchar(20) | `BULLISH`, `NEUTRAL`, `BEARISH` |
| insider_activity | varchar(20) | `FAVORABLE`, `NEUTRAL`, `UNFAVORABLE` |
| investment_style | varchar(50) | `Large-Cap Blend` |
| industry_rank | varchar(100) | `Bottom 40% (145 out of 243)` (Zacks) |
| highlights | text | Highlights 전문 (CFRA) |
| reasons_to_buy | text | 매수 근거 전문 (Zacks ▲ 섹션) |
| reasons_to_sell | text | 매도 근거 전문 (Zacks ▼ 섹션) |
| investment_rationale | text | Investment Rationale/Risk 전문 (CFRA) |
| business_summary | text | Business Summary / Overview 전문 |
| sub_industry_outlook | text | Sub-Industry Outlook 전문 (CFRA) |
| last_earnings_summary | text | 최근 실적 요약 (Zacks Last Earnings Report) |
| outlook | text | 회사 전망 (Zacks Outlook) |
| recent_news | jsonb | `[{"date":"2026-02-17","title":"Acquisition of Masimo","content":"..."}]` |
| raw_pdf_path | varchar(500) | 원본 PDF 경로 |
| organization_id | bigint FK | 멀티테넌시 |
| inserted_at / updated_at | timestamps | |

**유니크 제약**: `(stock_profile_id, source, report_date)`

---

### 1-3. `stock_financials` — 분기/연간 재무 데이터

| 컬럼 | 타입 | 설명 |
|------|------|------|
| id | bigserial PK | |
| stock_profile_id | bigint FK | |
| fiscal_year | integer | `2025` |
| fiscal_quarter | integer (nullable) | `1`~`4`, NULL이면 연간 |
| period_type | varchar(10) | `quarterly`, `annual` |
| is_estimate | boolean | `true` = E(추정치), `false` = 실적 |
| revenue | decimal(15,2) | 백만 USD 단위 |
| operating_income | decimal(15,2) | |
| pretax_income | decimal(15,2) | |
| net_income | decimal(15,2) | |
| eps | decimal(8,4) | |
| eps_normalized | decimal(8,4) | 조정 EPS |
| free_cash_flow_ps | decimal(8,4) | 주당 FCF |
| tangible_book_value_ps | decimal(8,4) | |
| depreciation | decimal(12,2) | |
| effective_tax_rate | decimal(6,2) | % 단위 |
| gross_margin_pct | decimal(6,2) | 매출총이익률 (Zacks: 59.1%) |
| operating_margin_pct | decimal(6,2) | 영업이익률 (Zacks: 19.1%) |
| segment_revenues | jsonb | `[{"name":"Diagnostics","revenue":2720,"growth_pct":3.0},...]` (Zacks) |
| eps_surprise_pct | decimal(6,2) | EPS 서프라이즈 (Zacks: 0.45%) |
| sales_surprise_pct | decimal(6,2) | 매출 서프라이즈 (Zacks: 0.64%) |
| organization_id | bigint FK | |
| inserted_at / updated_at | timestamps | |

**유니크 제약**: `(stock_profile_id, fiscal_year, fiscal_quarter, is_estimate)`

---

### 1-4. `stock_balance_sheets` — 대차대조표 연간 데이터

| 컬럼 | 타입 | 설명 |
|------|------|------|
| id | bigserial PK | |
| stock_profile_id | bigint FK | |
| fiscal_year | integer | |
| cash | decimal(15,2) | |
| current_assets | decimal(15,2) | |
| total_assets | decimal(15,2) | |
| current_liabilities | decimal(15,2) | |
| long_term_debt | decimal(15,2) | |
| total_capital | decimal(15,2) | |
| capital_expenditures | decimal(15,2) | |
| cash_from_operations | decimal(15,2) | |
| current_ratio | decimal(6,2) | |
| ltd_to_cap_pct | decimal(6,2) | |
| net_income_to_revenue_pct | decimal(6,2) | |
| return_on_assets_pct | decimal(6,2) | |
| return_on_equity_pct | decimal(6,2) | |
| organization_id | bigint FK | |
| inserted_at / updated_at | timestamps | |

**유니크 제약**: `(stock_profile_id, fiscal_year)`

---

### 1-5. `stock_key_stats` — 핵심 통계 (리포트 기준일 스냅샷)

| 컬럼 | 타입 | 설명 |
|------|------|------|
| id | bigserial PK | |
| stock_report_id | bigint FK | stock_reports 참조 |
| week_52_high | decimal(12,2) | |
| week_52_low | decimal(12,2) | |
| trailing_12m_eps | decimal(8,4) | |
| trailing_12m_pe | decimal(10,2) | |
| market_cap_b | decimal(12,2) | 십억 USD |
| shares_outstanding_m | decimal(12,2) | 백만주 |
| beta | decimal(6,2) | |
| eps_cagr_3yr_pct | decimal(6,2) | |
| institutional_ownership_pct | decimal(6,2) | |
| dividend_yield_pct | decimal(6,2) | |
| price_to_sales | decimal(10,2) | |
| price_to_ebitda | decimal(10,2) | |
| price_to_pretax | decimal(10,2) | |
| net_margin_1yr_pct | decimal(6,2) | |
| net_margin_3yr_pct | decimal(6,2) | |
| sales_growth_1yr_pct | decimal(6,2) | |
| sales_growth_3yr_pct | decimal(6,2) | |
| pe_forward_12m | decimal(10,2) | Forward P/E (Zacks: 24.84) |
| ps_forward_12m | decimal(10,2) | Forward P/S (Zacks: 5.78) |
| ev_ebitda | decimal(10,2) | EV/EBITDA (Zacks: 23.47) |
| peg_ratio | decimal(10,2) | PEG (Zacks: 3.24) |
| price_to_book | decimal(10,2) | P/B (Zacks: 2.84) |
| price_to_cashflow | decimal(10,2) | P/CF (Zacks: 18.58) |
| debt_equity | decimal(10,2) | D/E (Zacks: 0.35) |
| cash_per_share | decimal(10,2) | 주당 현금 (Zacks: 11.37) |
| earnings_yield_pct | decimal(6,2) | 이익수익률 (Zacks: 3.97%) |
| dividend_rate | decimal(8,2) | 주당 배당금 (1.28) |
| valuation_multiples | jsonb | 5년 범위 비교 (아래 참조) |
| organization_id | bigint FK | |
| inserted_at / updated_at | timestamps | |

`valuation_multiples` jsonb 구조 (Zacks Valuation Multiples 테이블 저장용):
```json
{
  "pe_f12m": {"current": 24.84, "sub_industry": 15.9, "sector": 21.4, "sp500": 22.59,
              "high_5yr": 34.76, "low_5yr": 21.53, "median_5yr": 27.24},
  "ps_f12m": {"current": 5.78, "sub_industry": 0.48, "sector": 2.24, "sp500": 5.22,
              "high_5yr": 8.12, "low_5yr": 6.02, "median_5yr": 6.4}
}
```

---

### 1-6. `stock_peers` — 피어 그룹 비교

| 컬럼 | 타입 | 설명 |
|------|------|------|
| id | bigserial PK | |
| stock_report_id | bigint FK | 어떤 리포트 기준인지 |
| peer_ticker | varchar(10) | `ADBE`, `CRM` 등 |
| peer_name | varchar(255) | |
| exchange | varchar(50) | |
| recent_price | decimal(12,2) | |
| market_cap_m | decimal(15,2) | |
| price_chg_30d_pct | decimal(6,2) | |
| price_chg_1yr_pct | decimal(6,2) | |
| pe_ratio | decimal(10,2) | |
| fair_value_calc | decimal(12,2) | CFRA Fair Value |
| yield_pct | decimal(6,2) | |
| roe_pct | decimal(6,2) | |
| ltd_to_cap_pct | decimal(6,2) | |
| recommendation | varchar(20) | 피어의 추천등급 (Zacks) |
| rank | integer | 피어의 랭크 (Zacks: 1~5) |
| detailed_comparison | jsonb | Zacks 40개 상세 지표 비교 (아래 참조) |
| organization_id | bigint FK | |
| inserted_at / updated_at | timestamps | |

---

### 1-7. `stock_analyst_notes` — 애널리스트 리서치 노트

| 컬럼 | 타입 | 설명 |
|------|------|------|
| id | bigserial PK | |
| stock_profile_id | bigint FK | |
| source | varchar(50) | `CFRA` |
| published_at | naive_datetime | `2026-02-03 09:31:00` |
| analyst_name | varchar(100) | |
| title | varchar(500) | 노트 제목/첫 줄 |
| stock_price_at_note | decimal(12,2) | 노트 작성 시점 주가 |
| action | varchar(50) | `Maintains Buy`, `Upgrade`, `Downgrade` |
| target_price | decimal(12,2) | 해당 노트 시점 목표가 |
| content | text | 노트 전문 |
| organization_id | bigint FK | |
| inserted_at / updated_at | timestamps | |

---

## 2. ER 다이어그램 (관계)

```
stock_profiles (1) ──< (N) stock_reports
stock_profiles (1) ──< (N) stock_financials
stock_profiles (1) ──< (N) stock_balance_sheets
stock_profiles (1) ──< (N) stock_analyst_notes
stock_reports  (1) ──< (N) stock_peers
stock_reports  (1) ──< (1) stock_key_stats
```

---

## 3. 모듈 구조 (기존 market/ 확장)

```
lib/app_name/
├── market/
│   ├── market_indicator.ex      # 기존
│   ├── market_report.ex         # 기존
│   ├── earnings_calendar.ex     # 기존
│   │
│   ├── stock_profile.ex         # NEW: 종목 기본정보
│   ├── stock_report.ex          # NEW: 리포트 메타
│   ├── stock_financial.ex       # NEW: 분기/연간 재무
│   ├── stock_balance_sheet.ex   # NEW: 대차대조표
│   ├── stock_key_stat.ex        # NEW: 핵심 통계
│   ├── stock_peer.ex            # NEW: 피어 비교
│   ├── stock_analyst_note.ex    # NEW: 애널리스트 노트
│   │
│   └── stock_reports.ex         # 컨텍스트 모듈 (비즈니스 로직)
```

---

## 4. 마이그레이션 순서

기존 마이그레이션 순서(CLAUDE.md 8번) 이후에 추가:

```
8-1. stock_profiles
8-2. stock_reports (→ stock_profiles FK)
8-3. stock_financials (→ stock_profiles FK)
8-4. stock_balance_sheets (→ stock_profiles FK)
8-5. stock_key_stats (→ stock_reports FK)
8-6. stock_peers (→ stock_reports FK)
8-7. stock_analyst_notes (→ stock_profiles FK)
```

---

## 5. 인덱스 전략

```sql
-- 빠른 종목 조회
CREATE UNIQUE INDEX idx_stock_profiles_ticker ON stock_profiles(ticker, exchange);

-- 리포트 검색 (최신순)
CREATE INDEX idx_stock_reports_date ON stock_reports(stock_profile_id, report_date DESC);
CREATE INDEX idx_stock_reports_source ON stock_reports(source, report_date DESC);

-- 재무 데이터 조회 (연도/분기)
CREATE INDEX idx_stock_financials_period ON stock_financials(stock_profile_id, fiscal_year DESC, fiscal_quarter);
CREATE INDEX idx_stock_financials_estimate ON stock_financials(stock_profile_id, is_estimate);

-- 애널리스트 노트 (최신순)
CREATE INDEX idx_analyst_notes_date ON stock_analyst_notes(stock_profile_id, published_at DESC);

-- 멀티테넌시 스코프
CREATE INDEX idx_stock_profiles_org ON stock_profiles(organization_id);
CREATE INDEX idx_stock_reports_org ON stock_reports(organization_id);
```

---

## 6. 콘텐츠 작성 시 참조 활용 전략

### 6-1. 컨텍스트 함수 설계 (stock_reports.ex)

```elixir
defmodule AppName.Market.StockReports do
  @moduledoc "Stock Report DB 조회 및 콘텐츠 참조용 컨텍스트"

  # 최신 리포트 + 프로필 조회
  def get_latest_report(ticker, opts \\ [])

  # 특정 종목의 N년치 재무 데이터
  def list_financials(ticker, years: 5, type: :annual)

  # 분기별 Revenue/EPS 추이 (차트용)
  def get_quarterly_trend(ticker, quarters: 8)

  # 피어 비교 데이터
  def list_peers(report_id)

  # 애널리스트 노트 (최근 N개)
  def list_analyst_notes(ticker, limit: 5)

  # ★ 콘텐츠 생성용 통합 조회
  def get_report_bundle(ticker) do
    %{
      profile: get_profile(ticker),
      report: get_latest_report(ticker),
      financials: list_financials(ticker, years: 3),
      key_stats: get_key_stats(ticker),
      peers: list_peers(ticker),
      notes: list_analyst_notes(ticker, limit: 3)
    }
  end

  # ★ 콘텐츠 템플릿에 주입할 변수 맵
  def to_content_vars(ticker) do
    bundle = get_report_bundle(ticker)
    %{
      company_name: bundle.profile.company_name,
      ticker: ticker,
      recommendation: bundle.report.recommendation,
      target_price: bundle.report.target_price,
      current_price: bundle.report.current_price,
      upside_pct: calc_upside(bundle.report),
      revenue_latest: latest_revenue(bundle.financials),
      revenue_growth: calc_revenue_growth(bundle.financials),
      eps_latest: latest_eps(bundle.financials),
      risk_level: bundle.report.risk_assessment,
      top_peers: format_peers(bundle.peers),
      latest_note_summary: summarize_note(hd(bundle.notes))
    }
  end
end
```

### 6-2. 콘텐츠 라인과의 연동

```
[stock_reports DB] → StockReports.to_content_vars("PLTR")
                          ↓
              [ContentTemplate] 에 변수 주입
                          ↓
              [ContentPost] 자동 생성
                          ↓
              [Distribution] 멀티플랫폼 배포
```

기존 `content_posts` 테이블에 참조 컬럼 추가:

```sql
ALTER TABLE content_posts
  ADD COLUMN stock_profile_id bigint REFERENCES stock_profiles(id),
  ADD COLUMN stock_report_id bigint REFERENCES stock_reports(id);
```

이렇게 하면 어떤 콘텐츠가 어떤 리포트 데이터를 기반으로 생성되었는지 추적 가능.

### 6-3. 활용 예시

| 콘텐츠 유형 | 참조 데이터 |
|------------|-----------|
| 종목 분석 블로그 | profile + report + financials + peers |
| 실적 속보 | financials(분기별) + analyst_notes |
| 비교 분석글 | peers + key_stats 복수 종목 조인 |
| 뉴스레터 | report.highlights + key_stats |
| 투자 인사이트 | report.investment_rationale + sub_industry_outlook |

---

## 7. 데이터 입력 방식

### 7-1. PDF 파싱 (Oban Worker)

```elixir
defmodule AppName.Workers.StockReportParser do
  use Oban.Worker, queue: :reports

  @impl true
  def perform(%{args: %{"pdf_path" => path, "org_id" => org_id}}) do
    # 1. PDF 텍스트 추출 (pdfplumber via Python port)
    # 2. 섹션별 파싱 (정규식 + 패턴 매칭)
    # 3. 테이블 데이터 → stock_financials, stock_balance_sheets
    # 4. 텍스트 데이터 → stock_reports, stock_analyst_notes
    # 5. Ecto.Multi로 원자적 삽입
  end
end
```

### 7-2. 수동 입력 (어드민 UI)

LiveView 폼에서 직접 입력/수정 (P50 어드민 영역 확장)

### 7-3. API 입력

```
POST /api/stock-reports     (Pro+ 플랜)
POST /api/stock-financials  (Pro+ 플랜)
```

---

## 8. PLTR 리포트 → DB 매핑 예시

### 8-A. PLTR (CFRA 리포트) → DB 매핑

```elixir
# stock_profiles
%StockProfile{
  ticker: "PLTR",
  company_name: "Palantir Technologies Inc.",
  exchange: "NasdaqGS",
  gics_sector: "Information Technology",
  gics_sub_industry: "Application Software",
  founded_year: 2003,
  employees: 4429
}

# stock_reports
%StockReport{
  source: "CFRA",
  report_date: ~D[2026-02-21],
  analyst_name: "Janice Quek",
  recommendation: "Buy",
  stars_rating: 4,
  target_price: Decimal.new("203.00"),
  current_price: Decimal.new("135.24"),
  risk_assessment: "MEDIUM",
  fair_value: Decimal.new("89.94"),
  technical_eval: "BULLISH"
}

# stock_financials (Q4 2025 실적 예시)
%StockFinancial{
  fiscal_year: 2025,
  fiscal_quarter: 4,
  period_type: "quarterly",
  is_estimate: false,
  revenue: Decimal.new("1407.00"),
  eps: Decimal.new("0.25")
}

# stock_financials (2026 연간 추정치 예시)
%StockFinancial{
  fiscal_year: 2026,
  fiscal_quarter: nil,
  period_type: "annual",
  is_estimate: true,
  revenue: Decimal.new("7209.00"),
  eps: Decimal.new("1.25")
}
```

### 8-B. DHR (Zacks 리포트) → DB 매핑

```elixir
# stock_profiles
%StockProfile{
  ticker: "DHR",
  company_name: "Danaher Corporation",
  exchange: "NYSE",
  gics_sector: "Health Care",
  industry: "Medical Services",
  domicile: "Washington, DC",
  employees: 63000,
  segments: [
    %{name: "Diagnostics", pct: 40.5},
    %{name: "Life Sciences", pct: 29.9},
    %{name: "Biotechnology", pct: 29.6}
  ],
  geo_breakdown: [
    %{region: "North America", pct: 43.1},
    %{region: "Western Europe", pct: 23.0},
    %{region: "High-growth markets", pct: 28.7},
    %{region: "Other developed", pct: 5.2}
  ]
}

# stock_reports (Zacks)
%StockReport{
  source: "Zacks",
  report_date: ~D[2026-02-20],
  recommendation: "Neutral",
  prior_recommendation: "Underperform",
  zacks_rank: 3,
  style_scores: %{value: "D", growth: "D", momentum: "B", vgm: "C"},
  target_price: Decimal.new("224.00"),
  current_price: Decimal.new("211.25"),
  price_date: ~D[2026-02-19],
  industry_rank: "Bottom 40% (145 out of 243)",
  reasons_to_buy: "Biotechnology segment 강세... Masimo 인수($9.9B)... DBS 이니셔티브...",
  reasons_to_sell: "Life Sciences 약세... SG&A 비용 증가... 부채 $18.4B...",
  last_earnings_summary: "Q4 2025 adj EPS $2.23 (beat $2.22), 매출 $6.84B (beat $6.79B)...",
  outlook: "2026 core sales 3-6% Y/Y 성장, adj EPS $8.35-$8.50 가이던스",
  recent_news: [
    %{date: "2026-02-17", title: "Acquisition of Masimo",
      content: "$9.9B 인수, Diagnostics 포트폴리오 강화"},
    %{date: "2025-12-09", title: "Dividend Update",
      content: "분기 배당 $0.32/주, 연환산 수익률 0.6%"}
  ]
}

# stock_financials (Q4 2025 실적)
%StockFinancial{
  fiscal_year: 2025,
  fiscal_quarter: 4,
  period_type: "quarterly",
  is_estimate: false,
  revenue: Decimal.new("6838.00"),
  eps: Decimal.new("2.23"),
  gross_margin_pct: Decimal.new("59.1"),
  operating_margin_pct: Decimal.new("19.1"),
  eps_surprise_pct: Decimal.new("0.45"),
  sales_surprise_pct: Decimal.new("0.64"),
  segment_revenues: [
    %{name: "Life Sciences", revenue: 2090, growth_pct: 2.5},
    %{name: "Diagnostics", revenue: 2720, growth_pct: 3.0},
    %{name: "Biotechnology", revenue: 2030, growth_pct: 9.0}
  ]
}

# stock_financials (2026 연간 추정치)
%StockFinancial{
  fiscal_year: 2026,
  fiscal_quarter: nil,
  period_type: "annual",
  is_estimate: true,
  revenue: Decimal.new("25335.00"),
  eps: Decimal.new("8.32")
}

# stock_key_stats
%StockKeyStat{
  week_52_high: Decimal.new("242.80"),
  week_52_low: Decimal.new("171.00"),
  market_cap_b: Decimal.new("149.2"),
  beta: Decimal.new("0.91"),
  dividend_yield_pct: Decimal.new("0.6"),
  dividend_rate: Decimal.new("1.28"),
  trailing_12m_pe: Decimal.new("27.1"),
  pe_forward_12m: Decimal.new("24.84"),
  ps_forward_12m: Decimal.new("5.78"),
  ev_ebitda: Decimal.new("23.47"),
  peg_ratio: Decimal.new("3.24"),
  price_to_book: Decimal.new("2.84"),
  debt_equity: Decimal.new("0.35"),
  valuation_multiples: %{
    pe_f12m: %{current: 24.84, sub_industry: 15.9, sector: 21.4, sp500: 22.59,
               high_5yr: 34.76, low_5yr: 21.53, median_5yr: 27.24},
    ps_f12m: %{current: 5.78, sub_industry: 0.48, sector: 2.24, sp500: 5.22,
               high_5yr: 8.12, low_5yr: 6.02, median_5yr: 6.4}
  }
}

# stock_peers (Zacks Top Peers)
[
  %StockPeer{peer_ticker: "BZLFY", peer_name: "Bunzl PLC",
             recommendation: "Neutral", rank: 3},
  %StockPeer{peer_ticker: "HON", peer_name: "Honeywell International Inc.",
             recommendation: "Neutral", rank: 3},
  %StockPeer{peer_ticker: "MKL", peer_name: "Markel Group Inc.",
             recommendation: "Neutral", rank: 2},
  %StockPeer{peer_ticker: "MMM", peer_name: "3M Company",
             recommendation: "Neutral", rank: 3},
  %StockPeer{peer_ticker: "CSL", peer_name: "Carlisle Companies",
             recommendation: "Underperform", rank: 4},
  %StockPeer{peer_ticker: "GFF", peer_name: "Griffon Corporation",
             recommendation: "Underperform", rank: 5}
]
```

---

## 9. 소스별 필드 매핑 가이드

동일한 테이블에 CFRA/Zacks 데이터를 저장할 때 어떤 필드가 어디서 오는지 참조:

### `stock_reports` 필드 소스 매핑

| 컬럼 | CFRA | Zacks |
|------|------|-------|
| recommendation | Buy/Hold/Sell | Outperform/Neutral/Underperform |
| prior_recommendation | — | ✅ Prior Recommendation |
| stars_rating | ✅ STARS 1~5 | — |
| zacks_rank | — | ✅ Zacks Rank 1~5 |
| style_scores | — | ✅ V/G/M/VGM scores |
| target_price | ✅ 12-Mo Target | ✅ Price Target |
| risk_assessment | ✅ LOW/MED/HIGH | — |
| fair_value | ✅ Fair Value Calc | — |
| fair_value_rank | ✅ 1~5 | — |
| volatility | ✅ LOW/AVG/HIGH | — |
| technical_eval | ✅ BULLISH/BEARISH | — |
| insider_activity | ✅ FAV/NEUTRAL/UNFAV | — |
| industry_rank | — | ✅ Bottom 40% (145/243) |
| highlights | ✅ Highlights 섹션 | — |
| reasons_to_buy | — | ✅ Reasons To Buy (▲) |
| reasons_to_sell | — | ✅ Reasons To Sell (▼) |
| investment_rationale | ✅ Rationale/Risk | — |
| business_summary | ✅ Business Summary | ✅ Overview |
| sub_industry_outlook | ✅ Sub-Industry Outlook | — |
| last_earnings_summary | — | ✅ Last Earnings Report |
| outlook | — | ✅ Danaher's Outlook |
| recent_news | — | ✅ Recent News 섹션 |

### `stock_key_stats` 필드 소스 매핑

| 컬럼 | CFRA | Zacks |
|------|------|-------|
| trailing_12m_pe | ✅ | ✅ P/E TTM |
| pe_forward_12m | — | ✅ P/E F1 |
| ps_forward_12m | — | ✅ P/S TTM → F12M |
| ev_ebitda | — | ✅ EV/EBITDA |
| peg_ratio | — | ✅ PEG F1 |
| price_to_sales | ✅ Price/Sales | ✅ |
| valuation_multiples | — | ✅ 5yr range vs sector/SP500 |
| beta | ✅ | ✅ |
| market_cap_b | ✅ | ✅ |
| dividend_yield_pct | ✅ (N/A for PLTR) | ✅ 0.6% |

이 매핑을 통해 `source` 필드로 CFRA/Zacks를 구분하면서도,
콘텐츠 생성 시에는 `get_report_bundle(ticker)`로 통합 조회하여
소스에 관계없이 동일한 변수 맵을 생성할 수 있다.
