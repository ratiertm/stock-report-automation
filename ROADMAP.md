# Stock Report Hub — Roadmap

**최종 수정**: 2026-02-28
**목표 MVP 출시**: 2026-03-31
**운영**: 1인 + Claude 협업 (Cowork + Claude Code)

---

## Status Overview

| 상태 | 항목 수 |
|------|--------|
| **Done** | 4 (포털 분석, DB 설계, 자동화 설계, PRD) |
| **Not Started** | 16 |
| **Total** | 20 |

---

## Phase 1: 데이터 수집 엔진 (3/1 ~ 3/14, 2주)

**목표**: 티커 입력 → PDF 다운로드 → 파싱 → DB 저장이 End-to-End로 동작

| ID | 항목 | 도구 | 상태 | 기간 | 의존성 | PRD |
|----|------|------|------|------|--------|-----|
| 1.0 | 포털 구조 분석 + 검색 플로우 테스트 | Cowork | **Done** | - | - | - |
| 1.1 | Python 환경 세팅 (pdfplumber, tabula-py, venv) | Claude Code | **Not Started** | 3/1 | - | - |
| 1.2 | DB 마이그레이션 7개 테이블 | Claude Code | **Not Started** | 3/1~3/2 | 1.1 | P0-4 |
| 1.3 | CFRA 파서 개발 (pltr.pdf 기준) | Claude Code | **Not Started** | 3/2~3/5 | 1.1 | P0-2 |
| 1.4 | CFRA 파싱 정확도 검증 (수동 대조) | Cowork | **Not Started** | 3/5~3/6 | 1.3 | P0-2 |
| 1.5 | Zacks 파서 개발 (DHR.pdf 기준) | Claude Code | **Not Started** | 3/6~3/9 | 1.1 | P0-3 |
| 1.6 | Zacks 파싱 정확도 검증 | Cowork | **Not Started** | 3/9~3/10 | 1.5 | P0-3 |
| 1.7 | Chrome MCP 수집 자동화 (단일 티커) | Cowork | **Not Started** | 3/10~3/11 | 1.4, 1.6 | P0-1 |
| 1.8 | 워치리스트 모델 + CRUD | Claude Code | **Not Started** | 3/11~3/12 | 1.2 | P0-6 |
| 1.9 | 일괄 수집 (워치리스트 기반) | Cowork | **Not Started** | 3/12~3/14 | 1.7, 1.8 | P0-6 |

### Phase 1 완료 기준

- [ ] pltr.pdf → 7개 테이블 저장, 숫자 필드 정확도 ≥ 98%
- [ ] DHR.pdf → 7개 테이블 저장, 숫자 필드 정확도 ≥ 98%
- [ ] 10종목 일괄 수집 → 전체 성공률 ≥ 95%

### Phase 1 리스크

| 리스크 | 영향 | 대응 |
|--------|------|------|
| pdfplumber 테이블 파싱 정확도 부족 | 재무제표 데이터 누락 | tabula-py 병행, 수동 보정 로직 추가 |
| Fidelity 포털 rate limiting | 일괄 수집 실패 | 요청 간 딜레이 5~10초, 재시도 로직 |
| PDF 포맷 변형 (같은 소스 내 차이) | 파서 실패 | 추가 샘플 5개로 견고성 테스트 |

---

## Phase 2: 조회 UI + 비교 뷰 (3/15 ~ 3/28, 2주)

**목표**: 저장된 데이터를 웹에서 검색·조회·비교할 수 있는 서비스 상태

| ID | 항목 | 도구 | 상태 | 기간 | 의존성 | PRD |
|----|------|------|------|------|--------|-----|
| 2.1 | 종목 검색 페이지 (LiveView) | Claude Code | **Not Started** | 3/15~3/16 | Phase 1 | P0-5 |
| 2.2 | 종목 프로필 상세 페이지 | Claude Code | **Not Started** | 3/16~3/18 | 2.1 | P0-5 |
| 2.3 | 리포트 상세 뷰 (highlights, rationale, scores) | Claude Code | **Not Started** | 3/18~3/19 | 2.2 | P0-5 |
| 2.4 | 재무 데이터 테이블 (연간/분기 토글) | Claude Code | **Not Started** | 3/19~3/21 | 2.2 | P0-5 |
| 2.5 | 멀티소스 비교 뷰 (CFRA vs Zacks 사이드바이사이드) | Claude Code | **Not Started** | 3/22~3/24 | 2.3 | P0-7 |
| 2.6 | 워치리스트 대시보드 (카드 뷰) | Claude Code | **Not Started** | 3/24~3/26 | 2.1, 1.8 | P1-4 |
| 2.7 | 50종목 실데이터 수집 + 통합 테스트 | Cowork | **Not Started** | 3/26~3/28 | All | - |

### Phase 2 완료 기준

- [ ] 티커 검색 → 프로필 + 리포트 + 재무 한 화면 표시
- [ ] CFRA/Zacks 동일 종목 비교 뷰 동작
- [ ] 50종목 데이터 수집·저장·조회 정상 동작

### Phase 2 리스크

| 리스크 | 영향 | 대응 |
|--------|------|------|
| LiveView 페이지 복잡도 | 개발 지연 | 기본 테이블 뷰 먼저, 차트는 P1로 이관 |
| 50종목 수집 시간 초과 | 서비스 출시 지연 | 병렬 수집(큐 2개) + 야간 배치 |

---

## Phase 3: 완전 자동화 + 안정화 (3/29 ~ 4/15, 2.5주)

**목표**: 사람 개입 없이 정기 수집, 에러 복구, 알림까지 자동 동작

| ID | 항목 | 도구 | 상태 | 기간 | 의존성 | PRD |
|----|------|------|------|------|--------|-----|
| 3.1 | Python Playwright headless 스크립트 | Claude Code | **Not Started** | 3/29~4/1 | Phase 1 | P1-1 |
| 3.2 | Oban 정기 수집 스케줄러 (매일 7AM) | Claude Code | **Not Started** | 4/1~4/3 | 3.1 | P1-1 |
| 3.3 | 리포트 변경 감지 (등급/목표가 diff) | Claude Code | **Not Started** | 4/3~4/5 | Phase 2 | P1-3 |
| 3.4 | 콘텐츠 변수 맵 (`to_content_vars`) | Claude Code | **Not Started** | 4/5~4/8 | Phase 2 | P1-2 |
| 3.5 | PDF 아카이브 (날짜별 보관 + 다운로드) | Claude Code | **Not Started** | 4/8~4/10 | Phase 1 | P1-5 |
| 3.6 | 에러 핸들링 + 실패 알림 (이메일) | Claude Code | **Not Started** | 4/10~4/12 | 3.2 | - |
| 3.7 | 1주 연속 운영 안정성 테스트 | Cowork | **Not Started** | 4/12~4/15 | All | - |

### Phase 3 완료 기준

- [ ] 매일 7AM 워치리스트 자동 수집 → 1주 연속 성공률 ≥ 95%
- [ ] 등급/목표가 변경 감지 + 이메일 알림
- [ ] `to_content_vars("PLTR")` → 블로그 템플릿 변수 맵 반환

---

## Phase 4: 확장 + SaaS 연동 (4/16~, 지속적)

**목표**: 추가 소스, API, 콘텐츠 자동 생성, SaaS 티어 연동

| ID | 항목 | 도구 | 상태 | 기간 | 의존성 | PRD |
|----|------|------|------|------|--------|-----|
| 4.1 | Argus 파서 추가 | Claude Code | **Not Started** | TBD | Phase 3 | P2-1 |
| 4.2 | S&P Capital IQ 파서 추가 | Claude Code | **Not Started** | TBD | Phase 3 | P2-1 |
| 4.3 | REST API (종목 데이터 외부 제공) | Claude Code | **Not Started** | TBD | Phase 2 | P2-2 |
| 4.4 | 웹훅 알림 (새 리포트/등급 변경) | Claude Code | **Not Started** | TBD | 3.3 | P2-3 |
| 4.5 | 콘텐츠 자동 생성 파이프라인 | Claude Code | **Not Started** | TBD | 3.4 | P2-4 |
| 4.6 | 종목 카드 임베드 위젯 | Claude Code | **Not Started** | TBD | 4.3 | P2-5 |
| 4.7 | SaaS 플랜 연동 (Feature Gating) | Claude Code | **Not Started** | TBD | 4.3 | P2-6 |
| 4.8 | HTTP 직접 다운로드 전환 (Playwright 대체) | Claude Code | **Not Started** | TBD | 4.1 | - |

---

## Dependency Map

```
Phase 1                    Phase 2                Phase 3              Phase 4
─────────────────────────────────────────────────────────────────────────────────

1.1 Python 환경 ─┐
                  ├─ 1.3 CFRA 파서 ──┐
1.2 DB 마이그 ───┤                    ├─ 1.7 수집 자동화 ──┐
                  ├─ 1.5 Zacks 파서 ─┘                     │
                  └─ 1.8 워치리스트 ──── 1.9 일괄수집 ─────┤
                                                            │
                         2.1 검색 ── 2.2 프로필 ── 2.3 리포트 ── 2.5 비교뷰
                                         │                            │
                                    2.4 재무테이블    2.6 대시보드     │
                                                            │         │
                                    3.1 Playwright ── 3.2 스케줄러    │
                                         │                   │        │
                                    3.4 변수맵 ─── 3.3 변경감지     │
                                         │              │            │
                                    3.5 아카이브    3.6 알림         │
                                                                      │
                                              4.1~4.2 추가파서       │
                                              4.3 REST API ──────────┘
                                              4.5 콘텐츠 자동생성
                                              4.7 SaaS 연동
```

---

## Key Milestones

| 날짜 | 마일스톤 | 의미 |
|------|---------|------|
| **3/6** | CFRA 파서 검증 완료 | 첫 소스 파싱 동작 확인 |
| **3/10** | Zacks 파서 검증 완료 | 멀티소스 파싱 동작 |
| **3/14** | Phase 1 완료 | End-to-End 수집→저장 파이프라인 |
| **3/24** | 비교 뷰 완성 | 핵심 차별화 기능 |
| **3/28** | 50종목 통합 테스트 | 서비스 품질 검증 |
| **3/31** | **MVP 출시** | 서비스 가능 상태 |
| **4/15** | Phase 3 완료 | 완전 자동 운영 |

---

## 도구 전환 가이드: Cowork vs Claude Code

### 역할 분담 원칙

| 도구 | 핵심 역할 | 사용 시점 |
|------|----------|----------|
| **Cowork** | 브라우저 자동화, 문서 작성, PDF 분석, 데이터 검증 | Chrome MCP가 필요한 작업, 비코드 작업 |
| **Claude Code** | Elixir/Python 코드 개발, 테스트, 마이그레이션, 서버 실행 | 프로젝트 폴더에서 코드를 쓰고 실행하는 작업 |

### 구분 기준: "이 작업에 브라우저가 필요한가, 터미널이 필요한가?"

- **브라우저 필요** → Cowork (Chrome MCP로 포털 조작, PDF 다운로드, UI 확인)
- **터미널 필요** → Claude Code (`mix`, `python3`, `git`, 코드 편집, 테스트 실행)
- **둘 다 필요** → Claude Code 메인 + Cowork 보조

### Phase별 도구 비중

```
Phase 1 (3/1~3/14)
├── Week 1: Claude Code 70% + Cowork 30%
│   ├── Claude Code: venv 세팅, DB 마이그레이션, CFRA/Zacks 파서 코드
│   └── Cowork: 추가 PDF 샘플 수집 (Chrome MCP), 파싱 결과 vs 원본 PDF 대조 검증
│
├── Week 2: Cowork 60% + Claude Code 40%
│   ├── Cowork: Chrome MCP 수집 자동화 테스트, 일괄 수집 실행
│   └── Claude Code: 워치리스트 모델, 수집 모듈 코드
│
Phase 2 (3/15~3/28)
├── Claude Code 90% + Cowork 10%
│   ├── Claude Code: LiveView 페이지, 컴포넌트, 라우팅 전부
│   └── Cowork: 완성된 UI를 브라우저에서 확인, 50종목 수집 실행
│
Phase 3 (3/29~4/15)
├── Claude Code 95% + Cowork 5%
│   ├── Claude Code: Playwright 스크립트, Oban 워커, 에러 핸들링 전부
│   └── Cowork: 1주 연속 운영 모니터링 시 브라우저 확인
│
Phase 4 (4/16~)
└── Claude Code 100%
    └── 코드 개발 전용 (Cowork 불필요)
```

### 동시 사용 패턴 (병행이 효과적인 경우)

1. **파서 개발 + 검증 루프** (Phase 1, Week 1)
   - Claude Code에서 파서 코드 수정 → 실행 → JSON 출력
   - Cowork에서 원본 PDF 열어서 결과 대조 → 오류 보고 → Claude Code로 돌아가서 수정

2. **수집 + 코드 루프** (Phase 1, Week 2)
   - Cowork에서 Chrome MCP로 PDF 다운로드 실행
   - Claude Code에서 다운로드된 PDF를 파싱 → DB 저장 → 결과 확인

3. **UI 개발 + 확인 루프** (Phase 2)
   - Claude Code에서 LiveView 코드 작성 → `mix phx.server` 실행
   - Cowork에서 localhost:4000 접속하여 UI 확인 → 피드백

---

## Capacity Notes

1인 + Claude 협업 기준, 일일 유효 작업 시간 4~6시간 가정.

- **Phase 1 (2주)**: 코드 비중 높음. Claude가 파서 코드 생성, 본인이 검증·튜닝. 가장 병목 구간은 **파싱 정확도 튜닝** (PDF마다 미세 차이)
- **Phase 2 (2주)**: LiveView UI 작업. Claude가 컴포넌트 생성, 본인이 UX 확인. 비교적 예측 가능
- **Phase 3 (2.5주)**: 인프라 작업. Playwright 세팅이 한 번 걸리면 나머지는 수월
- **Phase 4 (지속)**: 새 소스 추가 시 파서당 2~3일 예상

**버퍼**: 각 Phase에 2~3일 버퍼 내장. 전체 1개월 + 2주 버퍼 = 약 6주 안에 Phase 3까지 완료 목표.
