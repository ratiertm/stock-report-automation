#!/usr/bin/env python3
"""Stealth PDF downloader — random delays, shuffled order, human-like pattern."""

import asyncio
import random
import sys
import os
from datetime import datetime
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from app.services.fetcher_service import fetch_pdf

# 알파벳별 5개 티커
TICKERS = """A AAPL ABBV ABNB ABT BA BAC BALL BAX BBY C CAG CAH CARR CAT
D DAL DASH DD DDOG EA EBAY ECL ED EFX F FANG FAST FCX FDS
GD GDDY GE GEHC GEN HAL HAS HBAN HCA HD IBKR IBM ICE IDXX IEX
J JBHT JBL JCI JKHY KDP KEY KEYS KHC KIM L LDOS LEN LH LHX
MA MAA MAR MAS MCD NCLH NDAQ NDSN NEE NEM O ODFL OKE OMC ON
PANW PAYC PAYX PCAR PCG QCOM RCL REG REGN RF RJF
SBAC SBUX SCHW SHOP SHW T TAP TDG TDY TEAM UAL UBER UDR UHS ULTA
V VICI VLO VLTO VMC WAB WAT WBD WDAY WDC XEL XOM XYL XYZ
YUM ZBH ZBRA ZS ZTS""".split()

SOURCES = ["CFRA", "ZACKS"]


async def main():
    # 모든 (ticker, source) 조합을 만들고 셔플
    tasks = [(t, s) for t in TICKERS for s in SOURCES]
    random.shuffle(tasks)

    total = len(tasks)
    success = 0
    fail = 0
    skipped = 0
    
    log_path = Path(f"stealth_download_{datetime.now().strftime('%Y%m%d_%H%M')}.log")
    
    print(f"🎯 총 {total}개 PDF 다운로드 시작 (셔플된 순서, 랜덤 딜레이)")
    print(f"📝 로그: {log_path}")
    print()

    with open(log_path, "w") as log:
        log.write(f"Start: {datetime.now().isoformat()}\n")
        log.write(f"Total targets: {total}\n\n")
        
        for i, (ticker, source) in enumerate(tasks):
            # 이미 다운로드된 파일 스킵
            today = datetime.now().strftime("%Y-%m-%d")
            pdf_path = Path(f"storage/pdfs/{today}/{ticker}_{source}.pdf")
            if pdf_path.exists() and pdf_path.stat().st_size > 1000:
                skipped += 1
                print(f"  [{i+1}/{total}] {ticker} {source} — SKIP (이미 있음)")
                log.write(f"SKIP {ticker} {source}\n")
                continue

            # 랜덤 딜레이 (8~35초, 가끔 더 긴 휴식)
            if i > 0:
                if random.random() < 0.1:  # 10% 확률로 긴 휴식
                    delay = random.uniform(45, 90)
                    print(f"  ☕ 긴 휴식 {delay:.0f}초...")
                elif random.random() < 0.2:  # 20% 확률로 중간 휴식
                    delay = random.uniform(20, 45)
                else:
                    delay = random.uniform(8, 20)
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
