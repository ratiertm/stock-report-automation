#!/usr/bin/env python3
"""Lightweight remaining downloader — subprocess per PDF to avoid memory leak."""

import subprocess
import random
import time
import sys
from pathlib import Path
from datetime import datetime

TICKERS = """ACGL ACN ADBE ADI ADM BDX BEN BF.B BG BIIB CB CBOE CBRE CCEP CCI
DE DECK DELL DG DGX EG EIX EL ELV EME FDX FE FER FFIV FICO
GEV GILD GIS GL GLW HIG HII HLT HOLX HON IFF INCY INSM INTC INTU
JNJ JPM KKR KLAC KMB KMI KO LII LIN LLY LMT LNT
MCHP MCK MCO MDLZ MDT NFLX NI NKE NOC NOW ORCL ORLY OTIS OXY
PDD PEG PEP PFE PFG RL RMD ROK ROL ROP SJM SLB SMCI SNA SNDK
TECH TEL TER TFC TGT UNH UNP UPS URI USB VRSK VRSN VRTX VST VTR
WEC WELL WFC WM WMB""".split()

RETRY = [("SHOP","CFRA"),("SHOP","ZACKS"),("CARR","ZACKS"),("VICI","ZACKS"),("L","ZACKS")]
SOURCES = ["CFRA", "ZACKS"]

FETCH_SCRIPT = '''
import asyncio, sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath("{script_dir}")))
from app.services.fetcher_service import fetch_pdf
r = asyncio.run(fetch_pdf("{ticker}", "{source}"))
print(r["status"] + "|" + r.get("pdf_path", r.get("error", "")))
'''

def main():
    today = datetime.now().strftime("%Y-%m-%d")
    done = set()
    pdf_dir = Path(f"storage/pdfs/{today}")
    if pdf_dir.exists():
        for f in pdf_dir.glob("*.pdf"):
            if f.stat().st_size > 1000:
                done.add(f.stem)

    tasks = [(t, s) for t in TICKERS for s in SOURCES] + RETRY
    remaining = [(t, s) for t, s in tasks if f"{t}_{s}" not in done]
    random.shuffle(remaining)

    total = len(remaining)
    success = fail = 0

    print(f"🎯 남은 {total}개 PDF (subprocess 방식)", flush=True)

    script_dir = str(Path(__file__).parent)
    venv_python = str(Path(script_dir) / ".venv" / "bin" / "python3")

    for i, (ticker, source) in enumerate(remaining):
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

        code = FETCH_SCRIPT.format(ticker=ticker, source=source, script_dir=script_dir + "/x")
        try:
            result = subprocess.run(
                [venv_python, "-c", code],
                capture_output=True, text=True, timeout=60, cwd=script_dir
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
