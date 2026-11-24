#!/usr/bin/env python3
"""State-level network of every life insurer from IRDAI's Handbook (Excel): offices by state (10 years), individual and
group new business by state, office mix by area type, and industry totals by state.

Usage: python3 scripts/parse_irdai_states.py <folder with 'Part I.xlsx'> <FY e.g. 2024-25> <source url>
Writes data/benchmark/sources/irdai_states_<FY>.json
"""
import json
import re
import sys
from pathlib import Path

import openpyxl

sys.path.insert(0, str(Path(__file__).resolve().parent))
from insurer_names import num  # noqa: E402
from parse_irdai_handbook import sheet, wide_by_particulars, wide_by_insurer, clean  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
CANON = {
    "andhra pradesh": "Andhra Pradesh", "arunachal pradesh": "Arunachal Pradesh", "assam": "Assam", "bihar": "Bihar",
    "chattisgarh": "Chhattisgarh", "chhattisgarh": "Chhattisgarh", "goa": "Goa", "gujarat": "Gujarat", "haryana": "Haryana",
    "himachal pradesh": "Himachal Pradesh", "jharkhand": "Jharkhand", "jharkand": "Jharkhand", "karnataka": "Karnataka",
    "kerala": "Kerala", "madhya pradesh": "Madhya Pradesh", "maharashtra": "Maharashtra", "manipur": "Manipur",
    "meghalaya": "Meghalaya", "mizoram": "Mizoram", "nagaland": "Nagaland", "odisha": "Odisha", "orissa": "Odisha",
    "punjab": "Punjab", "rajasthan": "Rajasthan", "rajashtan": "Rajasthan", "sikkim": "Sikkim", "tamil nadu": "Tamil Nadu",
    "tamilnadu": "Tamil Nadu", "telangana": "Telangana", "tripura": "Tripura", "uttrakhand": "Uttarakhand",
    "uttarakhand": "Uttarakhand", "uttar pradesh": "Uttar Pradesh", "west bengal": "West Bengal",
    "andaman & nicobar": "Andaman & Nicobar", "chandigarh": "Chandigarh", "delhi": "Delhi", "delhi (nct)": "Delhi",
    "jammu & kashmir": "Jammu & Kashmir", "ladakh": "Ladakh", "lakshadweep": "Lakshadweep", "puducherry": "Puducherry",
    "dadra & nagra haveli and daman & diu": "Dadra & Nagar Haveli and Daman & Diu",
    "daman, diu, dadra & nagar haveli": "Dadra & Nagar Haveli and Daman & Diu",
}
REGION = {
    "North": ["Delhi", "Haryana", "Punjab", "Himachal Pradesh", "Jammu & Kashmir", "Ladakh", "Chandigarh", "Uttarakhand", "Uttar Pradesh", "Rajasthan"],
    "West": ["Maharashtra", "Gujarat", "Goa", "Dadra & Nagar Haveli and Daman & Diu", "Madhya Pradesh", "Chhattisgarh"],
    "South": ["Karnataka", "Tamil Nadu", "Kerala", "Andhra Pradesh", "Telangana", "Puducherry", "Lakshadweep", "Andaman & Nicobar"],
    "East": ["West Bengal", "Odisha", "Bihar", "Jharkhand"],
    "North-East": ["Assam", "Arunachal Pradesh", "Manipur", "Meghalaya", "Mizoram", "Nagaland", "Sikkim", "Tripura"],
}


def canon(s):
    return CANON.get(" ".join(str(s or "").lower().split()))


def main():
    folder, fy, src = Path(sys.argv[1]), sys.argv[2], sys.argv[3]
    p1 = openpyxl.load_workbook(folder / "Part I.xlsx", data_only=True, read_only=True)
    co, ind = {}, {}

    # offices by state (Table 29)
    for cid, rec in wide_by_particulars(sheet(p1, "29"), label_col=1, ins_row=1, year_row=2).items():
        for (lab, y), v in rec.items():
            st = canon(lab)
            if st:
                co.setdefault(cid, {}).setdefault("offices", {}).setdefault(st, {})[y] = v
    # individual new business by state (Table 6)
    for cid, rec in wide_by_particulars(sheet(p1, "6"), label_col=1, ins_row=2, year_row=3, sub_row=4).items():
        for (lab, y, sub), v in rec.items():
            st = canon(lab)
            if st and sub:
                k = "ind_policies" if "polic" in sub.lower() else "ind_premium_cr"
                co.setdefault(cid, {}).setdefault(k, {}).setdefault(st, {})[y] = v
    # group new business by state (Table 8)
    for cid, rec in wide_by_particulars(sheet(p1, "8"), label_col=1, ins_row=1, year_row=2, sub_row=3).items():
        for (lab, y, sub), v in rec.items():
            st = canon(lab)
            if st and sub and y == fy:
                k = "grp_premium_cr" if "premium" in sub.lower() else "grp_lives" if "lives" in sub.lower() else "grp_schemes"
                co.setdefault(cid, {}).setdefault(k, {})[st] = v
    # office mix by area type (Table 30), latest year
    last = str(int(fy[:4]) + 1)
    for cid, rec in wide_by_insurer(sheet(p1, "30")).items():
        for lab, v in rec.items():
            if len(lab) >= 2 and str(lab[-1]).startswith(last) and lab[0] != "Total":
                co.setdefault(cid, {}).setdefault("office_mix", {})[lab[0]] = v
    # industry by state (Table 5)
    rows = sheet(p1, "5")
    yrs = [clean(x) for x in rows[2]]
    subs = [clean(x) for x in rows[3]]
    y = None
    cols = []
    for j, (a, b) in enumerate(zip(yrs, subs)):
        if a:
            y = a
        if b and y:
            cols.append((j, y, "policies" if "polic" in b.lower() else "premium_cr"))
    for r in rows[4:]:
        st = canon(r[1] if len(r) > 1 else None)
        if st:
            for j, y, k in cols:
                v = num(r[j]) if j < len(r) else None
                if v is not None:
                    ind.setdefault(st, {}).setdefault(k, {})[y] = v
    region_of = {s: rg for rg, ss in REGION.items() for s in ss}
    out = {"source": src, "fy": fy, "regions": REGION, "region_of": region_of, "industry": ind, "companies": co,
           "notes": "Offices at 31 March of the year ending each FY; premium in Rs crore. From IRDAI Handbook tables 5, 6, 8, 29 and 30."}
    dest = ROOT / "data" / "benchmark" / "sources" / f"irdai_states_{fy}.json"
    dest.write_text(json.dumps(out, ensure_ascii=False, indent=0))
    print(f"wrote {dest.relative_to(ROOT)}: {len(co)} insurers, {len(ind)} states; "
          f"offices {sum(1 for c in co.values() if 'offices' in c)}, ind NB {sum(1 for c in co.values() if 'ind_premium_cr' in c)}, mix {sum(1 for c in co.values() if 'office_mix' in c)}")


if __name__ == "__main__":
    main()
