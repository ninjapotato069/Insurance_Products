#!/usr/bin/env python3
"""Build data/dashboard.json and exports/*.csv from the source data files.

Sources (edit these):
  data/companies.json        insurer master (profile, URLs, app ids)
  data/metrics.json          company metrics + industry metrics
  data/reviews.json          app ratings, third-party ratings, review themes, digital servicing
  data/products/<id>.json    one product catalogue per insurer (schema: docs/SPEC.md)
  data/changelog.json        change log (weekly refresh + manual)
  data/ownership.json        FDI cap timeline, shareholders, foreign partners, ownership events (optional)
  data/refresh/last_run.json status of the last automated refresh (optional)

Outputs (never edit by hand):
  data/dashboard.json        everything the dashboard needs, nulls stripped
  exports/products.csv       flat product table (Excel / Power BI)
  exports/companies.csv      flat insurer table

Usage: python3 scripts/build.py
"""
import csv
import datetime as dt
import json
import re
import statistics
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
EXPORTS = ROOT / "exports"
IST = dt.timezone(dt.timedelta(hours=5, minutes=30))

INDIVIDUAL_CATS = ["Term", "ULIP", "Savings - Par", "Savings - Non-Par", "Pension & Annuity", "Health & CI"]
TAXONOMY = {
    "segments": ["Individual", "Rider", "Group", "Micro"],
    "categories": {
        "Individual": INDIVIDUAL_CATS,
        "Group": ["Group Term", "Credit Life", "Group Fund (Gratuity/Superannuation/Leave)", "Group Annuity",
                  "Group Health & Accident", "Govt Scheme", "Group Other"],
        "Rider": ["Accidental Death/Disability", "Critical Illness", "Waiver of Premium", "Term Rider",
                  "Health/Hospital", "Other Rider"],
        "Micro": ["Micro Insurance"],
    },
    "need_tags": ["Protection", "Savings", "Wealth", "Retirement", "Child", "Health", "Legacy"],
}
UIN_RE = re.compile(r"^(\d{3})([A-Z])(\d{3})V(\d{2})$")
# Metrics where a lower value is better (used by the dashboard to colour comparisons)
LOWER_IS_BETTER = {"grievances_per_10k", "grievances_total", "ombudsman_complaints", "claims_repudiated_pct"}
# Insurers excluded from industry medians
MEDIAN_EXCLUDE = {"indiapost", "sahara"}


def load(path, default):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return default


def strip_nulls(obj):
    """Recursively drop None, empty strings, empty lists and empty dicts."""
    if isinstance(obj, dict):
        out = {}
        for k, v in obj.items():
            v = strip_nulls(v)
            if v is None or v == "" or v == [] or v == {}:
                continue
            out[k] = v
        return out
    if isinstance(obj, list):
        return [x for x in (strip_nulls(v) for v in obj) if x not in (None, "", [], {})]
    return obj


def slug(text):
    return re.sub(r"[^a-z0-9]+", "-", (text or "").lower()).strip("-")[:60] or "item"


def parse_date(value):
    """Return (date, precision) for YYYY / YYYY-MM / YYYY-MM-DD strings."""
    if not value or not isinstance(value, str):
        return None, None
    parts = value.split("-")
    try:
        if len(parts) == 3:
            return dt.date(int(parts[0]), int(parts[1]), int(parts[2])), "day"
        if len(parts) == 2:
            return dt.date(int(parts[0]), int(parts[1]), 1), "month"
        return dt.date(int(parts[0]), 1, 1), "year"
    except ValueError:
        return None, None


def metric_value(company, key):
    m = (company.get("metrics") or {}).get(key)
    if isinstance(m, dict) and isinstance(m.get("value"), (int, float)) and not isinstance(m.get("value"), bool):
        return m["value"]
    return None


def build():
    today = dt.datetime.now(IST).date()
    companies_src = load(DATA / "companies.json", [])
    metrics_src = load(DATA / "metrics.json", {"industry": {}, "companies": {}})
    reviews_src = load(DATA / "reviews.json", {"companies": {}})
    changelog = load(DATA / "changelog.json", [])
    last_run = load(DATA / "refresh" / "last_run.json", None)
    ownership_src = load(DATA / "ownership.json", None) or {}

    companies = {c["id"]: dict(c) for c in companies_src}
    order = [c["id"] for c in companies_src]

    # ---- products -------------------------------------------------------
    products = []
    for path in sorted((DATA / "products").glob("*.json")):
        doc = load(path, None)
        if not doc:
            continue
        cid = doc.get("company_id") or path.stem
        if cid not in companies:
            companies[cid] = {"id": cid, "name": doc.get("company_name") or cid, "short": cid}
            order.append(cid)
        comp = companies[cid]
        # catalogue URLs live with the catalogue; companies.json values win when set
        urls = dict(doc.get("urls") or {})
        urls.update({k: v for k, v in (comp.get("urls") or {}).items() if v})
        comp["urls"] = urls
        comp["catalogue_notes"] = doc.get("notes")
        comp["catalogue_researched_on"] = doc.get("researched_on")
        for p in doc.get("products") or []:
            q = dict(p)
            q["company_id"] = cid
            uin = (q.get("uin") or "").strip().upper() or None
            q["uin"] = uin
            m = UIN_RE.match(uin) if uin else None
            if m:
                q["uin_base"] = f"{m.group(1)}{m.group(2)}{m.group(3)}"
                q["uin_version"] = int(m.group(4))
            q["id"] = uin if uin else f"{cid}-{slug(q.get('name'))}"
            # keep only the category_details block that applies
            cd = q.get("category_details") or {}
            q["category_details"] = {k: v for k, v in cd.items() if v}
            q["status_label"] = q.get("status") or "Active"
            products.append(q)

    # de-duplicate ids (same UIN listed twice): keep the most complete record
    rank = {"full": 3, "partial": 2, "list-only": 1}
    by_id = {}
    for q in products:
        cur = by_id.get(q["id"])
        if cur is None:
            by_id[q["id"]] = q
            continue
        better = (q.get("status") == "Active", rank.get(q.get("completeness"), 0)) > \
                 (cur.get("status") == "Active", rank.get(cur.get("completeness"), 0))
        if better:
            by_id[q["id"]] = q
    products = list(by_id.values())

    # versions: newest active version of a product number wins; older ones are "Superseded"
    newest_active = {}
    for q in products:
        if q.get("status") == "Active" and q.get("uin_base"):
            key = (q["company_id"], q["uin_base"])
            if key not in newest_active or q["uin_version"] > newest_active[key]["uin_version"]:
                newest_active[key] = q
    for q in products:
        if not q.get("uin_base"):
            continue
        head = newest_active.get((q["company_id"], q["uin_base"]))
        if head and head is not q and head["uin_version"] > q.get("uin_version", 0):
            q["status_label"] = "Superseded"
            q["superseded_by"] = head["id"]

    # recency flags
    for q in products:
        d, prec = parse_date(q.get("launch_date"))
        if d and prec in ("day", "month") and q["status_label"] == "Active":
            age = (today - d).days
            if 0 <= age <= 365:
                q["launched_12m"] = True
            if 0 <= age <= 120:
                q["is_new"] = True

    # ---- company enrichment ---------------------------------------------
    mcomp = metrics_src.get("companies") or {}
    rcomp = reviews_src.get("companies") or {}
    for cid, comp in companies.items():
        src = mcomp.get(cid) or {}
        for k, v in src.items():
            if k == "metrics":
                continue
            comp.setdefault(k, v)
        comp["metrics"] = src.get("metrics") or {}
        comp["reviews"] = rcomp.get(cid) or {}
        mine = [q for q in products if q["company_id"] == cid]
        active = [q for q in mine if q["status_label"] == "Active"]
        by_cat = {}
        for q in active:
            if q.get("segment") == "Individual":
                by_cat[q.get("category")] = by_cat.get(q.get("category"), 0) + 1
        full = sum(1 for q in active if q.get("segment") == "Individual" and q.get("completeness") == "full")
        n_ind = sum(1 for q in active if q.get("segment") == "Individual")
        comp["stats"] = {
            "active_individual": n_ind,
            "active_rider": sum(1 for q in active if q.get("segment") == "Rider"),
            "active_group": sum(1 for q in active if q.get("segment") == "Group"),
            "active_micro": sum(1 for q in active if q.get("segment") == "Micro"),
            "withdrawn": sum(1 for q in mine if q["status_label"] == "Withdrawn"),
            "superseded": sum(1 for q in mine if q["status_label"] == "Superseded"),
            "by_category": by_cat,
            "launches_12m": sum(1 for q in active if q.get("launched_12m")),
            "full_spec_pct": round(100 * full / n_ind) if n_ind else None,
        }

    # ownership: structured block per insurer; a free-text `ownership` from the profile moves to `ownership_text`
    own_by_co = ownership_src.get("companies") or {}
    for cid, comp in companies.items():
        if isinstance(comp.get("ownership"), str):
            comp["ownership_text"] = comp.pop("ownership")
        block = own_by_co.get(cid)
        if isinstance(block, dict) and block:
            comp["ownership"] = block
    unknown_own = sorted(set(own_by_co) - set(companies))
    if unknown_own:
        print(f"warning: ownership.json has unknown company ids: {', '.join(unknown_own)}")

    # industry medians
    keys = set()
    for comp in companies.values():
        keys.update((comp.get("metrics") or {}).keys())
    medians = {}
    for key in sorted(keys):
        vals = [metric_value(c, key) for cid, c in companies.items() if cid not in MEDIAN_EXCLUDE]
        vals = [v for v in vals if v is not None]
        if len(vals) >= 5:
            medians[key] = round(statistics.median(vals), 2)

    # ---- changelog --------------------------------------------------------
    changelog = [e for e in changelog if e.get("status") != "dismissed"]
    changelog = sorted(changelog, key=lambda e: (e.get("date") or "", e.get("company_id") or ""), reverse=True)

    # ---- assemble ---------------------------------------------------------
    seg_order = {s: i for i, s in enumerate(TAXONOMY["segments"])}
    status_order = {"Active": 0, "Superseded": 1, "Withdrawn": 2}
    products.sort(key=lambda q: (order.index(q["company_id"]) if q["company_id"] in order else 999,
                                 status_order.get(q["status_label"], 3), seg_order.get(q.get("segment"), 9),
                                 q.get("category") or "", q.get("name") or ""))
    counts = {
        "insurers": len(companies),
        "products_total": len(products),
        "active_individual": sum(1 for q in products if q["status_label"] == "Active" and q.get("segment") == "Individual"),
        "active_rider": sum(1 for q in products if q["status_label"] == "Active" and q.get("segment") == "Rider"),
        "active_group": sum(1 for q in products if q["status_label"] == "Active" and q.get("segment") == "Group"),
        "active_micro": sum(1 for q in products if q["status_label"] == "Active" and q.get("segment") == "Micro"),
        "withdrawn": sum(1 for q in products if q["status_label"] == "Withdrawn"),
        "superseded": sum(1 for q in products if q["status_label"] == "Superseded"),
        "launches_12m": sum(1 for q in products if q.get("launched_12m")),
    }
    dashboard = {
        "meta": {
            "built_at": dt.datetime.now(IST).isoformat(timespec="minutes"),
            "data_as_of": max([q.get("last_verified") or "" for q in products] + [""]) or None,
            "repo": "https://github.com/ninjapotato069/Insurance_Products",
            "last_refresh": last_run,
            "ownership_researched_on": ownership_src.get("researched_on"),
            "counts": counts,
            "lower_is_better": sorted(LOWER_IS_BETTER),
        },
        "taxonomy": TAXONOMY,
        "industry": {"metrics": (metrics_src.get("industry") or {}).get("metrics") or {},
                     "notes": (metrics_src.get("industry") or {}).get("notes"),
                     "medians": medians,
                     "ownership": ownership_src.get("industry")},
        "companies": [companies[c] for c in order if c in companies],
        "products": products,
        "changelog": changelog,
    }
    dashboard = strip_nulls(dashboard)
    out = DATA / "dashboard.json"
    with open(out, "w", encoding="utf-8") as f:
        json.dump(dashboard, f, ensure_ascii=False, separators=(",", ":"))

    write_exports(dashboard)
    print(f"built {out.relative_to(ROOT)}: {counts} ({out.stat().st_size/1024:.0f} KB)")
    n_own = sum(1 for c in dashboard["companies"] if isinstance(c.get("ownership"), dict))
    n_ev = sum(len(c["ownership"].get("events") or []) for c in dashboard["companies"] if isinstance(c.get("ownership"), dict))
    if n_own:
        print(f"ownership: {n_own} insurers, {n_ev} events")


def join(v):
    if isinstance(v, list):
        return "; ".join(x.get("name", "") if isinstance(x, dict) else str(x) for x in v)
    return "" if v is None else v


def write_exports(d):
    EXPORTS.mkdir(exist_ok=True)
    names = {c["id"]: c.get("short") or c.get("name") for c in d["companies"]}
    cols = ["insurer", "company_id", "uin", "name", "segment", "category", "plan_structure", "sub_category",
            "linkage", "participation", "need_tags", "standard_product", "status", "launch_date",
            "withdrawn_date", "entry_age_min", "entry_age_max", "maturity_age_max", "policy_term_min",
            "policy_term_max", "whole_life", "ppt_options", "premium_modes", "min_annual_premium_inr",
            "min_single_premium_inr", "min_sum_assured_inr", "max_sum_assured", "guaranteed",
            "return_of_premium", "online_purchase", "channels", "variants", "riders_available",
            "key_features", "product_page", "brochure", "completeness", "last_verified"]
    with open(EXPORTS / "products.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(cols)
        for q in d["products"]:
            el, bn, urls = q.get("eligibility", {}), q.get("benefits", {}), q.get("urls", {})
            w.writerow([names.get(q["company_id"]), q["company_id"], q.get("uin"), q.get("name"), q.get("segment"),
                        q.get("category"), q.get("plan_structure"), q.get("sub_category"), q.get("linkage"),
                        q.get("participation"), join(q.get("need_tags")), q.get("standard_product"),
                        q.get("status_label"), q.get("launch_date"), q.get("withdrawn_date"),
                        el.get("entry_age_min_years"), el.get("entry_age_max_years"), el.get("maturity_age_max_years"),
                        el.get("policy_term_min_years"), el.get("policy_term_max_years"), el.get("whole_life"),
                        join(el.get("ppt_options")), join(el.get("premium_modes")), el.get("min_annual_premium_inr"),
                        el.get("min_single_premium_inr"), el.get("min_sum_assured_inr"),
                        el.get("max_sum_assured_text"), bn.get("guaranteed"), bn.get("return_of_premium"),
                        q.get("online_purchase"), join(q.get("channels")), join(q.get("variants")),
                        join(q.get("riders_available")), join(q.get("key_features")), urls.get("product_page"),
                        urls.get("brochure"), q.get("completeness"), q.get("last_verified")])
    mkeys = sorted({k for c in d["companies"] for k in (c.get("metrics") or {})})
    with open(EXPORTS / "companies.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        base = ["company_id", "name", "short", "irdai_reg_no", "sector", "listed", "established_year", "hq_city",
                "active_individual", "active_rider", "active_group", "withdrawn", "launches_12m",
                "android_rating", "ios_rating"]
        w.writerow(base + mkeys + [f"{k}_period" for k in mkeys])
        for c in d["companies"]:
            st, rv, mt = c.get("stats", {}), c.get("reviews", {}), c.get("metrics", {})
            w.writerow([c["id"], c.get("legal_name") or c.get("name"), c.get("short"), c.get("irdai_reg_no"),
                        c.get("sector"), c.get("listed"), c.get("established_year"), c.get("hq_city"),
                        st.get("active_individual"), st.get("active_rider"), st.get("active_group"),
                        st.get("withdrawn"), st.get("launches_12m"),
                        (rv.get("android") or {}).get("rating"), (rv.get("ios") or {}).get("rating")]
                       + [(mt.get(k) or {}).get("value") for k in mkeys]
                       + [(mt.get(k) or {}).get("period") for k in mkeys])


if __name__ == "__main__":
    build()
