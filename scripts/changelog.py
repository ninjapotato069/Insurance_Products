#!/usr/bin/env python3
"""Add or resolve change-log entries (data/changelog.json).

  python3 scripts/changelog.py list                       # open needs_review items
  python3 scripts/changelog.py add --company hdfc --type launch --uin 101N190V01 \
      --title "HDFC Life Click 2 Achieve Plus launched" --details "..." --source https://...
  python3 scripts/changelog.py resolve --id <entry id> --type launch --title "..." --details "..."
  python3 scripts/changelog.py resolve --id <entry id> --dismiss --details "Not a new product: ..."

Types: launch, new_version, withdrawal, new_uin, missing_uin, rating_change, spec_update,
metric_update, rename, page_failed, baseline.
"""
import argparse
import datetime as dt
import json
from pathlib import Path

PATH = Path(__file__).resolve().parents[1] / "data" / "changelog.json"
IST = dt.timezone(dt.timedelta(hours=5, minutes=30))


def load():
    return json.loads(PATH.read_text(encoding="utf-8")) if PATH.exists() else []


def save(log):
    PATH.write_text(json.dumps(log, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["list", "add", "resolve"])
    ap.add_argument("--id")
    ap.add_argument("--company")
    ap.add_argument("--type")
    ap.add_argument("--uin")
    ap.add_argument("--title")
    ap.add_argument("--details")
    ap.add_argument("--source")
    ap.add_argument("--date")
    ap.add_argument("--dismiss", action="store_true")
    a = ap.parse_args()
    log = load()
    today = a.date or dt.datetime.now(IST).date().isoformat()
    if a.cmd == "list":
        for e in log:
            if e.get("status") == "needs_review":
                print(" | ".join(str(e.get(k)) for k in ["id", "company_id", "type", "uin", "title", "source"]))
        return
    if a.cmd == "add":
        eid = a.id or f"{today}-{a.company}-{a.type}-{a.uin or len(log)}"
        log.append({k: v for k, v in {"id": eid, "date": today, "company_id": a.company, "type": a.type,
                                      "uin": a.uin, "title": a.title, "details": a.details, "source": a.source,
                                      "status": "done"}.items() if v})
        save(log)
        print("added", eid)
        return
    for e in log:
        if e.get("id") == a.id:
            if a.dismiss:
                e["status"] = "dismissed"
            else:
                e["status"] = "done"
                for k in ["type", "title", "uin", "source"]:
                    if getattr(a, k):
                        e[k] = getattr(a, k)
            if a.details:
                e["details"] = a.details
            e["resolved_on"] = today
            save(log)
            print("resolved", a.id, e["status"])
            return
    raise SystemExit(f"no entry with id {a.id}")


if __name__ == "__main__":
    main()
