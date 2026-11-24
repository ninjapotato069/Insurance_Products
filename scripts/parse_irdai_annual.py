#!/usr/bin/env python3
"""Parse insurer-wise life tables from the IRDAI Annual Report (text from `pdftotext -layout`).

Usage: python3 scripts/parse_irdai_annual.py <report.txt> <FY label e.g. 2024-25> <source url>
Writes data/benchmark/sources/irdai_annual_<FY>.json with, per insurer:
  premium (Statement 3), linked / non-linked new business and renewal (Statement 4),
  quarterly solvency (Statement 11), AUM by fund (Statement 16), products and riders filed (Annexure 7).
"""
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from insurer_names import insurer_id, num  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
NUM = r"\(?-?[\d,]+(?:\.\d+)?\)?|-|\$"


def section(lines, start_pat, end_pat, start_at=0):
    """Lines from the first match of start_pat (after start_at) up to the next match of end_pat."""
    s = next((i for i in range(start_at, len(lines)) if re.search(start_pat, lines[i])), None)
    if s is None:
        return [], None
    e = next((i for i in range(s + 1, len(lines)) if re.search(end_pat, lines[i])), len(lines))
    return lines[s:e], s


def rows(block, min_nums=1, left_only=False):
    """Yield (company_id, name, [numbers...]) for lines that start with an insurer name."""
    for ln in block:
        text = ln.rstrip()
        if left_only:  # two-column annexures: keep the left half (life insurers)
            m = re.match(r"^\s*\d*\s*([A-Za-z][^\d]*?)\s{2,}(\d+)\s+(\d+)", text)
            if m:
                cid = insurer_id(m.group(1))
                if cid:
                    yield cid, m.group(1).strip(), [float(m.group(2)), float(m.group(3))]
            continue
        m = re.match(r"^\s*(?:\d+\s+)?([A-Za-z][A-Za-z.&,'()\- ]+?[A-Za-z.)$*]+)\s{2,}(.*)$", text)
        if not m:
            continue
        cid = insurer_id(m.group(1))
        if not cid:
            continue
        toks = re.findall(NUM, m.group(2))
        if len(toks) < min_nums:
            continue
        yield cid, m.group(1).strip(), [num(t) for t in toks]


def main():
    txt_path, fy, src = sys.argv[1], sys.argv[2], sys.argv[3]
    lines = Path(txt_path).read_text(encoding="utf-8", errors="ignore").splitlines()
    out = {"source": src, "fy": fy, "tables": {}, "companies": {}}
    co = out["companies"]

    def put(cid, key, val):
        if val is not None:
            co.setdefault(cid, {})[key] = val

    # Statement 3: total premium, previous and current year
    blk, _ = section(lines, r"TOTAL PREMIUM UNDERWRITTEN BY LIFE INSURERS", r"Statement 4|Industry Total")
    for cid, _, v in rows(blk, 2):
        put(cid, "total_premium_prev_cr", v[-2])
        put(cid, "total_premium_cr", v[-1])
    out["tables"]["premium"] = "Statement 3: Total premium underwritten by life insurers"

    # Statement 4: linked / non-linked / total x (first year, single, new business, renewal, total)
    blk, _ = section(lines, r"LINKED AND NON-LINKED PREMIUM OF LIFE INSURERS", r"Industry Total")
    keys = ["first_year", "single", "new_business", "renewal", "total"]
    for cid, _, v in rows(blk, 15):
        v = v[-15:]
        for gi, g in enumerate(["linked", "nonlinked", "all"]):
            for ki, k in enumerate(keys):
                put(cid, f"{g}_{k}_cr", v[gi * 5 + ki])
    out["tables"]["premium_split"] = "Statement 4: Linked and non-linked premium of life insurers"

    # Statement 11: solvency ratio for the four quarters
    blk, _ = section(lines, r"SOLVENCY RATIO OF LIFE INSURERS", r"Statement 12")
    for cid, _, v in rows(blk, 4):
        put(cid, "solvency_q", v[-4:])
        put(cid, "solvency_ratio", v[-1])
    out["tables"]["solvency"] = "Statement 11: Solvency ratio of life insurers (Jun, Sep, Dec, Mar)"

    # Statement 16: AUM. The unit-linked page ends with Total ULIP (prev, curr) and Total all funds (prev, curr)
    s16 = [i for i, ln in enumerate(lines) if "UNIT LINKED FUND" in ln]
    if s16:
        blk, _ = section(lines, r"UNIT LINKED FUND", r"Industry Total|Statement 17", s16[0] - 1)
        for cid, _, v in rows(blk, 4):
            put(cid, "aum_ulip_prev_cr", v[-4])
            put(cid, "aum_ulip_cr", v[-3])
            put(cid, "aum_total_prev_cr", v[-2])
            put(cid, "aum_total_cr", v[-1])
    out["tables"]["aum"] = "Statement 16: Assets under management of life insurers (31 March)"

    # Annexure 7: products and riders filed in the year (File & Use, Use & File)
    blk, _ = section(lines, r"NUMBER OF PRODUCTS & RIDERS", r"Annexure 8")
    for cid, _, v in rows(blk, left_only=True):
        put(cid, "products_filed_fu", v[0])
        put(cid, "products_filed_uf", v[1])
        put(cid, "products_filed", v[0] + v[1])
    out["tables"]["products_filed"] = "Annexure 7: Number of products and riders filed during the year"

    dest = ROOT / "data" / "benchmark" / "sources" / f"irdai_annual_{fy}.json"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(out, indent=1))
    n = {k: sum(1 for c in co.values() if any(x.startswith(p) for x in c)) for k, p in
         [("premium", "total_premium"), ("split", "all_total"), ("solvency", "solvency"), ("aum", "aum_total"), ("filed", "products_filed")]}
    print(f"wrote {dest.relative_to(ROOT)}: {len(co)} insurers; coverage {n}")


if __name__ == "__main__":
    main()
