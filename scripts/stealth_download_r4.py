#!/usr/bin/env python3
"""Stealth PDF downloader Round 4 — alphabetical 5 per letter, excluding 2026-03-07 done."""

import subprocess, random, time, sys
from pathlib import Path
from datetime import datetime

# 알파벳별 5개 (어제 다운로드 제외)
TICKERS = """AVY AXON AON AKAM AFL BXP BX BMY BF.B BRO CMI CINF CVNA CMS CRWD
DUK DVN DTE DOW DXCM EXE EW EXPE EXPD EXR FOX FRT FSLR FTV FTNT
GRMN GPN GOOG GS GWW HSY HUM HWM HOOD HUBB IT ITW IVZ ISRG
LW LYV LYB MRVL MSFT META MTCH MRK NWS NWSA NVDA NXPI NVR
PTC PNC PLTR PLD PPG Q STX SYF SRE STLD SW
TSLA TT TTD TRMB TTWO WY WYNN""".split()

SOURCES = ["CFRA", "ZACKS"]

FETCH_SCRIPT = '''
import asyncio, sys, os
sys.path.insert(0, "{script_dir}")
from app.services.fetcher_service import fetch_pdf
r = asyncio.run(fetch_pdf("{ticker}", "{source}"))
print(r["status"] + "|" + r.get("pdf_path", r.get("error", "")))
'''

def main():
    script_dir = str(Path(__file__).parent)
    venv_python = str(Path(script_dir) / ".venv" / "bin" / "python3")

    # 이미 받은 파일 확인
    done = set()
    for d in Path(f"{script_dir}/storage/pdfs").glob("*"):
        if d.is_dir():
            for f in d.glob("*.pdf"):
                if f.stat().st_size > 1000:
                    done.add(f.stem)

    tasks = [(t, s) for t in TICKERS for s in SOURCES if f"{t}_{s}" not in done]
    random.shuffle(tasks)
    total = len(tasks)
    success = fail = skip_count = 0

    log_path = Path(f"stealth_download_r4_{datetime.now().strftime('%Y%m%d_%H%M')}.log")
    print(f"🎯 Round 4: {total}개 PDF ({len(TICKERS)}티커, 이미 받은 건 제외)", flush=True)
    print(f"📝 로그: {log_path}", flush=True)

    with open(log_path, "w") as log:
        log.write(f"Start: {datetime.now().isoformat()}\nTargets: {total}\n\n")

        for i, (ticker, source) in enumerate(tasks):
            # 랜덤 딜레이 — 인간처럼
            if i > 0:
                r = random.random()
                if r < 0.06:
                    delay = random.uniform(60, 120)
                    print(f"  ☕ 긴 휴식 {delay:.0f}초...", flush=True)
                elif r < 0.15:
                    delay = random.uniform(30, 55)
                    print(f"  ☕ 휴식 {delay:.0f}초...", flush=True)
                elif r < 0.35:
                    delay = random.uniform(15, 30)
                else:
                    delay = random.uniform(8, 18)
                time.sleep(delay)

            print(f"  [{i+1}/{total}] {ticker} {source}...", end=" ", flush=True)
            code = FETCH_SCRIPT.format(ticker=ticker, source=source, script_dir=script_dir)
            try:
                result = subprocess.run(
                    [venv_python, "-c", code], capture_output=True, text=True, timeout=90, cwd=script_dir
                )
                out = result.stdout.strip()
                if out.startswith("success|"):
                    success += 1
                    print(f"✅", flush=True)
                    log.write(f"OK {ticker} {source} {out.split('|',1)[1]}\n")
                else:
                    fail += 1
                    err = out.split("|",1)[-1] if "|" in out else result.stderr[:80]
                    print(f"❌ {err[:60]}", flush=True)
                    log.write(f"FAIL {ticker} {source} {err[:100]}\n")
            except subprocess.TimeoutExpired:
                fail += 1
                print(f"⏱️ timeout", flush=True)
                log.write(f"TIMEOUT {ticker} {source}\n")
            except Exception as e:
                fail += 1
                print(f"💥 {str(e)[:60]}", flush=True)
                log.write(f"ERROR {ticker} {source} {str(e)[:100]}\n")

        summary = f"\n🏁 완료! ✅ {success} / ❌ {fail} (총 {total})"
        print(summary, flush=True)
        log.write(f"\n{summary}\nEnd: {datetime.now().isoformat()}\n")

if __name__ == "__main__":
    main()
