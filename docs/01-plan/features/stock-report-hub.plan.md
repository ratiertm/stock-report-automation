# Stock Report Hub — Master Plan (v2)

> **Date**: 2026-03-02
> **Status**: Active
> **이전 Plan**: docs/archive/2026-03-01/python-stack.plan.md (폐기)

---

## 실제 완료 상태 (검증 기준)

| 항목 | 상태 | 검증 결과 |
|------|------|----------|
| Python 파서 2종 (CFRA, Zacks) | DONE | 9 PDF × 170항목 100% |
| SQLAlchemy ORM 7 모델 | DONE | 코드 존재 |
| Alembic 마이그레이션 2개 | DONE | DB 테이블 7개 생성 확인 |
| CRUD UPSERT 7테이블 | DONE | 코드 존재 |
| parser_service (parse_and_store) | DONE | E2E 동작 확인 |
| **E2E: 9 PDF → DB 저장** | **DONE** | 9/9 성공, 에러 0건 |
| DB 데이터 | DONE | 8종목, 11리포트, 278 financials |
| PostgreSQL | RUNNING | localhost:5432/stock_hub |

---

## 남은 Phase 정의

### Phase 1: FastAPI 서버 + REST API (현재 단계)

**목표**: DB에 저장된 데이터를 HTTP API로 제공

| # | Feature | 파일 | 수용 기준 |
|---|---------|------|----------|
| 1.1 | FastAPI 앱 엔트리포인트 | app/main.py | `uvicorn app.main:app` 기동 |
| 1.2 | Pydantic 응답 스키마 | app/schemas/stock.py | 7 모델 대응 |
| 1.3 | GET /api/stocks | app/api/stocks.py | 전체 종목 목록 |
| 1.4 | GET /api/stocks/{ticker} | 위 파일 | 프로필 + 최신 리포트 |
| 1.5 | GET /api/stocks/{ticker}/financials | 위 파일 | 연간/분기 재무 |
| 1.6 | GET /api/stocks/{ticker}/compare | 위 파일 | CFRA vs Zacks 비교 |
| 1.7 | POST /api/parse | 위 파일 | PDF 업로드 → 파싱 → DB |
| 1.8 | GET /api/stocks/{ticker}/bundle | 위 파일 | 콘텐츠 변수 맵 |

**Preview Test**: Swagger UI (/docs)에서 8개 엔드포인트 전부 호출 → 응답 확인
**Doc 정리**: API spec 문서 생성, CLAUDE.md 업데이트

---

### Phase 2: 데이터 품질 강화

**목표**: 파서 커버리지 확대 + 데이터 완성도 향상

| # | Feature | 수용 기준 |
|---|---------|----------|
| 2.1 | Zacks Financials 파싱 추가 | DHR.pdf fin >= 20 |
| 2.2 | CFRA Balance Sheet 파싱 | pltr.pdf balance_sheet 레코드 존재 |
| 2.3 | Analyst Notes 상세화 (action, title, target_price) | CFRA notes에 action 필드 |
| 2.4 | Zacks Key Stats 확장 | 기존 부분 → 전체 지표 |
| 2.5 | UPSERT 중복 방지 테스트 | 동일 PDF 2회 → 레코드 수 동일 |

**Preview Test**: validate_all.py 확장 + 9 PDF 재파싱 → DB 검증
**Doc 정리**: parser-accuracy-report.md 업데이트

---

### Phase 3: 자동 수집 파이프라인

**목표**: 사람 개입 없이 티커 → PDF → DB 자동화

| # | Feature | 수용 기준 |
|---|---------|----------|
| 3.1 | Playwright headless 스크립트 | 단일 티커 PDF 다운로드 성공 |
| 3.2 | fetcher_service.py | fetch_pdf(ticker, source) → pdf_path |
| 3.3 | APScheduler 정기 수집 | 매일 7AM cron 동작 |
| 3.4 | Watchlist 모델 + CRUD | 종목 추가/삭제/목록 |
| 3.5 | batch_fetch (워치리스트 일괄) | 10종목 순차 수집 성공률 >= 95% |

**Preview Test**: 10종목 일괄 수집 → DB 저장 → API 조회
**Doc 정리**: automation 아키텍처 문서 업데이트

---

### Phase 4: 콘텐츠 파이프라인 + 알림

**목표**: 수집된 데이터 → 블로그/뉴스레터 자동 생성 기반

| # | Feature | 수용 기준 |
|---|---------|----------|
| 4.1 | to_content_vars(ticker) | 템플릿 변수 맵 반환 |
| 4.2 | 등급/목표가 변경 감지 | diff 결과 반환 |
| 4.3 | 변경 시 이메일 알림 | 이메일 수신 확인 |
| 4.4 | PDF 아카이브 (날짜별 보관) | /data/reports/YYYY-MM-DD/ |

**Preview Test**: PLTR 리포트 변경 시뮬레이션 → 알림 → 콘텐츠 변수 확인
**Doc 정리**: 콘텐츠 파이프라인 문서

---

## Phase별 Gate 규칙

```
Plan → Do → Preview Test → Doc 정리 → ✅ 다음 Phase
                ↓ FAIL
           Fix → Re-test
```

모든 Phase는 반드시:
1. Preview Test 통과
2. 관련 문서 정리/업데이트
3. CLAUDE.md 현재 상태 반영

이 3가지를 완료해야 다음 Phase로 진행.

---

## 즉시 시작: Phase 1 (FastAPI API)

이미 데이터가 DB에 있으므로 API만 얹으면 서비스 가능 상태.
예상 작업량: app/main.py + app/schemas/ + app/api/ = 3~4개 파일.
