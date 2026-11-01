#!/usr/bin/env python3
"""Copy research outputs into the repo's data folder.

Usage: python3 scripts/import_research.py <research_out_dir>

<company_id>.json -> data/products/<company_id>.json  (validated shape, sorted products)
_metrics.json     -> data/metrics.json
_reviews.json     -> data/reviews.json (app ids also copied into data/companies.json as `apps`)
A 'baseline' entry is added to data/changelog.json the first time an insurer's catalogue is imported.
"""
import datetime as dt
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
IST = dt.timezone(dt.timedelta(hours=5, minutes=30))


def load(p, default):
    try:
        return json.loads(Path(p).read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def dump(p, obj):
    Path(p).parent.mkdir(parents=True, exist_ok=True)
    Path(p).write_text(json.dumps(obj, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


def main(src):
    src = Path(src)
    today = dt.datetime.now(IST).date().isoformat()
    changelog = load(DATA / "changelog.json", [])
    baselined = {e.get("company_id") for e in changelog if e.get("type") == "baseline"}
    companies = load(DATA / "companies.json", [])
    ids = {c["id"] for c in companies}
    imported = []
    for f in sorted(src.glob("*.json")):
        if f.name.startswith("_") or f.name.startswith("."):
            continue
        doc = load(f, None)
        if not doc or not doc.get("products"):
            continue
        cid = doc.get("company_id") or f.stem
        if cid not in ids:
            print(f"skip {f.name}: unknown company_id {cid}")
            continue
        dump(DATA / "products" / f"{cid}.json", doc)
        imported.append(cid)
        if cid not in baselined:
            n = sum(1 for p in doc["products"] if p.get("status") == "Active")
            changelog.append({"date": today, "company_id": cid, "type": "baseline",
                              "title": f"Catalogue baseline: {n} active products recorded",
                              "details": "First full research pass. Later weekly checks compare against this list.",
                              "status": "done"})
    m = load(src / "_metrics.json", None)
    if m:
        dump(DATA / "metrics.json", m)
    r = load(src / "_reviews.json", None)
    if r:
        dump(DATA / "reviews.json", r)
        for c in companies:
            rv = (r.get("companies") or {}).get(c["id"]) or {}
            apps = {}
            if (rv.get("android") or {}).get("package"):
                apps["android"] = rv["android"]["package"]
            if (rv.get("ios") or {}).get("app_id"):
                apps["ios"] = str(rv["ios"]["app_id"])
            if apps:
                c["apps"] = apps
        dump(DATA / "companies.json", companies)
    dump(DATA / "changelog.json", changelog)
    print(f"imported catalogues: {', '.join(imported) or 'none'}; metrics: {bool(m)}; reviews: {bool(r)}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "/home/claude/research/out")
