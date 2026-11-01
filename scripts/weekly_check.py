#!/usr/bin/env python3
"""Weekly automated check (runs in GitHub Actions; needs internet).

1. Re-reads each insurer's official product list page(s) and extracts IRDAI UINs.
   - UIN on the page that the catalogue does not have      -> changelog `new_uin` (needs_review)
   - Same product number with a higher version            -> changelog `new_version` (needs_review)
   - UIN that was on the page last week and is now gone   -> changelog `missing_uin` (needs_review)
2. Refreshes Google Play and App Store ratings for each insurer's servicing app
   (changes of 0.1 or more are logged) and appends to data/history/ratings.csv.
3. Writes data/refresh/last_run.json so the follow-up Claude session knows what to research.

The Claude weekly session (docs/WEEKLY_TASK.md) resolves every needs_review item.
Usage: python3 scripts/weekly_check.py [--no-ratings] [--only <company_id>]
"""
import csv
import datetime as dt
import io
import json
import re
import sys
import time
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
IST = dt.timezone(dt.timedelta(hours=5, minutes=30))
UIN_RE = re.compile(r"(?<![0-9A-Z])(\d{3})\s?([A-Z])\s?(\d{3})\s?V\s?(\d{2})(?![0-9])")
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/124.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/pdf;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-IN,en;q=0.9",
}
PAGE_KEYS = ["product_list_url", "riders_url", "group_url", "withdrawn_list_url"]
# Developer/seller name fragments used to recognise each insurer's own app in store search results
APP_MATCH = {
    "lic": ["life insurance corporation"], "sbi": ["sbi life"], "hdfc": ["hdfc life"],
    "icici": ["icici prudential life", "icici pru"], "axismax": ["max life"], "bajaj": ["bajaj allianz life", "bajaj life"],
    "tataaia": ["tata aia"], "kotak": ["kotak mahindra life", "kotak life"], "absli": ["aditya birla sun life insurance"],
    "pnbmetlife": ["pnb metlife", "metlife india"], "canarahsbc": ["canara hsbc"], "indiafirst": ["indiafirst", "india first life"],
    "sud": ["star union", "sud life"], "ageasfederal": ["ageas federal"], "indusindnippon": ["nippon life"],
    "bharti": ["bharti axa life", "bharti life"], "generalicentral": ["generali"], "edelweiss": ["edelweiss life", "edelweiss tokio"],
    "pramerica": ["pramerica"], "aviva": ["aviva life"], "shriram": ["shriram life"], "bandhan": ["bandhan life", "aegon life"],
    "creditaccess": ["creditaccess life", "credit access life"], "godigit": ["go digit life", "digit life"], "acko": ["acko"],
    "indiapost": ["department of posts"],
}
NOT_CUSTOMER_APP = re.compile(r"agent|advis|partner|sales|employee|\bpos\b|recruit|\bcrm\b|channel|mitra|saathi|sathi|"
                              r"dealer|branch|\bhr\b|training|learning|\bdms\b|bancassurance|distributor", re.I)


TEST_BUILD = re.compile(r"(^|[._])(uat|test|qa|dev|staging|beta|sit)([._]|$)", re.I)


def _pick(results, tokens, title_key, dev_keys, id_key):
    for r in results:
        rid = r.get(id_key)
        if not rid or TEST_BUILD.search(str(rid)):
            continue
        title = str(r.get(title_key) or "")
        dev = " ".join(str(r.get(k) or "") for k in dev_keys).lower()
        if NOT_CUSTOMER_APP.search(title):
            continue
        if any(t in dev for t in tokens):
            return r
    return None


def discover_apps(companies):
    """Find a customer-servicing app id for insurers that have none (store search + developer-name match)."""
    found = []
    try:
        from google_play_scraper import search as play_search
    except Exception:  # noqa: BLE001
        play_search = None
    for comp in companies:
        tokens = APP_MATCH.get(comp["id"])
        if not tokens:
            continue
        apps = comp.setdefault("apps", {})
        query = comp.get("name") or comp.get("short")
        if not apps.get("android") and play_search:
            try:
                hit = _pick(play_search(query, lang="en", country="in", n_hits=10) or [], tokens, "title", ["developer"],
                            "appId")
                if hit:
                    apps["android"] = hit["appId"]
                    comp["apps_auto"] = sorted(set(comp.get("apps_auto", [])) | {"android"})
                    found.append({"company_id": comp["id"], "store": "android", "id": hit["appId"],
                                  "title": hit.get("title"), "developer": hit.get("developer")})
            except Exception as e:  # noqa: BLE001
                found.append({"company_id": comp["id"], "store": "android", "error": str(e)[:120]})
        if not apps.get("ios"):
            try:
                r = requests.get("https://itunes.apple.com/search", headers=HEADERS, timeout=30,
                                 params={"term": query, "country": "in", "entity": "software", "limit": 10})
                hit = _pick(r.json().get("results") or [], tokens, "trackName", ["sellerName", "artistName"], "trackId")
                if hit:
                    apps["ios"] = str(hit["trackId"])
                    comp["apps_auto"] = sorted(set(comp.get("apps_auto", [])) | {"ios"})
                    found.append({"company_id": comp["id"], "store": "ios", "id": str(hit["trackId"]),
                                  "title": hit.get("trackName"), "developer": hit.get("sellerName")})
            except Exception as e:  # noqa: BLE001
                found.append({"company_id": comp["id"], "store": "ios", "error": str(e)[:120]})
        if not apps:
            comp.pop("apps", None)
    return found


def load(p, default):
    try:
        return json.loads(Path(p).read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def dump(p, obj):
    Path(p).parent.mkdir(parents=True, exist_ok=True)
    Path(p).write_text(json.dumps(obj, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


def fetch_text(url):
    """Return (text, error). Text includes raw HTML so UINs inside links/attributes are found."""
    last = None
    for attempt in range(2):
        try:
            r = requests.get(url, headers=HEADERS, timeout=40, allow_redirects=True)
            if r.status_code != 200:
                last = f"HTTP {r.status_code}"
                time.sleep(3)
                continue
            ctype = r.headers.get("content-type", "").lower()
            if "pdf" in ctype or url.lower().split("?")[0].endswith(".pdf"):
                from pypdf import PdfReader
                reader = PdfReader(io.BytesIO(r.content))
                return "\n".join((pg.extract_text() or "") for pg in reader.pages), None
            html = r.text
            try:
                from bs4 import BeautifulSoup
                text = BeautifulSoup(html, "html.parser").get_text(" ")
            except Exception:  # noqa: BLE001
                text = ""
            return html + "\n" + text, None
        except Exception as e:  # noqa: BLE001
            last = type(e).__name__ + ": " + str(e)[:160]
            time.sleep(3)
    return None, last


def uins_in(text, prefixes):
    found = set()
    for m in UIN_RE.finditer(text.upper()):
        u = f"{m.group(1)}{m.group(2)}{m.group(3)}V{m.group(4)}"
        if not prefixes or m.group(1) in prefixes:
            found.add(u)
    return found


def check_products(companies, today, changelog, only=None):
    page_state = load(DATA / "refresh" / "page_uins.json", {})
    existing_ids = {e.get("id") for e in changelog}
    ok, failed, no_uin, flags, unmatched = 0, [], [], 0, []
    for comp in companies:
        cid = comp["id"]
        if only and cid != only:
            continue
        cat = load(DATA / "products" / f"{cid}.json", None)
        if not cat:
            continue
        products = cat.get("products") or []
        known = {p["uin"] for p in products if p.get("uin")}
        active = {p["uin"] for p in products if p.get("uin") and p.get("status") == "Active"}
        prefixes = {u[:3] for u in known}
        versions = {}
        for u in known:
            versions[u[:7]] = max(versions.get(u[:7], 0), int(u[-2:]))
        urls = dict(cat.get("urls") or {})
        urls.update({k: v for k, v in (comp.get("urls") or {}).items() if v})
        pages = [urls[k] for k in PAGE_KEYS if urls.get(k)]
        for url in dict.fromkeys(pages):
            text, err = fetch_text(url)
            if err:
                failed.append({"company_id": cid, "url": url, "error": err})
                continue
            found = uins_in(text, prefixes)
            if not found:
                no_uin.append({"company_id": cid, "url": url})
                continue
            ok += 1
            first_read = url not in page_state
            prev = set((page_state.get(url) or {}).get("uins") or [])
            withdrawn_page = url == urls.get("withdrawn_list_url")
            if first_read and not withdrawn_page:
                # First read of this page: UINs we lack are a coverage gap, not a change this week.
                unmatched.extend({"company_id": cid, "uin": u, "url": url} for u in sorted(found - known))
            elif not withdrawn_page:
                for u in sorted(found - prev - known):
                    base, ver = u[:7], int(u[-2:])
                    typ = "new_version" if base in versions and ver > versions[base] else "new_uin"
                    eid = f"{today}-{cid}-{typ}-{u}"
                    if eid in existing_ids:
                        continue
                    changelog.append({"id": eid, "date": today, "company_id": cid, "type": typ, "uin": u,
                                      "title": f"{u} appeared on the official product list",
                                      "details": "Spotted automatically; needs research to name and spec it.",
                                      "source": url, "status": "needs_review"})
                    existing_ids.add(eid)
                    flags += 1
                if prev:
                    for u in sorted((prev - found) & active):
                        eid = f"{today}-{cid}-missing_uin-{u}"
                        if eid in existing_ids:
                            continue
                        name = next((p.get("name") for p in products if p.get("uin") == u), u)
                        changelog.append({"id": eid, "date": today, "company_id": cid, "type": "missing_uin", "uin": u,
                                          "title": f"{name} is no longer on the product list",
                                          "details": "Possible withdrawal or new version; needs confirmation.",
                                          "source": url, "status": "needs_review"})
                        existing_ids.add(eid)
                        flags += 1
            page_state[url] = {"company_id": cid, "uins": sorted(found), "last_ok": today}
    dump(DATA / "refresh" / "page_uins.json", page_state)
    return {"ok": ok, "failed": failed, "no_uin": no_uin, "flags_added": flags, "unmatched": unmatched}


def check_ratings(companies, today, changelog):
    reviews = load(DATA / "reviews.json", {"companies": {}})
    rc = reviews.setdefault("companies", {})
    hist_path = DATA / "history" / "ratings.csv"
    new_file = not hist_path.exists()
    hist_path.parent.mkdir(parents=True, exist_ok=True)
    stats = {"android_ok": 0, "ios_ok": 0, "failed": []}
    try:
        from google_play_scraper import app as play_app
    except Exception:  # noqa: BLE001
        play_app = None
    with open(hist_path, "a", newline="", encoding="utf-8") as hf:
        w = csv.writer(hf)
        if new_file:
            w.writerow(["date", "company_id", "store", "rating", "ratings_count"])
        for comp in companies:
            cid = comp["id"]
            entry = rc.setdefault(cid, {})
            apps = comp.get("apps") or {}
            pkg = apps.get("android") or (entry.get("android") or {}).get("package")
            if pkg and play_app:
                try:
                    info = play_app(pkg, lang="en", country="in")
                    a = entry.get("android") or {}
                    old = a.get("rating")
                    new = round(info.get("score") or 0, 2) or None
                    a.update({"package": pkg, "app_name": info.get("title") or a.get("app_name"), "rating": new,
                              "ratings_count": info.get("ratings"), "installs": info.get("installs"),
                              "last_updated": dt.datetime.fromtimestamp(info["updated"], IST).date().isoformat() if info.get("updated") else a.get("last_updated"),
                              "observed_on": today, "source": f"https://play.google.com/store/apps/details?id={pkg}"})
                    entry["android"] = a
                    w.writerow([today, cid, "android", new, info.get("ratings")])
                    stats["android_ok"] += 1
                    if old is not None and new is not None and abs(new - old) >= 0.1:
                        changelog.append({"id": f"{today}-{cid}-rating-android", "date": today, "company_id": cid,
                                          "type": "rating_change", "title": f"Android app rating {old} → {new}",
                                          "source": a["source"], "status": "done"})
                except Exception as e:  # noqa: BLE001
                    stats["failed"].append({"company_id": cid, "store": "android", "error": str(e)[:120]})
            ios = apps.get("ios") or (entry.get("ios") or {}).get("app_id")
            if ios:
                try:
                    r = requests.get("https://itunes.apple.com/lookup", params={"id": ios, "country": "in"},
                                     headers=HEADERS, timeout=30)
                    res = (r.json().get("results") or [None])[0]
                    if res:
                        a = entry.get("ios") or {}
                        old = a.get("rating")
                        new = round(res.get("averageUserRating") or 0, 2) or None
                        a.update({"app_id": str(ios), "app_name": res.get("trackName") or a.get("app_name"),
                                  "rating": new, "ratings_count": res.get("userRatingCount"),
                                  "observed_on": today, "source": res.get("trackViewUrl") or a.get("source")})
                        entry["ios"] = a
                        w.writerow([today, cid, "ios", new, res.get("userRatingCount")])
                        stats["ios_ok"] += 1
                        if old is not None and new is not None and abs(new - old) >= 0.1:
                            changelog.append({"id": f"{today}-{cid}-rating-ios", "date": today, "company_id": cid,
                                              "type": "rating_change", "title": f"iOS app rating {old} → {new}",
                                              "source": a.get("source"), "status": "done"})
                    else:
                        stats["failed"].append({"company_id": cid, "store": "ios", "error": "not found"})
                except Exception as e:  # noqa: BLE001
                    stats["failed"].append({"company_id": cid, "store": "ios", "error": str(e)[:120]})
    dump(DATA / "reviews.json", reviews)
    return stats


def main():
    args = sys.argv[1:]
    only = args[args.index("--only") + 1] if "--only" in args else None
    today = dt.datetime.now(IST).date().isoformat()
    companies = load(DATA / "companies.json", [])
    changelog = load(DATA / "changelog.json", [])
    result = {"run_at": dt.datetime.now(IST).isoformat(timespec="minutes"), "source": "github-actions"}
    result["product_pages"] = check_products(companies, today, changelog, only)
    if "--no-ratings" not in args:
        result["apps_discovered"] = discover_apps(companies)
        if any("id" in a for a in result["apps_discovered"]):
            dump(DATA / "companies.json", companies)
        result["ratings"] = check_ratings(companies, today, changelog)
    dump(DATA / "changelog.json", changelog)
    dump(DATA / "refresh" / "last_run.json", result)
    pp = result["product_pages"]
    print(f"product pages ok={pp['ok']} failed={len(pp['failed'])} no_uin={len(pp['no_uin'])} flags={pp['flags_added']}")
    if "ratings" in result:
        r = result["ratings"]
        print(f"ratings android={r['android_ok']} ios={r['ios_ok']} failed={len(r['failed'])}")


if __name__ == "__main__":
    main()
