# Python Stack 전환 Planning Document

> **Summary**: Elixir/Phoenix 기반 설계를 Python 단독 스택(FastAPI + SQLAlchemy + APScheduler)으로 전환
>
> **Project**: Stock Report Hub
> **Author**: MindBuild
> **Date**: 2026-03-01
> **Status**: Draft

---

## 1. Overview

### 1.1 Purpose

기존 Elixir/Phoenix + Ecto + Oban 기반으로 설계된 Stock Report Hub를
**Python 단독 스택**으로 전환한다.

Python 생태계의 넓은 레퍼런스, PDF 파싱(pdfplumber)과의 네이티브 통합,
FastAPI의 빠른 개발 속도를 활용하여 MVP 출시를 가속화한다.

### 1.2 Background

- 파서 2종(cfra_parser.py, zacks_parser.py)이 이미 Python으로 개발 완료 (정확도 100%)
- Elixir 스택은 Python 파서를 System.cmd로 호출하는 간접 연동이 필요했음
- Python 단독이면 파서 → DB 저장 → API 제공이 한 프로세스에서 직결
- 1인 운영 기준으로 Elixir보다 Python 레퍼런스/커뮤니티가 압도적

### 1.3 Related Documents

- DB 스키마 설계: `stock-report-db-design.md`
- 자동화 아키텍처: `stock-report-automation.md`
- PRD: `PRD-stock-report-hub.md`
- 파서 검증 리포트: `parser-accuracy-report.md`

---

## 2. Scope

### 2.1 In Scope

- [x] 기존 Python 파서 2종 재활용 (cfra_parser.py, zacks_parser.py)
- [ ] SQLAlchemy 2.0 ORM 모델 7개 테이블
- [ ] Alembic DB 마이그레이션
- [ ] CRUD + UPSERT 로직 (파서 결과 → DB 저장)
- [ ] FastAPI REST API 엔드포인트
- [ ] APScheduler 기반 정기 수집
- [ ] Playwright 포털 PDF 자동 다운로드
- [ ] 콘텐츠 변수 맵 생성 (to_content_vars)

### 2.2 Out of Scope

- Next.js 프론트엔드 (별도 프로젝트로 후속 진행)
- SaaS 멀티테넌시 (organization_id는 컬럼만 정의, 로직 미구현)
- 추가 소스 파서 (Argus, S&P — Phase 4)
- 자동매매 연동

---

## 3. Requirements

### 3.1 Functional Requirements

| ID | Requirement | Priority | Status |
|----|-------------|----------|--------|
| FR-01 | 7개 DB 테이블 생성 (stock-report-db-design.md 기반) | High | Pending |
| FR-02 | CFRA/Zacks 파서 결과를 DB에 UPSERT | High | Pending |
| FR-03 | 종목 프로필 + 최신 리포트 조회 API | High | Pending |
| FR-04 | 멀티소스 비교 API (CFRA vs Zacks 동일 종목) | High | Pending |
| FR-05 | PDF 업로드 → 파싱 → DB 저장 API | High | Pending |
| FR-06 | 재무 데이터 조회 API (연간/분기) | Medium | Pending |
| FR-07 | 콘텐츠 생성용 통합 데이터 번들 API | Medium | Pending |
| FR-08 | Playwright 기반 Fidelity 포털 PDF 자동 수집 | Medium | Pending |
| FR-09 | APScheduler 매일 7AM 워치리스트 자동 수집 | Medium | Pending |
| FR-10 | 리포트 변경 감지 (등급/목표가 diff) | Low | Pending |

### 3.2 Non-Functional Requirements

| Category | Criteria | Measurement Method |
|----------|----------|-------------------|
| Performance | 단일 PDF 파싱+저장 < 5초 | 타이머 |
| Performance | API 응답 < 200ms | FastAPI 미들웨어 |
| Reliability | 50종목 일괄 수집 성공률 >= 95% | 로그 분석 |
| Data Integrity | 파싱 정확도 >= 98% (숫자 필드) | validate_all.py |

---

## 4. Success Criteria

### 4.1 Definition of Done

- [ ] 7개 테이블 Alembic 마이그레이션 완료
- [ ] 9개 샘플 PDF → DB 저장 E2E 동작
- [ ] FastAPI 서버 기동 + API 6개 엔드포인트 동작
- [ ] validate_all.py 회귀 테스트 통과 (파서 무결성)

### 4.2 Quality Criteria

- [ ] UPSERT 중복 방지 동작 확인
- [ ] API 응답 Pydantic 스키마 검증
- [ ] 에러 핸들링 (잘못된 PDF, DB 연결 실패 등)

---

## 5. Risks and Mitigation

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| 파서 이동 시 import 경로 변경으로 기존 validate_all.py 깨짐 | Medium | High | import path 호환 유지 또는 validate_all.py 업데이트 |
| PostgreSQL 미설치 / 연결 실패 | High | Medium | Docker compose로 PostgreSQL 제공, .env 설정 가이드 |
| SQLAlchemy UPSERT 구현 복잡성 | Medium | Low | PostgreSQL INSERT ON CONFLICT 직접 사용 |
| Playwright 브라우저 설치 이슈 (WSL) | Medium | Medium | Phase 1에서는 수동 PDF, Phase 3에서 Playwright 도입 |

---

## 6. Architecture

### 6.1 기술 스택

| Layer | Technology | Role |
|-------|-----------|------|
| PDF Parsing | pdfplumber 0.11.9 | 텍스트/테이블 추출 (기존 파서) |
| ORM | SQLAlchemy 2.0 + Alembic | DB 모델, 마이그레이션 |
| DB | PostgreSQL 16 | 정규화 저장 |
| API | FastAPI + Uvicorn | REST API |
| Validation | Pydantic v2 | 요청/응답 스키마 |
| Scheduling | APScheduler | 정기 수집 |
| Browser | Playwright | 포털 자동화 |
| Frontend | Next.js (별도) | 웹 UI (후속) |

### 6.2 프로젝트 구조

```
stock-report-automation/
├── app/
│   ├── __init__.py
│   ├── main.py                  # FastAPI 앱 엔트리포인트
│   ├── config.py                # Settings (pydantic-settings)
│   ├── database.py              # engine, SessionLocal, Base
│   │
│   ├── models/                  # SQLAlchemy ORM (7 테이블)
│   │   ├── __init__.py          # Base, 모든 모델 re-export
│   │   ├── stock_profile.py
│   │   ├── stock_report.py
│   │   ├── stock_financial.py
│   │   ├── stock_balance_sheet.py
│   │   ├── stock_key_stat.py
│   │   ├── stock_peer.py
│   │   └── stock_analyst_note.py
│   │
│   ├── schemas/                 # Pydantic v2 스키마
│   │   ├── __init__.py
│   │   └── stock.py
│   │
│   ├── crud/                    # CRUD + UPSERT
│   │   ├── __init__.py
│   │   └── stock.py
│   │
│   ├── api/                     # FastAPI 라우터
│   │   ├── __init__.py
│   │   └── stocks.py
│   │
│   ├── services/                # 비즈니스 로직
│   │   ├── __init__.py
│   │   ├── parser_service.py    # 파서 호출 → DB 저장
│   │   ├── fetcher_service.py   # Playwright 수집
│   │   └── scheduler.py         # APScheduler
│   │
│   └── parsers/                 # 파서 모듈
│       ├── __init__.py
│       ├── cfra_parser.py
│       └── zacks_parser.py
│
├── alembic/                     # DB 마이그레이션
│   ├── env.py
│   └── versions/
│
├── tests/
│   ├── test_parsers.py
│   ├── test_crud.py
│   └── test_api.py
│
├── alembic.ini
├── requirements.txt
├── .env.example
├── docker-compose.yml           # PostgreSQL
└── validate_all.py              # 기존 파서 검증 (유지)
```

### 6.3 DB 스키마 관계

```
stock_profiles (1) ──< (N) stock_reports
stock_profiles (1) ──< (N) stock_financials
stock_profiles (1) ──< (N) stock_balance_sheets
stock_profiles (1) ──< (N) stock_analyst_notes
stock_reports  (1) ──< (N) stock_peers
stock_reports  (1) ──< (1) stock_key_stats
```

### 6.4 API 엔드포인트

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/stocks/{ticker}` | 종목 프로필 + 최신 리포트 |
| GET | `/api/stocks/{ticker}/reports` | 리포트 목록 (소스 필터) |
| GET | `/api/stocks/{ticker}/financials` | 재무 데이터 (연간/분기) |
| GET | `/api/stocks/{ticker}/compare` | 멀티소스 비교 (CFRA vs Zacks) |
| GET | `/api/stocks/{ticker}/bundle` | 콘텐츠 생성용 통합 데이터 |
| POST | `/api/parse` | PDF 업로드 → 파싱 → DB 저장 |
| GET | `/api/stocks` | 전체 종목 목록 |
| POST | `/api/fetch/{ticker}` | 포털에서 PDF 수집 트리거 |

### 6.5 UPSERT 전략

```python
# PostgreSQL INSERT ... ON CONFLICT DO UPDATE
from sqlalchemy.dialects.postgresql import insert

stmt = insert(StockProfile).values(**data)
stmt = stmt.on_conflict_do_update(
    index_elements=["ticker", "exchange"],
    set_={col: stmt.excluded[col] for col in update_cols}
)
session.execute(stmt)
```

유니크 제약 기반:
- `stock_profiles`: `(ticker, exchange)`
- `stock_reports`: `(stock_profile_id, source, report_date)`
- `stock_financials`: `(stock_profile_id, fiscal_year, fiscal_quarter, is_estimate)`
- `stock_balance_sheets`: `(stock_profile_id, fiscal_year)`

---

## 7. Implementation Plan

### Step 1: 프로젝트 초기화 + DB 모델 (Day 1)

1. `requirements.txt` 생성
2. `app/config.py` — pydantic-settings로 환경변수
3. `app/database.py` — SQLAlchemy engine + session
4. `app/models/` — 7개 ORM 모델 (stock-report-db-design.md 기준)
5. `docker-compose.yml` — PostgreSQL 16
6. `alembic init` + autogenerate 마이그레이션
7. `alembic upgrade head` → 테이블 생성 확인

### Step 2: 파서 통합 + DB 저장 (Day 2)

1. 기존 파서를 `app/parsers/`로 복사
2. `app/crud/stock.py` — UPSERT 함수들
3. `app/services/parser_service.py` — parse_and_store() 오케스트레이터
4. 9개 PDF E2E 테스트 (파싱 → DB 확인)

### Step 3: FastAPI API (Day 3)

1. `app/schemas/stock.py` — Pydantic 응답 모델
2. `app/api/stocks.py` — 8개 엔드포인트
3. `app/main.py` — FastAPI 앱 + 라우터 등록
4. Swagger UI 확인 (`/docs`)

### Step 4: 스케줄러 + 수집 (Day 4-5)

1. `app/services/fetcher_service.py` — Playwright 수집
2. `app/services/scheduler.py` — APScheduler 설정
3. 단일 티커 수집 E2E 테스트

### Step 5: 콘텐츠 파이프라인 (Day 6)

1. `to_content_vars(ticker)` 함수
2. 리포트 변경 감지 로직
3. 통합 테스트

---

## 8. Convention

### 8.1 Naming

- 파일명: snake_case (`stock_profile.py`)
- 클래스: PascalCase (`StockProfile`)
- 함수/변수: snake_case (`get_latest_report`)
- API 경로: kebab-case 없이 복수형 (`/api/stocks`)

### 8.2 Environment Variables

| Variable | Purpose | Example |
|----------|---------|---------|
| `DATABASE_URL` | PostgreSQL 연결 | `postgresql://user:pass@localhost:5432/stock_hub` |
| `PDF_STORAGE_PATH` | PDF 저장 경로 | `./storage/pdfs` |
| `FIDELITY_PORTAL_URL` | 포털 URL | `https://public.fidelityresearch.com/...` |
| `SCHEDULER_ENABLED` | 스케줄러 활성화 | `true` |
| `SCHEDULER_CRON_HOUR` | 수집 시간 | `7` |

### 8.3 Error Handling

- FastAPI HTTPException으로 통일
- 파서 에러는 `errors`/`warnings` 리스트로 반환 (기존 패턴 유지)
- DB 에러는 트랜잭션 롤백 + 로깅

---

## 9. Next Steps

1. [ ] Plan 승인 후 → Design 문서 작성 (`/pdca design python-stack`)
2. [ ] Design 승인 후 → Step 1부터 구현 시작
3. [ ] CLAUDE.md 업데이트 (Elixir 참조 제거, Python 스택 반영)

---

## Version History

| Version | Date | Changes | Author |
|---------|------|---------|--------|
| 0.1 | 2026-03-01 | Initial draft — Python 단독 스택 전환 계획 | MindBuild |
