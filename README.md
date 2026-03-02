# Stock Report Automation

Fidelity Research 포털에서 CFRA/Zacks 주식 리서치 리포트를 자동 수집 → PDF 파싱 → DB 저장하는 파이프라인.

## 기술 스택

| 레이어 | 기술 | 용도 |
|--------|------|------|
| PDF 파싱 | Python pdfplumber | 텍스트/테이블 추출 |
| ORM | SQLAlchemy 2.0 + Alembic | 모델, 마이그레이션 |
| DB | PostgreSQL | 정규화 저장 (7 테이블) |
| 설정 | pydantic-settings | .env 기반 설정 |
| 수집 (Phase 1) | Chrome MCP | 포털 브라우저 자동화 |
| 수집 (Phase 3) | Python Playwright (예정) | headless 자동 수집 |

## 파일 구조

```
stock-report-automation/
├── CLAUDE.md                          ← Claude Code 프로젝트 가이드
├── README.md                          ← 이 파일
├── bkit.config.json                   ← bkit PDCA 설정
│
├── app/                               ← Python 애플리케이션
│   ├── config.py                      ← pydantic-settings (DB URL 등)
│   ├── database.py                    ← SQLAlchemy engine, SessionLocal, Base
│   ├── models/                        ← SQLAlchemy ORM 모델 (7 테이블)
│   │   ├── stock_profile.py           ← 종목 기본정보
│   │   ├── stock_report.py            ← 리포트 메타
│   │   ├── stock_financial.py         ← 분기/연간 재무 데이터
│   │   ├── stock_balance_sheet.py     ← 대차대조표
│   │   ├── stock_key_stat.py          ← 핵심 통계 스냅샷
│   │   ├── stock_peer.py              ← 피어 그룹 비교
│   │   └── stock_analyst_note.py      ← 애널리스트 리서치 노트
│   ├── crud/
│   │   └── stock.py                   ← UPSERT 로직 (profile, report, financials, key_stats, peers, notes)
│   ├── parsers/
│   │   └── __init__.py                ← CFRAParser, ZacksParser re-export
│   └── services/
│       └── parser_service.py          ← PDF 파싱 → DB 저장 오케스트레이터
│
├── alembic/                           ← DB 마이그레이션
│   ├── env.py
│   └── versions/
│       ├── b7c84913beb1_initial_7_tables.py
│       └── 75ef54aaed55_add_missing_parser_fields.py
│
├── cfra_parser.py                     ← CFRA 파서 (pdfplumber 기반)
├── zacks_parser.py                    ← Zacks 파서 (pdfplumber 기반)
├── validate_all.py                    ← 9개 PDF × 170항목 검증 스크립트
│
├── priv/python/                       ← CLI 래퍼
│   ├── parse_report.py                ← CLI: python parse_report.py --source cfra --file pltr.pdf
│   └── parsers/                       ← 파서 복사본
│
├── docs/                              ← bkit PDCA 문서
├── stock-report-db-design.md          ← DB 스키마 상세 설계
├── stock-report-automation.md         ← 자동화 아키텍처 설계
├── parser-accuracy-report.md          ← 파서 정확도 최종 리포트 (100%)
├── parsing-validation-report.md       ← 파싱 검증 결과
├── PRD-stock-report-hub.md            ← 제품 요구사항 정의서
├── ROADMAP.md                         ← 로드맵
├── phase-tasks.md                     ← Phase별 작업 목록
│
├── pltr.pdf                           ← CFRA (Palantir, IT/App Software)
├── MSFT-CFRA.pdf                      ← CFRA (Microsoft, IT/Systems Software)
├── JNJ-CFRA.pdf                       ← CFRA (J&J, Healthcare/Pharma)
├── JPM-CFRA.pdf                       ← CFRA (JPMorgan, Financials/Banks)
├── PG-CFRA.pdf                        ← CFRA (P&G, Consumer Staples)
├── DHR.pdf                            ← Zacks (Danaher, Healthcare/Medical)
├── AAPL-Zacks.pdf                     ← Zacks (Apple, IT/Computers)
├── MSFT-Zacks.pdf                     ← Zacks (Microsoft, IT/Software)
└── JPM-Zacks.pdf                      ← Zacks (JPMorgan, Financials/Banks)
```

## 현재 진행 상황

| Phase | 상태 | 설명 |
|-------|------|------|
| 포털 분석 | ✅ 완료 | Fidelity Research 사이트 구조, 검색 플로우, PDF URL 패턴 파악 |
| DB 설계 | ✅ 완료 | 7 테이블 설계, CFRA+Zacks 필드 매핑 |
| 자동화 설계 | ✅ 완료 | 3가지 방안 비교, Phase별 구현 순서 |
| PDF 수집 | ✅ 완료 | 9개 PDF (CFRA 5 + Zacks 4, 4개 섹터) |
| Phase 1 파서 | ✅ 완료 | CFRA/Zacks 파서 개발, 170개 항목 정확도 100% |
| Phase 2 DB 연동 | ✅ 완료 | SQLAlchemy ORM, Alembic 마이그레이션, CRUD UPSERT, Parser Service |
| Phase 2 검증 | ⬜ 진행중 | 파서 → DB 파이프라인 E2E 테스트, 불일치 해소 |

## 데이터 소스

| 소스 | 포털 | 레이팅 체계 | 리포트 형식 |
|------|------|-----------|-----------|
| CFRA | Fidelity Research | STARS 1~5 + Buy/Hold/Sell | 9페이지, 8년 재무제표, 리서치노트 시계열 |
| Zacks | Fidelity Research | Rank 1~5 + Style Scores(VGM) | 8페이지, 산업비교 40개 지표, Buy/Sell 근거 분리 |

## 빠른 시작

```bash
# 의존성 설치
pip install pdfplumber sqlalchemy[asyncio] psycopg alembic pydantic-settings

# DB 설정 (.env)
echo 'DATABASE_URL=postgresql+psycopg://stock_user:stock_pass@localhost:5432/stock_hub' > .env

# 마이그레이션 실행
alembic upgrade head

# PDF 파싱 → DB 저장
python -c "
from app.database import SessionLocal
from app.services.parser_service import parse_and_store

session = SessionLocal()
result = parse_and_store('pltr.pdf', 'CFRA', session)
print(result)
session.close()
"
```

## 연관 프로젝트

- Elixir SaaS MVP — `market/` 모듈 하위에 통합 예정
- 데이터 소스: https://public.fidelityresearch.com/nationalfinancialnet
