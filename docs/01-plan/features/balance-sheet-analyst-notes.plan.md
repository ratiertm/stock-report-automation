# Balance Sheet + Analyst Notes 파싱 확장 Planning Document

> **Summary**: CFRA Balance Sheet 10년 데이터 파싱 + Analyst Notes 상세 필드(action, title, target_price) 추출
>
> **Project**: Stock Report Hub
> **Author**: MindBuild
> **Date**: 2026-03-02
> **Status**: Draft

---

## 1. Overview

### 1.1 Purpose

E2E 파이프라인 검증 완료 후, DB 테이블 중 비어있는 `stock_balance_sheets`와
불완전한 `stock_analyst_notes`를 채우는 파서 확장 작업.

### 1.2 Background

- E2E 파이프라인 11개 PDF → DB 저장 검증 완료 (2026-03-02)
- `stock_balance_sheets` 테이블: 0 rows — 파서 미구현
- `stock_analyst_notes` 테이블: 6 rows — "Analysis prepared by" 1줄만 추출 중
- CFRA PDF에는 10년치 Balance Sheet + 4~8개 Analyst Research Notes 존재
- Zacks PDF에는 Balance Sheet 없음 (Financial Strength 섹션에 D/E만 존재)

### 1.3 Related Documents

- `stock-report-db-design.md` — DB 스키마 설계
- `parser-accuracy-report.md` — 파서 정확도 리포트
- `docs/01-plan/features/python-stack.plan.md` — Python 스택 전환 계획

---

## 2. Current State Analysis

### 2.1 Balance Sheet — 현재 상태

**DB 모델 (`stock_balance_sheets`)**: 13개 컬럼 정의 완료

| 컬럼 | 타입 | 설명 |
|------|------|------|
| cash | Numeric(15,2) | 현금성 자산 |
| current_assets | Numeric(15,2) | 유동자산 |
| total_assets | Numeric(15,2) | 총자산 |
| current_liabilities | Numeric(15,2) | 유동부채 |
| long_term_debt | Numeric(15,2) | 장기부채 |
| total_capital | Numeric(15,2) | 총자본 |
| capital_expenditures | Numeric(15,2) | 자본적 지출 |
| cash_from_operations | Numeric(15,2) | 영업현금흐름 |
| current_ratio | Numeric(6,2) | 유동비율 |
| ltd_to_cap_pct | Numeric(6,2) | 장기부채/자본 비율 |
| net_income_to_revenue_pct | Numeric(6,2) | 순이익률 |
| return_on_assets_pct | Numeric(6,2) | ROA |
| return_on_equity_pct | Numeric(6,2) | ROE |

**CRUD**: `upsert_balance_sheet()` — 아직 미구현
**파서**: Balance Sheet 파싱 로직 — 아직 미구현

**CFRA PDF 실제 데이터 (MSFT 예시)**:
```
Balance Sheet and Other Financial Data (Million USD)
Cash 94,565 75,543 111,256 104,749 130,256 136,492 133,832 133,664 132,901 113,041
Current Assets 191,131 159,734 184,257 ...
Total Assets 619,003 512,163 411,976 ...
Current Liabilities 141,218 125,286 104,149 ...
Long Term Debt 40,152 42,688 41,990 ...
Total Capital 455,663 366,329 285,664 ...
Capital Expenditures 64,551 44,477 28,107 ...
Cash from Operations 136,162 118,548 87,582 ...
Current Ratio 1.35 1.27 1.77 ...
% Long Term Debt of Capitalization 8.80 11.70 14.70 ...
% Net Income of Revenue 36.10 36.00 34.10 ...
% Return on Assets 14.20 14.80 14.24 ...
% Return on Equity 33.30 37.10 38.80 ...
```
- 10년치 데이터 (2016~2025), 연도 헤더는 "Per Share Data (USD)" 줄에 있음
- 13개 항목이 DB 모델과 1:1 매핑

### 2.2 Analyst Notes — 현재 상태

**DB 모델 (`stock_analyst_notes`)**: 필드 정의 완료

| 컬럼 | 현재 추출 | 미추출 |
|------|----------|--------|
| published_at | ✅ (1개만) | 4~8개 모두 추출 필요 |
| analyst_name | ✅ (1개만) | 각 노트별 추출 필요 |
| stock_price_at_note | ✅ (1개만) | 각 노트별 추출 필요 |
| title | ❌ | 신규 추출 필요 |
| action | ❌ | 신규 추출 필요 |
| target_price | ❌ | 신규 추출 필요 |
| content | ❌ | 신규 추출 필요 |

**CFRA PDF 실제 데이터 (MSFT 예시)**:
```
Analyst Research Notes and other Company News
January 29, 2026
06:05 AM ET... CFRA Maintains Strong Buy Opinion on Shares of Microsoft Corporation (MSFT 449.18*****):
We cut our target to $550 from $620, on a lower revised P/E of about 27x our CY 27
view of $20.55. We increase our FY 26 (Jun.) EPS estimate to $16.17 from $15.70
and FY 27 to $18.89 from $18.31. Despite the lower share price post earnings...
/ Angelo Zino, CFA

January 28, 2026
05:04 PM ET... MSFT: Delivers Dec-Q Beat and Massive Bookings Growth; OpenAI
Exposure Rises (MSFT 470.28*****):
...content...
```

구조:
- 날짜 (January 29, 2026)
- 타임스탬프 + 액션 제목 (06:05 AM ET... CFRA Maintains Strong Buy...)
- 종목+가격 (MSFT 449.18*****)
- 본문
- 서명 (/ Angelo Zino, CFA)

---

## 3. Implementation Plan

### 3.1 Task 1: CFRA Balance Sheet 파싱

**범위**: cfra_parser.py에 `_parse_balance_sheet()` 메서드 추가

**접근법**:
1. "Per Share Data (USD)" 줄에서 연도 배열 추출 (예: [2025, 2024, ..., 2016])
2. "Balance Sheet and Other Financial Data (Million USD)" 이후 13개 행 파싱
3. 각 행의 레이블과 값을 DB 컬럼에 매핑
4. 연도별 ZacksFinancial처럼 리스트로 반환

**레이블 → DB 매핑**:
```python
LABEL_MAP = {
    "Cash": "cash",
    "Current Assets": "current_assets",
    "Total Assets": "total_assets",
    "Current Liabilities": "current_liabilities",
    "Long Term Debt": "long_term_debt",
    "Total Capital": "total_capital",
    "Capital Expenditures": "capital_expenditures",
    "Cash from Operations": "cash_from_operations",
    "Current Ratio": "current_ratio",
    "% Long Term Debt of Capitalization": "ltd_to_cap_pct",
    "% Net Income of Revenue": "net_income_to_revenue_pct",
    "% Return on Assets": "return_on_assets_pct",
    "% Return on Equity": "return_on_equity_pct",
}
```

**출력 예상**: 종목당 10개 레코드 (10년치) × 6종목 = 60 레코드

**필요 변경**:
- `cfra_parser.py`: `CFRABalanceSheet` dataclass + `_parse_balance_sheet()` 메서드
- `CFRAParseResult`: `balance_sheets` 필드 추가
- `app/crud/stock.py`: `upsert_balance_sheet()` 함수 추가
- `app/services/parser_service.py`: balance_sheet 저장 로직 추가

### 3.2 Task 2: CFRA Analyst Notes 상세화

**범위**: cfra_parser.py의 `_parse_analyst_notes()` 전면 재작성

**현재 문제**:
- "Analysis prepared by" 패턴만 매칭 → 리포트 메타 1줄만 추출
- 실제 "Analyst Research Notes" 섹션의 4~8개 노트는 미추출

**접근법**:
1. "Analyst Research Notes" 섹션 위치 찾기
2. 날짜 패턴 (`January 29, 2026`) 으로 각 노트 분리
3. 각 노트에서 추출:
   - `published_at`: 날짜 + 시간 (06:05 AM ET)
   - `title`: "CFRA Maintains Strong Buy..." 부분
   - `action`: title에서 추출 (Maintains, Raises, Lowers, Initiates, Reiterates 등)
   - `stock_price_at_note`: `(MSFT 449.18*****)` 에서 가격
   - `target_price`: 본문에서 "target to $550" 패턴
   - `analyst_name`: `/ Angelo Zino, CFA` 서명
   - `content`: 전체 본문 텍스트

**Action 분류**:
```python
ACTION_MAP = {
    "Maintains": "maintain",
    "Raises": "upgrade",
    "Lowers": "downgrade",
    "Initiates": "initiate",
    "Reiterates": "reiterate",
    "Upgrades": "upgrade",
    "Downgrades": "downgrade",
}
```

**출력 예상**: 종목당 4~8개 노트 × 6종목 = 24~48 레코드 (현재 6 → 4~8배 증가)

**필요 변경**:
- `cfra_parser.py`: `CFRAAnalystNote` dataclass 필드 추가 (title, action, target_price, content)
- `_parse_analyst_notes()` 전면 재작성
- `app/crud/stock.py`: `save_analyst_notes()`에 title, action, target_price 매핑 추가

### 3.3 Task 3: CRUD + Service 연동

- `upsert_balance_sheet()` 신규 함수
- `save_analyst_notes()` 기존 함수에 신규 필드 매핑
- `parser_service.py`에 balance_sheet 저장 호출 추가

### 3.4 Task 4: 회귀 테스트

- 기존 11개 PDF 전체 회귀 테스트 (파서 수정 후)
- Balance Sheet: CFRA 6종목 × 10년 = 60 레코드 검증
- Analyst Notes: CFRA 6종목 × 4~8개 = 상세 필드 추출 검증
- DB E2E 재실행: 전체 테이블 카운트 + 샘플 데이터 확인

---

## 4. Scope Boundaries

### In Scope
- CFRA Balance Sheet 파싱 (10년치 × 13개 지표)
- CFRA Analyst Notes 상세화 (title, action, target_price, content)
- CRUD 함수 추가/수정
- 11개 PDF 회귀 테스트

### Out of Scope
- Zacks Balance Sheet (소스 데이터 부재)
- Zacks Analyst Notes (소스 데이터 부재)
- Income Statement 별도 파싱 (현재 Revenue/EPS는 financials 테이블로 충분)
- Per Share Data 파싱 (TBV, FCF 등 — 향후 확장)

---

## 5. Risk Assessment

| 리스크 | 영향 | 완화 방안 |
|--------|------|----------|
| Balance Sheet 연도 헤더와 데이터 행 간 인터리브 | 파싱 실패 | "Per Share Data" 줄에서 연도 배열 추출 후 재사용 |
| Analyst Notes 다중 컬럼 인터리브 (좌우 노트 병합) | 노트 분리 실패 | 날짜 패턴 기반 분리 + 2컬럼 병합 허용 |
| 기존 파서 수정으로 인한 회귀 | Revenue/EPS 추출 깨짐 | 회귀 테스트로 기존 170+ 항목 검증 |

---

## 6. Estimated Effort

| Task | 예상 |
|------|------|
| Balance Sheet 파싱 + CRUD | 중간 |
| Analyst Notes 상세화 | 중간 |
| Service 연동 + 테스트 | 낮음 |
| 회귀 테스트 | 낮음 |
| **합계** | **4개 태스크** |

---

## 7. Success Criteria

- [ ] `stock_balance_sheets` 테이블: CFRA 6종목 × 10년 = 60 레코드
- [ ] Balance Sheet 13개 지표 전부 정상 추출 (NULL 최소화)
- [ ] `stock_analyst_notes` 테이블: CFRA 6종목 × 4~8개 = 24~48 레코드
- [ ] Analyst Notes에 title, action, target_price, content 필드 채워짐
- [ ] 기존 11개 PDF 회귀 테스트 ALL PASS (Revenue, EPS, Highlights 유지)
- [ ] E2E 파이프라인 재실행 후 전체 테이블 정합성 확인
