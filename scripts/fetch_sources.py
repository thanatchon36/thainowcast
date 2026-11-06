"""Fetch helpers to run ON YOUR OWN MACHINE (the Claude sandbox has no access to these hosts).

Usage:
    python scripts/fetch_sources.py trends          # Google Trends -> data/raw/gt_*.csv
    python scripts/fetch_sources.py bot --key KEY   # BOT API -> pci.csv, pii.csv, credit.csv
    python scripts/fetch_sources.py lights          # prints the NASA Black Marble recipe

Everything here is a starting point written without network access: endpoints, series codes
and column names must be checked against the live documentation [ต้องตรวจ].
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

RAW = Path(__file__).resolve().parents[1] / "data" / "raw"

TRENDS = {
    "gt_unemploy": ["ว่างงาน", "หางาน"],
    "gt_loan": ["กู้เงิน", "สินเชื่อ"],
    "gt_car_installment": ["ผ่อนรถ"],
    "gt_travel": ["ที่พัก", "จองโรงแรม"],
    "gt_prices": ["ของแพง", "ราคาน้ำมันวันนี้"],
}


def fetch_trends() -> None:
    from pytrends.request import TrendReq  # pip install pytrends

    tr = TrendReq(hl="th-TH", tz=420)
    for sid, kws in TRENDS.items():
        # One request per topic keeps the 0-100 scaling comparable within the topic. Pull the
        # full history in one call (Google returns monthly data for ranges longer than 5 years).
        tr.build_payload(kws, geo="TH", timeframe="2008-01-01 2026-12-31")
        df = tr.interest_over_time()
        if df.empty:
            print(f"{sid}: empty response", file=sys.stderr)
            continue
        s = df[kws].mean(axis=1)
        s.index = pd.PeriodIndex(s.index, freq="M")
        out = pd.DataFrame({"period": s.index.astype(str), "value": s.values})
        out.to_csv(RAW / f"{sid}.csv", index=False)
        print(f"wrote {sid}.csv ({len(out)} rows)")


def fetch_bot(key: str) -> None:
    import requests

    # BOT API portal: https://apiportal.bot.or.th — subscribe to the statistics products and
    # look up the exact series codes in the data dictionary. The call below mirrors the
    # documented pattern but the product path and codes are placeholders [ต้องตรวจ].
    base = "https://apigw1.bot.or.th/bot/public/observations/"
    series = {"pci": "EC_EI_027.PCI", "pii": "EC_EI_027.PII", "credit": "FI_CB_001.LOANS"}
    for sid, code in series.items():
        r = requests.get(base, params={"series_code": code, "start_period": "2004-01", "end_period": "2026-12"}, headers={"X-IBM-Client-Id": key}, timeout=60)
        r.raise_for_status()
        obs = r.json()["result"]["series"][0]["observations"]
        out = pd.DataFrame({"period": [o["period_start"][:7] for o in obs], "value": [float(o["value"]) for o in obs]})
        out.to_csv(RAW / f"{sid}.csv", index=False)
        print(f"wrote {sid}.csv ({len(out)} rows)")


def lights_recipe() -> None:
    print(
        """NASA Black Marble VNP46A3 (monthly) -> nightlights.csv
1. Create an Earthdata login and a LAADS DAAC app key.
2. Download VNP46A3 tiles covering Thailand (h27v07, h28v07, h28v08 approx.) for every month since 2012-04.
3. For each month: read the 'AllAngle_Composite_Snow_Free' layer, mask with the Thailand boundary
   (GADM level 0 or 1), sum radiance (nW/cm2/sr) over all pixels (or per province, then sum).
4. Write period,value with the national sum. Expect a 30-45 day publication lag."""
    )


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("what", choices=["trends", "bot", "lights"])
    ap.add_argument("--key", default="")
    a = ap.parse_args()
    RAW.mkdir(parents=True, exist_ok=True)
    {"trends": fetch_trends, "bot": lambda: fetch_bot(a.key), "lights": lights_recipe}[a.what]()
