#!/usr/bin/env python3
"""Daily market data for listed life insurers (and listed parents, marked as such) from Yahoo Finance's chart API.

    python3 scripts/market_data.py                 # refresh data/benchmark/auto/market.json
    python3 scripts/market_data.py --file CID=chart.json   # parse a saved response (testing)

Stores last close, 1-day / 1-month / 1-year / YTD returns, 52-week range and a 1-year weekly price series.
Market capitalisation is close x shares outstanding, with the share count kept by hand in data/benchmark/listed.json.
"""
import argparse
import datetime as dt
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "benchmark" / "auto" / "market.json"
LISTED = ROOT / "data" / "benchmark" / "listed.json"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"


def parse_chart(js):
    res = js["chart"]["result"][0]
    meta = res.get("meta", {})
    ts = res.get("timestamp") or []
    closes = (res.get("indicators", {}).get("quote") or [{}])[0].get("close") or []
    pts = [(dt.datetime.utcfromtimestamp(t).date(), c) for t, c in zip(ts, closes) if c is not None]
    if not pts:
        return None
    last_d, last = pts[-1]

    def ret(days=None, since=None):
        target = since or (last_d - dt.timedelta(days=days))
        base = next((c for d, c in pts if d >= target), None)
        return round((last / base - 1) * 100, 2) if base else None
    prev = pts[-2][1] if len(pts) > 1 else None
    yr = [c for d, c in pts if d >= last_d - dt.timedelta(days=365)]
    weekly, wk = [], None
    for d, c in pts:
        k = d.isocalendar()[:2]
        if k != wk:
            weekly.append([d.isoformat(), round(c, 2)])
            wk = k
        else:
            weekly[-1] = [d.isoformat(), round(c, 2)]
    return {"symbol": meta.get("symbol"), "currency": meta.get("currency"), "close": round(last, 2), "as_of": last_d.isoformat(),
            "chg_1d_pct": round((last / prev - 1) * 100, 2) if prev else None, "ret_1m_pct": ret(30), "ret_1y_pct": ret(365),
            "ret_ytd_pct": ret(since=dt.date(last_d.year, 1, 1)), "high_52w": round(max(yr), 2), "low_52w": round(min(yr), 2),
            "weekly": weekly[-60:]}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", action="append", default=[])
    a = ap.parse_args()
    listed = json.loads(LISTED.read_text())
    state = json.loads(OUT.read_text()) if OUT.exists() else {"companies": {}}
    if a.file:
        for spec in a.file:
            cid, path = spec.split("=", 1)
            state["companies"][cid] = parse_chart(json.loads(Path(path).read_text()))
    else:
        import requests
        s = requests.Session()
        s.headers["User-Agent"] = UA
        for cid, info in listed["companies"].items():
            url = f"https://query1.finance.yahoo.com/v8/finance/chart/{info['symbol']}?range=2y&interval=1d"
            try:
                r = s.get(url, timeout=30)
                r.raise_for_status()
                rec = parse_chart(r.json())
                if rec:
                    state["companies"][cid] = rec
            except Exception as e:
                state["companies"].setdefault(cid, {})["error"] = f"{type(e).__name__}"
            time.sleep(1)
    for cid, rec in state["companies"].items():
        info = listed["companies"].get(cid, {})
        if rec and rec.get("close") and info.get("shares_cr"):
            rec["mcap_cr"] = round(rec["close"] * info["shares_cr"], 0)
        if rec:
            rec["entity"] = info.get("entity")
            rec["pure_play"] = info.get("pure_play", True)
    state["updated"] = dt.date.today().isoformat()
    state["source"] = "Yahoo Finance chart API (NSE prices); share counts from data/benchmark/listed.json"
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(state, indent=1))
    print(f"market: {sum(1 for r in state['companies'].values() if r and r.get('close'))} listed prices")


if __name__ == "__main__":
    sys.exit(main())
