#!/usr/bin/env python3
"""IRDAI monthly 'New Business Statement of Life Insurers' (first-year premium, policies, lives, sum assured).

    python3 scripts/irdai_monthly.py                 # find the latest statement on IRDAI's site, parse it if new
    python3 scripts/irdai_monthly.py --file X.xlsx --url U   # parse a downloaded statement

Keeps data/benchmark/auto/monthly_nb.json: one entry per month (FY to date and the month itself), per insurer and
by segment (individual single / non-single, group single / non-single / yearly renewable). Used by the daily job.
"""
import argparse
import datetime as dt
import io
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from insurer_names import insurer_id, num  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "benchmark" / "auto" / "monthly_nb.json"
LIST_PAGES = ["https://irdai.gov.in/monthly-business-figures1",
              "https://policyholder.gov.in/web/guest/monthly-business-figures1"]
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"
SEGMENTS = {"individual single premium": "ind_single", "individual non-single premium": "ind_nonsingle",
            "group single premium": "grp_single", "group non-single premium": "grp_nonsingle",
            "group yearly renewable premium": "grp_yrt"}
GROUPS = [("first year premium", "fyp"), ("no. of policies", "pol"), ("no. of lives", "lives"), ("sum assured", "sa")]


def col_keys(hdr_top, hdr_sub):
    """Map column index -> metric key, e.g. 'fyp_month', 'fyp_month_prev', 'fyp_ytd', 'fyp_ytd_prev', 'fyp_ytd_growth', 'fyp_share'."""
    keys, group = {}, None
    for j in range(len(hdr_sub)):
        top = str(hdr_top[j] or "").strip().lower() if j < len(hdr_top) else ""
        for pat, g in GROUPS:
            if top.startswith(pat):
                group = g
        sub = " ".join(str(hdr_sub[j] or "").split()).lower()
        if not group or not sub:
            continue
        if sub.startswith("for "):
            k = "month"
        elif sub.startswith("up to"):
            k = "ytd"
        elif "growth" in sub:
            k = "growth"
        elif "market share" in sub:
            k = "share"
        else:
            continue
        keys[j] = (group, k, sub)
    # 'for' and 'up to' appear twice: previous year first, current year second
    out, seen = {}, {}
    for j in sorted(keys):
        g, k, sub = keys[j]
        n = seen.get((g, k), 0)
        seen[(g, k)] = n + 1
        if k in ("month", "ytd"):
            out[j] = f"{g}_{k}_prev" if n == 0 else f"{g}_{k}"
        elif k == "growth":
            out[j] = f"{g}_month_growth" if n == 0 else f"{g}_ytd_growth"
        else:
            out[j] = f"{g}_share"
    return out


def parse(xlsx_bytes):
    import openpyxl
    wb = openpyxl.load_workbook(io.BytesIO(xlsx_bytes), data_only=True, read_only=True)
    ws = next((w for w in wb.worksheets if re.search(r"as (at|on)|^[a-z ]*\d{4}$", w.title.strip(), re.I) and not re.search(r"[ऀ-ॿ]", w.title)), wb.worksheets[-1])
    rows = [list(r) for r in ws.iter_rows(values_only=True)]
    title = next((str(c) for r in rows[:3] for c in r if c and "period" in str(c).lower()), "")
    hi = next(i for i, r in enumerate(rows) if any(str(c or "").strip().lower() == "insurer" for c in r))
    keys = col_keys(rows[hi], rows[hi + 1])
    m = re.search(r"(\d{1,2})(?:st|nd|rd|th)?\s+([A-Za-z]+)[ ,]+(\d{4})", title)
    as_on = None
    if m:
        try:
            as_on = dt.datetime.strptime(f"{m.group(1)} {m.group(2)[:3]} {m.group(3)}", "%d %b %Y").date()
        except ValueError:
            as_on = None
    companies, totals, cur = {}, {}, None
    for r in rows[hi + 2:]:
        name = " ".join(str(r[1]).split()) if len(r) > 1 and r[1] else ""
        if not name:
            continue
        vals = {k: num(r[j]) for j, k in keys.items() if j < len(r)}
        seg = SEGMENTS.get(name.lower())
        if seg and cur is not None:
            cur.setdefault("segments", {})[seg] = {k: v for k, v in vals.items() if v is not None}
            continue
        low = name.lower()
        if low.startswith("private total") or low.startswith("grand total"):
            cur = totals.setdefault("private" if low.startswith("private") else "industry", {})
            cur.update({k: v for k, v in vals.items() if v is not None})
            continue
        cid = insurer_id(name)
        if cid:
            cur = companies.setdefault(cid, {"name": name})
            cur.update({k: v for k, v in vals.items() if v is not None})
        else:
            cur = None
    return {"title": title.strip(), "as_on": as_on.isoformat() if as_on else None, "companies": companies, "totals": totals}


def discover(session):
    """Return [(as_on_date, url)] for statements listed on IRDAI's monthly business figures pages, newest first."""
    from bs4 import BeautifulSoup
    found = {}
    for page in LIST_PAGES:
        try:
            r = session.get(page, timeout=60)
            if r.status_code != 200:
                continue
        except Exception:
            continue
        soup = BeautifulSoup(r.text, "html.parser")
        for a in soup.find_all("a", href=True):
            href = a["href"]
            text = " ".join(a.get_text(" ", strip=True).split()) + " " + href
            if "first year premium of life insurers" not in text.lower().replace("+", " ") or ".xls" not in href.lower():
                continue
            m = re.search(r"(\d{2})\.(\d{2})\.(\d{4})", text)
            if not m:
                continue
            d = dt.date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
            if href.startswith("/"):
                href = re.match(r"https?://[^/]+", page).group(0) + href
            found.setdefault(d, href)
        if found:
            break
    return sorted(found.items(), reverse=True)


def load():
    return json.loads(OUT.read_text()) if OUT.exists() else {"latest": None, "periods": {}}


def save(state, parsed, url):
    if not parsed.get("as_on"):
        raise SystemExit("statement date not found")
    key = parsed["as_on"][:7]
    state["periods"][key] = {"as_on": parsed["as_on"], "title": parsed["title"], "source": url,
                             "fetched_on": dt.date.today().isoformat(), "companies": parsed["companies"], "totals": parsed["totals"]}
    keep = sorted(state["periods"])[-36:]
    state["periods"] = {k: state["periods"][k] for k in keep}
    state["latest"] = max(state["periods"])
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(state, indent=1, ensure_ascii=False))
    return key


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--file")
    ap.add_argument("--url", default="")
    ap.add_argument("--backfill", type=int, default=2, help="also fetch this many older statements if missing")
    a = ap.parse_args()
    state = load()
    if a.file:
        key = save(state, parse(Path(a.file).read_bytes()), a.url)
        print(f"monthly NB: saved {key} ({len(state['periods'][key]['companies'])} insurers)")
        return 0
    import requests
    s = requests.Session()
    s.headers["User-Agent"] = UA
    listed = discover(s)
    if not listed:
        print("monthly NB: could not read IRDAI's list page; nothing changed")
        return 0
    added = []
    for d, url in listed[: 1 + a.backfill]:
        if d.isoformat()[:7] in state["periods"]:
            continue
        try:
            r = s.get(url, timeout=120)
            r.raise_for_status()
            added.append(save(state, parse(r.content), url))
        except Exception as e:  # keep the job going; the next run retries
            print(f"monthly NB: {d} failed: {e}")
    print(f"monthly NB: latest {state.get('latest')}; added {added or 'nothing'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
