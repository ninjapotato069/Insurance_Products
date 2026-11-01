#!/usr/bin/env python3
"""List the spec backlog: active individual products whose specs are not yet full.

Usage: python3 scripts/backlog.py [N]        (default 25)
Ordered by insurer share of new business (largest first), then list-only before partial.
Columns: company_id | uin | category | completeness | name | product_page | brochure
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"


def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 25
    try:
        metrics = json.loads((DATA / "metrics.json").read_text(encoding="utf-8")).get("companies") or {}
    except FileNotFoundError:
        metrics = {}
    share = {cid: ((m.get("metrics") or {}).get("nbp_market_share_pct") or {}).get("value") or 0
             for cid, m in metrics.items()}
    rows = []
    for f in sorted((DATA / "products").glob("*.json")):
        doc = json.loads(f.read_text(encoding="utf-8"))
        cid = doc.get("company_id") or f.stem
        for p in doc.get("products") or []:
            if p.get("segment") == "Individual" and p.get("status") == "Active" and p.get("completeness") != "full":
                rows.append((-share.get(cid, 0), 0 if p.get("completeness") == "list-only" else 1, cid, p))
    rows.sort(key=lambda r: (r[0], r[1], r[2], r[3].get("name") or ""))
    print(f"{len(rows)} products in backlog; showing {min(n, len(rows))}")
    for _, _, cid, p in rows[:n]:
        u = p.get("urls") or {}
        print(" | ".join(str(x) for x in [cid, p.get("uin"), p.get("category"), p.get("completeness"), p.get("name"),
                                          u.get("product_page"), u.get("brochure")]))


if __name__ == "__main__":
    main()
