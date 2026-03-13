#!/usr/bin/env python3
"""Stealth PDF downloader Round 2 — 알파벳별 다음 5개 + 실패 재시도"""

import asyncio
import random
import sys
import os
from datetime import datetime
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from app.services.fetcher_service import fetch_pdf

TICKERS = """ACGL ACN ADBE ADI ADM BDX BEN BF.B BG BIIB CB CBOE CBRE CCEP CCI
DE DECK DELL DG DGX EG EIX EL ELV EME FDX FE FER FFIV FICO
GEV GILD GIS GL GLW HIG HII HLT HOLX HON IFF INCY INSM INTC INTU
JNJ JPM KKR KLAC KMB KMI KO LII LIN LLY LMT LNT
MCHP MCK MCO MDLZ MDT NFLX NI NKE NOC NOW ORCL ORLY OTIS OXY
PDD PEG PEP PFE PFG RL RMD ROK ROL ROP SJM SLB SMCI SNA SNDK
TECH TEL TER TFC TGT UNH UNP UPS URI USB VRSK VRSN VRTX VST VTR
WEC WELL WFC WM WMB""".split()

# 어제 실패 재시도 (SHOP, CARR Zacks, VICI Zacks, L Zacks)
RETRY_PAIRS = [("SHOP", "CFRA"), ("SHOP", "ZACKS"), ("CARR", "ZACKS"), ("VICI", "ZACKS"), ("L", "ZACKS")]

SOURCES = ["CFRA", "ZACKS"]


async def main():
    tasks = [(t, s) for t in TICKERS for s in SOURCES]
    tasks.extend(RETRY_PAIRS)
    random.shuffle(tasks)

    total = len(tasks)
    success = 0
    fail = 0
    skipped = 0

    log_path = Path(f"stealth_download_r2_{datetime.now().strftime('%Y%m%d_%H%M')}.log")

    print(f"🎯 Round 2: {total}개 PDF 다운로드 (셔플+랜덤딜레이)")
    print(f"📝 로그: {log_path}")
    print()

    with open(log_path, "w") as log:
        log.write(f"Start: {datetime.now().isoformat()}\n")
        log.write(f"Total targets: {total}\n\n")

        for i, (ticker, source) in enumerate(tasks):
            today = datetime.now().strftime("%Y-%m-%d")
            pdf_path = Path(f"storage/pdfs/{today}/{ticker}_{source}.pdf")
            if pdf_path.exists() and pdf_path.stat().st_size > 1000:
                skipped += 1
                log.write(f"SKIP {ticker} {source}\n")
                continue

            if i > 0:
                if random.random() < 0.08:
                    delay = random.uniform(50, 100)
                    print(f"  ☕ 긴 휴식 {delay:.0f}초...", flush=True)
                elif random.random() < 0.15:
                    delay = random.uniform(25, 50)
                else:
                    delay = random.uniform(8, 22)
                await asyncio.sleep(delay)

            print(f"  [{i+1}/{total}] {ticker} {source}...", end=" ", flush=True)

            try:
                result = await fetch_pdf(ticker, source)
                if result["status"] == "success":
                    success += 1
                    size = Path(result["pdf_path"]).stat().st_size
                    print(f"✅ ({size//1024}KB)")
                    log.write(f"OK {ticker} {source} {result['pdf_path']} {size}\n")
                else:
                    fail += 1
                    print(f"❌ {result.get('error', 'unknown')[:60]}")
                    log.write(f"FAIL {ticker} {source} {result.get('error', '')}\n")
            except Exception as e:
                fail += 1
                print(f"💥 {str(e)[:60]}")
                log.write(f"ERROR {ticker} {source} {str(e)}\n")

        summary = f"\n🏁 완료! ✅ {success} / ❌ {fail} / ⏭️ {skipped} (총 {total})"
        print(summary)
        log.write(f"\n{summary}\n")
        log.write(f"End: {datetime.now().isoformat()}\n")


if __name__ == "__main__":
    asyncio.run(main())
