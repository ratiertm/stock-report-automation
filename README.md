# Stock Report Automation

Fidelity Research 포털에서 CFRA/Zacks 주식 리서치 리포트를 자동 수집 → PDF 파싱 → DB 저장하는 파이프라인.

## 파일 구조

```
Stock_report_automation/
├── README.md                      ← 이 파일
├── stock-report-db-design.md      ← DB 스키마 설계 (7 테이블)
├── stock-report-automation.md     ← 자동화 아키텍처 설계
├── pltr.pdf                       ← CFRA 샘플 리포트 (Palantir)
└── DHR.pdf                        ← Zacks 샘플 리포트 (Danaher)
```

## 현재 진행 상황

| Phase | 상태 | 설명 |
|-------|------|------|
| 포털 분석 | ✅ 완료 | Fidelity Research 사이트 구조, 검색 플로우, PDF URL 패턴 파악 |
| DB 설계 | ✅ 완료 | 7 테이블 설계, CFRA+Zacks 필드 매핑, Ecto 스키마 |
| 자동화 설계 | ✅ 완료 | 3가지 방안 비교, Phase별 구현 순서 |
| Phase 1 MVP | ⬜ 대기 | Chrome MCP + pdfplumber 파싱 검증 |

## 구현 로드맵 (Phase × 방안 매칭)

| Phase | 방안 | 핵심 작업 | 소요 기간(추정) |
|-------|------|----------|---------------|
| 1 MVP | A (Chrome MCP) | 파서 개발 + 정확도 검증 | 1~2주 |
| 2 반자동 | A + DB 연결 | DB 저장 + 콘텐츠 파이프라인 | 1~2주 |
| 3 완전자동 | C (Playwright) | headless 스크립트 + Oban 스케줄러 | 2~3주 |
| 4 확장 | C → B 검토 | 추가 소스 파서 + UI + HTTP 전환 | 지속적 |

### Phase 1 (MVP) → 방안 A: Claude Desktop + Chrome MCP

지금 당장 사용 가능. Chrome MCP로 포털 조작 → PDF 다운로드 → pdfplumber로 파싱. 별도 인프라 불필요. 파서 정확도를 튜닝하면서 CFRA/Zacks 각 필드 매핑을 검증하는 데 적합.

### Phase 2 (반자동) → 방안 A 유지 + DB 저장 연결

여전히 Claude Desktop에서 트리거하지만, 파싱 결과를 Elixir 앱의 PostgreSQL에 직접 저장하는 연결고리를 구축. 티커 목록 일괄 처리 + `to_content_vars` 파이프라인 연결.

### Phase 3 (완전 자동) → 방안 C: Python Playwright + Elixir Port

핵심 전환 포인트. PDF 파싱에 이미 Python(pdfplumber)을 쓰므로 다운로드도 Python Playwright로 통일하면 의존성 관리가 깔끔. Oban 스케줄러가 `System.cmd("python3", ...)` 로 호출, headless로 서버에서 자동 실행.

### Phase 4 (확장) → 방안 C 유지 + 방안 B 부분 전환 검토

트래픽 증가 시 Wallaby나 Elixir 네이티브 HTTP 방식 전환 검토. feedID/doctag 패턴이 충분히 파악되면 HTTP 직접 요청으로 브라우저 자동화 자체를 생략 가능.

### 3가지 방안 요약

| 방안 | 설명 | 장점 | 단점 |
|------|------|------|------|
| A. Chrome MCP | Chrome 브라우저 자동 조작 | 즉시 사용, JS 렌더링 완벽 | 수동 트리거, 브라우저 의존 |
| B. Headless Chrome (Wallaby) | Elixir에서 직접 Chrome 제어 | 완전 자동, 네이티브 | chromedriver 설치 필요 |
| C. Python Playwright + Elixir Port | Python으로 다운로드+파싱 통합 | Playwright 생태계, 안정적 | Python 의존성 |

## 연관 프로젝트

- Elixir SaaS MVP (`CLAUDE.md` 참조) — `market/` 모듈 하위에 통합 예정
- 데이터 소스: https://public.fidelityresearch.com/nationalfinancialnet
