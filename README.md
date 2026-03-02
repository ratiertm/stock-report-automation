# Stock Report Hub

Fidelity Research 포털에서 CFRA/Zacks 주식 리서치 리포트를 자동 수집 → PDF 파싱 → DB 저장 → 콘텐츠 생성 + 알림까지 제공하는 파이프라인.

## 기술 스택

| 레이어 | 기술 | 용도 |
|--------|------|------|
| API 서버 | FastAPI + Uvicorn | REST API 19개 엔드포인트 |
| PDF 파싱 | Python pdfplumber | 텍스트/테이블 추출 |
| ORM | SQLAlchemy 2.0 + Alembic | 모델, 마이그레이션 |
| DB | PostgreSQL | 정규화 저장 (10 테이블) |
| 수집 | Python Playwright (headless) | Fidelity 포털 자동 다운로드 |
| 스케줄러 | APScheduler | 매일 자동 수집 |
| 설정 | pydantic-settings | .env 기반 설정 |

## 빠른 시작

```bash
# 1. 의존성 설치
pip install -r requirements.txt
python -m playwright install chromium

# 2. DB 설정 (.env)
cp .env.example .env
# DATABASE_URL 수정

# 3. DB 마이그레이션
python -m alembic upgrade head

# 4. 서버 실행
python -m uvicorn app.main:app --port 8000

# Swagger UI: http://localhost:8000/docs
```

## 사용법

### 특정 종목 리포트 수집

```bash
# PLTR의 CFRA 리포트 다운로드 → 파싱 → DB 저장 (한번에)
curl -X POST "http://localhost:8000/api/fetch/PLTR?source=CFRA"

# Zacks 리포트도
curl -X POST "http://localhost:8000/api/fetch/PLTR?source=ZACKS"
```

### 워치리스트로 일괄 수집

```bash
# 워치리스트에 종목 추가
curl -X POST http://localhost:8000/api/watchlist/add \
  -H "Content-Type: application/json" \
  -d '{"ticker": "NVDA", "sources": "CFRA,ZACKS"}'

# 워치리스트 전체 일괄 다운로드 + 파싱
curl -X POST http://localhost:8000/api/fetch-watchlist

# 워치리스트 확인
curl http://localhost:8000/api/watchlist
```

### 이미 있는 PDF 파싱

```bash
# 로컬 PDF 파싱 (프로젝트 루트에 파일이 있을 때)
curl -X POST "http://localhost:8000/api/parse-local/MSFT?source=CFRA"

# 파일 업로드 방식
curl -X POST http://localhost:8000/api/parse \
  -F "file=@MSFT-CFRA.pdf" -F "source=CFRA"
```

### 데이터 조회

```bash
# 전체 종목 목록
curl http://localhost:8000/api/stocks

# 종목 상세 (프로필 + 최신 리포트)
curl http://localhost:8000/api/stocks/PLTR

# 재무 데이터 (연간/분기)
curl "http://localhost:8000/api/stocks/PLTR/financials?period=annual"

# CFRA vs Zacks 비교
curl http://localhost:8000/api/stocks/PLTR/compare

# 애널리스트 노트
curl http://localhost:8000/api/stocks/PLTR/notes
```

### 콘텐츠 생성 + 알림

```bash
# 블로그/뉴스레터용 콘텐츠 변수 맵 (30+ 필드)
curl http://localhost:8000/api/content/PLTR

# 등급/목표가 변경 감지
curl http://localhost:8000/api/diff/PLTR

# 워치리스트 변경 감지 → 알림 생성
curl -X POST http://localhost:8000/api/alerts/check

# 미발송 알림 확인
curl http://localhost:8000/api/alerts

# 이메일 알림 발송 (.env에 SMTP 설정 필요)
curl -X POST http://localhost:8000/api/alerts/send
```

## API 엔드포인트 (19개)

| Method | Path | 설명 |
|--------|------|------|
| GET | `/api/stocks` | 전체 종목 목록 |
| GET | `/api/stocks/{ticker}` | 프로필 + 최신 리포트 |
| GET | `/api/stocks/{ticker}/financials` | 재무 데이터 (?period=annual\|quarterly\|all) |
| GET | `/api/stocks/{ticker}/compare` | CFRA vs Zacks 비교 |
| GET | `/api/stocks/{ticker}/bundle` | 콘텐츠 변수 맵 |
| GET | `/api/stocks/{ticker}/notes` | 애널리스트 노트 |
| POST | `/api/parse` | PDF 업로드 → 파싱 → DB |
| GET | `/api/watchlist` | 워치리스트 조회 |
| POST | `/api/watchlist/add` | 티커 추가 |
| POST | `/api/watchlist/remove` | 티커 제거 |
| POST | `/api/fetch/{ticker}` | 단일 PDF 다운로드 (Playwright) |
| POST | `/api/fetch-watchlist` | 워치리스트 일괄 다운로드 + 파싱 |
| POST | `/api/parse-local/{ticker}` | 로컬 PDF 파싱 |
| GET | `/api/content/{ticker}` | 블로그용 콘텐츠 변수 (30+ 필드) |
| GET | `/api/diff/{ticker}` | 등급/목표가 변경 감지 |
| POST | `/api/alerts/check` | 워치리스트 변경 감지 → 알림 생성 |
| GET | `/api/alerts` | 미발송 알림 목록 |
| POST | `/api/alerts/send` | 이메일 알림 발송 |
| GET | `/health` | 헬스체크 |

## 데이터 소스

| 소스 | 포털 | 레이팅 체계 | 리포트 형식 |
|------|------|-----------|-----------|
| CFRA | Fidelity Research | STARS 1~5 + Buy/Hold/Sell | 9페이지, 8년 재무제표, 리서치노트 시계열 |
| Zacks | Fidelity Research | Rank 1~5 + Style Scores(VGM) | 8페이지, 산업비교 40개 지표, Buy/Sell 근거 분리 |

## 환경 변수 (.env)

```env
DATABASE_URL=postgresql+psycopg://stock_user:stock_pass@localhost:5432/stock_hub
PDF_STORAGE_PATH=./storage/pdfs
SCHEDULER_ENABLED=false
SCHEDULER_CRON_HOUR=7
ALERT_EMAIL_TO=
ALERT_SMTP_HOST=localhost
ALERT_SMTP_PORT=587
ALERT_SMTP_USER=
ALERT_SMTP_PASS=
```
