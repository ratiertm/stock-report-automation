# 세션 로그 — 2026-02-28

## 세션 개요

- **환경**: Claude Desktop Cowork 모드
- **작업 기간**: 2026-02-28 (이전 세션에서 이어진 연속 세션)
- **주요 목표**: CFRA/Zacks PDF 파서 개발 + 정확도 검증 + 프로젝트 정비
- **최종 결과**: 파서 2종 100% 정확도 달성, bkit PDCA 워크플로우 통합

---

## 이전 세션 (컨텍스트 요약)

### 완료 항목

- Fidelity Research 포털 구조 분석 (Chrome MCP)
- PDF 9개 수집 (CFRA 5 + Zacks 4, 4개 섹터)
- 초기 파싱 테스트 및 P0 버그 식별
- `parsing-validation-report.md` 초안 작성

### 식별된 P0 버그

| 버그 | 원인 | 상태 |
|------|------|------|
| CFRA ticker/exchange 뒤바뀜 | "Symbol: NasdaqGS \| PLTR" 파싱 순서 오류 | → 이번 세션에서 수정 |
| CFRA sub_industry 텍스트 오버플로우 | 단어 수 제한 없음 | → 이번 세션에서 수정 |
| Zacks Rank 파싱 오류 | "(1-5) 2-Buy" → rank=1, label=5로 잘못 파싱 | → 이번 세션에서 수정 |

---

## 이번 세션 작업 내역

### 1. CFRA 파서 개발 (`cfra_parser.py`)

**생성한 파일**: `cfra_parser.py` (26KB)

- Python dataclass 5종: CFRAProfile, CFRAReport, CFRAKeyStats, CFRAFinancial, CFRAAnalystNote
- DB 7테이블 매핑 완료
- P0 버그 수정:
  - `_parse_header`: ticker/exchange 분리 수정 (`Symbol: NasdaqGS | PLTR`)
  - `_parse_header`: sub_industry 3단어 제한으로 오버플로우 방지
- 텍스트 섹션 파싱 이슈 발견 및 수정:
  - **문제**: highlights, investment_rationale, business_summary, sub_industry_outlook 모두 "NOT FOUND"
  - **원인**: CFRA Page 1의 멀티컬럼 레이아웃 — Highlights와 Investment Rationale이 EPS 데이터와 인터리빙
  - **해결**: `_parse_text_sections` 완전 재작성 — 멀티컬럼 감지 + 불릿 포인트 수집 + EPS 데이터 클리닝
  - Business Summary는 Page 2, Sub-Industry Outlook은 Page 4에서 별도 추출

### 2. Zacks 파서 개발 (`zacks_parser.py`)

**생성한 파일**: `zacks_parser.py` (18KB)

- Python dataclass 5종: ZacksProfile, ZacksReport, ZacksKeyStats, ZacksFinancial, ZacksPeer
- P0 버그 수정:
  - Zacks Rank regex: `r'Zacks Rank:\s*\(1-5\)\s*(\d)-(\w+)'`
- 텍스트 섹션 이슈 발견 및 수정:
  - **문제**: Reasons To Buy/Sell "NOT FOUND", Peers 0개
  - **원인 1**: 섹션 헤더가 ":" 로 끝남 (예: `Reasons To Buy:\n`) — 초기 regex에 `:` 누락
  - **원인 2**: pdfplumber 테이블 추출이 1-row만 반환 → 피어 데이터 못 읽음
  - **해결**: 섹션 regex에 `:` 추가, Industry Comparison을 텍스트 기반 파싱으로 전환

### 3. 정확도 검증 (`validate_all.py`)

**생성한 파일**: `validate_all.py` (12KB)

- 9개 PDF × 170개 검증 항목 ground truth 작성
- CFRA: 5개 파일 (PLTR, MSFT, JNJ, JPM, PG) — profile, report, key_stats, financials count, text sections
- Zacks: 4개 파일 (DHR, AAPL, MSFT, JPM) — profile, report, style_scores, text sections, peers count
- 초기 결과: 99.4% (1 실패 — PLTR stars_rating)
- PLTR STARS 검증: PDF에 `«` 5개 = STARS 5 확인 → ground truth 오류 (4로 잘못 기록)
- **최종 결과: 100% 정확도**

### 4. 리포트 정비

#### `parser-accuracy-report.md` (신규 생성)
- 파서 코드 정확도 리포트
- 9개 PDF × 170항목 상세 검증 결과
- 파서 아키텍처, DB 매핑 커버리지, P2 잔여 작업

#### `parsing-validation-report.md` (최종 업데이트)
- 목적 재정의: "DB 스키마 적합성 검증"
- 7개 테이블 모두 "적합, 수정 불필요"로 확정
- 초기 잘못된 권고 정정:
  - stock_reports 컬럼 추가 불필요 (stock_key_stats에서 이미 커버)
  - is_estimate 컬럼 이미 설계에 존재

### 5. CLAUDE.md 업데이트 (파서 참조 추가)

- Python 파서 모듈 섹션 추가 (의존성, API 예시, 반환 구조, DB 매핑 커버리지)
- Elixir 연동 방식 (Python Port) 코드 예시
- 파일 구조 업데이트 (9개 PDF + 3개 Python 파일)
- 코드 생성 규칙 추가 (#2 파서 참조, #10 validate_all.py 회귀 테스트)
- 현재 상태 및 다음 단계 업데이트

### 6. bkit (Vibecoding Kit) 프로젝트 통합

- 웹 검색으로 bkit 정보 수집 (GitHub, 공식 사이트)
- `bkit.config.json` 생성 — Elixir/Python 프로젝트에 맞춤 설정:
  - sourceExtensions: `.ex`, `.exs`, `.heex`, `.py`, `.js`
  - excludePatterns: `_build`, `deps`, `__pycache__` 등
  - PDCA 90% 임계값, 최대 5회 자동 수정
- `docs/` PDCA 디렉토리 구조 생성 (01-plan ~ 04-report + archive)
- CLAUDE.md에 bkit 섹션 추가 (설치, 명령어 8개, 문서 구조, 활용 예시)

### 7. 대화 원문 백업

- `session-transcript-2026-02-28.jsonl` (12MB) — 전체 대화 원문 프로젝트 폴더에 복사

---

## 의사결정 기록

| 결정 | 이유 |
|------|------|
| pdfplumber 테이블 추출 대신 텍스트 기반 regex 사용 | CFRA 8~13개 테이블 대부분 비구조적, Zacks는 1-row만 반환 |
| DB 스키마 변경 없음 | 초기 컬럼 추가 권고는 stock_key_stats에서 이미 커버되는 필드 |
| Python Port 방식 Elixir 연동 | System.cmd로 JSON stdout 파싱 — 가장 단순하고 의존성 적음 |
| bkit PDCA를 프로젝트에 포함 | Phase 2 Elixir 개발을 체계적 PDCA 사이클로 진행하기 위함 |

---

## 생성/수정된 파일 목록

| 파일 | 작업 | 크기 |
|------|------|------|
| `cfra_parser.py` | 신규 생성 | 26KB |
| `zacks_parser.py` | 신규 생성 | 18KB |
| `validate_all.py` | 신규 생성 | 12KB |
| `parser-accuracy-report.md` | 신규 생성 | — |
| `parsing-validation-report.md` | 최종 업데이트 | — |
| `CLAUDE.md` | 2회 업데이트 (파서 참조 + bkit) | — |
| `bkit.config.json` | 신규 생성 | — |
| `docs/` (5개 디렉토리) | 신규 생성 | — |
| `session-transcript-2026-02-28.jsonl` | 대화 원문 복사 | 12MB |

---

## 현재 프로젝트 상태

### 완료

- ✅ Fidelity Research 포털 구조 분석
- ✅ Chrome MCP 검색 플로우 테스트
- ✅ DB 스키마 7테이블 설계 (CFRA + Zacks 호환)
- ✅ 자동화 아키텍처 3방안 설계
- ✅ 9개 PDF 수집 (CFRA 5 + Zacks 4)
- ✅ Python 파서 2종 개발 (cfra_parser.py, zacks_parser.py)
- ✅ 정확도 검증 100% (170개 항목)
- ✅ bkit PDCA 워크플로우 통합

### 다음 단계 (Claude Code에서 진행)

1. `priv/python/parse_report.py` CLI 래퍼 생성
2. Ecto 마이그레이션 7개 테이블
3. Ecto 스키마 7개 모듈
4. `stock_reports.ex` 컨텍스트 모듈 (UPSERT)
5. `report_parse_worker.ex` Oban 워커
6. P2: EPS merge, Balance Sheet, Zacks Financials

---

## 기술 노트

### CFRA 멀티컬럼 레이아웃 (Page 1)

```
[Highlights 텍스트]  |  [Investment Rationale 텍스트]
[• bullet point]     |  [• bullet point]
[EPS 데이터 행]      |  [EPS 데이터 행]
[• bullet point]     |  [• bullet point]
```

pdfplumber는 이를 한 줄로 합쳐서 반환 → "Highlights Investment Rationale/Risk" 합쳐진 헤더를 감지하고, 불릿 포인트만 수집하는 방식으로 해결.

### Zacks 섹션 구분자

Zacks PDF의 섹션 헤더는 `SectionName:\n` 형식 (콜론 + 줄바꿈). 초기에 콜론을 빠뜨려서 모든 텍스트 섹션이 NOT FOUND였음.

### Ground Truth 검증의 중요성

PLTR STARS rating ground truth를 4로 잘못 기록 → 99.4% 결과. 실제 PDF에서 `«` 문자 5개 확인 후 100%로 정정. 파서가 아닌 검증 데이터의 오류였음.
