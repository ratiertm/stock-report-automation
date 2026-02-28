# Stock Report 자동화 아키텍처

## 개요

Fidelity Research 포털(`public.fidelityresearch.com`)에서 CFRA/Zacks 주식 리서치 리포트 PDF를 자동 수집하고, 파싱하여 PostgreSQL DB에 저장하는 파이프라인.

**목표**: 티커 목록 입력 → PDF 자동 다운로드 → 구조화 파싱 → DB 저장 → 콘텐츠 생성 참조

---

## 1. Fidelity Research 포털 분석 결과

### 1-1. 사이트 구조

```
public.fidelityresearch.com/nationalfinancialnet
├── 메인 페이지 (부모)
│   └── iframe (name="iframeContainer")
│       └── /NationalFinancialNet/MurielSiebert/PageContent (실제 콘텐츠)
│           ├── Search For Reports (검색 폼)
│           ├── My Recently Viewed Reports
│           ├── Stock & Industry Reports
│           ├── News, Market & Investing Reports
│           └── Economic Outlook Reports
```

- **로그인**: 불필요 (Public 접근)
- **iframe 기반**: 검색 폼과 결과가 모두 iframe 내부에 위치
- **직접 접근 가능**: iframe URL로 직접 네비게이션 가능

### 1-2. 검색 흐름 (테스트 검증 완료)

```
Step 1: Firm 드롭다운 선택 (CFRA / Zacks / Argus / S&P Capital IQ / ISS-EVA)
Step 2: Report Type 선택 (Company Reports)
Step 3: 티커/회사명 입력 (예: "AAPL")
Step 4: Autocomplete 드롭다운에서 회사 클릭 (예: "Apple Inc  AAPL; NA...")
Step 5: Search 버튼 클릭
Step 6: Search Results에 결과 표시 (예: "Apple Inc  21-FEB-2026  CFRA")
Step 7: 결과 링크 클릭 → 새 탭에서 PDF 열림
```

### 1-3. PDF URL 패턴

```
https://public.fidelityresearch.com/NationalFinancialNet/Api/PDF
  ?doctag={DOCUMENT_TAG}
  &feedID={FEED_ID}
  &versionTag={VERSION_TAG}
```

| 파라미터 | 예시 | 설명 |
|---------|------|------|
| doctag | `69608A10` | 문서 고유 태그 |
| feedID | `72` | 피드 ID (소스별 고정값 가능성) |
| versionTag | `6I6NRPBT2EC3CN0H7N7S54TPNU` | 버전 해시 |

- 링크의 `href`는 세션/쿠키 데이터를 포함하여 JavaScript로 직접 추출 시 차단됨
- `target="_blank"` → 새 탭에서 PDF 열림
- 클래스: `a.itemReport`

### 1-4. 사용 가능 소스 (Firm)

| Firm | feedID (추정) | 리포트 형식 |
|------|-------------|-----------|
| CFRA | 72 | STARS Rating, 9페이지 PDF |
| Zacks | ? | Zacks Rank, 8페이지 PDF |
| Argus | ? | Company Report |
| S&P Capital IQ | ? | Company Report |
| ISS-EVA | ? | EVA Analysis |

---

## 2. 자동화 아키텍처

### 2-1. 전체 파이프라인

```
┌─────────────────────────────────────────────────────────────────┐
│                    Elixir/Phoenix Application                    │
│                                                                  │
│  ┌──────────┐    ┌──────────────┐    ┌────────────────────┐     │
│  │ Oban     │    │ Chrome MCP   │    │ PDF Parser         │     │
│  │ Scheduler│───▶│ Automation   │───▶│ (Tabula/pdfplumber)│     │
│  │          │    │              │    │                    │     │
│  │ Cron:    │    │ 1. Navigate  │    │ 1. Text extraction │     │
│  │ 매일 7AM │    │ 2. Search    │    │ 2. Table parsing   │     │
│  │          │    │ 3. Download  │    │ 3. Structure map   │     │
│  └──────────┘    └──────────────┘    └────────┬───────────┘     │
│                                                │                 │
│                                      ┌─────────▼─────────┐     │
│                                      │ DB Writer          │     │
│                                      │                    │     │
│                                      │ stock_profiles     │     │
│                                      │ stock_reports      │     │
│                                      │ stock_financials   │     │
│                                      │ stock_key_stats    │     │
│                                      │ stock_peers        │     │
│                                      │ stock_analyst_notes│     │
│                                      └────────────────────┘     │
└─────────────────────────────────────────────────────────────────┘
```

### 2-2. 방안 비교

| 방안 | 설명 | 장점 | 단점 |
|------|------|------|------|
| **A. Chrome MCP** | Chrome 브라우저 자동 조작 | 실제 사용자 흐름, JS 렌더링 완벽 지원 | 속도 느림, 브라우저 의존성 |
| **B. HTTP 직접 요청** | PDF URL 패턴으로 직접 다운로드 | 빠름, 경량 | doctag/versionTag를 미리 알아야 함 |
| **C. 하이브리드** | 검색은 Chrome MCP, 다운로드는 HTTP | 균형잡힌 접근 | 복잡도 중간 |

**권장: 방안 A (Chrome MCP) + 방안 C 점진 전환**

- 초기: Chrome MCP로 전체 플로우 자동화 (검증된 방식)
- 향후: feedID/doctag 패턴 분석 후 HTTP 직접 다운로드로 전환

---

## 3. 구현 설계

### 3-1. 모듈 구조

```
lib/app_name/
├── market/
│   ├── stock_reports.ex              # 컨텍스트 (기존 DB 설계 문서 참조)
│   ├── stock_report_fetcher.ex       # Chrome MCP 자동화 오케스트레이터
│   ├── stock_report_parser.ex        # PDF → 구조화 데이터
│   ├── parsers/
│   │   ├── cfra_parser.ex            # CFRA 포맷 전용 파서
│   │   └── zacks_parser.ex           # Zacks 포맷 전용 파서
│   └── workers/
│       ├── report_fetch_worker.ex    # Oban: PDF 다운로드 워커
│       ├── report_parse_worker.ex    # Oban: PDF 파싱 워커
│       └── report_schedule_worker.ex # Oban: 정기 수집 스케줄러
```

### 3-2. Chrome MCP 자동화 모듈

```elixir
defmodule AppName.Market.StockReportFetcher do
  @moduledoc """
  Chrome MCP를 통해 Fidelity Research 포털에서 PDF를 자동 다운로드.

  플로우:
  1. iframe 콘텐츠 페이지로 직접 이동
  2. Firm 드롭다운에서 소스 선택 (CFRA/Zacks)
  3. 티커 입력 → autocomplete 선택
  4. Search 클릭
  5. 검색 결과에서 리포트 링크 클릭
  6. 새 탭에서 열린 PDF 다운로드
  """

  @base_url "https://public.fidelityresearch.com/NationalFinancialNet/MurielSiebert/PageContent"

  @firm_options %{
    "CFRA" => "CFRA",
    "Zacks" => "Zacks",
    "Argus" => "Argus",
    "S&P" => "S&P Capital IQ",
    "ISS-EVA" => "ISS-EVA"
  }

  @doc """
  주어진 티커와 소스로 PDF를 다운로드한다.

  ## 파라미터
  - ticker: 주식 티커 (예: "AAPL")
  - source: 리포트 소스 (예: "CFRA", "Zacks")
  - opts: 추가 옵션

  ## 반환
  {:ok, pdf_path} | {:error, reason}
  """
  def fetch_report(ticker, source, opts \\ []) do
    download_dir = Keyword.get(opts, :download_dir, report_download_dir())

    with :ok <- navigate_to_portal(),
         :ok <- select_firm(source),
         :ok <- enter_ticker(ticker),
         :ok <- select_autocomplete_match(ticker),
         :ok <- click_search(),
         {:ok, _result_text} <- find_search_result(ticker, source),
         :ok <- click_search_result(),
         {:ok, pdf_path} <- wait_and_save_pdf(ticker, source, download_dir) do
      {:ok, pdf_path}
    end
  end

  @doc """
  여러 티커를 순차적으로 다운로드한다.
  Rate limiting을 위해 각 다운로드 사이에 딜레이를 둔다.
  """
  def fetch_reports(tickers, source, opts \\ []) do
    delay_ms = Keyword.get(opts, :delay_ms, 5_000)

    tickers
    |> Enum.reduce([], fn ticker, acc ->
      result = fetch_report(ticker, source, opts)
      Process.sleep(delay_ms)
      [{ticker, result} | acc]
    end)
    |> Enum.reverse()
  end

  # --- Private ---

  defp navigate_to_portal do
    # Chrome MCP: navigate to @base_url
    # 직접 iframe URL로 이동하여 iframe 격리 문제 우회
    :ok
  end

  defp select_firm(source) do
    # Chrome MCP: find firm dropdown → form_input with source value
    :ok
  end

  defp enter_ticker(ticker) do
    # Chrome MCP: find input → click → type ticker
    :ok
  end

  defp select_autocomplete_match(_ticker) do
    # Chrome MCP: wait for autocomplete dropdown → click first match
    # 중요: autocomplete 클릭 후 드롭다운이 닫히는 것을 확인
    :ok
  end

  defp click_search do
    # Chrome MCP: find Search button → click
    :ok
  end

  defp find_search_result(_ticker, _source) do
    # Chrome MCP: wait for Search Results → find result matching ticker + source
    {:ok, "found"}
  end

  defp click_search_result do
    # Chrome MCP: click result link (a.itemReport) → new tab opens with PDF
    :ok
  end

  defp wait_and_save_pdf(ticker, source, download_dir) do
    # Chrome MCP: switch to new tab → save PDF
    # 파일명: {ticker}_{source}_{date}.pdf (예: AAPL_CFRA_2026-02-21.pdf)
    date_str = Date.utc_today() |> Date.to_iso8601()
    filename = "#{ticker}_#{source}_#{date_str}.pdf"
    path = Path.join(download_dir, filename)
    {:ok, path}
  end

  defp report_download_dir do
    Application.get_env(:app_name, :report_download_dir, "/tmp/stock_reports")
  end
end
```

### 3-3. PDF 파서 (소스별 분리)

```elixir
defmodule AppName.Market.StockReportParser do
  @moduledoc """
  PDF 파일을 읽어 구조화된 데이터로 변환.
  소스(CFRA/Zacks)에 따라 적절한 파서로 위임.
  """

  alias AppName.Market.Parsers.{CfraParser, ZacksParser}

  @doc """
  PDF 파일을 파싱하여 구조화된 맵을 반환.

  ## 반환 형태
  %{
    profile: %{ticker, company_name, exchange, ...},
    report: %{source, report_date, recommendation, ...},
    financials: [%{fiscal_year, revenue, ...}, ...],
    key_stats: %{market_cap, pe_ratio, ...},
    peers: [%{ticker, company_name, ...}, ...],
    analyst_notes: [%{date, note_type, text}, ...]
  }
  """
  def parse(pdf_path, source) do
    with {:ok, raw_text} <- extract_text(pdf_path),
         {:ok, tables} <- extract_tables(pdf_path) do
      case source do
        "CFRA" -> CfraParser.parse(raw_text, tables)
        "Zacks" -> ZacksParser.parse(raw_text, tables)
        _ -> {:error, :unsupported_source}
      end
    end
  end

  # Python pdfplumber 호출 (Elixir Port 또는 System.cmd)
  defp extract_text(pdf_path) do
    case System.cmd("python3", [
      "-c",
      """
      import pdfplumber, json, sys
      pdf = pdfplumber.open(sys.argv[1])
      pages = [{"page": i+1, "text": p.extract_text() or ""} for i, p in enumerate(pdf.pages)]
      print(json.dumps(pages))
      """,
      pdf_path
    ]) do
      {output, 0} -> {:ok, Jason.decode!(output)}
      {error, _} -> {:error, error}
    end
  end

  defp extract_tables(pdf_path) do
    case System.cmd("python3", [
      "-c",
      """
      import pdfplumber, json, sys
      pdf = pdfplumber.open(sys.argv[1])
      all_tables = []
      for i, page in enumerate(pdf.pages):
          tables = page.extract_tables()
          for j, table in enumerate(tables):
              all_tables.append({"page": i+1, "table_idx": j, "data": table})
      print(json.dumps(all_tables))
      """,
      pdf_path
    ]) do
      {output, 0} -> {:ok, Jason.decode!(output)}
      {error, _} -> {:error, error}
    end
  end
end
```

### 3-4. CFRA 파서 예시

```elixir
defmodule AppName.Market.Parsers.CfraParser do
  @moduledoc """
  CFRA Stock Report PDF를 구조화 데이터로 파싱.

  CFRA 리포트 구조 (9페이지):
  - P1: 헤더(티커, 회사명, 가격, STARS), Highlights, Analyst Research Notes
  - P2: Key Stats 테이블, Revenue/Earnings 차트
  - P3: Investment Rationale/Risk, Company Profile
  - P4-6: 8년 재무제표(P&L, Balance Sheet)
  - P7-9: 법적고지, 용어설명
  """

  def parse(pages_text, tables) do
    with {:ok, profile} <- parse_profile(pages_text),
         {:ok, report} <- parse_report_meta(pages_text),
         {:ok, financials} <- parse_financials(tables),
         {:ok, key_stats} <- parse_key_stats(tables),
         {:ok, peers} <- parse_peers(tables),
         {:ok, notes} <- parse_analyst_notes(pages_text) do
      {:ok, %{
        profile: profile,
        report: Map.put(report, :source, "CFRA"),
        financials: financials,
        key_stats: key_stats,
        peers: peers,
        analyst_notes: notes
      }}
    end
  end

  defp parse_profile(pages) do
    page1 = get_page_text(pages, 1)
    page3 = get_page_text(pages, 3)

    profile = %{
      ticker: extract_regex(page1, ~r/\b([A-Z]{1,5})\s+on\s+(NYSE|NASDAQ|NasdaqGS)/),
      company_name: extract_regex(page1, ~r/^(.+?)(?:\s+\d)/m),
      exchange: extract_regex(page1, ~r/on\s+(NYSE|NASDAQ|NasdaqGS)/),
      gics_sector: extract_regex(page3, ~r/GICS Sector:\s*(.+)/),
      gics_sub_industry: extract_regex(page3, ~r/Sub-Industry:\s*(.+)/),
      employees: extract_integer(page3, ~r/Employees:\s*([\d,]+)/),
      description: extract_section(page3, "Company Profile")
    }

    {:ok, profile}
  end

  defp parse_report_meta(pages) do
    page1 = get_page_text(pages, 1)

    report = %{
      report_date: extract_date(page1),
      analyst_name: extract_regex(page1, ~r/Analyst:\s*(.+)/),
      stars_rating: extract_integer(page1, ~r/(\d)\s*STARS?/),
      recommendation: stars_to_recommendation(extract_integer(page1, ~r/(\d)\s*STARS?/)),
      target_price: extract_decimal(page1, ~r/12-Mo\.\s*Target\s*\$?([\d.]+)/),
      current_price: extract_decimal(page1, ~r/Price\s*as\s*of.*\$?([\d.]+)/),
      risk_assessment: extract_regex(page1, ~r/Risk Assessment:\s*(\w+)/),
      fair_value: extract_decimal(page1, ~r/Fair Value.*\$?([\d.]+)/),
      highlights: extract_section(page1, "Highlights"),
      investment_rationale: extract_section(get_page_text(pages, 3), "Investment Rationale/Risk")
    }

    {:ok, report}
  end

  defp parse_financials(tables) do
    # P4~P6의 테이블에서 8년치 재무데이터 추출
    # Revenue, Operating Income, Net Income, EPS 등
    financial_tables = Enum.filter(tables, fn t -> t["page"] in [4, 5, 6] end)
    rows = Enum.flat_map(financial_tables, &parse_financial_table/1)
    {:ok, rows}
  end

  defp parse_key_stats(tables) do
    # P2의 Key Statistics 테이블
    stats_table = Enum.find(tables, fn t -> t["page"] == 2 end)
    {:ok, parse_stats_table(stats_table)}
  end

  defp parse_peers(_tables) do
    # CFRA는 명시적 peer 비교 테이블이 제한적
    {:ok, []}
  end

  defp parse_analyst_notes(pages) do
    page1 = get_page_text(pages, 1)
    # "Analyst Research Notes" 섹션에서 날짜별 노트 추출
    notes = extract_dated_notes(page1)
    {:ok, notes}
  end

  # --- Helper functions ---

  defp get_page_text(pages, num) do
    case Enum.find(pages, fn p -> p["page"] == num end) do
      nil -> ""
      page -> page["text"]
    end
  end

  defp extract_regex(text, regex) do
    case Regex.run(regex, text) do
      [_, match | _] -> String.trim(match)
      _ -> nil
    end
  end

  defp extract_integer(text, regex) do
    case extract_regex(text, regex) do
      nil -> nil
      str -> str |> String.replace(",", "") |> String.to_integer()
    end
  end

  defp extract_decimal(text, regex) do
    case extract_regex(text, regex) do
      nil -> nil
      str -> Decimal.new(str)
    end
  end

  defp extract_date(_text), do: nil  # 구현 필요
  defp extract_section(_text, _name), do: nil  # 구현 필요
  defp extract_dated_notes(_text), do: []  # 구현 필요
  defp parse_financial_table(_table), do: []  # 구현 필요
  defp parse_stats_table(_table), do: %{}  # 구현 필요

  defp stars_to_recommendation(5), do: "Strong Buy"
  defp stars_to_recommendation(4), do: "Buy"
  defp stars_to_recommendation(3), do: "Hold"
  defp stars_to_recommendation(2), do: "Sell"
  defp stars_to_recommendation(1), do: "Strong Sell"
  defp stars_to_recommendation(_), do: nil
end
```

### 3-5. Oban 워커

```elixir
# --- 1) 개별 리포트 다운로드 워커 ---
defmodule AppName.Market.Workers.ReportFetchWorker do
  use Oban.Worker,
    queue: :report_fetch,
    max_attempts: 3,
    priority: 2

  alias AppName.Market.{StockReportFetcher, StockReportParser, StockReports}

  @impl Oban.Worker
  def perform(%Oban.Job{args: %{"ticker" => ticker, "source" => source} = args}) do
    org_id = args["organization_id"]

    with {:ok, pdf_path} <- StockReportFetcher.fetch_report(ticker, source),
         {:ok, parsed} <- StockReportParser.parse(pdf_path, source),
         {:ok, _records} <- StockReports.upsert_from_parsed(parsed, org_id) do
      # 성공 시 PDF 보관 (선택)
      maybe_archive_pdf(pdf_path, args["archive"])
      :ok
    else
      {:error, reason} ->
        # 실패 시 Oban이 자동 재시도
        {:error, reason}
    end
  end

  defp maybe_archive_pdf(pdf_path, true) do
    archive_dir = Application.get_env(:app_name, :report_archive_dir, "/data/reports")
    File.cp!(pdf_path, Path.join(archive_dir, Path.basename(pdf_path)))
  end
  defp maybe_archive_pdf(_, _), do: :ok
end

# --- 2) 정기 수집 스케줄러 워커 ---
defmodule AppName.Market.Workers.ReportScheduleWorker do
  use Oban.Worker,
    queue: :report_schedule,
    max_attempts: 1

  alias AppName.Market.Workers.ReportFetchWorker

  @doc """
  매일 아침 7시에 실행.
  워치리스트의 모든 티커에 대해 FetchWorker 잡을 생성.
  """
  @impl Oban.Worker
  def perform(%Oban.Job{args: args}) do
    org_id = args["organization_id"]
    sources = args["sources"] || ["CFRA", "Zacks"]

    # 워치리스트에서 티커 목록 가져오기
    tickers = AppName.Market.StockReports.get_watchlist_tickers(org_id)

    # 각 티커 × 소스 조합으로 FetchWorker 잡 삽입
    jobs =
      for ticker <- tickers, source <- sources do
        %{
          "ticker" => ticker,
          "source" => source,
          "organization_id" => org_id,
          "archive" => true
        }
        |> ReportFetchWorker.new(schedule_in: :rand.uniform(300))
      end

    Oban.insert_all(jobs)
    :ok
  end
end
```

### 3-6. Oban Cron 설정

```elixir
# config/config.exs
config :app_name, Oban,
  queues: [
    default: 10,
    mailers: 5,
    report_fetch: 2,      # 동시 다운로드 2개 제한 (사이트 부하 방지)
    report_schedule: 1
  ],
  plugins: [
    {Oban.Plugins.Cron, crontab: [
      # 기존
      {"0 0 * * *", AppName.Workers.ExpirationWorker},
      {"0 9 * * *", AppName.Workers.TrialExpiringWorker},
      # 리포트 수집 (매일 오전 7시)
      {"0 7 * * 1-5", AppName.Market.Workers.ReportScheduleWorker,
        args: %{"sources" => ["CFRA", "Zacks"]}},
    ]}
  ]
```

---

## 4. Chrome MCP 연동 방식

### 4-1. 방안 A: Claude Desktop에서 수동 트리거

사용자가 Claude Desktop(Cowork)에서 직접 명령:

```
"AAPL, MSFT, GOOGL 리포트 수집해줘"
→ Chrome MCP로 Fidelity 포털 자동 조작
→ PDF 다운로드 → 파싱 → DB 저장
```

**장점**: 즉시 사용 가능, 별도 인프라 불필요
**단점**: 수동 트리거 필요, Claude 세션 유지 필요

### 4-2. 방안 B: Elixir에서 Headless Chrome 연동

```elixir
# mix.exs
defp deps do
  [
    {:wallaby, "~> 0.30"},  # Headless Chrome 드라이버
    # 또는
    {:playwright, "~> 1.0"} # Playwright Elixir 바인딩
  ]
end
```

Wallaby/Playwright로 Chrome을 프로그래밍 방식으로 제어:

```elixir
defmodule AppName.Market.Browser do
  use Wallaby.DSL

  @portal_url "https://public.fidelityresearch.com/NationalFinancialNet/MurielSiebert/PageContent"

  def fetch_pdf(session, ticker, source) do
    session
    |> visit(@portal_url)
    |> find(Query.css("select#firmSelect"), fn select ->
      click(select, Query.option(source))
    end)
    |> fill_in(Query.css("input[placeholder*='symbol']"), with: ticker)
    |> find(Query.css(".autocomplete-item"), fn item ->
      click(item)
    end)
    |> click(Query.button("Search"))
    |> find(Query.css("a.itemReport"), fn link ->
      click(link)
    end)
    # ... PDF 다운로드 처리
  end
end
```

**장점**: 완전 자동, Oban 스케줄러와 연동
**단점**: chromedriver/playwright 설치 필요, 서버 리소스

### 4-3. 방안 C: Python Selenium/Playwright + Elixir Port

```python
# scripts/fetch_report.py
import sys
from playwright.sync_api import sync_playwright

def fetch_report(ticker, source, download_dir):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        # Navigate to portal
        page.goto("https://public.fidelityresearch.com/NationalFinancialNet/MurielSiebert/PageContent")

        # Select firm
        page.select_option("select", label=source)

        # Enter ticker and select autocomplete
        page.fill("input[placeholder*='symbol']", ticker)
        page.wait_for_selector(".autocomplete-item")
        page.click(".autocomplete-item >> text=" + ticker)

        # Search
        page.click("text=Search")
        page.wait_for_selector("a.itemReport")

        # Click result → new tab with PDF
        with page.expect_popup() as popup_info:
            page.click("a.itemReport")
        pdf_page = popup_info.value

        # Download PDF
        pdf_url = pdf_page.url
        response = pdf_page.request.get(pdf_url)
        filename = f"{ticker}_{source}_{date.today()}.pdf"
        filepath = os.path.join(download_dir, filename)
        with open(filepath, "wb") as f:
            f.write(response.body())

        browser.close()
        return filepath

if __name__ == "__main__":
    ticker, source, download_dir = sys.argv[1], sys.argv[2], sys.argv[3]
    path = fetch_report(ticker, source, download_dir)
    print(path)
```

Elixir에서 호출:
```elixir
{pdf_path, 0} = System.cmd("python3", [
  "scripts/fetch_report.py", ticker, source, download_dir
])
```

**장점**: Playwright 생태계 활용, 안정적
**단점**: Python 의존성

---

## 5. 권장 구현 순서

### Phase 1: MVP (수동 트리거)
1. Claude Desktop(Cowork) + Chrome MCP로 수동 PDF 다운로드
2. Python pdfplumber로 PDF 텍스트/테이블 추출
3. CFRA 파서 구현 → DB 저장
4. 단일 티커 End-to-End 검증

### Phase 2: 반자동화
1. Zacks 파서 추가
2. 티커 목록 일괄 처리 (Claude에게 목록 전달)
3. DB → 콘텐츠 변환 파이프라인 (`to_content_vars`)
4. 파싱 정확도 검증 및 튜닝

### Phase 3: 완전 자동화
1. Python Playwright 스크립트 (headless)
2. Oban 스케줄러 연동 (매일 7AM)
3. 에러 알림 (Oban 실패 → 이메일 알림)
4. PDF 아카이브 저장소

### Phase 4: 확장
1. Argus, S&P Capital IQ 파서 추가
2. 워치리스트 관리 UI (LiveView)
3. 리포트 비교/변경 감지 (이전 리포트 대비 변화)
4. 콘텐츠 자동 생성 트리거 (새 리포트 → 자동 블로그/뉴스레터)

---

## 6. 기술적 고려사항

### 6-1. Rate Limiting
- Fidelity 포털 부하 방지: 요청 간 5초 딜레이
- Oban `report_fetch` 큐: 동시 2개 제한
- 일일 총 요청: 100건 이하 권장

### 6-2. 에러 처리
| 에러 유형 | 대응 |
|----------|------|
| 검색 결과 없음 | 티커/소스 조합 로깅, 스킵 |
| PDF 로딩 타임아웃 | Oban 재시도 (max 3회) |
| 파싱 실패 | raw PDF 보관 + 수동 검토 플래그 |
| 사이트 구조 변경 | 파서 셀렉터 업데이트 필요 |

### 6-3. PDF 파싱 도구 비교
| 도구 | 언어 | 텍스트 | 테이블 | 추천도 |
|------|------|--------|--------|--------|
| pdfplumber | Python | ★★★★★ | ★★★★☆ | **최우선** |
| tabula-py | Python | ★★★☆☆ | ★★★★★ | 테이블 특화 |
| PyMuPDF (fitz) | Python | ★★★★☆ | ★★★☆☆ | 속도 우선 |
| pdf-extract (Elixir) | Elixir | ★★★☆☆ | ★★☆☆☆ | 네이티브 |

**권장**: `pdfplumber` (텍스트+테이블 균형) + `tabula-py` (복잡한 테이블 보조)

### 6-4. 데이터 정합성
- `stock_reports` 유니크: `(stock_profile_id, source, report_date)`
- 같은 날 같은 소스 리포트 → UPSERT (새 데이터로 덮어쓰기)
- 파싱 결과 checksum 저장 → 변경 감지

---

## 7. 기존 DB 설계와 연결

이 자동화 파이프라인은 `stock-report-db-design.md`의 7개 테이블로 데이터를 저장합니다:

```
PDF 파싱 결과        →  DB 테이블
─────────────────────────────────────
parsed.profile       →  stock_profiles (UPSERT by ticker+exchange)
parsed.report        →  stock_reports (INSERT)
parsed.financials    →  stock_financials (UPSERT by profile+year+period)
parsed.key_stats     →  stock_key_stats (INSERT, report 연결)
parsed.peers         →  stock_peers (INSERT, report 연결)
parsed.analyst_notes →  stock_analyst_notes (UPSERT by profile+date)
```

DB 저장 후 콘텐츠 생성 파이프라인으로 연결:
```
DB → StockReports.get_report_bundle(ticker)
   → StockReports.to_content_vars(ticker)
   → ContentTemplate 렌더링
   → ContentPost 생성
   → Distribution (멀티플랫폼 배포)
```

---

## 참조

- DB 설계: `stock-report-db-design.md`
- 프로젝트 가이드: `CLAUDE.md`
- CFRA 리포트 샘플: `pltr.pdf`
- Zacks 리포트 샘플: `DHR.pdf`
