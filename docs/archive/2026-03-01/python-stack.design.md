# Python Stack Design Document

> **Summary**: Python 단독 스택(FastAPI + SQLAlchemy + APScheduler) 상세 설계 명세
>
> **Project**: Stock Report Hub
> **Author**: MindBuild
> **Date**: 2026-03-01
> **Status**: Draft
> **Planning Doc**: [python-stack.plan.md](../../01-plan/features/python-stack.plan.md)

---

## 1. Overview

### 1.1 Design Goals

- 기존 Python 파서 2종을 수정 없이 통합하여 DB 저장까지 단일 프로세스로 연결
- SQLAlchemy 모델이 `stock-report-db-design.md`의 7개 테이블을 정확히 반영
- FastAPI 엔드포인트를 통해 종목 조회, 비교, 콘텐츠 번들을 JSON API로 제공
- UPSERT 패턴으로 동일 데이터 중복 방지

### 1.2 Design Principles

- **파서 무결성 보존**: cfra_parser.py, zacks_parser.py의 출력 구조를 변경하지 않음
- **DB 스키마 충실도**: stock-report-db-design.md의 컬럼 정의를 그대로 SQLAlchemy 모델로 변환
- **관심사 분리**: models(ORM) / schemas(Pydantic) / crud(DB 로직) / api(라우터) / services(비즈니스)

---

## 2. Architecture

### 2.1 Component Diagram

```
                    ┌──────────────┐
                    │   Client     │
                    │  (Next.js)   │
                    └──────┬───────┘
                           │ HTTP/JSON
                    ┌──────▼───────┐
                    │   FastAPI    │
                    │   (API)      │
                    ├──────────────┤
                    │  Pydantic    │
                    │  Schemas     │
                    ├──────────────┤
                    │   CRUD       │
                    │  (UPSERT)    │
                    ├──────────────┤
                    │  SQLAlchemy  │
                    │  Models      │
                    └──────┬───────┘
                           │
                    ┌──────▼───────┐
                    │ PostgreSQL   │
                    │  (7 tables)  │
                    └──────────────┘

  ┌────────────┐    ┌──────────────┐    ┌──────────────┐
  │ PDF Files  │───▶│   Parsers    │───▶│ ParserService│──▶ CRUD ──▶ DB
  │ (CFRA/     │    │ cfra_parser  │    │ (orchestrate)│
  │  Zacks)    │    │ zacks_parser │    └──────────────┘
  └────────────┘    └──────────────┘

  ┌────────────┐    ┌──────────────┐
  │ Fidelity   │◀──│  Playwright  │──▶ PDF 저장 ──▶ ParserService
  │  Portal    │    │ FetcherSvc   │
  └────────────┘    └──────────────┘

  ┌──────────────┐
  │ APScheduler  │──▶ FetcherService (매일 7AM)
  └──────────────┘
```

### 2.2 Data Flow

```
[PDF 수집 플로우]
APScheduler/Manual → FetcherService → Fidelity Portal → PDF Download → Storage

[파싱 플로우]
PDF File → ParserService → cfra_parser/zacks_parser → Dict → CRUD UPSERT → PostgreSQL

[조회 플로우]
Client → FastAPI Router → CRUD Query → SQLAlchemy → PostgreSQL → Pydantic Response → JSON
```

### 2.3 Dependencies

| Component | Depends On | Purpose |
|-----------|-----------|---------|
| `app/api/stocks.py` | `app/crud/stock.py`, `app/schemas/stock.py` | API 라우터 |
| `app/crud/stock.py` | `app/models/*`, `app/database.py` | DB CRUD |
| `app/services/parser_service.py` | `app/parsers/*`, `app/crud/stock.py` | 파싱→저장 |
| `app/services/fetcher_service.py` | Playwright | PDF 다운로드 |
| `app/services/scheduler.py` | APScheduler, `fetcher_service`, `parser_service` | 정기 수집 |
| `app/parsers/*` | pdfplumber | PDF 파싱 (기존 코드) |

---

## 3. Data Model

### 3.1 SQLAlchemy ORM Models (7 Tables)

#### `StockProfile` — stock_profiles

```python
class StockProfile(Base):
    __tablename__ = "stock_profiles"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    ticker = Column(String(10), nullable=False)
    company_name = Column(String(255))
    exchange = Column(String(50))
    currency = Column(String(10), default="USD")
    gics_sector = Column(String(100))
    gics_sub_industry = Column(String(100))
    industry = Column(String(100))         # Zacks 산업 분류
    domicile = Column(String(100))
    founded_year = Column(Integer)
    employees = Column(Integer)
    website = Column(String(255))
    description = Column(Text)
    segments = Column(JSONB)               # [{"name":"...", "pct":40.5}]
    geo_breakdown = Column(JSONB)
    officers = Column(JSONB)
    board_members = Column(JSONB)
    index_memberships = Column(ARRAY(String))
    organization_id = Column(BigInteger)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    # Unique constraint
    __table_args__ = (
        UniqueConstraint("ticker", "exchange", name="uq_profile_ticker_exchange"),
    )

    # Relationships
    reports = relationship("StockReport", back_populates="profile")
    financials = relationship("StockFinancial", back_populates="profile")
    balance_sheets = relationship("StockBalanceSheet", back_populates="profile")
    analyst_notes = relationship("StockAnalystNote", back_populates="profile")
```

#### `StockReport` — stock_reports

```python
class StockReport(Base):
    __tablename__ = "stock_reports"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    stock_profile_id = Column(BigInteger, ForeignKey("stock_profiles.id"), nullable=False)
    source = Column(String(50), nullable=False)        # "CFRA", "Zacks"
    report_date = Column(Date, nullable=False)
    analyst_name = Column(String(100))
    recommendation = Column(String(20))                # Buy, Hold, Neutral, etc.
    prior_recommendation = Column(String(20))          # Zacks
    stars_rating = Column(Integer)                     # CFRA STARS 1-5
    zacks_rank = Column(Integer)                       # Zacks Rank 1-5
    style_scores = Column(JSONB)                       # {"value":"D","growth":"D","momentum":"B","vgm":"C"}
    target_price = Column(Numeric(12, 2))
    current_price = Column(Numeric(12, 2))
    price_date = Column(Date)
    risk_assessment = Column(String(20))               # LOW/MEDIUM/HIGH
    fair_value = Column(Numeric(12, 2))
    fair_value_rank = Column(Integer)
    volatility = Column(String(20))
    technical_eval = Column(String(20))
    insider_activity = Column(String(20))
    investment_style = Column(String(50))
    industry_rank = Column(String(100))                # Zacks
    highlights = Column(Text)                          # CFRA
    reasons_to_buy = Column(Text)                      # Zacks
    reasons_to_sell = Column(Text)                     # Zacks
    investment_rationale = Column(Text)                # CFRA
    business_summary = Column(Text)
    sub_industry_outlook = Column(Text)                # CFRA
    last_earnings_summary = Column(Text)               # Zacks
    outlook = Column(Text)                             # Zacks
    recent_news = Column(JSONB)
    raw_pdf_path = Column(String(500))
    organization_id = Column(BigInteger)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        UniqueConstraint("stock_profile_id", "source", "report_date",
                         name="uq_report_profile_source_date"),
    )

    profile = relationship("StockProfile", back_populates="reports")
    key_stats = relationship("StockKeyStat", back_populates="report", uselist=False)
    peers = relationship("StockPeer", back_populates="report")
```

#### `StockFinancial` — stock_financials

```python
class StockFinancial(Base):
    __tablename__ = "stock_financials"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    stock_profile_id = Column(BigInteger, ForeignKey("stock_profiles.id"), nullable=False)
    fiscal_year = Column(Integer, nullable=False)
    fiscal_quarter = Column(Integer)                   # NULL = annual
    period_type = Column(String(10), nullable=False)   # "quarterly" / "annual"
    is_estimate = Column(Boolean, default=False)
    revenue = Column(Numeric(15, 2))                   # millions USD
    operating_income = Column(Numeric(15, 2))
    pretax_income = Column(Numeric(15, 2))
    net_income = Column(Numeric(15, 2))
    eps = Column(Numeric(8, 4))
    eps_normalized = Column(Numeric(8, 4))
    free_cash_flow_ps = Column(Numeric(8, 4))
    tangible_book_value_ps = Column(Numeric(8, 4))
    depreciation = Column(Numeric(12, 2))
    effective_tax_rate = Column(Numeric(6, 2))
    gross_margin_pct = Column(Numeric(6, 2))
    operating_margin_pct = Column(Numeric(6, 2))
    segment_revenues = Column(JSONB)
    eps_surprise_pct = Column(Numeric(6, 2))
    sales_surprise_pct = Column(Numeric(6, 2))
    organization_id = Column(BigInteger)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        UniqueConstraint("stock_profile_id", "fiscal_year", "fiscal_quarter", "is_estimate",
                         name="uq_financial_profile_year_quarter_estimate"),
    )

    profile = relationship("StockProfile", back_populates="financials")
```

#### `StockBalanceSheet` — stock_balance_sheets

```python
class StockBalanceSheet(Base):
    __tablename__ = "stock_balance_sheets"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    stock_profile_id = Column(BigInteger, ForeignKey("stock_profiles.id"), nullable=False)
    fiscal_year = Column(Integer, nullable=False)
    cash = Column(Numeric(15, 2))
    current_assets = Column(Numeric(15, 2))
    total_assets = Column(Numeric(15, 2))
    current_liabilities = Column(Numeric(15, 2))
    long_term_debt = Column(Numeric(15, 2))
    total_capital = Column(Numeric(15, 2))
    capital_expenditures = Column(Numeric(15, 2))
    cash_from_operations = Column(Numeric(15, 2))
    current_ratio = Column(Numeric(6, 2))
    ltd_to_cap_pct = Column(Numeric(6, 2))
    net_income_to_revenue_pct = Column(Numeric(6, 2))
    return_on_assets_pct = Column(Numeric(6, 2))
    return_on_equity_pct = Column(Numeric(6, 2))
    organization_id = Column(BigInteger)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        UniqueConstraint("stock_profile_id", "fiscal_year",
                         name="uq_balance_sheet_profile_year"),
    )

    profile = relationship("StockProfile", back_populates="balance_sheets")
```

#### `StockKeyStat` — stock_key_stats

```python
class StockKeyStat(Base):
    __tablename__ = "stock_key_stats"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    stock_report_id = Column(BigInteger, ForeignKey("stock_reports.id"), nullable=False, unique=True)
    week_52_high = Column(Numeric(12, 2))
    week_52_low = Column(Numeric(12, 2))
    trailing_12m_eps = Column(Numeric(8, 4))
    trailing_12m_pe = Column(Numeric(10, 2))
    market_cap_b = Column(Numeric(12, 2))
    shares_outstanding_m = Column(Numeric(12, 2))
    beta = Column(Numeric(6, 2))
    eps_cagr_3yr_pct = Column(Numeric(6, 2))
    institutional_ownership_pct = Column(Numeric(6, 2))
    dividend_yield_pct = Column(Numeric(6, 2))
    dividend_rate = Column(Numeric(8, 2))
    price_to_sales = Column(Numeric(10, 2))
    price_to_ebitda = Column(Numeric(10, 2))
    price_to_pretax = Column(Numeric(10, 2))
    net_margin_1yr_pct = Column(Numeric(6, 2))
    net_margin_3yr_pct = Column(Numeric(6, 2))
    sales_growth_1yr_pct = Column(Numeric(6, 2))
    sales_growth_3yr_pct = Column(Numeric(6, 2))
    # Zacks-specific
    pe_forward_12m = Column(Numeric(10, 2))
    ps_forward_12m = Column(Numeric(10, 2))
    ev_ebitda = Column(Numeric(10, 2))
    peg_ratio = Column(Numeric(10, 2))
    price_to_book = Column(Numeric(10, 2))
    price_to_cashflow = Column(Numeric(10, 2))
    debt_equity = Column(Numeric(10, 2))
    cash_per_share = Column(Numeric(10, 2))
    earnings_yield_pct = Column(Numeric(6, 2))
    valuation_multiples = Column(JSONB)
    organization_id = Column(BigInteger)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    report = relationship("StockReport", back_populates="key_stats")
```

#### `StockPeer` — stock_peers

```python
class StockPeer(Base):
    __tablename__ = "stock_peers"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    stock_report_id = Column(BigInteger, ForeignKey("stock_reports.id"), nullable=False)
    peer_ticker = Column(String(10))
    peer_name = Column(String(255))
    exchange = Column(String(50))
    recent_price = Column(Numeric(12, 2))
    market_cap_m = Column(Numeric(15, 2))
    price_chg_30d_pct = Column(Numeric(6, 2))
    price_chg_1yr_pct = Column(Numeric(6, 2))
    pe_ratio = Column(Numeric(10, 2))
    fair_value_calc = Column(Numeric(12, 2))
    yield_pct = Column(Numeric(6, 2))
    roe_pct = Column(Numeric(6, 2))
    ltd_to_cap_pct = Column(Numeric(6, 2))
    recommendation = Column(String(20))
    rank = Column(Integer)
    detailed_comparison = Column(JSONB)
    organization_id = Column(BigInteger)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    report = relationship("StockReport", back_populates="peers")
```

#### `StockAnalystNote` — stock_analyst_notes

```python
class StockAnalystNote(Base):
    __tablename__ = "stock_analyst_notes"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    stock_profile_id = Column(BigInteger, ForeignKey("stock_profiles.id"), nullable=False)
    source = Column(String(50))
    published_at = Column(DateTime)
    analyst_name = Column(String(100))
    title = Column(String(500))
    stock_price_at_note = Column(Numeric(12, 2))
    action = Column(String(50))
    target_price = Column(Numeric(12, 2))
    content = Column(Text)
    organization_id = Column(BigInteger)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    profile = relationship("StockProfile", back_populates="analyst_notes")
```

### 3.2 Entity Relationships

```
stock_profiles (1) ──< (N) stock_reports
stock_profiles (1) ──< (N) stock_financials
stock_profiles (1) ──< (N) stock_balance_sheets
stock_profiles (1) ──< (N) stock_analyst_notes
stock_reports  (1) ──< (N) stock_peers
stock_reports  (1) ──< (1) stock_key_stats
```

### 3.3 Indexes

```sql
-- 검색 성능용 인덱스
CREATE INDEX ix_stock_profiles_ticker ON stock_profiles(ticker);
CREATE INDEX ix_stock_reports_profile_source ON stock_reports(stock_profile_id, source);
CREATE INDEX ix_stock_reports_report_date ON stock_reports(report_date DESC);
CREATE INDEX ix_stock_financials_profile_year ON stock_financials(stock_profile_id, fiscal_year);
CREATE INDEX ix_stock_analyst_notes_profile ON stock_analyst_notes(stock_profile_id);
CREATE INDEX ix_stock_analyst_notes_published ON stock_analyst_notes(published_at DESC);
```

---

## 4. API Specification

### 4.1 Endpoint List

| Method | Path | Description | Auth |
|--------|------|-------------|------|
| GET | `/api/stocks` | 전체 종목 목록 | - |
| GET | `/api/stocks/{ticker}` | 종목 프로필 + 최신 리포트 | - |
| GET | `/api/stocks/{ticker}/reports` | 리포트 목록 (소스 필터) | - |
| GET | `/api/stocks/{ticker}/financials` | 재무 데이터 | - |
| GET | `/api/stocks/{ticker}/compare` | 멀티소스 비교 | - |
| GET | `/api/stocks/{ticker}/bundle` | 콘텐츠 생성용 통합 | - |
| POST | `/api/parse` | PDF 업로드 → 파싱 → DB 저장 | - |
| POST | `/api/fetch/{ticker}` | 포털 PDF 수집 트리거 | - |

### 4.2 Detailed Specification

#### `GET /api/stocks/{ticker}`

**Response (200):**
```json
{
  "profile": {
    "id": 1,
    "ticker": "PLTR",
    "company_name": "Palantir Technologies Inc.",
    "exchange": "NasdaqGS",
    "gics_sector": "Information Technology",
    "gics_sub_industry": "Application Software"
  },
  "latest_reports": [
    {
      "id": 1,
      "source": "CFRA",
      "report_date": "2026-02-21",
      "recommendation": "Buy",
      "stars_rating": 4,
      "target_price": 203.00,
      "current_price": 135.24
    }
  ]
}
```

#### `GET /api/stocks/{ticker}/compare`

**Response (200):**
```json
{
  "ticker": "MSFT",
  "company_name": "Microsoft Corp.",
  "sources": {
    "CFRA": {
      "recommendation": "Strong Buy",
      "stars_rating": 5,
      "target_price": 550.00,
      "risk_assessment": "LOW"
    },
    "Zacks": {
      "recommendation": "Neutral",
      "zacks_rank": 3,
      "target_price": 520.00,
      "style_scores": {"value": "C", "growth": "B", "momentum": "B", "vgm": "B"}
    }
  }
}
```

#### `POST /api/parse`

**Request:** `multipart/form-data`
- `file`: PDF 파일
- `source`: "CFRA" 또는 "Zacks"

**Response (201):**
```json
{
  "status": "success",
  "ticker": "PLTR",
  "source": "CFRA",
  "report_date": "2026-02-21",
  "records_saved": {
    "profile": 1,
    "report": 1,
    "financials": 30,
    "key_stats": 1,
    "analyst_notes": 5
  },
  "warnings": []
}
```

#### `GET /api/stocks/{ticker}/bundle`

콘텐츠 생성용 통합 데이터. `to_content_vars()` 결과와 동일.

**Response (200):**
```json
{
  "company_name": "Palantir Technologies Inc.",
  "ticker": "PLTR",
  "recommendation": "Buy",
  "target_price": 203.00,
  "current_price": 135.24,
  "upside_pct": 50.1,
  "stars_rating": 4,
  "highlights": "...",
  "investment_rationale": "...",
  "revenue_latest": 2872.0,
  "eps_latest": 0.41,
  "pe_ratio": 330.0,
  "market_cap_b": 317.39
}
```

### 4.3 Error Response Format

```json
{
  "detail": "Stock not found: INVALID"
}
```

| Code | Cause |
|------|-------|
| 400 | 잘못된 source 파라미터, 파일 형식 오류 |
| 404 | 종목/리포트 미존재 |
| 422 | PDF 파싱 실패 |
| 500 | DB 연결 실패 등 |

---

## 5. CRUD / UPSERT Design

### 5.1 UPSERT Strategy

PostgreSQL `INSERT ... ON CONFLICT DO UPDATE` 패턴 사용.

```python
from sqlalchemy.dialects.postgresql import insert

def upsert_profile(session: Session, data: dict) -> StockProfile:
    stmt = insert(StockProfile).values(**data)
    stmt = stmt.on_conflict_do_update(
        index_elements=["ticker", "exchange"],
        set_={k: stmt.excluded[k] for k in data if k not in ("ticker", "exchange")}
    )
    result = session.execute(stmt)
    session.commit()
    return session.query(StockProfile).filter_by(
        ticker=data["ticker"], exchange=data.get("exchange")
    ).one()
```

### 5.2 CRUD Functions

| Function | Table | Conflict Key | Operation |
|----------|-------|-------------|-----------|
| `upsert_profile(data)` | stock_profiles | (ticker, exchange) | insert/update |
| `upsert_report(profile_id, data)` | stock_reports | (profile_id, source, report_date) | insert/update |
| `upsert_financial(profile_id, data)` | stock_financials | (profile_id, fiscal_year, fiscal_quarter, is_estimate) | insert/update |
| `upsert_balance_sheet(profile_id, data)` | stock_balance_sheets | (profile_id, fiscal_year) | insert/update |
| `upsert_key_stats(report_id, data)` | stock_key_stats | (stock_report_id) | insert/update |
| `save_peers(report_id, peers_list)` | stock_peers | delete+insert | replace all |
| `save_analyst_notes(profile_id, notes)` | stock_analyst_notes | upsert by published_at | insert/update |

### 5.3 Parser → CRUD Mapping

```python
def parse_and_store(pdf_path: str, source: str, session: Session) -> dict:
    # 1. Parse
    if source == "CFRA":
        result = CFRAParser().parse(pdf_path)
    elif source == "Zacks":
        result = ZacksParser().parse(pdf_path)

    data = asdict(result)

    # 2. Upsert profile
    profile = upsert_profile(session, data["profile"])

    # 3. Upsert report
    report_data = data["report"]
    report_data["stock_profile_id"] = profile.id
    report_data["raw_pdf_path"] = pdf_path
    report = upsert_report(session, profile.id, report_data)

    # 4. Upsert key_stats
    if data.get("key_stats"):
        upsert_key_stats(session, report.id, data["key_stats"])

    # 5. Upsert financials
    for fin in data.get("financials", []):
        fin["stock_profile_id"] = profile.id
        upsert_financial(session, profile.id, fin)

    # 6. Save peers (Zacks)
    if data.get("peers"):
        save_peers(session, report.id, data["peers"])

    # 7. Save analyst notes (CFRA)
    if data.get("analyst_notes"):
        save_analyst_notes(session, profile.id, data["analyst_notes"])

    return {"ticker": profile.ticker, "source": source, ...}
```

---

## 6. Services Design

### 6.1 ParserService (`app/services/parser_service.py`)

```python
class ParserService:
    def parse_and_store(self, pdf_path: str, source: str) -> dict:
        """PDF 파싱 → DB 저장 오케스트레이터."""

    def to_content_vars(self, ticker: str) -> dict:
        """블로그/뉴스레터 템플릿용 변수 맵 반환."""

    def detect_changes(self, ticker: str, source: str) -> dict | None:
        """이전 리포트 대비 등급/목표가 변경 감지."""
```

### 6.2 FetcherService (`app/services/fetcher_service.py`)

```python
class FetcherService:
    async def fetch_pdf(self, ticker: str, source: str) -> str:
        """Playwright로 Fidelity 포털에서 PDF 다운로드. 파일 경로 반환."""

    async def fetch_watchlist(self, tickers: list[str]) -> list[dict]:
        """워치리스트 일괄 수집. 각 티커 사이 5초 딜레이."""
```

### 6.3 Scheduler (`app/services/scheduler.py`)

```python
# APScheduler 설정
scheduler = BackgroundScheduler()

@scheduler.scheduled_job("cron", hour=7, minute=0)
def daily_fetch():
    """매일 7AM 워치리스트 자동 수집."""
```

---

## 7. Configuration

### 7.1 Environment Variables

| Variable | Purpose | Default | Required |
|----------|---------|---------|----------|
| `DATABASE_URL` | PostgreSQL 연결 | - | Yes |
| `PDF_STORAGE_PATH` | PDF 저장 경로 | `./storage/pdfs` | No |
| `FIDELITY_PORTAL_URL` | 포털 URL | 하드코딩 | No |
| `SCHEDULER_ENABLED` | 스케줄러 ON/OFF | `false` | No |
| `SCHEDULER_CRON_HOUR` | 수집 시각 | `7` | No |
| `LOG_LEVEL` | 로깅 레벨 | `INFO` | No |

### 7.2 Config Class

```python
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    database_url: str
    pdf_storage_path: str = "./storage/pdfs"
    scheduler_enabled: bool = False
    scheduler_cron_hour: int = 7
    log_level: str = "INFO"

    class Config:
        env_file = ".env"
```

---

## 8. Docker Setup

### 8.1 docker-compose.yml

```yaml
services:
  db:
    image: postgres:16-alpine
    environment:
      POSTGRES_DB: stock_hub
      POSTGRES_USER: stock_user
      POSTGRES_PASSWORD: stock_pass
    ports:
      - "5432:5432"
    volumes:
      - pgdata:/var/lib/postgresql/data

volumes:
  pgdata:
```

---

## 9. File Structure (Final)

```
stock-report-automation/
├── app/
│   ├── __init__.py
│   ├── main.py
│   ├── config.py
│   ├── database.py
│   ├── models/
│   │   ├── __init__.py
│   │   ├── stock_profile.py
│   │   ├── stock_report.py
│   │   ├── stock_financial.py
│   │   ├── stock_balance_sheet.py
│   │   ├── stock_key_stat.py
│   │   ├── stock_peer.py
│   │   └── stock_analyst_note.py
│   ├── schemas/
│   │   ├── __init__.py
│   │   └── stock.py
│   ├── crud/
│   │   ├── __init__.py
│   │   └── stock.py
│   ├── api/
│   │   ├── __init__.py
│   │   └── stocks.py
│   ├── services/
│   │   ├── __init__.py
│   │   ├── parser_service.py
│   │   ├── fetcher_service.py
│   │   └── scheduler.py
│   └── parsers/
│       ├── __init__.py
│       ├── cfra_parser.py
│       └── zacks_parser.py
├── alembic/
│   ├── env.py
│   └── versions/
├── storage/
│   └── pdfs/
├── tests/
│   ├── __init__.py
│   ├── test_parsers.py
│   ├── test_crud.py
│   └── test_api.py
├── alembic.ini
├── docker-compose.yml
├── requirements.txt
├── .env.example
├── validate_all.py              # 기존 파서 검증 유지
├── cfra_parser.py               # 기존 위치 유지 (validate_all.py 호환)
├── zacks_parser.py              # 기존 위치 유지
└── *.pdf                        # 샘플 PDF 9개
```

> **Note**: 기존 `cfra_parser.py`, `zacks_parser.py`는 루트에 그대로 유지하고,
> `app/parsers/`에서 import하여 사용. `validate_all.py` 호환성 보존.

---

## 10. Implementation Order

### Step 1: 프로젝트 초기화 + DB 모델

| # | Task | Output |
|---|------|--------|
| 1.1 | `requirements.txt` 생성 | 의존성 파일 |
| 1.2 | `.env.example` 생성 | 환경변수 템플릿 |
| 1.3 | `docker-compose.yml` 생성 | PostgreSQL 컨테이너 |
| 1.4 | `app/config.py` | Settings 클래스 |
| 1.5 | `app/database.py` | engine, SessionLocal, Base |
| 1.6 | `app/models/` 7개 파일 | SQLAlchemy ORM |
| 1.7 | `alembic init` + env.py 설정 | 마이그레이션 환경 |
| 1.8 | `alembic revision --autogenerate` | 초기 마이그레이션 |
| 1.9 | `alembic upgrade head` | 테이블 생성 확인 |

### Step 2: 파서 통합 + DB 저장

| # | Task | Output |
|---|------|--------|
| 2.1 | `app/parsers/__init__.py` (기존 파서 import) | 파서 모듈 |
| 2.2 | `app/crud/stock.py` (UPSERT 함수 7개) | CRUD 레이어 |
| 2.3 | `app/services/parser_service.py` | 파싱→저장 오케스트레이터 |
| 2.4 | E2E 테스트: 9개 PDF → DB 저장 | 검증 |

### Step 3: FastAPI API

| # | Task | Output |
|---|------|--------|
| 3.1 | `app/schemas/stock.py` (Pydantic 응답) | 스키마 |
| 3.2 | `app/api/stocks.py` (8개 엔드포인트) | 라우터 |
| 3.3 | `app/main.py` (FastAPI 앱) | 엔트리포인트 |
| 3.4 | Swagger UI 테스트 | 검증 |

### Step 4: 스케줄러 + 수집

| # | Task | Output |
|---|------|--------|
| 4.1 | `app/services/fetcher_service.py` | Playwright 수집 |
| 4.2 | `app/services/scheduler.py` | APScheduler |
| 4.3 | E2E 테스트: 포털 → PDF → DB | 검증 |

### Step 5: 콘텐츠 파이프라인

| # | Task | Output |
|---|------|--------|
| 5.1 | `to_content_vars()` 구현 | 변수 맵 |
| 5.2 | `detect_changes()` 구현 | 변경 감지 |

---

## Version History

| Version | Date | Changes | Author |
|---------|------|---------|--------|
| 0.1 | 2026-03-01 | Initial design — 7 models, 8 APIs, UPSERT strategy | MindBuild |
