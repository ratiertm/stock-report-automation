# 데이터베이스 아키텍처 리뷰 — Stock Report Hub

> **작성일:** 2026-03-05  
> **대상 시스템:** stock_hub (PostgreSQL 15, NAS 192.168.219.100:5433)  
> **데이터 소스:** CFRA Stock Reports (9pp), Zacks Equity Research (9pp)  
> **현재 규모:** 14 종목, 22 리포트, 395 재무 레코드  
> **목표 규모:** 500+ 종목, 주간 업데이트, 5년+ 히스토리

---

## 목차

1. [PDF 원문 구조 매핑](#1-pdf-원문-구조-매핑)
2. [현재 스키마 평가](#2-현재-스키마-평가)
3. [문제점 분석](#3-문제점-분석)
4. [이상적 스키마 제안](#4-이상적-스키마-제안)
5. [마이그레이션 전략](#5-마이그레이션-전략)
6. [인덱싱 전략](#6-인덱싱-전략)
7. [확장성 고려](#7-확장성-고려)
8. [데이터 품질 규칙](#8-데이터-품질-규칙)

---

## 1. PDF 원문 구조 매핑

### 1.1 CFRA Stock Report (9페이지)

| 페이지 | 섹션 | 데이터 엔티티 | 현재 파싱 여부 |
|--------|------|--------------|---------------|
| **P1** | Header | ticker, exchange, company_name, report_date, S&P 500 멤버십 | ✅ |
| | Recommendation | recommendation (BUY/HOLD/SELL 등), STARS (★1-5) | ✅ |
| | Price & Target | current_price, price_date, target_price, currency, investment_style | ✅ |
| | Analyst | analyst_name (e.g., "Angelo Zino, CFA") | ✅ |
| | GICS | gics_sector, gics_sub_industry | ✅ |
| | Key Stock Statistics | 52wk range, trailing EPS/P/E, oper EPS estimates (2yr), market cap, beta, yield, dividend rate, shares outstanding, CAGR, institutional ownership, quality ranking | ✅ |
| | Price Performance | 차트 (비구조화 — 이미지) | ❌ 불가 |
| | Risk Assessment | LOW/MEDIUM/HIGH + 서술 텍스트 | ⚠️ 추론 기반 |
| | Revenue/Earnings Data | 연간/분기 매출(Million USD) — 2개 연도 실적 + 1개 연도 추정 | ✅ |
| | Highlights & Rationale | 2개 텍스트 섹션 (2열 레이아웃) | ⚠️ 분리 불완전 |
| **P2** | Business Summary | 사업 개요 텍스트 (좌측) | ✅ |
| | Corporate Info | investor contact, office address, phone, fax, website | ❌ 미수집 |
| | Officers | 임원 목록 (이름, 직함) | ❌ 미수집 |
| **P3** | Quantitative Evaluations | fair_value_rank (1-5), fair_value_calculation (USD), volatility, technical_eval, insider_activity | ✅ |
| | Expanded Ratio Analysis | Price/Sales, Price/EBITDA, Price/Pretax, P/E Ratio — 4개년 | ⚠️ 일부만 |
| | Key Growth Rates | Net Income growth (1/3/5yr), Sales growth (1/3/5yr) | ❌ 미수집 |
| | Ratio Analysis Averages | Net Margin, LT Debt/Cap, ROE — 연평균 | ❌ 미수집 |
| | Per Share Data (10yr) | Tangible BV, FCF, EPS, Normalized EPS, Dividends, Payout Ratio, Price High/Low, P/E High/Low | ⚠️ EPS만 |
| | **Balance Sheet (10yr)** | Cash, Current Assets, Total Assets, Current Liab, LT Debt, Total Capital, CapEx, CFO, Current Ratio, LTD/Cap%, NI/Rev%, ROA%, ROE% | ✅ |
| | Income Statement (10yr) | Revenue, Operating Income, Depreciation, Interest Expense, Pretax Income, Tax Rate, Net Income, S&P Core EPS | ❌ 미수집 |
| **P4** | Sub-Industry Outlook | 산업 전망 텍스트 + 차트 | ✅ 텍스트만 |
| | Industry Performance | GICS 섹터/서브인더스트리 5년 차트 | ❌ 이미지 |
| **P5** | Analyst Research Notes | 날짜, 타임스탬프, 제목, 주가, 행동(maintain/upgrade 등), 본문, 애널리스트명 | ✅ |
| **P6** | Wall Street Consensus | Buy/Hold/Sell 분포 (현재/1M/3M 전), FY EPS 추정 (avg/high/low/count), 분기 추정 | ❌ 미수집 |
| **P7-9** | Glossary & Disclosures | 약어, 방법론, 법적 고지 | N/A (비데이터) |

### 1.2 Zacks Equity Research (9페이지)

| 페이지 | 섹션 | 데이터 엔티티 | 현재 파싱 여부 |
|--------|------|--------------|---------------|
| **P1** | Header | company_name, ticker, report_date | ✅ |
| | Recommendation | recommendation (Outperform/Neutral/Underperform), prior_recommendation | ✅ |
| | Price & Target | current_price, price_date, target_price | ✅ |
| | Zacks Rank | rank (1-5), rank_label (Strong Buy~Strong Sell) | ✅ |
| | Style Scores | VGM, Value, Growth, Momentum (A-F) | ✅ |
| | Summary | 요약 텍스트 | ✅ |
| | Data Overview | 52wk range, 20d avg volume, market cap, YTD change, beta, dividend/yield, industry, industry rank, last surprise(EPS/Sales), expected report date, ESP, P/E TTM/F1, PEG | ⚠️ 일부 |
| | Sales Estimates | 3개년 × (Q1-Q4 + Annual), A/E 마커 | ✅ |
| | EPS Estimates | 3개년 × (Q1-Q4 + Annual), A/E 마커 | ✅ |
| **P2** | Overview | 사업 개요 + 매출 비중 파이차트 데이터 | ⚠️ 텍스트만 |
| | Revenue Breakdown | 제품별/지역별 매출 비중 (%) | ❌ 미수집 |
| **P3** | Reasons To Buy | 매수 근거 텍스트 + 사이드바 하이라이트 | ✅ 텍스트만 |
| **P4** | Reasons To Sell | 매도 근거 텍스트 + 사이드바 하이라이트 | ✅ 텍스트만 |
| **P5** | Last Earnings Report | 실적 요약, EPS/Sales surprise%, 분기 EPS/매출 상세 | ✅ 텍스트만 |
| | Margin Data | gross margin, operating margin (bps 변화) | ❌ 미수집 |
| **P6** | Recent News | 뉴스 목록 (날짜 + 내용) — 최근 6-12개월 | ❌ 미수집 |
| **P7** | Valuation | 6개월/12개월 가격 변화, Forward P/E, 5yr P/E range, median | ⚠️ 일부 |
| **P8** | Industry Analysis | Top Peers 목록 (ticker, name, recommendation) | ✅ |
| | Industry Comparison | 30+ 지표 비교 테이블 (AAPL vs Industry vs S&P 500 vs Peers) | ⚠️ 부분적 |
| | Comparison Metrics | Mkt Cap, Div Yield, EV/EBITDA, PEG, P/B, P/CF, P/E, P/S, Earnings Yield, D/E, Cash/Share, Hist/Proj EPS Growth, Current Ratio, Net Margin, ROE, Sales/Assets 등 | ❌ 대부분 미수집 |
| **P9** | Rating System | 방법론 설명 | N/A (비데이터) |

### 1.3 누락 데이터 요약

**고가치 누락 항목 (수집 우선순위 HIGH):**

| 항목 | 소스 | 가치 |
|------|------|------|
| Wall Street Consensus (Buy/Hold/Sell 분포) | CFRA P6 | 시장 심리 지표 |
| Consensus EPS Estimates (avg/high/low/count) | CFRA P6 | 밸류에이션 핵심 |
| Income Statement 10yr | CFRA P3 | 수익성 트렌드 |
| Per Share Data 10yr (FCF, Dividends, Payout) | CFRA P3 | 배당/현금흐름 분석 |
| Revenue Breakdown (제품별/지역별) | Zacks P2 | 사업 다각화 분석 |
| Recent News | Zacks P6 | 이벤트 트래킹 |
| Industry Comparison 전체 지표 | Zacks P8 | 피어 벤치마킹 |
| 20일 평균 거래량 | Zacks P1 | 유동성 지표 |
| Earnings ESP | Zacks P1 | 서프라이즈 예측 |
| Expected Report Date | Zacks P1 | 실적 캘린더 |

---

## 2. 현재 스키마 평가

### 2.1 ERD 요약 (현재)

```
stock_profiles (14 rows)
  ├─< stock_reports (22 rows) — FK: stock_profile_id
  │     ├── stock_key_stats (22 rows, 1:1) — FK: stock_report_id
  │     └─< stock_peers (70 rows) — FK: stock_report_id
  ├─< stock_financials (395 rows) — FK: stock_profile_id
  ├─< stock_balance_sheets (115 rows) — FK: stock_profile_id
  └─< stock_analyst_notes (84 rows) — FK: stock_profile_id

watchlists ─< watchlist_items ─> stock_profiles
alerts (ticker 기반, FK 없음)
api_keys (독립)
```

### 2.2 정규화 수준 평가

**현재: 2NF~3NF 사이, 비정규화 혼재**

| 테이블 | 정규화 | 문제 |
|--------|--------|------|
| stock_profiles | 2NF | ticker+exchange 유니크인데 exchange가 소스마다 다름 (UNKNOWN vs NasdaqGS) |
| stock_reports | 3NF | 양호하나, CFRA/Zacks 공통 필드와 소스별 필드가 한 테이블에 혼재 |
| stock_key_stats | 2NF | CFRA와 Zacks의 지표가 한 테이블에 통합 — 소스별 NULL 범람 |
| stock_financials | 3NF | 양호. period_type + is_estimate로 실적/추정 구분 |
| stock_balance_sheets | 3NF | 양호하나 CFRA만 제공하는 데이터 — 소스 컬럼 없음 |
| stock_peers | 2NF | CFRA/Zacks 피어가 한 테이블, 구조가 다름 |
| stock_analyst_notes | 3NF | 양호 |
| alerts | 1NF | ticker 문자열 기반, stock_profiles FK 없음 |

### 2.3 관계 설계 평가

**장점:**
- stock_profiles → stock_reports → stock_key_stats 계층이 논리적
- stock_financials가 stock_profile_id에 직접 연결 (리포트 독립적 시계열)
- UNIQUE 제약조건이 적절히 설정됨

**단점:**
- `stock_key_stats`가 `stock_report_id`에 종속 → 리포트 없이 key stats 접근 불가
- `stock_balance_sheets`에 소스(source) 컬럼 없음 → CFRA/Zacks 데이터 구분 불가
- `alerts.ticker`가 FK가 아닌 문자열 → 참조 무결성 없음
- `stock_peers`가 `stock_report_id`에 종속 → 피어 관계의 시계열 추적이 리포트에 묶임

### 2.4 타입 설계 평가

| 항목 | 현재 | 평가 |
|------|------|------|
| 금액/비율 | `NUMERIC` | ✅ 정확 (DECIMAL이 아닌 무제한 NUMERIC) |
| 날짜 | `DATE` / `TIMESTAMP` | ⚠️ 혼재 (with/without timezone) |
| JSON 필드 | `JSON` (alerts) vs `JSONB` (나머지) | ⚠️ alerts만 JSON — 인덱싱 불가 |
| 텍스트 | `TEXT` / `VARCHAR` | ✅ 적절 |
| Boolean | `BOOLEAN` | ✅ |

---

## 3. 문제점 분석

### 3.1 🔴 Critical: 프로파일 중복

```sql
SELECT id, ticker, exchange FROM stock_profiles WHERE ticker='AAPL';
-- id=84, ticker=AAPL, exchange=UNKNOWN   ← Zacks 파서 (exchange 미파싱)
-- id=106, ticker=AAPL, exchange=NasdaqGS ← CFRA 파서
```

**원인:** `uq_profile_ticker_exchange` 유니크 제약이 `(ticker, exchange)` 조합이라 같은 종목이 exchange가 다르면 별도 레코드로 생성됨. Zacks 파서가 exchange를 파싱하지 않아 'UNKNOWN'이 삽입됨.

**영향:**
- 같은 종목의 CFRA/Zacks 데이터가 서로 다른 profile_id에 연결
- 재무 데이터가 분산 → 통합 조회 불가
- watchlist에 같은 종목 두 번 추가 가능

### 3.2 🔴 Critical: 소스 구분 부재 (Balance Sheets)

`stock_balance_sheets`에 `source` 컬럼이 없음. 현재 CFRA에서만 데이터가 들어오지만, Zacks도 재무 데이터를 제공. 향후 데이터 출처 추적이 불가능.

### 3.3 🟡 Major: Key Stats 테이블의 소스별 NULL 범람

```
stock_key_stats 컬럼 수: 33개
CFRA 전용 필드: quality_ranking, oper_eps_current_e, oper_eps_next_e, pe_on_oper_eps_current
Zacks 전용 필드: pe_forward_12m, ps_forward_12m, ev_ebitda, peg_ratio, price_to_book,
                  price_to_cashflow, debt_equity, cash_per_share, earnings_yield_pct,
                  valuation_multiples
공통 필드: week_52_high/low, beta, market_cap_b, dividend_yield_pct, dividend_rate
```

CFRA 리포트의 key_stats 레코드에서 Zacks 전용 10개 필드는 항상 NULL. 그 반대도 마찬가지. **33개 컬럼 중 약 40%가 항상 NULL** — 스토리지 낭비이자 스키마 가독성 저하.

### 3.4 🟡 Major: Financials 중복 가능성

`uq_financial_profile_year_quarter_estimate`가 `(stock_profile_id, fiscal_year, fiscal_quarter, is_estimate)` 조합이지만, 같은 종목에 대해 CFRA와 Zacks가 다른 EPS 추정치를 제공할 수 있음. 현재는 profile 중복(3.1)으로 우연히 분리되지만, 프로파일 통합 시 충돌 발생.

### 3.5 🟡 Major: Peers 테이블 설계 혼란

- CFRA 피어: 상세 비교 데이터 (price, market_cap, pe_ratio, fair_value 등)
- Zacks 피어: 추천/랭크 + 30개 지표 비교 (Industry Comparison 테이블)
- 두 소스의 피어 데이터 구조가 근본적으로 다른데 같은 테이블에 통합

### 3.6 🟢 Minor: 타임스탬프 일관성

```
stock_profiles.created_at: TIMESTAMP WITH TIME ZONE
alerts.created_at: TIMESTAMP WITHOUT TIME ZONE
```

동일 시스템 내에서 timezone aware/naive가 혼재. 서버 timezone 설정에 따라 데이터 해석이 달라질 수 있음.

### 3.7 🟢 Minor: organization_id 미활용

대부분의 테이블에 `organization_id` 컬럼이 있으나 어떤 테이블에도 `organizations` 테이블이 없고, 전부 NULL. 멀티테넌시 준비인 것 같으나 현재는 데드 컬럼.

---

## 4. 이상적 스키마 제안

### 4.1 설계 원칙

1. **단일 종목 = 단일 프로파일** — ticker 기준, exchange는 속성
2. **소스 독립적 시계열** — 모든 시계열 데이터에 source 컬럼
3. **소스별 테이블 분리 vs 통합** — 공통 구조는 통합, 소스 고유 데이터는 JSONB
4. **이력 보존** — UPDATE 대신 INSERT (SCD Type 2 또는 시계열)
5. **확장성 우선** — 파티셔닝, 적절한 인덱스, JSONB 활용

### 4.2 제안 ERD

```
companies (종목 마스터)
  ├─< reports (리포트 메타)
  │     ├── report_ratings (추천/등급)
  │     ├── report_key_stats (핵심 지표)
  │     └── report_text_sections (텍스트 블록)
  ├─< financials (재무 시계열)
  ├─< balance_sheets (대차대조표 시계열)
  ├─< income_statements (손익계산서 시계열) ← NEW
  ├─< per_share_data (주당 지표 시계열) ← NEW
  ├─< analyst_notes (애널리스트 노트)
  ├─< consensus_estimates (컨센서스) ← NEW
  ├─< peer_comparisons (피어 비교)
  └─< company_events (뉴스/이벤트) ← NEW

watchlists ─< watchlist_items ─> companies
alerts ─> companies (FK)
```

### 4.3 전체 DDL

```sql
-- ============================================================
-- Stock Report Hub — 제안 스키마 v2.0
-- ============================================================

-- 1. 종목 마스터 (구 stock_profiles)
-- 하나의 종목 = 하나의 레코드. ticker가 자연키.
CREATE TABLE companies (
    id          BIGSERIAL PRIMARY KEY,
    ticker      VARCHAR(10) NOT NULL UNIQUE,  -- 단일 유니크 (exchange 제외)
    company_name VARCHAR(200),
    exchange    VARCHAR(20),                   -- 주 상장 거래소
    currency    VARCHAR(3) DEFAULT 'USD',
    
    -- GICS 분류 (CFRA 소스)
    gics_sector       VARCHAR(100),
    gics_sub_industry VARCHAR(100),
    
    -- Zacks 분류
    zacks_industry    VARCHAR(100),
    zacks_industry_rank VARCHAR(100),          -- "Bottom 5% (231 out of 243)"
    
    -- 기업 기본 정보
    investment_style  VARCHAR(30),             -- "Large-Cap Growth"
    website           VARCHAR(200),
    description       TEXT,
    domicile          VARCHAR(50),
    founded_year      SMALLINT,
    employees         INTEGER,
    
    -- 구조화 데이터 (변경 빈도 낮음)
    officers          JSONB,                   -- [{name, title}, ...]
    board_members     JSONB,
    segments          JSONB,                   -- {product: {iPhone: 50.4, ...}, geo: {Americas: 42.9, ...}}
    index_memberships VARCHAR(50)[],           -- {'S&P 500', 'NASDAQ-100'}
    
    -- 메타
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE companies IS '종목 마스터. ticker 기준 단일 레코드. CFRA/Zacks 공통.';
COMMENT ON COLUMN companies.segments IS '매출 비중. {product: {name: pct}, geo: {region: pct}}';


-- 2. 리포트 메타 (구 stock_reports의 핵심)
CREATE TABLE reports (
    id              BIGSERIAL PRIMARY KEY,
    company_id      BIGINT NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    source          VARCHAR(10) NOT NULL CHECK (source IN ('CFRA', 'Zacks')),
    report_date     DATE NOT NULL,
    
    -- 가격 스냅샷
    current_price   NUMERIC(12,4),
    price_date      DATE,
    target_price    NUMERIC(12,4),
    
    -- 애널리스트
    analyst_name    VARCHAR(100),
    
    -- PDF 원본
    raw_pdf_path    VARCHAR(500),
    
    -- 메타
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    UNIQUE (company_id, source, report_date)
);

COMMENT ON TABLE reports IS '개별 리포트 메타데이터. 종목×소스×날짜 유니크.';


-- 3. 리포트 추천/등급 (소스별 구조가 다른 부분)
CREATE TABLE report_ratings (
    id              BIGSERIAL PRIMARY KEY,
    report_id       BIGINT NOT NULL REFERENCES reports(id) ON DELETE CASCADE UNIQUE,
    
    -- CFRA 전용
    recommendation  VARCHAR(20),               -- BUY, STRONG BUY, HOLD, SELL
    stars_rating    SMALLINT CHECK (stars_rating BETWEEN 1 AND 5),
    risk_assessment VARCHAR(10),               -- LOW, MEDIUM, HIGH
    fair_value      NUMERIC(12,4),
    fair_value_rank SMALLINT CHECK (fair_value_rank BETWEEN 1 AND 5),
    volatility      VARCHAR(10),               -- LOW, AVERAGE, HIGH
    technical_eval  VARCHAR(10),               -- BULLISH, NEUTRAL, BEARISH
    insider_activity VARCHAR(15),              -- FAVORABLE, NEUTRAL, UNFAVORABLE
    investment_style VARCHAR(30),
    quality_ranking VARCHAR(5),                -- A+, A, B+, etc.
    
    -- Zacks 전용
    zacks_rank      SMALLINT CHECK (zacks_rank BETWEEN 1 AND 5),
    zacks_rank_label VARCHAR(20),              -- Strong Buy, Buy, Hold, Sell, Strong Sell
    prior_recommendation VARCHAR(20),
    style_scores    JSONB,                     -- {vgm: "B", value: "D", growth: "A", momentum: "B"}
    
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE report_ratings IS '리포트별 투자 의견/등급. CFRA와 Zacks의 등급 체계가 다르므로 모든 필드 포함.';


-- 4. 핵심 지표 (구 stock_key_stats)
CREATE TABLE report_key_stats (
    id              BIGSERIAL PRIMARY KEY,
    report_id       BIGINT NOT NULL REFERENCES reports(id) ON DELETE CASCADE UNIQUE,
    
    -- 가격 관련
    week_52_high    NUMERIC(12,4),
    week_52_low     NUMERIC(12,4),
    beta            NUMERIC(6,3),
    avg_volume_20d  BIGINT,                    -- ← NEW: 20일 평균 거래량
    ytd_price_change_pct NUMERIC(8,4),         -- ← NEW: YTD 변화율
    
    -- 수익 관련
    trailing_12m_eps    NUMERIC(12,4),
    trailing_12m_pe     NUMERIC(10,2),
    oper_eps_current_e  NUMERIC(12,4),         -- CFRA: 당해 Operating EPS 추정
    oper_eps_next_e     NUMERIC(12,4),         -- CFRA: 차년 Operating EPS 추정
    pe_on_oper_eps      NUMERIC(10,2),         -- CFRA: P/E on Operating EPS
    pe_forward_12m      NUMERIC(10,2),         -- Zacks: Forward P/E (F1)
    
    -- 시가총액/유통
    market_cap_b        NUMERIC(12,4),
    shares_outstanding_m NUMERIC(12,2),
    institutional_ownership_pct NUMERIC(6,2),
    
    -- 배당
    dividend_yield_pct  NUMERIC(6,3),
    dividend_rate       NUMERIC(8,4),
    
    -- 성장
    eps_cagr_3yr_pct    NUMERIC(8,2),
    
    -- 밸류에이션 멀티플
    price_to_sales      NUMERIC(10,2),
    price_to_ebitda     NUMERIC(10,2),
    price_to_pretax     NUMERIC(10,2),
    price_to_book       NUMERIC(10,2),
    price_to_cashflow   NUMERIC(10,2),
    ev_ebitda           NUMERIC(10,2),
    peg_ratio           NUMERIC(8,3),
    
    -- 재무 건전성
    debt_equity         NUMERIC(10,4),
    cash_per_share      NUMERIC(12,4),
    earnings_yield_pct  NUMERIC(8,4),
    
    -- 마진/수익률 (연평균)
    net_margin_1yr_pct  NUMERIC(8,2),
    net_margin_3yr_pct  NUMERIC(8,2),
    sales_growth_1yr_pct NUMERIC(8,2),
    sales_growth_3yr_pct NUMERIC(8,2),
    
    -- Zacks: Earnings ESP & 서프라이즈
    earnings_esp_pct    NUMERIC(8,4),          -- ← NEW
    last_eps_surprise_pct NUMERIC(8,4),        -- ← NEW
    last_sales_surprise_pct NUMERIC(8,4),      -- ← NEW
    expected_report_date DATE,                 -- ← NEW
    
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE report_key_stats IS '리포트 시점의 핵심 지표 스냅샷. CFRA/Zacks 공통 + 소스별 필드 통합.';


-- 5. 텍스트 섹션 (구 stock_reports의 텍스트 필드들)
CREATE TABLE report_text_sections (
    id          BIGSERIAL PRIMARY KEY,
    report_id   BIGINT NOT NULL REFERENCES reports(id) ON DELETE CASCADE,
    section_type VARCHAR(30) NOT NULL,
    -- section_type enum:
    --   highlights, investment_rationale, business_summary,
    --   sub_industry_outlook, reasons_to_buy, reasons_to_sell,
    --   last_earnings_summary, outlook, summary
    content     TEXT NOT NULL,
    
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    UNIQUE (report_id, section_type)
);

COMMENT ON TABLE report_text_sections IS '리포트 텍스트 섹션. EAV 패턴으로 유연하게 섹션 추가 가능.';


-- 6. 재무 데이터 (구 stock_financials — 개선)
CREATE TABLE financials (
    id              BIGSERIAL PRIMARY KEY,
    company_id      BIGINT NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    source          VARCHAR(10) NOT NULL CHECK (source IN ('CFRA', 'Zacks')),
    fiscal_year     SMALLINT NOT NULL,
    fiscal_quarter  SMALLINT CHECK (fiscal_quarter BETWEEN 1 AND 4),
    period_type     VARCHAR(10) NOT NULL CHECK (period_type IN ('annual', 'quarterly')),
    is_estimate     BOOLEAN NOT NULL DEFAULT FALSE,
    
    -- P&L
    revenue             NUMERIC(15,2),         -- Million USD
    operating_income    NUMERIC(15,2),
    pretax_income       NUMERIC(15,2),
    net_income          NUMERIC(15,2),
    depreciation        NUMERIC(15,2),
    interest_expense    NUMERIC(15,2),         -- ← NEW
    effective_tax_rate  NUMERIC(6,3),
    
    -- Per Share
    eps                 NUMERIC(10,4),
    eps_normalized      NUMERIC(10,4),
    
    -- Margins
    gross_margin_pct    NUMERIC(6,2),
    operating_margin_pct NUMERIC(6,2),
    
    -- Segments (JSONB for flexibility)
    segment_revenues    JSONB,                 -- {iPhone: 85270, Services: 30010, ...}
    
    -- Surprise (Zacks)
    eps_surprise_pct    NUMERIC(8,4),
    sales_surprise_pct  NUMERIC(8,4),
    
    -- 메타
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    UNIQUE (company_id, source, fiscal_year, fiscal_quarter, is_estimate)
);

COMMENT ON TABLE financials IS '재무 시계열. 소스별로 별도 레코드. CFRA/Zacks의 추정치가 다를 수 있으므로 source 포함.';


-- 7. 대차대조표 (구 stock_balance_sheets — 소스 추가)
CREATE TABLE balance_sheets (
    id              BIGSERIAL PRIMARY KEY,
    company_id      BIGINT NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    source          VARCHAR(10) NOT NULL DEFAULT 'CFRA' CHECK (source IN ('CFRA', 'Zacks')),
    fiscal_year     SMALLINT NOT NULL,
    
    -- 자산
    cash                NUMERIC(15,2),
    current_assets      NUMERIC(15,2),
    total_assets        NUMERIC(15,2),
    
    -- 부채
    current_liabilities NUMERIC(15,2),
    long_term_debt      NUMERIC(15,2),
    total_capital       NUMERIC(15,2),
    
    -- 현금흐름
    capital_expenditures NUMERIC(15,2),
    cash_from_operations NUMERIC(15,2),
    
    -- 비율
    current_ratio           NUMERIC(8,3),
    ltd_to_cap_pct          NUMERIC(6,2),
    net_income_to_revenue_pct NUMERIC(6,2),
    return_on_assets_pct    NUMERIC(8,2),
    return_on_equity_pct    NUMERIC(8,2),
    
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    UNIQUE (company_id, source, fiscal_year)
);


-- 8. 손익계산서 (NEW — CFRA P3에서 추출 가능)
CREATE TABLE income_statements (
    id              BIGSERIAL PRIMARY KEY,
    company_id      BIGINT NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    source          VARCHAR(10) NOT NULL DEFAULT 'CFRA',
    fiscal_year     SMALLINT NOT NULL,
    
    revenue             NUMERIC(15,2),
    operating_income    NUMERIC(15,2),
    depreciation        NUMERIC(15,2),
    interest_expense    NUMERIC(15,2),
    pretax_income       NUMERIC(15,2),
    effective_tax_rate  NUMERIC(6,3),
    net_income          NUMERIC(15,2),
    sp_core_eps         NUMERIC(10,4),         -- S&P Core EPS (CFRA 고유)
    
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    UNIQUE (company_id, source, fiscal_year)
);

COMMENT ON TABLE income_statements IS 'CFRA P3의 10년 손익계산서. balance_sheets와 동일 기간.';


-- 9. 주당 지표 (NEW — CFRA P3의 Per Share Data)
CREATE TABLE per_share_data (
    id              BIGSERIAL PRIMARY KEY,
    company_id      BIGINT NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    source          VARCHAR(10) NOT NULL DEFAULT 'CFRA',
    fiscal_year     SMALLINT NOT NULL,
    
    tangible_book_value NUMERIC(10,4),
    free_cash_flow      NUMERIC(10,4),
    earnings            NUMERIC(10,4),
    earnings_normalized NUMERIC(10,4),
    dividends           NUMERIC(10,4),
    payout_ratio_pct    NUMERIC(6,2),
    price_high          NUMERIC(12,4),
    price_low           NUMERIC(12,4),
    pe_high             NUMERIC(8,2),
    pe_low              NUMERIC(8,2),
    
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    UNIQUE (company_id, source, fiscal_year)
);

COMMENT ON TABLE per_share_data IS 'CFRA P3의 10년 주당 데이터. 배당, FCF, EPS 히스토리.';


-- 10. 컨센서스 추정 (NEW — CFRA P6)
CREATE TABLE consensus_estimates (
    id              BIGSERIAL PRIMARY KEY,
    company_id      BIGINT NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    report_id       BIGINT REFERENCES reports(id) ON DELETE SET NULL,
    snapshot_date   DATE NOT NULL,             -- 스냅샷 시점
    
    -- Analyst Recommendations Distribution
    buy_count       SMALLINT,
    buy_hold_count  SMALLINT,
    hold_count      SMALLINT,
    weak_hold_count SMALLINT,
    sell_count      SMALLINT,
    no_opinion_count SMALLINT,
    total_analysts  SMALLINT,
    
    -- EPS Consensus
    fiscal_year     SMALLINT NOT NULL,
    eps_avg         NUMERIC(10,4),
    eps_high        NUMERIC(10,4),
    eps_low         NUMERIC(10,4),
    eps_est_count   SMALLINT,
    estimated_pe    NUMERIC(10,2),
    
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    UNIQUE (company_id, snapshot_date, fiscal_year)
);

COMMENT ON TABLE consensus_estimates IS 'CFRA P6 Wall Street 컨센서스. 시계열 보관으로 추정치 변화 추적.';


-- 11. 애널리스트 노트 (기존 유지 + 개선)
CREATE TABLE analyst_notes (
    id              BIGSERIAL PRIMARY KEY,
    company_id      BIGINT NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    source          VARCHAR(10) NOT NULL DEFAULT 'CFRA',
    published_at    TIMESTAMPTZ,
    analyst_name    VARCHAR(100),
    title           VARCHAR(500),
    stock_price_at_note NUMERIC(12,4),
    action          VARCHAR(20),               -- maintain, upgrade, downgrade, initiate
    target_price    NUMERIC(12,4),
    content         TEXT,
    
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE analyst_notes IS '애널리스트 리서치 노트. CFRA P5에서 추출.';


-- 12. 피어 비교 (재설계)
CREATE TABLE peer_comparisons (
    id              BIGSERIAL PRIMARY KEY,
    report_id       BIGINT NOT NULL REFERENCES reports(id) ON DELETE CASCADE,
    peer_ticker     VARCHAR(10) NOT NULL,
    peer_name       VARCHAR(200),
    
    -- 공통 메트릭
    recommendation  VARCHAR(20),
    rank            SMALLINT,
    
    -- 상세 비교 지표 (소스에 따라 다른 구조 → JSONB)
    metrics         JSONB,
    -- CFRA: {exchange, recent_price, market_cap_m, price_chg_30d_pct, pe_ratio, fair_value, yield_pct, roe_pct, ltd_to_cap_pct}
    -- Zacks: {market_cap, div_yield, ev_ebitda, peg, pb, pcf, pe_f1, ps, earnings_yield, de, ...30+ metrics}
    
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    UNIQUE (report_id, peer_ticker)
);

COMMENT ON TABLE peer_comparisons IS '피어 비교. 소스별 상세 지표는 metrics JSONB에 저장.';


-- 13. 기업 이벤트/뉴스 (NEW — Zacks P6)
CREATE TABLE company_events (
    id          BIGSERIAL PRIMARY KEY,
    company_id  BIGINT NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    source      VARCHAR(10) NOT NULL DEFAULT 'Zacks',
    event_date  DATE,
    headline    TEXT NOT NULL,
    content     TEXT,
    
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    UNIQUE (company_id, source, event_date, headline)
);

COMMENT ON TABLE company_events IS 'Zacks P6 Recent News. 기업별 이벤트 타임라인.';


-- 14. 알림 (개선: FK 추가)
CREATE TABLE alerts (
    id          BIGSERIAL PRIMARY KEY,
    company_id  BIGINT NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    source      VARCHAR(10),
    alert_type  VARCHAR(30) NOT NULL,          -- rating_change, price_target_change, earnings_surprise
    field       VARCHAR(50),
    old_value   VARCHAR(100),
    new_value   VARCHAR(100),
    message     TEXT,
    metadata    JSONB,
    notified    BOOLEAN DEFAULT FALSE,
    notified_at TIMESTAMPTZ,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);


-- 15. 워치리스트 (기존 유지)
CREATE TABLE watchlists (
    id          BIGSERIAL PRIMARY KEY,
    name        VARCHAR(100) NOT NULL,
    is_default  BOOLEAN DEFAULT FALSE,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE watchlist_items (
    id              BIGSERIAL PRIMARY KEY,
    watchlist_id    BIGINT NOT NULL REFERENCES watchlists(id) ON DELETE CASCADE,
    company_id      BIGINT NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    sources         VARCHAR(20),               -- 'CFRA,Zacks'
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    UNIQUE (watchlist_id, company_id)
);


-- 16. API 키 (기존 유지)
CREATE TABLE api_keys (
    id              BIGSERIAL PRIMARY KEY,
    key_hash        VARCHAR(64) NOT NULL UNIQUE,
    key_prefix      VARCHAR(10) NOT NULL,
    name            VARCHAR(100) NOT NULL,
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_used_at    TIMESTAMPTZ,
    revoked_at      TIMESTAMPTZ
);
```

### 4.4 설계 결정 근거

| 결정 | 근거 |
|------|------|
| `companies.ticker` UNIQUE (exchange 제외) | 현재 미국 주식만 대상. 같은 ticker의 다중 상장은 없음. exchange는 속성. |
| `financials`에 `source` 컬럼 추가 | CFRA와 Zacks의 EPS 추정치가 다를 수 있음 (AAPL: CFRA $8.55 vs Zacks $8.41) |
| `report_text_sections` EAV 패턴 | 텍스트 섹션 종류가 소스마다 다르고 향후 추가 가능. TEXT 필드 10개를 한 행에 넣는 것보다 유연. |
| `peer_comparisons.metrics` JSONB | CFRA는 8개 지표, Zacks는 30+ 지표. 스키마로 정규화하면 60개 컬럼. JSONB가 실용적. |
| `consensus_estimates` 별도 테이블 | 시계열로 "컨센서스 변화"를 추적 — 가장 가치 있는 데이터 중 하나 |
| `organization_id` 제거 | 현재 멀티테넌시 미사용. YAGNI 원칙. 필요 시 추가 가능. |

---

## 5. 마이그레이션 전략

### 5.1 단계별 계획

```
Phase 1: 스키마 생성 (다운타임 없음)
  - 새 테이블을 기존 DB에 추가 (이름 충돌 없음: companies vs stock_profiles)
  - 데이터 마이그레이션 스크립트 작성 및 테스트

Phase 2: 데이터 마이그레이션 (트랜잭션)
  - stock_profiles → companies (중복 AAPL 병합)
  - stock_reports → reports + report_ratings + report_text_sections
  - stock_key_stats → report_key_stats
  - stock_financials → financials (source 추가)
  - stock_balance_sheets → balance_sheets (source='CFRA' 추가)
  - stock_peers → peer_comparisons
  - stock_analyst_notes → analyst_notes
  - alerts → alerts (ticker → company_id 변환)

Phase 3: 파서 코드 업데이트
  - cfra_parser.py: 새 테이블 매핑
  - zacks_parser.py: 새 테이블 매핑
  - 새 섹션 파싱 추가 (consensus, income_statement, per_share_data, events)

Phase 4: 검증 & 전환
  - 신/구 테이블 데이터 비교 검증
  - API 엔드포인트 업데이트
  - 구 테이블 rename → _deprecated

Phase 5: 정리
  - _deprecated 테이블 삭제
  - Alembic 마이그레이션 기록
```

### 5.2 핵심 마이그레이션 SQL

```sql
-- Phase 2: 데이터 마이그레이션

BEGIN;

-- 1. companies: 중복 프로파일 병합
INSERT INTO companies (id, ticker, company_name, exchange, currency, gics_sector, gics_sub_industry,
                       website, description, segments, officers, board_members, index_memberships,
                       created_at, updated_at)
SELECT DISTINCT ON (ticker)
    id, ticker, company_name,
    CASE WHEN exchange = 'UNKNOWN' THEN NULL ELSE exchange END,
    currency, gics_sector, gics_sub_industry,
    website, description, segments, officers, board_members, index_memberships,
    created_at, updated_at
FROM stock_profiles
ORDER BY ticker, 
    CASE WHEN exchange = 'UNKNOWN' THEN 1 ELSE 0 END,  -- 실제 exchange 우선
    id DESC;  -- 최신 레코드 우선

-- 프로파일 ID 매핑 (구 → 신)
CREATE TEMP TABLE profile_map AS
SELECT sp.id AS old_id, c.id AS new_id
FROM stock_profiles sp
JOIN companies c ON c.ticker = sp.ticker;

-- 2. reports
INSERT INTO reports (id, company_id, source, report_date, current_price, price_date,
                     target_price, analyst_name, raw_pdf_path, created_at, updated_at)
SELECT sr.id, pm.new_id, sr.source, sr.report_date, sr.current_price, sr.price_date,
       sr.target_price, sr.analyst_name, sr.raw_pdf_path, sr.created_at, sr.updated_at
FROM stock_reports sr
JOIN profile_map pm ON pm.old_id = sr.stock_profile_id;

-- 3. report_ratings
INSERT INTO report_ratings (report_id, recommendation, stars_rating, risk_assessment,
    fair_value, fair_value_rank, volatility, technical_eval, insider_activity,
    investment_style, quality_ranking, zacks_rank, zacks_rank_label,
    prior_recommendation, style_scores)
SELECT sr.id,
    sr.recommendation, sr.stars_rating, sr.risk_assessment,
    sr.fair_value, sr.fair_value_rank, sr.volatility, sr.technical_eval,
    sr.insider_activity, sr.investment_style,
    sk.quality_ranking, sr.zacks_rank, sr.zacks_rank_label,
    sr.prior_recommendation, sr.style_scores
FROM stock_reports sr
LEFT JOIN stock_key_stats sk ON sk.stock_report_id = sr.id;

-- 4. report_text_sections
INSERT INTO report_text_sections (report_id, section_type, content)
SELECT id, 'highlights', highlights FROM stock_reports WHERE highlights IS NOT NULL
UNION ALL
SELECT id, 'investment_rationale', investment_rationale FROM stock_reports WHERE investment_rationale IS NOT NULL
UNION ALL
SELECT id, 'business_summary', business_summary FROM stock_reports WHERE business_summary IS NOT NULL
UNION ALL
SELECT id, 'sub_industry_outlook', sub_industry_outlook FROM stock_reports WHERE sub_industry_outlook IS NOT NULL
UNION ALL
SELECT id, 'reasons_to_buy', reasons_to_buy FROM stock_reports WHERE reasons_to_buy IS NOT NULL
UNION ALL
SELECT id, 'reasons_to_sell', reasons_to_sell FROM stock_reports WHERE reasons_to_sell IS NOT NULL
UNION ALL
SELECT id, 'last_earnings_summary', last_earnings_summary FROM stock_reports WHERE last_earnings_summary IS NOT NULL
UNION ALL
SELECT id, 'outlook', outlook FROM stock_reports WHERE outlook IS NOT NULL;

-- 5. financials (source 추가 — 기존 데이터는 source 결정 필요)
INSERT INTO financials (company_id, source, fiscal_year, fiscal_quarter, period_type,
    is_estimate, revenue, operating_income, pretax_income, net_income, eps, eps_normalized,
    gross_margin_pct, operating_margin_pct, segment_revenues, eps_surprise_pct,
    sales_surprise_pct, depreciation, effective_tax_rate, created_at, updated_at)
SELECT pm.new_id,
    COALESCE(
        (SELECT sr.source FROM stock_reports sr WHERE sr.stock_profile_id = sf.stock_profile_id LIMIT 1),
        'CFRA'
    ),
    sf.fiscal_year, sf.fiscal_quarter, sf.period_type, sf.is_estimate,
    sf.revenue, sf.operating_income, sf.pretax_income, sf.net_income, sf.eps, sf.eps_normalized,
    sf.gross_margin_pct, sf.operating_margin_pct, sf.segment_revenues, sf.eps_surprise_pct,
    sf.sales_surprise_pct, sf.depreciation, sf.effective_tax_rate, sf.created_at, sf.updated_at
FROM stock_financials sf
JOIN profile_map pm ON pm.old_id = sf.stock_profile_id;

COMMIT;
```

---

## 6. 인덱싱 전략

### 6.1 쿼리 패턴 분석

| 쿼리 패턴 | 빈도 | 현재 인덱스 | 제안 |
|-----------|------|------------|------|
| 종목별 최신 리포트 조회 | 매우 높음 | ❌ | `(company_id, report_date DESC)` |
| 티커로 종목 조회 | 높음 | ✅ ix_stock_profiles_ticker | `companies.ticker` UNIQUE |
| 소스별 리포트 필터 | 높음 | ❌ | `(source, report_date DESC)` |
| 특정 종목의 재무 시계열 | 높음 | ❌ | `(company_id, fiscal_year, fiscal_quarter)` |
| 실적/추정 필터 | 중간 | ❌ | `is_estimate` partial index |
| 알림 미통지 조회 | 중간 | ❌ | `(notified) WHERE notified = FALSE` |
| 피어 비교 조회 | 중간 | ❌ | `(report_id)` |
| 텍스트 검색 (비즈니스 서머리) | 낮음 | ❌ | GIN on `to_tsvector(content)` |

### 6.2 제안 인덱스 DDL

```sql
-- companies
CREATE UNIQUE INDEX idx_companies_ticker ON companies (ticker);

-- reports
CREATE INDEX idx_reports_company_date ON reports (company_id, report_date DESC);
CREATE INDEX idx_reports_source_date ON reports (source, report_date DESC);
CREATE INDEX idx_reports_date ON reports (report_date DESC);

-- financials
CREATE INDEX idx_financials_company_year ON financials (company_id, fiscal_year DESC, fiscal_quarter);
CREATE INDEX idx_financials_estimates ON financials (company_id, is_estimate, fiscal_year DESC)
    WHERE is_estimate = TRUE;

-- balance_sheets
CREATE INDEX idx_bs_company_year ON balance_sheets (company_id, fiscal_year DESC);

-- analyst_notes
CREATE INDEX idx_notes_company_date ON analyst_notes (company_id, published_at DESC);

-- consensus_estimates
CREATE INDEX idx_consensus_company_date ON consensus_estimates (company_id, snapshot_date DESC);

-- alerts
CREATE INDEX idx_alerts_unnotified ON alerts (created_at DESC) WHERE notified = FALSE;
CREATE INDEX idx_alerts_company ON alerts (company_id, created_at DESC);

-- text search (optional, for full-text search across reports)
CREATE INDEX idx_text_sections_fts ON report_text_sections 
    USING GIN (to_tsvector('english', content));
```

---

## 7. 확장성 고려

### 7.1 데이터 볼륨 예측

| 항목 | 현재 | 500종목 1년 | 500종목 5년 |
|------|------|------------|------------|
| companies | 14 | 500 | 500 |
| reports | 22 | 52,000 (주간×2소스) | 260,000 |
| financials | 395 | ~500K | ~2.5M |
| balance_sheets | 115 | ~50K | ~50K (10yr 고정) |
| analyst_notes | 84 | ~100K | ~500K |
| consensus_estimates | 0 | ~52K | ~260K |
| report_text_sections | 0 | ~300K | ~1.5M |
| **총 예상 디스크** | ~1MB | ~500MB | ~2.5GB |

### 7.2 파티셔닝 전략

**현재 규모에서는 불필요.** 500종목 5년 운영 시에도 2.5GB 수준으로 단일 파티션에서 충분히 처리 가능. 다만, 향후 성장 대비:

```sql
-- 3년 후 고려: reports 테이블 연도별 파티셔닝
-- CREATE TABLE reports (...) PARTITION BY RANGE (report_date);
-- CREATE TABLE reports_2026 PARTITION OF reports FOR VALUES FROM ('2026-01-01') TO ('2027-01-01');
```

### 7.3 데이터 보관 정책

| 데이터 | 보관 기간 | 전략 |
|--------|----------|------|
| companies | 영구 | soft delete (is_active flag) |
| reports | 영구 | 분석 가치 높음 |
| financials | 10년 (CFRA 기준) | 자연 윈도우 |
| analyst_notes | 5년 | 5년 이상 → archive 테이블 |
| alerts | 1년 | 통지 완료 후 90일 삭제 가능 |
| report_text_sections | 영구 | 리포트와 동일 수명 |

### 7.4 배치 업데이트 전략

```
주간 처리 플로우:
1. PDF 다운로드 (batch_download.py — 현재 구현됨)
2. PDF 파싱 (cfra_parser.py, zacks_parser.py)
3. Upsert to DB:
   - companies: INSERT ON CONFLICT (ticker) DO UPDATE
   - reports: INSERT ON CONFLICT (company_id, source, report_date) DO NOTHING
   - financials: INSERT ON CONFLICT DO UPDATE (추정치 → 실적 전환)
4. 변경 감지 → alerts 생성
5. PDF 아카이빙: storage/pdfs/YYYY-MM-DD/
```

---

## 8. 데이터 품질 규칙

### 8.1 제약조건 (스키마 레벨)

```sql
-- 이미 DDL에 포함된 CHECK 제약:
-- stars_rating BETWEEN 1 AND 5
-- zacks_rank BETWEEN 1 AND 5
-- fair_value_rank BETWEEN 1 AND 5
-- source IN ('CFRA', 'Zacks')
-- period_type IN ('annual', 'quarterly')
-- fiscal_quarter BETWEEN 1 AND 4

-- 추가 비즈니스 규칙:
ALTER TABLE companies ADD CONSTRAINT chk_ticker_format 
    CHECK (ticker ~ '^[A-Z]{1,5}$');

ALTER TABLE reports ADD CONSTRAINT chk_price_positive 
    CHECK (current_price > 0 AND (target_price IS NULL OR target_price > 0));

ALTER TABLE financials ADD CONSTRAINT chk_fiscal_year_range 
    CHECK (fiscal_year BETWEEN 2000 AND 2100);

ALTER TABLE balance_sheets ADD CONSTRAINT chk_total_assets_positive 
    CHECK (total_assets IS NULL OR total_assets > 0);
```

### 8.2 애플리케이션 레벨 유효성 검증

```python
# 파서 출력 검증 규칙 (validate_all.py에 추가)

VALIDATION_RULES = {
    "companies": {
        "ticker": {"required": True, "pattern": r"^[A-Z]{1,5}$"},
        "company_name": {"required": True, "min_length": 2},
    },
    "reports": {
        "report_date": {"required": True, "max_age_days": 30},
        "current_price": {"required": True, "range": (0.01, 100000)},
        "target_price": {"range": (0.01, 100000)},
    },
    "financials": {
        "fiscal_year": {"required": True, "range": (2015, 2030)},
        "revenue": {"range": (0, 1_000_000_000)},  # Million USD
        "eps": {"range": (-100, 1000)},
    },
}
```

### 8.3 데이터 정합성 모니터링 쿼리

```sql
-- 1. 중복 프로파일 검출
SELECT ticker, COUNT(*) FROM companies GROUP BY ticker HAVING COUNT(*) > 1;

-- 2. 리포트 없는 종목
SELECT c.ticker FROM companies c
LEFT JOIN reports r ON r.company_id = c.id
WHERE r.id IS NULL;

-- 3. 재무 데이터 갭 (연도 누락)
SELECT company_id, fiscal_year, 
    fiscal_year - LAG(fiscal_year) OVER (PARTITION BY company_id ORDER BY fiscal_year) AS gap
FROM financials
WHERE period_type = 'annual' AND is_estimate = FALSE
HAVING gap > 1;

-- 4. EPS 추정치 vs 실적 불일치 (서프라이즈 검증)
SELECT f_est.company_id, f_est.fiscal_year, f_est.fiscal_quarter,
    f_est.eps AS estimated, f_act.eps AS actual,
    ROUND((f_act.eps - f_est.eps) / ABS(f_est.eps) * 100, 2) AS calc_surprise_pct,
    f_act.eps_surprise_pct AS reported_surprise_pct
FROM financials f_est
JOIN financials f_act ON f_act.company_id = f_est.company_id
    AND f_act.fiscal_year = f_est.fiscal_year
    AND f_act.fiscal_quarter IS NOT DISTINCT FROM f_est.fiscal_quarter
    AND f_act.is_estimate = FALSE
WHERE f_est.is_estimate = TRUE;

-- 5. 최근 업데이트 모니터링
SELECT source, MAX(report_date) AS latest, COUNT(*) AS total
FROM reports GROUP BY source;
```

---

## 부록 A: 현재 vs 제안 테이블 매핑

| 현재 | 제안 | 변경 사항 |
|------|------|----------|
| stock_profiles (14) | companies | ticker UNIQUE, exchange는 속성, organization_id 제거 |
| stock_reports (22) | reports + report_ratings + report_text_sections | 텍스트 필드 분리, 등급 분리 |
| stock_key_stats (22) | report_key_stats | 새 필드 추가 (ESP, 거래량, surprise 등) |
| stock_financials (395) | financials | source 컬럼 추가, UNIQUE 제약 변경 |
| stock_balance_sheets (115) | balance_sheets | source 컬럼 추가 |
| stock_peers (70) | peer_comparisons | 상세 지표 → JSONB metrics |
| stock_analyst_notes (84) | analyst_notes | stock_profile_id → company_id |
| alerts (3) | alerts | ticker → company_id FK |
| watchlists / watchlist_items | 유지 | stock_profile_id → company_id |
| api_keys | 유지 | organization_id 제거 |
| _(없음)_ | income_statements | NEW: CFRA P3 |
| _(없음)_ | per_share_data | NEW: CFRA P3 |
| _(없음)_ | consensus_estimates | NEW: CFRA P6 |
| _(없음)_ | company_events | NEW: Zacks P6 |

## 부록 B: 파서 개선 우선순위

| 우선순위 | 파서 | 추가 대상 | 난이도 |
|---------|------|----------|--------|
| 1 | cfra_parser | Consensus Estimates (P6) | 중 |
| 2 | cfra_parser | Income Statement 10yr (P3) | 중 |
| 3 | cfra_parser | Per Share Data 10yr (P3) | 중 |
| 4 | zacks_parser | Revenue Breakdown % (P2) | 하 |
| 5 | zacks_parser | Recent News (P6) | 하 |
| 6 | zacks_parser | Industry Comparison 전체 (P8) | 상 |
| 7 | cfra_parser | Corporate Info (P2) | 하 |
| 8 | zacks_parser | Margin bps 변화 (P5) | 중 |

---

*본 리포트는 현재 14종목 22리포트의 실제 데이터와 AAPL/A의 PDF 원문 분석을 기반으로 작성되었습니다.*
