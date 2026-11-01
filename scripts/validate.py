#!/usr/bin/env python3
"""Validate a per-insurer product catalogue JSON against SPEC.md.

Usage: python3 scripts/validate.py <file.json> [<file2.json> ...]
Exit code 1 if any ERROR.
"""
import json
import re
import sys
from collections import Counter

COMPANY_IDS = {
    "lic", "hdfc", "axismax", "icici", "kotak", "absli", "tataaia", "sbi", "bajaj", "pnbmetlife",
    "indusindnippon", "aviva", "sahara", "shriram", "bharti", "generalicentral", "ageasfederal",
    "canarahsbc", "bandhan", "pramerica", "sud", "indiafirst", "edelweiss", "creditaccess", "acko",
    "godigit", "indiapost",
}
SEGMENTS = {"Individual", "Group", "Rider", "Micro"}
CATEGORIES = {
    "Individual": {"Term", "ULIP", "Savings - Par", "Savings - Non-Par", "Pension & Annuity", "Health & CI"},
    "Group": {"Group Term", "Credit Life", "Group Fund (Gratuity/Superannuation/Leave)", "Group Annuity",
              "Group Health & Accident", "Govt Scheme", "Group Other"},
    "Rider": {"Accidental Death/Disability", "Critical Illness", "Waiver of Premium", "Term Rider",
              "Health/Hospital", "Other Rider"},
    "Micro": {"Micro Insurance"},
}
PLAN_STRUCTURES = {"Pure Term", "Term with ROP", "Endowment", "Money Back", "Whole Life", "Guaranteed Income",
                   "Unit Linked", "Immediate Annuity", "Deferred Annuity", "Pension Accumulation",
                   "Fixed Benefit Health", "Group Scheme", "Rider", "Other"}
NEED_TAGS = {"Protection", "Savings", "Wealth", "Retirement", "Child", "Health", "Legacy"}
STATUS = {"Active", "Withdrawn"}
COMPLETENESS = {"full", "partial", "list-only"}
LINKAGE = {"Linked", "Non-Linked"}
PARTICIPATION = {"Par", "Non-Par"}
UIN_RE = re.compile(r"^\d{3}[A-Z]\d{3}V\d{2}$")
DATE_RE = re.compile(r"^\d{4}(-\d{2}(-\d{2})?)?$")

PRODUCT_KEYS = ["uin", "name", "segment", "category", "plan_structure", "sub_category", "linkage",
                "participation", "need_tags", "standard_product", "status", "launch_date", "withdrawn_date",
                "variants", "eligibility", "benefits", "category_details", "key_features", "riders_available",
                "online_purchase", "channels", "tax_benefits", "description", "urls", "sources",
                "completeness", "last_verified"]
ELIG_NUM = ["entry_age_min_years", "entry_age_max_years", "maturity_age_max_years", "policy_term_min_years",
            "policy_term_max_years", "min_annual_premium_inr", "min_single_premium_inr", "min_sum_assured_inr"]
ELIG_KEYS = ELIG_NUM + ["whole_life", "ppt_options", "premium_modes", "max_premium_text", "max_sum_assured_text",
                        "notes"]
BEN_KEYS = ["death", "maturity", "survival_income", "guaranteed", "return_of_premium", "loan",
            "partial_withdrawal", "other"]
CD_BLOCKS = ["term", "ulip", "savings", "annuity", "health"]


def is_num(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def validate(path):
    errs, warns = [], []
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:  # noqa: BLE001
        return [f"cannot parse JSON: {e}"], [], None

    for k in ["company_id", "company_name", "researched_on", "urls", "products", "notes"]:
        if k not in data:
            errs.append(f"missing top-level key '{k}'")
    if data.get("company_id") not in COMPANY_IDS:
        errs.append(f"company_id '{data.get('company_id')}' not in allowed list")
    urls = data.get("urls") or {}
    for k in ["website", "product_list_url", "withdrawn_list_url", "riders_url", "group_url", "newsroom_url"]:
        if k not in urls:
            errs.append(f"urls missing '{k}'")
    if not urls.get("product_list_url"):
        warns.append("urls.product_list_url empty — weekly scraper needs it")

    products = data.get("products") or []
    if not isinstance(products, list) or not products:
        errs.append("products must be a non-empty list")
        products = []

    seen = Counter()
    for i, p in enumerate(products):
        tag = f"[{i}] {p.get('name', '?')!r}"
        for k in PRODUCT_KEYS:
            if k not in p:
                errs.append(f"{tag}: missing key '{k}'")
        seg = p.get("segment")
        if seg not in SEGMENTS:
            errs.append(f"{tag}: bad segment {seg!r}")
        cat = p.get("category")
        status = p.get("status")
        if status not in STATUS:
            errs.append(f"{tag}: bad status {status!r}")
        if seg in CATEGORIES:
            if cat is None and status == "Withdrawn":
                warns.append(f"{tag}: withdrawn item without category")
            elif cat not in CATEGORIES[seg]:
                errs.append(f"{tag}: category {cat!r} not valid for segment {seg}")
        ps = p.get("plan_structure")
        if ps is not None and ps not in PLAN_STRUCTURES:
            errs.append(f"{tag}: bad plan_structure {ps!r}")
        if p.get("linkage") not in LINKAGE | {None}:
            errs.append(f"{tag}: bad linkage {p.get('linkage')!r}")
        if p.get("participation") not in PARTICIPATION | {None}:
            errs.append(f"{tag}: bad participation {p.get('participation')!r}")
        tags = p.get("need_tags") or []
        if not isinstance(tags, list) or any(t not in NEED_TAGS for t in tags):
            errs.append(f"{tag}: bad need_tags {tags!r}")
        if p.get("completeness") not in COMPLETENESS:
            errs.append(f"{tag}: bad completeness {p.get('completeness')!r}")
        uin = p.get("uin")
        if uin is None:
            if data.get("company_id") != "indiapost":
                warns.append(f"{tag}: uin is null")
        elif not isinstance(uin, str) or not UIN_RE.match(uin):
            warns.append(f"{tag}: uin {uin!r} not in standard format")
        if uin:
            seen[(uin, status)] += 1
        for dk in ["launch_date", "withdrawn_date", "last_verified"]:
            v = p.get(dk)
            if v is not None and (not isinstance(v, str) or not DATE_RE.match(v)):
                errs.append(f"{tag}: {dk} {v!r} not YYYY[-MM[-DD]]")
        if not p.get("sources"):
            warns.append(f"{tag}: no sources")

        el = p.get("eligibility")
        if not isinstance(el, dict):
            errs.append(f"{tag}: eligibility must be an object")
            el = {}
        for k in ELIG_KEYS:
            if k not in el:
                errs.append(f"{tag}: eligibility missing '{k}'")
        for k in ELIG_NUM:
            v = el.get(k)
            if v is not None and not is_num(v):
                errs.append(f"{tag}: eligibility.{k} must be number or null, got {v!r}")
        for k in ["entry_age_min_years", "entry_age_max_years", "maturity_age_max_years"]:
            v = el.get(k)
            if is_num(v) and not (0 <= v <= 110):
                warns.append(f"{tag}: eligibility.{k}={v} out of range")
        if is_num(el.get("entry_age_min_years")) and is_num(el.get("entry_age_max_years")) \
                and el["entry_age_min_years"] > el["entry_age_max_years"]:
            errs.append(f"{tag}: entry_age_min > entry_age_max")
        for k in ["ppt_options", "premium_modes"]:
            if k in el and not isinstance(el.get(k), list):
                errs.append(f"{tag}: eligibility.{k} must be a list")

        bn = p.get("benefits")
        if not isinstance(bn, dict):
            errs.append(f"{tag}: benefits must be an object")
            bn = {}
        for k in BEN_KEYS:
            if k not in bn:
                errs.append(f"{tag}: benefits missing '{k}'")

        cd = p.get("category_details")
        if not isinstance(cd, dict):
            errs.append(f"{tag}: category_details must be an object")
        else:
            for k in CD_BLOCKS:
                if k not in cd:
                    errs.append(f"{tag}: category_details missing '{k}' (use null)")
            if cd.get("ulip") and is_num(cd["ulip"].get("fmc_max_pct")) and cd["ulip"]["fmc_max_pct"] > 1.35:
                warns.append(f"{tag}: ULIP FMC {cd['ulip']['fmc_max_pct']} > 1.35% cap — check")

        for k in ["variants", "key_features", "riders_available", "channels", "sources"]:
            if k in p and not isinstance(p.get(k), list):
                errs.append(f"{tag}: {k} must be a list")
        if not isinstance(p.get("urls"), dict):
            errs.append(f"{tag}: urls must be an object")

        if p.get("completeness") == "full":
            missing = [k for k in ["entry_age_min_years", "entry_age_max_years"] if el.get(k) is None]
            if el.get("policy_term_min_years") is None and not el.get("whole_life") and \
                    p.get("category") != "Pension & Annuity":
                missing.append("policy_term")
            if not el.get("ppt_options"):
                missing.append("ppt_options")
            if el.get("min_annual_premium_inr") is None and el.get("min_single_premium_inr") is None \
                    and el.get("min_sum_assured_inr") is None:
                missing.append("min premium/SA")
            if not (bn.get("death") or bn.get("maturity") or bn.get("survival_income")):
                missing.append("benefits")
            if not p.get("key_features"):
                missing.append("key_features")
            if missing:
                warns.append(f"{tag}: marked full but missing {missing}")
        if status == "Active" and seg == "Individual" and p.get("completeness") == "list-only":
            warns.append(f"{tag}: active individual product is list-only")

    for (uin, status), n in seen.items():
        if n > 1:
            errs.append(f"duplicate UIN {uin} with status {status} ({n}x)")

    summary = Counter((p.get("segment"), p.get("status")) for p in products)
    comp = Counter(p.get("completeness") for p in products
                   if p.get("segment") == "Individual" and p.get("status") == "Active")
    return errs, warns, (summary, comp)


def main():
    bad = False
    for path in sys.argv[1:]:
        errs, warns, info = validate(path)
        print(f"== {path}")
        if info:
            summary, comp = info
            print("  counts:", ", ".join(f"{s}/{st}={n}" for (s, st), n in sorted(summary.items(), key=str)))
            print("  active individual completeness:", dict(comp))
        for e in errs[:80]:
            print("  ERROR", e)
        if len(errs) > 80:
            print(f"  ... {len(errs) - 80} more errors")
        for w in warns[:40]:
            print("  WARN ", w)
        if len(warns) > 40:
            print(f"  ... {len(warns) - 40} more warnings")
        print(f"  => {len(errs)} errors, {len(warns)} warnings")
        bad = bad or bool(errs)
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
