#!/usr/bin/env python3
"""Daily news feed per insurer from Google News RSS (headline, outlet, date, link; no article text is stored).

    python3 scripts/news_feed.py              # refresh data/benchmark/auto/news.json
    python3 scripts/news_feed.py --file CID=feed.xml   # parse a saved feed (testing)

Keeps 90 days of headlines per insurer, tags each headline by theme and counts mentions over 30 days
(share of voice). Headlines are matched on the insurer's current and former names.
"""
import argparse
import datetime as dt
import email.utils
import json
import re
import sys
import time
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.parse import quote_plus

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "benchmark" / "auto" / "news.json"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"

QUERIES = {
    "lic": ['"LIC" "life insurance corporation"'], "sbi": ['"SBI Life"'], "hdfc": ['"HDFC Life"'],
    "icici": ['"ICICI Prudential Life" OR "ICICI Life"'], "axismax": ['"Axis Max Life" OR "Max Life Insurance"'],
    "bajaj": ['"Bajaj Life Insurance" OR "Bajaj Allianz Life"'], "tataaia": ['"Tata AIA"'],
    "kotak": ['"Kotak Life" OR "Kotak Mahindra Life"'], "absli": ['"Aditya Birla Sun Life Insurance" OR "ABSLI"'],
    "pnbmetlife": ['"PNB MetLife"'], "canarahsbc": ['"Canara HSBC Life"'], "indiafirst": ['"IndiaFirst Life"'],
    "sud": ['"Star Union Dai-ichi" OR "SUD Life"'], "ageasfederal": ['"Ageas Federal Life"'],
    "indusindnippon": ['"IndusInd Nippon Life" OR "Reliance Nippon Life"'], "bharti": ['"Bharti Life Insurance" OR "Bharti AXA Life"'],
    "generalicentral": ['"Generali Central Life" OR "Future Generali India Life"'], "edelweiss": ['"Edelweiss Life Insurance"'],
    "pramerica": ['"Pramerica Life"'], "aviva": ['"Aviva Life Insurance" OR "Aviva India"'], "shriram": ['"Shriram Life Insurance"'],
    "bandhan": ['"Bandhan Life"'], "creditaccess": ['"CreditAccess Life"'], "godigit": ['"Go Digit Life" OR "Digit Life Insurance"'],
    "acko": ['"Acko Life"'], "sahara": ['"Sahara India Life"'], "indiapost": ['"Postal Life Insurance"'],
}
THEMES = [
    ("Launch", r"launch|unveil|introduc|new plan|rolls out|debut"),
    ("Results", r"\bq[1-4]\b|quarter|results|profit|pat\b|vnb|premium (?:rises|grows|jumps|falls|up|down)|earnings|fy2\d"),
    ("Regulatory", r"irdai|penalt|fine[sd]?\b|regulator|show[- ]cause|compliance|sebi"),
    ("Deal & capital", r"stake|acqui|merger|ipo|listing|invest|fdi|joint venture|jv\b|partner exit|buyback|raise[sd]? ₹|capital"),
    ("Partnership", r"partner|tie[- ]?up|bancassurance|alliance|mou\b|collaborat"),
    ("People", r"appoint|ceo|md\b|managing director|chief|resign|joins|elevat"),
    ("Claims & service", r"claim|grievance|complaint|ombudsman|settle"),
    ("Digital", r"\bapp\b|digital|\bai\b|whatsapp|technology|platform|online"),
    ("Award", r"award|recogni|wins|honou?r"),
]


def theme_of(title):
    t = title.lower()
    return next((name for name, pat in THEMES if re.search(pat, t)), "Other")


def parse_feed(xml_bytes):
    root = ET.fromstring(xml_bytes)
    items = []
    for it in root.iter("item"):
        title = (it.findtext("title") or "").strip()
        link = (it.findtext("link") or "").strip()
        src = it.find("source")
        outlet = (src.text or "").strip() if src is not None and src.text else ""
        if outlet and title.endswith(" - " + outlet):
            title = title[: -len(outlet) - 3].strip()
        pub = it.findtext("pubDate")
        try:
            d = email.utils.parsedate_to_datetime(pub).date().isoformat() if pub else None
        except (TypeError, ValueError):
            d = None
        if title and link:
            items.append({"title": title, "outlet": outlet, "date": d, "link": link, "theme": theme_of(title)})
    return items


def merge(old, new, today):
    cutoff = (today - dt.timedelta(days=90)).isoformat()
    seen, out = set(), []
    for x in sorted(new + old, key=lambda x: x.get("date") or "", reverse=True):
        key = re.sub(r"\W+", " ", x["title"].lower()).strip()[:90]
        if key in seen or (x.get("date") and x["date"] < cutoff):
            continue
        seen.add(key)
        out.append(x)
    return out[:150]


def summarise(state, today):
    c30 = (today - dt.timedelta(days=30)).isoformat()
    tot = 0
    for cid, c in state["companies"].items():
        recent = [x for x in c.get("items", []) if (x.get("date") or "") >= c30]
        c["mentions_30d"] = len(recent)
        th = {}
        for x in recent:
            th[x["theme"]] = th.get(x["theme"], 0) + 1
        c["themes_30d"] = dict(sorted(th.items(), key=lambda kv: -kv[1]))
        tot += len(recent)
    for c in state["companies"].values():
        c["share_of_voice_pct"] = round(100 * c["mentions_30d"] / tot, 2) if tot else None
    state["total_mentions_30d"] = tot


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", action="append", default=[])
    a = ap.parse_args()
    today = dt.date.today()
    state = json.loads(OUT.read_text()) if OUT.exists() else {"companies": {}}
    if a.file:
        for spec in a.file:
            cid, path = spec.split("=", 1)
            c = state["companies"].setdefault(cid, {})
            c["items"] = merge(c.get("items", []), parse_feed(Path(path).read_bytes()), today)
            c["checked_on"] = today.isoformat()
    else:
        import requests
        s = requests.Session()
        s.headers["User-Agent"] = UA
        for cid, qs in QUERIES.items():
            c = state["companies"].setdefault(cid, {})
            got = []
            for q in qs:
                url = f"https://news.google.com/rss/search?q={quote_plus(q + ' when:30d')}&hl=en-IN&gl=IN&ceid=IN:en"
                try:
                    r = s.get(url, timeout=30)
                    if r.status_code == 200:
                        got += parse_feed(r.content)
                        c["status"] = "ok"
                    else:
                        c["status"] = f"HTTP {r.status_code}"
                except Exception as e:
                    c["status"] = type(e).__name__
                time.sleep(1.5)
            c["items"] = merge(c.get("items", []), got, today)
            c["checked_on"] = today.isoformat()
    summarise(state, today)
    state["updated"] = today.isoformat()
    state["source"] = "Google News RSS search, India edition (headlines and links only)"
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(state, indent=1, ensure_ascii=False))
    print(f"news: {state['total_mentions_30d']} mentions in 30 days across {len(state['companies'])} insurers")


if __name__ == "__main__":
    sys.exit(main())
