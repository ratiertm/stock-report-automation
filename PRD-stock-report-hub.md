# PRD: Stock Report Hub — 주식 정보 허브

**작성일**: 2026-02-28
**작성자**: MindBuild
**상태**: Draft
**목표 출시**: 2026-03-31 (1개월)

---

## Problem Statement

개인 투자자와 콘텐츠 제작자는 CFRA, Zacks 등 여러 리서치 소스에서 종목 리포트를 **수동으로 하나씩** 찾아 읽고, 핵심 데이터를 직접 추출해야 한다. 데이터가 PDF에 갇혀 있어 소스 간 비교가 어렵고, 블로그나 뉴스레터 같은 콘텐츠를 작성할 때마다 같은 수작업을 반복해야 한다. 이 문제를 해결하지 않으면 리서치 시간의 70% 이상을 데이터 수집·정리에 소비하게 되며, 콘텐츠 생산 속도와 투자 의사결정 품질이 모두 떨어진다.

---

## Goals

1. **수집 자동화**: 티커 목록을 입력하면 CFRA/Zacks 리포트가 자동으로 수집·파싱·저장된다
2. **데이터 정규화**: 소스마다 다른 포맷(STARS vs Rank, 재무제표 구조 등)을 통합 스키마로 정규화하여 **1개 쿼리로 멀티소스 비교** 가능
3. **콘텐츠 파이프라인 연결**: 저장된 데이터가 템플릿 변수로 바로 주입되어 블로그/뉴스레터 초안 생성 시간을 **현재 대비 80% 단축**
4. **1개월 내 서비스 가능 상태**: 데이터 수집 + 저장 + 조회 UI까지 동작하는 상태로 출시
5. **확장 가능 구조**: 향후 Argus, S&P, Morningstar 등 추가 소스와 API 제공, SaaS 구독 모델로 확장 가능한 아키텍처

---

## Non-Goals

1. **실시간 시세 제공** — 이 프로젝트는 리서치 리포트 기반 정보 허브이며, 실시간 주가 피드는 범위 밖
2. **자동매매 연동** — 트레이딩 실행은 상위 SaaS의 `trading/` 모듈 담당. 여기서는 인사이트 데이터만 제공
3. **자체 애널리스트 리포트 생산** — 기존 리서치 하우스의 리포트를 가공·제공하는 것이지, 독자 분석을 생성하는 것이 아님
4. **모바일 앱** — 1개월 MVP는 웹(LiveView) 기반. 모바일은 Phase 4 이후 검토
5. **다국어 지원** — MVP는 영문 리포트 + 한국어 UI. 다국어 리포트 파싱은 향후 과제

---

## User Stories

### 본인 (1인 운영자)

- As a **콘텐츠 제작자**, I want to 워치리스트 종목의 최신 리포트를 매일 자동 수집 so that 매번 포털에 접속하는 수고를 없앤다
- As a **콘텐츠 제작자**, I want to 종목 데이터를 템플릿에 자동 주입 so that 블로그 초안 작성 시간이 수 분으로 줄어든다
- As a **투자자**, I want to CFRA와 Zacks의 동일 종목 리포트를 나란히 비교 so that 한쪽 소스에 편향되지 않은 판단을 내린다

### 소규모 팀

- As a **팀 리더**, I want to 팀원들이 동일한 정규화된 데이터를 조회 so that 분석 기준이 통일된다
- As a **팀원**, I want to 종목을 검색하면 프로필, 재무, 애널리스트 노트가 한 화면에 표시 so that 여러 PDF를 열 필요가 없다

### SaaS 구독자 (향후)

- As a **구독자**, I want to 내 워치리스트의 리포트 업데이트 알림을 받고 so that 중요한 등급 변경을 놓치지 않는다
- As a **구독자**, I want to 종목 카드 위젯을 내 사이트에 임베드 so that 독자에게 전문적인 데이터를 보여준다

### API 소비자 (향후)

- As a **개발자**, I want to REST API로 종목 데이터를 JSON으로 가져가 so that 내 앱에 리서치 데이터를 통합한다
- As a **개발자**, I want to 웹훅으로 새 리포트 알림을 받고 so that 실시간으로 데이터 파이프라인을 트리거한다

---

## Requirements

### P0: Must-Have (MVP — 1개월)

| ID | 요구사항 | 수용 기준 |
|----|---------|----------|
| P0-1 | **PDF 자동 수집** | 티커+소스 입력 → Fidelity 포털에서 PDF 다운로드 → 로컬 저장. 성공률 95% 이상 |
| P0-2 | **CFRA 파서** | pltr.pdf 기준: profile, report, financials(8년), key_stats, analyst_notes 추출. 숫자 필드 정확도 98% 이상 |
| P0-3 | **Zacks 파서** | DHR.pdf 기준: profile, report, financials, key_stats, peers, reasons_to_buy/sell 추출. 숫자 필드 정확도 98% 이상 |
| P0-4 | **DB 저장** | 7개 테이블(stock-report-db-design.md 기준)에 UPSERT. 동일 종목+소스+날짜 중복 방지 |
| P0-5 | **종목 조회 UI** | LiveView 페이지에서 티커 검색 → 프로필 + 최신 리포트 + 재무 요약 + 애널리스트 노트 표시 |
| P0-6 | **워치리스트** | 사용자별 워치리스트(최대 50종목) 관리. 워치리스트 기반 일괄 수집 가능 |
| P0-7 | **멀티소스 비교 뷰** | 동일 종목의 CFRA/Zacks 리포트를 나란히 비교하는 UI (recommendation, target_price, key_stats 대비) |

### P1: Nice-to-Have (2개월 내)

| ID | 요구사항 | 수용 기준 |
|----|---------|----------|
| P1-1 | **정기 자동 수집** | Oban 스케줄러로 매일 오전 7시 워치리스트 자동 수집. Python Playwright headless |
| P1-2 | **콘텐츠 변수 맵** | `to_content_vars(ticker)` → ContentTemplate에 주입 가능한 변수 맵 반환 |
| P1-3 | **리포트 변경 감지** | 이전 리포트 대비 등급/목표가 변경 시 하이라이트 + 알림 |
| P1-4 | **대시보드** | 워치리스트 전체 종목의 리포트 요약 대시보드 (카드 뷰) |
| P1-5 | **PDF 아카이브** | 원본 PDF를 날짜별로 보관, 다운로드 가능 |

### P2: Future Considerations

| ID | 요구사항 | 수용 기준 |
|----|---------|----------|
| P2-1 | **추가 소스 파서** | Argus, S&P Capital IQ, Morningstar 파서 추가 |
| P2-2 | **REST API** | 외부 개발자용 종목 데이터 API (Pro+ 플랜) |
| P2-3 | **웹훅 알림** | 새 리포트/등급 변경 시 웹훅 발송 |
| P2-4 | **콘텐츠 자동 생성** | 새 리포트 → 블로그 초안 자동 생성 → 배포 파이프라인 연결 |
| P2-5 | **종목 카드 임베드** | 외부 사이트에 임베드 가능한 종목 카드 위젯 |
| P2-6 | **SaaS 티어 연동** | 상위 Elixir SaaS의 플랜별 Feature Gating 적용 |

---

## Success Metrics

### Leading Indicators (1개월 내 측정)

| 지표 | 목표 | 측정 방법 |
|------|------|----------|
| PDF 수집 성공률 | ≥ 95% | 수집 시도 대비 성공 비율 |
| 파싱 정확도 (숫자 필드) | ≥ 98% | 수동 검증 vs 파싱 결과 비교 (샘플 10개) |
| 데이터 수집 시간 | ≤ 30초/종목 | 티커 입력 → DB 저장 완료 |
| 워치리스트 일괄 수집 | ≤ 15분/50종목 | 전체 워치리스트 수집 완료 시간 |

### Lagging Indicators (3개월 내 측정)

| 지표 | 목표 | 측정 방법 |
|------|------|----------|
| 콘텐츠 작성 시간 단축 | 80% 감소 | 리포트 기반 블로그 작성 시간 Before/After |
| 커버 종목 수 | 100+ 종목 | DB에 저장된 고유 종목 수 |
| 리포트 축적량 | 500+ 리포트 | stock_reports 테이블 row 수 |
| 멀티소스 커버리지 | 50%+ 종목이 2개 이상 소스 | CFRA+Zacks 동시 보유 종목 비율 |

---

## Open Questions

| # | 질문 | 담당 |
|---|------|------|
| Q1 | Fidelity 포털의 rate limiting 정책은? 일일 최대 요청 수는? | Engineering — 실제 수집 테스트로 확인 |
| Q2 | pdfplumber로 CFRA 8년 재무제표 테이블 파싱 정확도는 충분한가? tabula-py 병행 필요? | Engineering — Phase 1 MVP에서 검증 |
| Q3 | 포털 사이트 구조 변경 시 파서 업데이트 전략은? 자동 감지 가능? | Engineering |
| Q4 | 리포트 데이터의 재배포 라이선스 이슈는 없는가? API로 외부 제공 시 법적 검토 필요 | Legal |
| Q5 | 향후 SaaS 과금 시 종목 수 기반 vs 기능 기반 중 어떤 모델? | Product |
| Q6 | Argus, S&P Capital IQ 리포트의 PDF 구조는 CFRA/Zacks와 얼마나 다른가? | Engineering — 샘플 확보 후 분석 |

---

## Timeline

```
Week 1 (3/1~3/7)    ── Phase 1 MVP 핵심
├── pdfplumber 환경 세팅 + CFRA 파서 개발
├── pltr.pdf 파싱 정확도 검증
├── DB 마이그레이션 (7 테이블)
└── Zacks 파서 개발 시작

Week 2 (3/8~3/14)   ── Phase 1 완성 + 수집 자동화
├── Zacks 파서 완성 + DHR.pdf 검증
├── Chrome MCP 수집 자동화 안정화
├── 워치리스트 모델 + CRUD
└── 일괄 수집 기능

Week 3 (3/15~3/21)  ── Phase 2 조회 UI
├── 종목 검색 + 프로필 페이지 (LiveView)
├── 리포트 상세 뷰
├── 멀티소스 비교 뷰
└── 재무 데이터 테이블/차트

Week 4 (3/22~3/31)  ── 안정화 + 배포
├── 워치리스트 대시보드
├── 정기 수집 Oban 스케줄러 (Playwright 전환)
├── 에러 핸들링 + 알림
└── 50종목 실데이터 수집 테스트 + 버그 수정
```

### Dependencies

- **pdfplumber/tabula-py**: Python 3.10+ 환경 필요
- **Playwright** (Week 4): `pip install playwright && playwright install chromium`
- **Elixir SaaS 기반**: `market/` 모듈 구조, Oban 설정, Ecto 마이그레이션 체계
- **Fidelity Research 포털 접근성**: 사이트 구조 변경 시 파서 업데이트 필요

---

## Architecture Reference

상세 설계 문서는 같은 폴더에 위치:

- **DB 스키마**: `stock-report-db-design.md` — 7개 테이블, 인덱스, 소스별 필드 매핑, PLTR/DHR 매핑 예시
- **자동화 아키텍처**: `stock-report-automation.md` — 포털 구조, 3가지 방안, 코드 설계, Oban 워커
- **프로젝트 가이드**: `CLAUDE.md` — Claude Code용 컨텍스트, 모듈 구조, 코드 규칙
- **샘플 PDF**: `pltr.pdf` (CFRA), `DHR.pdf` (Zacks) — 파서 개발·검증용
