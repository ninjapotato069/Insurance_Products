#!/usr/bin/env python3
"""Parse insurer-wise life tables from IRDAI's Handbook on Indian Insurance Statistics (Excel edition).

Usage: python3 scripts/parse_irdai_handbook.py <folder with 'Part I.xlsx' and 'Part V.xlsx'> <FY e.g. 2024-25> <source url>
Writes data/benchmark/sources/irdai_handbook_<FY>.json: per insurer, multi-year series for premium, new business,
commission, death claims and settlement speed, AUM, solvency, revenue account, profit, net worth, lapse, persistency,
offices, grievances, policies in force, state spread, agents, agent productivity and channel mix.
"""
import json
import re
import sys
from pathlib import Path

import openpyxl

sys.path.insert(0, str(Path(__file__).resolve().parent))
from insurer_names import insurer_id, num  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]

LOOSE = [
    ("absli", r"aditya|birla|biral"), ("acko", r"acko"), ("bandhan", r"bandhan|aegon"), ("ageasfederal", r"ageas|aegas"),
    ("aviva", r"aviva"), ("bajaj", r"bajaj"), ("bharti", r"bharti"), ("canarahsbc", r"canara"),
    ("creditaccess", r"credit ?access"), ("edelweiss", r"edelweiss"), ("generalicentral", r"generali"),
    ("godigit", r"digit"), ("hdfc", r"hdfc"), ("icici", r"icici"), ("indiafirst", r"india ?first"), ("kotak", r"kotak"),
    ("axismax", r"\bmax"), ("pnbmetlife", r"pnb|metlife"), ("pramerica", r"pramerica"), ("indusindnippon", r"nippon"),
    ("sahara", r"sahara"), ("sbi", r"\bsbi"), ("shriram", r"shriram"), ("sud", r"star union|\bsud\b"), ("tataaia", r"tata"),
    ("lic", r"\blic\b|life insurance corporation"),
]


def cid_of(name):
    if name is None:
        return None
    s = " ".join(str(name).split())
    if not s or re.search(r"total|sector|exide|particulars|insurer$|s\.? ?no", s, re.I):
        return None
    c = insurer_id(s)
    if c:
        return c
    for k, p in LOOSE:
        if re.search(p, s, re.I):
            return k
    return None


def sheet(wb, name):
    ws = next((w for w in wb.worksheets if w.title.strip() == name), None)
    return [list(r) for r in ws.iter_rows(values_only=True)] if ws is not None else []


def clean(v):
    return " ".join(str(v).split()) if v is not None and str(v).strip() else None


def header_labels(hdr_rows, ncols):
    """Hierarchical forward-fill: a lower header row fills right only within its parent's span."""
    labels = [[] for _ in range(ncols)]
    parent = [None] * ncols
    for row in hdr_rows:
        row = (row + [None] * ncols)[:ncols]
        cur, last_parent, filled = None, object(), []
        for j in range(ncols):
            v = clean(row[j])
            if parent[j] != last_parent:
                cur = None
                last_parent = parent[j]
            if v is not None:
                cur = v
            filled.append(cur)
        for j in range(ncols):
            if filled[j] is not None:
                labels[j].append(filled[j])
        parent = [tuple(labels[j]) for j in range(ncols)]
    return [tuple(x) for x in labels]


def wide_by_insurer(rows, name_col=1):
    """Layout A: one row per insurer. Returns {cid: {label_tuple: value}} using the header rows above the first insurer."""
    first = next((i for i, r in enumerate(rows) if len(r) > name_col and cid_of(r[name_col])), None)
    if first is None:
        return {}
    start = max(i for i in range(first) if rows[i] and any(clean(x) and re.search(r"insurer|particulars", str(x), re.I) for x in rows[i][:3])) if any(
        rows[i] and any(clean(x) and re.search(r"insurer|particulars", str(x), re.I) for x in rows[i][:3]) for i in range(first)) else 0
    hdr = [r for r in rows[start:first] if any(clean(x) for x in r[name_col + 1:]) and not re.search(r"public sector|private sector", str(r[name_col] or ""), re.I)]
    ncols = max(len(r) for r in rows)
    labels = header_labels(hdr, ncols)
    out = {}
    for r in rows[first:]:
        if len(r) <= name_col:
            continue
        cid = cid_of(r[name_col])
        if not cid or cid in out:
            continue
        rec = {}
        for j in range(name_col + 1, len(r)):
            v = num(r[j])
            if v is not None and labels[j]:
                rec[labels[j]] = v
        out[cid] = rec
    return out


def wide_by_particulars(rows, label_col=0, ins_row=None, year_row=None, sub_row=None):
    """Layout B: insurers across column groups, particulars down. Returns {cid: {(particular, year[, sub]): value}}."""
    ncols = max(len(r) for r in rows)
    if ins_row is None:
        ins_row = next(i for i, r in enumerate(rows) if sum(1 for x in r if cid_of(x)) >= 5)
    if year_row is None:
        year_row = ins_row + 1
    hdr = [rows[ins_row], rows[year_row]] + ([rows[sub_row]] if sub_row is not None else [])
    labels = header_labels([list(r) for r in hdr], ncols)
    colmap = {}
    for j in range(ncols):
        lab = labels[j]
        if j <= label_col or len(lab) < len(hdr):
            continue
        c = cid_of(lab[0])
        if c:
            colmap[j] = (c,) + tuple(lab[1:])
    out = {}
    for r in rows[max(year_row, sub_row or 0) + 1:]:
        lab = clean(r[label_col]) if len(r) > label_col else None
        if not lab:
            continue
        for j, key in colmap.items():
            if j < len(r):
                v = num(r[j])
                if v is not None:
                    out.setdefault(key[0], {}).setdefault((lab,) + key[1:], v)
    return out


def fy_of(label):
    """Normalise year labels: 2025 -> '2024-25' style is left to the caller; keep strings."""
    return str(label).strip()


def main():
    folder, fy, src = Path(sys.argv[1]), sys.argv[2], sys.argv[3]
    p1 = openpyxl.load_workbook(folder / "Part I.xlsx", data_only=True, read_only=True)
    p5 = openpyxl.load_workbook(folder / "Part V.xlsx", data_only=True, read_only=True)
    co = {}

    def put(cid, key, sub, val):
        if val is None:
            return
        co.setdefault(cid, {}).setdefault(key, {})[str(sub)] = round(val, 4) if isinstance(val, float) else val

    # Table 2, 3: total premium and new business premium by year
    for tno, key in (("2", "total_premium_cr"), ("3", "nbp_cr")):
        for cid, rec in wide_by_insurer(sheet(p1, tno)).items():
            for lab, v in rec.items():
                if re.fullmatch(r"\d{4}-\d{2}", lab[-1]):
                    put(cid, key, lab[-1], v)

    # Table 13: commission
    for cid, rec in wide_by_insurer(sheet(p1, "13")).items():
        for lab, v in rec.items():
            y = lab[-1]
            g = " / ".join(lab[:-1]).lower()
            if "total commission (ulip+traditional)" in g:
                put(cid, "commission_cr", y, v)
            elif "of total commission to total premium" in g:
                put(cid, "commission_pct_premium", y, v)
            elif "ulip commission" in g and "%" not in g:
                put(cid, "commission_ulip_cr", y, v)
            elif "% to ulip premium" in g:
                put(cid, "commission_ulip_pct", y, v)
            elif "% to traditional premium" in g:
                put(cid, "commission_trad_pct", y, v)

    # Table 15 (individual) and 17 (group): death claims by year
    for tno, key in (("15", "death_claims_ind"), ("17", "death_claims_grp")):
        for cid, rec in wide_by_insurer(sheet(p1, tno)).items():
            for lab, v in rec.items():
                if len(lab) < 3:
                    continue
                y, what, unit = lab[0], lab[1].lower(), lab[2].lower()
                short = {"claims pending at start of the period": "pending_start", "claims intimated / booked": "intimated",
                         "total claims": "total", "claims paid": "paid", "claims repudiated": "repudiated",
                         "claims rejected": "rejected", "claims unclaimed": "unclaimed",
                         "claims pending at end of the period": "pending_end"}.get(what.strip())
                if short:
                    suf = "no" if "no." in unit else "amt" if "amount" in unit else None
                    if suf:
                        co.setdefault(cid, {}).setdefault(key, {}).setdefault(y, {})[f"{short}_{suf}"] = v
                elif what.startswith("break up"):
                    co.setdefault(cid, {}).setdefault(key, {}).setdefault(y, {})["pending_" + re.sub(r"\W+", "", unit)] = v

    # Table 18: duration-wise settlement of individual death claims (number of policies block)
    rows18 = sheet(p1, "18")
    cut = next((i for i, r in enumerate(rows18) if r and clean(r[0]) and "BENEFIT AMOUNT" in clean(r[0]).upper()), len(rows18))
    for cid, rec in wide_by_particulars(rows18[:cut]).items():
        for (lab, y), v in rec.items():
            k = {"within 30 days of intimation": "d30", "31 to 90 days": "d90", "91 to 180 days": "d180",
                 "181 days to 1 year": "d365", "more than 1 year": "d365plus", "total claims settled": "total"}.get(lab.lower())
            if k:
                co.setdefault(cid, {}).setdefault("claims_duration_ind", {}).setdefault(y, {})[k] = v

    # Table 21: AUM, grand total (all funds) and ULIP funds
    for cid, rec in wide_by_insurer(sheet(p1, "21")).items():
        for lab, v in rec.items():
            g = " / ".join(lab[:-1]).lower()
            if "grand total" in g:
                put(cid, "aum_cr", lab[-1], v)
            elif "total (ulip funds)" in g:
                put(cid, "aum_ulip_cr", lab[-1], v)

    # Table 21 in detail: investment mix by fund and asset category
    for cid, rec in wide_by_insurer(sheet(p1, "21")).items():
        for lab, v in rec.items():
            if len(lab) >= 3:
                fund = "life" if lab[0].lower().startswith("life") else "pension_group" if lab[0].lower().startswith("pension") else "ulip" if lab[0].lower().startswith("unit") else None
                if fund:
                    co.setdefault(cid, {}).setdefault("aum_mix", {}).setdefault(str(lab[-1]), {}).setdefault(fund, {})[lab[1]] = v

    # Table 22: equity share capital (Rs crore, 31 March)
    for cid, rec in wide_by_insurer(sheet(p1, "22")).items():
        for lab, v in rec.items():
            put(cid, "equity_capital_cr", lab[-1], v)

    # Table 23: solvency at quarter ends
    for cid, rec in wide_by_insurer(sheet(p1, "23")).items():
        for lab, v in rec.items():
            put(cid, "solvency", lab[-1], v)

    # Table 24: policyholders' account (Rs lakh)
    want24 = {"(a) premium": "premium", "(b) reinsurance ceded": "ri_ceded", "(a) interest, dividends & rent – gross": "inv_income", "commission": "commission", "operating expenses related to insurance business": "opex",
              "benefits paid (net)": "benefits", "surplus/ (deficit) (d) =(a)-(b)- (c )": "surplus"}
    for cid, rec in wide_by_particulars(sheet(p1, "24")).items():
        for (lab, y), v in rec.items():
            k = want24.get(" ".join(lab.lower().split()))
            if k:
                co.setdefault(cid, {}).setdefault("revenue_account_lakh", {}).setdefault(y, {}).setdefault(k, v)

    # Table 25: profit after tax (Rs lakh)
    for cid, rec in wide_by_particulars(sheet(p1, "25")).items():
        for (lab, y), v in rec.items():
            if re.sub(r"\s+", " ", lab.lower()).startswith("profit / (loss) after tax"):
                put(cid, "pat_lakh", y, v)
            if " ".join(lab.lower().split()).startswith("(a) interest, dividends & rent"):
                put(cid, "sh_inv_income_lakh", y, v)

    # Table 26: shareholders' funds = first 'Sub-Total' (Rs lakh)
    rows26 = sheet(p1, "26")
    first_sub = next((i for i, r in enumerate(rows26) if r and clean(r[0]) == "Sub-Total"), None)
    if first_sub:
        b = wide_by_particulars(rows26[:first_sub + 1])
        for cid, rec in b.items():
            for (lab, y), v in rec.items():
                if lab == "Sub-Total":
                    put(cid, "net_worth_lakh", y, v)

    # Table 27: lapse ratio (% of policies), individual non-linked
    for cid, rec in wide_by_insurer(sheet(p1, "27")).items():
        for lab, v in rec.items():
            if "lapse ratio" in lab[0].lower():
                put(cid, "lapse_ratio_pct", lab[-1], v)

    # Table 28: persistency by number of policies, at 31 March of each year
    for cid, rec in wide_by_insurer(sheet(p1, "28")).items():
        for lab, v in rec.items():
            if len(lab) >= 2:
                m = re.match(r"(\d+)", lab[-1])
                if m:
                    co.setdefault(cid, {}).setdefault("persistency_pct", {}).setdefault(str(lab[0]), {})[m.group(1)] = v

    # Table 29: offices, 'Total' row
    rows29 = sheet(p1, "29")
    for cid, rec in wide_by_particulars(rows29, label_col=1, ins_row=1, year_row=2).items():
        for (lab, y), v in rec.items():
            if lab.lower() == "total":
                put(cid, "offices", y, v)

    # Table 37: grievances
    for cid, rec in wide_by_insurer(sheet(p1, "37")).items():
        for lab, v in rec.items():
            if len(lab) >= 2:
                k = {"o/s at the start of the year": "os_start", "reported during the year": "reported",
                     "duplicate complaints": "duplicate", "actual reported during the year": "actual_reported",
                     "resolved during the year": "resolved", "closing balance": "closing"}.get(" ".join(lab[1].lower().split()))
                if k:
                    co.setdefault(cid, {}).setdefault("grievances", {}).setdefault(lab[0], {})[k] = v

    # Table 10: individual policies in force at year end ('000s), summed over business lines
    rows10 = sheet(p1, "10")
    for cid, rec in wide_by_particulars(rows10, label_col=0, ins_row=2, year_row=3).items():
        tot = {}
        for (lab, y), v in rec.items():
            if lab.lower().startswith("business in force at end"):
                tot[y] = tot.get(y, 0) + v
        for y, v in tot.items():
            put(cid, "policies_in_force_000", y, v)

    # Table 6: state-wise individual new business premium (latest year) -> spread and concentration
    rows6 = sheet(p1, "6")
    b6 = wide_by_particulars(rows6, label_col=1, ins_row=2, year_row=3, sub_row=4)
    for cid, rec in b6.items():
        prem = {lab: v for (lab, y, s), v in rec.items() if y == fy and s and "premium" in s.lower() and lab.lower() != "total" and v and v > 0}
        tot = sum(prem.values())
        if tot > 0:
            shares = sorted((v / tot for v in prem.values()), reverse=True)
            co.setdefault(cid, {})["state_spread"] = {
                "year": fy, "states_with_business": len(prem), "top_state": max(prem, key=prem.get),
                "top_state_share_pct": round(shares[0] * 100, 2), "top3_share_pct": round(sum(shares[:3]) * 100, 2),
                "hhi": round(sum(s * s for s in shares) * 10000)}

    # Part V: agents and productivity
    for tno, key in (("90", "individual_agents"), ("91", "corporate_agents")):
        for cid, rec in wide_by_insurer(sheet(p5, tno)).items():
            for lab, v in rec.items():
                put(cid, key, lab[-1], v)
    for tno, key in (("93", "agent_policies_avg"), ("94", "agent_nbp_lakh_avg"), ("95", "agent_premium_per_policy_inr")):
        for cid, rec in wide_by_insurer(sheet(p5, tno)).items():
            for lab, v in rec.items():
                if len(lab) >= 2:
                    who = "individual" if "individual" in lab[0].lower() else "corporate"
                    co.setdefault(cid, {}).setdefault(key, {}).setdefault(who, {})[lab[-1]] = v

    # Table 100 / 102: channel-wise new business (latest year)
    for tno, key in (("100", "channels_individual"), ("102", "channels_group")):
        for cid, rec in wide_by_insurer(sheet(p5, tno)).items():
            ch = {}
            for lab, v in rec.items():
                name = lab[0] if len(lab) < 3 or lab[0] != "Corporate Agents" else f"Corporate Agents - {lab[1].strip()}"
                unit = lab[-1].lower()
                k = "policies" if "polic" in unit else "schemes" if "scheme" in unit else "premium" if "premium" in unit else "lives" if "lives" in unit else None
                if k:
                    ch.setdefault(name.replace("**", "").replace("*", "").strip(), {})[k] = v
            co.setdefault(cid, {})[key] = {"year": fy, "by_channel": ch}

    # Part III tables 73 and 75: health products and health riders written by life insurers (new business, Rs lakh)
    try:
        p3 = openpyxl.load_workbook(folder / "Part III.xlsx", data_only=True, read_only=True)
        for tno, key in (("73", "health_products_nb"), ("75", "health_riders_nb")):
            for cid, rec in wide_by_insurer(sheet(p3, tno)).items():
                for lab, v in rec.items():
                    if len(lab) >= 3 and lab[1].upper().startswith("TOTAL"):
                        k = "premium_lakh" if "premium" in lab[2].lower() else "persons" if "persons" in lab[2].lower() else "count"
                        co.setdefault(cid, {}).setdefault(key, {}).setdefault(lab[0], {})[k] = v
    except FileNotFoundError:
        pass

    out = {"source": src, "fy": fy, "companies": co,
           "notes": "Parsed from IRDAI Handbook on Indian Insurance Statistics (Excel). Amounts in the units named by each key."}
    dest = ROOT / "data" / "benchmark" / "sources" / f"irdai_handbook_{fy}.json"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(out, indent=1, ensure_ascii=False))
    keys = sorted({k for c in co.values() for k in c})
    cov = {k: sum(1 for c in co.values() if k in c) for k in keys}
    print(f"wrote {dest.relative_to(ROOT)}: {len(co)} insurers")
    print(cov)


if __name__ == "__main__":
    main()
