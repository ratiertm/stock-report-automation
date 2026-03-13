#!/usr/bin/env python3
"""Stealth PDF downloader Round 3"""

import subprocess, random, time, sys
from pathlib import Path
from datetime import datetime

TICKERS = """ADP ADSK AEE AEP AES BK BKNG BKR BLDR BLK CCL CDNS CDW CEG CF
DHI DHR DIS DLR DLTR EMR EOG EPAM EQIX EQR FIS FISV FITB FIX FOX
GM GNRC GOOGL GPC HPE HPQ HRL HSIC INVH IP IQV IR IRM
KR KVUE LOW LRCX LULU LUV LVS MELI MET MGM MKC
NRG NSC NTAP NTRS NUE PG PGR PH PHM PKG
ROST RSG RTX RVTY SNPS SO SOLV SPG SPGI
TJX TKO TMO TMUS TPL VTRS VZ WMT WRB WSM WST WTW""".split()

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

    # 이미 받은 파일 확인 (모든 날짜)
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

    print(f"🎯 Round 3: {total}개 PDF (85티커, 이미 받은 건 제외)", flush=True)

    for i, (ticker, source) in enumerate(tasks):
        if i > 0:
            if random.random() < 0.08:
                delay = random.uniform(50, 95)
                print(f"  ☕ 휴식 {delay:.0f}초...", flush=True)
            elif random.random() < 0.15:
                delay = random.uniform(25, 45)
            else:
                delay = random.uniform(8, 20)
            time.sleep(delay)

        print(f"  [{i+1}/{total}] {ticker} {source}...", end=" ", flush=True)
        code = FETCH_SCRIPT.format(ticker=ticker, source=source, script_dir=script_dir)
        try:
            result = subprocess.run(
                [venv_python, "-c", code], capture_output=True, text=True, timeout=60, cwd=script_dir
            )
            out = result.stdout.strip()
            if out.startswith("success|"):
                success += 1
                print(f"✅", flush=True)
            else:
                fail += 1
                err = out.split("|",1)[-1] if "|" in out else result.stderr[:80]
                print(f"❌ {err[:60]}", flush=True)
        except subprocess.TimeoutExpired:
            fail += 1
            print(f"⏱️ timeout", flush=True)
        except Exception as e:
            fail += 1
            print(f"💥 {str(e)[:60]}", flush=True)

    print(f"\n🏁 완료! ✅ {success} / ❌ {fail} (총 {total})", flush=True)

if __name__ == "__main__":
    main()
