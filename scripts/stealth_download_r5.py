#!/usr/bin/env python3
"""Stealth PDF downloader Round 5 — remaining 139 tickers."""

import subprocess, random, time, sys
from pathlib import Path
from datetime import datetime

TICKERS = """AIG AIZ AJG ALB ALGN ALL ALLE ALNY AMAT AMCR AMD AME AMGN AMP AMT
AMZN ANET AOS APA APD APH APO APP APTV ARE ARES ARM ASML ATO AVB AVGO AWK AXP AZO
BF.B BR BRK.B BSX CFG CHD CHRW CHTR CI CIEN CL CLX CMCSA CME CMG CNC CNP COF COIN
COO COP COR COST CPAY CPB CPRT CPT CRH CRL CRM CSCO CSGP CSX CTAS CTRA CTSH CTVA CVS CVX
DOC DOV DPZ DRI DVA EQT ERIE ES ESS ETN ETR EVRG EXC FOX FOXA HOOD HST
META MLM MMM MNST MO MOH MOS MPC MPWR MRNA MRSH MS MSCI MSI MSTR MTB MTD MU
PLTR PM PNR PNW PODD POOL PPL PRU PSA PSKY PSX PWR PYPL
SHOP STE STT STZ SWK SWKS SYK SYY TPR TRGP TRI TROW TRV TSCO TSN TXN TXT TYL""".split()

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
    success = fail = 0

    log_path = Path(f"stealth_download_r5_{datetime.now().strftime('%Y%m%d_%H%M')}.log")
    print(f"🎯 Round 5: {total}개 PDF ({len(TICKERS)}티커, 이미 받은 건 제외)", flush=True)
    print(f"📝 로그: {log_path}", flush=True)

    with open(log_path, "w") as log:
        log.write(f"Start: {datetime.now().isoformat()}\nTargets: {total}\n\n")

        for i, (ticker, source) in enumerate(tasks):
            if i > 0:
                r = random.random()
                if r < 0.06:
                    delay = random.uniform(65, 130)
                    print(f"  ☕ 긴 휴식 {delay:.0f}초...", flush=True)
                elif r < 0.15:
                    delay = random.uniform(30, 60)
                    print(f"  ☕ 휴식 {delay:.0f}초...", flush=True)
                elif r < 0.35:
                    delay = random.uniform(15, 30)
                else:
                    delay = random.uniform(8, 20)
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
