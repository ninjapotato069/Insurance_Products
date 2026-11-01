#!/usr/bin/env python3
"""Merge a batch of products into data/products/<company_id>.json.

Usage:
  python3 scripts/add_products.py <company_id> <batch.json>   merge a batch (prints a one-line summary)
  python3 scripts/add_products.py <company_id> --summary      one line per saved product
  python3 scripts/add_products.py <company_id> --todo         active individual products whose specs are not yet full

batch.json is either a JSON list of products, or an object
  {"company_name": "...", "urls": {...}, "notes": "...", "products": [...]}
Give only the fields you know. Missing keys get null/[] defaults; `completeness` is computed for you.
A category block (term/ulip/savings/annuity/health) may sit at the top level of a product; it is moved
into category_details. Products match on UIN, else on segment + name (case-insensitive); matches are
deep-merged (non-null new values win, non-empty lists replace).
"""
import copy
import json
import re
import sys
from pathlib import Path

OUT = Path(__file__).resolve().parents[1] / "data" / "products"
import datetime as _dt
TODAY = _dt.datetime.now(_dt.timezone(_dt.timedelta(hours=5, minutes=30))).date().isoformat()
CD_KEYS = ["term", "ulip", "savings", "annuity", "health"]
ELIG = {"entry_age_min_years": None, "entry_age_max_years": None, "maturity_age_max_years": None,
        "policy_term_min_years": None, "policy_term_max_years": None, "whole_life": None,
        "ppt_options": [], "premium_modes": [], "min_annual_premium_inr": None, "min_single_premium_inr": None,
        "max_premium_text": None, "min_sum_assured_inr": None, "max_sum_assured_text": None, "notes": None}
BEN = {"death": None, "maturity": None, "survival_income": None, "guaranteed": None,
       "return_of_premium": None, "loan": None, "partial_withdrawal": None, "other": None}
TEMPLATE = {"uin": None, "name": None, "segment": None, "category": None, "plan_structure": None,
            "sub_category": None, "linkage": None, "participation": None, "need_tags": [],
            "standard_product": None, "status": "Active", "launch_date": None, "withdrawn_date": None,
            "variants": [], "eligibility": ELIG, "benefits": BEN,
            "category_details": {k: None for k in CD_KEYS}, "key_features": [], "riders_available": [],
            "online_purchase": None, "channels": [], "tax_benefits": None, "description": None,
            "urls": {"product_page": None, "brochure": None}, "sources": [], "completeness": "list-only",
            "last_verified": TODAY}
NUM_AGE = ["entry_age_min_years", "entry_age_max_years", "maturity_age_max_years",
           "policy_term_min_years", "policy_term_max_years"]
NUM_INR = ["min_annual_premium_inr", "min_single_premium_inr", "min_sum_assured_inr"]


def parse_inr(v):
    if v is None or isinstance(v, (int, float)) and not isinstance(v, bool):
        return v
    s = str(v).lower().replace(",", "").replace("₹", "").replace("rs.", "").replace("rs", "").strip()
    m = re.match(r"^([\d.]+)\s*(crore|cr|lakh|lac|l|k|thousand)?\b", s)
    if not m:
        return v
    n = float(m.group(1))
    mult = {"crore": 1e7, "cr": 1e7, "lakh": 1e5, "lac": 1e5, "l": 1e5, "k": 1e3, "thousand": 1e3}.get(m.group(2), 1)
    n = n * mult
    return int(n) if n == int(n) else n


def parse_age(v):
    if v is None or isinstance(v, (int, float)) and not isinstance(v, bool):
        return v
    s = str(v).lower()
    m = re.search(r"([\d.]+)", s)
    if not m:
        return v
    n = float(m.group(1))
    if "day" in s:
        return round(n / 365, 2)
    if "month" in s:
        return round(n / 12, 2)
    return int(n) if n == int(n) else n


def deep_merge(base, new):
    for k, v in new.items():
        if v is None:
            continue
        if isinstance(v, dict) and isinstance(base.get(k), dict):
            deep_merge(base[k], v)
        elif isinstance(v, list):
            if v:
                base[k] = v
            elif k not in base:
                base[k] = []
        else:
            base[k] = v
    return base


def normalize(p):
    p = copy.deepcopy(p)
    cd = p.pop("category_details", None) or {}
    for k in CD_KEYS:
        if isinstance(p.get(k), dict):
            cd[k] = p.pop(k)
        elif k in p and p[k] is None:
            p.pop(k)
    if cd:
        p["category_details"] = cd
    u = p.get("uin")
    if isinstance(u, str) and u.strip().lower() in ("", "none", "null", "n/a", "na", "-"):
        p.pop("uin")
    elif u:
        p["uin"] = re.sub(r"\s+", "", str(u)).upper()
    el = p.get("eligibility")
    if isinstance(el, dict):
        for k in NUM_AGE:
            if k in el:
                el[k] = parse_age(el[k])
        for k in NUM_INR:
            if k in el:
                el[k] = parse_inr(el[k])
    an = (p.get("category_details") or {}).get("annuity")
    if isinstance(an, dict) and "min_purchase_price_inr" in an:
        an["min_purchase_price_inr"] = parse_inr(an["min_purchase_price_inr"])
    return p


def completeness(p):
    el, bn = p.get("eligibility") or {}, p.get("benefits") or {}
    cdet = p.get("category_details") or {}
    pension = p.get("category") == "Pension & Annuity"
    has_price = any(el.get(k) is not None for k in NUM_INR) or \
        ((cdet.get("annuity") or {}).get("min_purchase_price_inr") is not None)
    full = (el.get("entry_age_min_years") is not None and el.get("entry_age_max_years") is not None
            and (el.get("policy_term_min_years") is not None or el.get("whole_life") or pension)
            and (el.get("ppt_options") or pension) and has_price
            and (bn.get("death") or bn.get("maturity") or bn.get("survival_income"))
            and p.get("key_features"))
    if full:
        return "full"
    some = any(el.get(k) is not None for k in NUM_AGE + NUM_INR) or any(bn.get(k) for k in ["death", "maturity", "survival_income"]) \
        or p.get("key_features")
    return "partial" if some else "list-only"


def key_of(p):
    return ("uin", p["uin"]) if p.get("uin") else ("name", (p.get("segment") or "").lower(), (p.get("name") or "").strip().lower())


def load(cid):
    path = OUT / f"{cid}.json"
    if path.exists():
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return {"company_id": cid, "company_name": None, "researched_on": TODAY,
            "urls": {"website": None, "product_list_url": None, "withdrawn_list_url": None, "riders_url": None,
                     "group_url": None, "newsroom_url": None}, "products": [], "notes": ""}


def save(cid, doc):
    OUT.mkdir(parents=True, exist_ok=True)
    tmp = OUT / f".{cid}.json.tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, indent=1)
    tmp.replace(OUT / f"{cid}.json")


def merge(cid, batch_path):
    with open(batch_path, encoding="utf-8") as f:
        batch = json.load(f)
    doc = load(cid)
    if isinstance(batch, dict):
        if batch.get("company_name"):
            doc["company_name"] = batch["company_name"]
        if isinstance(batch.get("urls"), dict):
            doc.setdefault("urls", {}).update({k: v for k, v in batch["urls"].items() if v})
        if batch.get("notes"):
            doc["notes"] = batch["notes"]
        items = batch.get("products") or []
    else:
        items = batch
    index = {key_of(p): i for i, p in enumerate(doc["products"])}
    name_index = {(("name", (p.get("segment") or "").lower(), (p.get("name") or "").strip().lower())): i
                  for i, p in enumerate(doc["products"])}
    added = updated = 0
    for raw in items:
        p = normalize(raw)
        k = key_of(p)
        i = index.get(k)
        if i is None and p.get("uin"):
            j = name_index.get(("name", (p.get("segment") or "").lower(), (p.get("name") or "").strip().lower()))
            if j is not None and not doc["products"][j].get("uin"):
                i = j
        if i is None:
            rec = deep_merge(copy.deepcopy(TEMPLATE), p)
            doc["products"].append(rec)
            i = len(doc["products"]) - 1
            added += 1
        else:
            deep_merge(doc["products"][i], p)
            updated += 1
        rec = doc["products"][i]
        for k2, v2 in TEMPLATE.items():
            if k2 not in rec:
                rec[k2] = copy.deepcopy(v2)
            elif isinstance(v2, dict):
                for kk, vv in v2.items():
                    rec[k2].setdefault(kk, copy.deepcopy(vv))
        rec["completeness"] = completeness(rec)
        rec["last_verified"] = TODAY
        index[key_of(rec)] = i
    save(cid, doc)
    print(f"{cid}: +{added} new, {updated} updated -> {summary_line(doc)}")


def summary_line(doc):
    from collections import Counter
    c = Counter((p.get("segment"), p.get("status")) for p in doc["products"])
    comp = Counter(p["completeness"] for p in doc["products"] if p.get("segment") == "Individual" and p.get("status") == "Active")
    return f"{len(doc['products'])} products " + ", ".join(f"{s}/{st}={n}" for (s, st), n in sorted(c.items(), key=str)) + \
        f" | active individual specs {dict(comp)}"


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)
    cid, arg = sys.argv[1], sys.argv[2]
    if arg == "--summary":
        doc = load(cid)
        for p in doc["products"]:
            print(" | ".join(str(x) for x in [p.get("uin"), p.get("status"), p.get("segment"), p.get("category"), p.get("completeness"), p.get("name")]))
        print(summary_line(doc))
    elif arg == "--todo":
        doc = load(cid)
        for p in doc["products"]:
            if p.get("segment") == "Individual" and p.get("status") == "Active" and p.get("completeness") != "full":
                u = p.get("urls") or {}
                print(" | ".join(str(x) for x in [p.get("uin"), p.get("category"), p.get("completeness"), p.get("name"), u.get("product_page"), u.get("brochure")]))
    else:
        merge(cid, arg)


if __name__ == "__main__":
    main()
