"""Map insurer names as printed by IRDAI, the Life Insurance Council and insurers themselves to company ids."""
import re

# Order matters: the first pattern that matches wins.
PATTERNS = [
    ("lic", r"life insurance corporation|\blic\b(?! *of)|lic of india"),
    ("sbi", r"\bsbi life"),
    ("hdfc", r"\bhdfc life|\bhdfc standard"),
    ("icici", r"\bicici (prudential )?life|icici pru"),
    ("axismax", r"axis max|\bmax life"),
    ("bajaj", r"\bbajaj (allianz )?life"),
    ("tataaia", r"tata aia"),
    ("kotak", r"kotak (mahindra )?life|kotak life"),
    ("absli", r"aditya birla sun life|\babsli\b|birla sun life"),
    ("pnbmetlife", r"pnb met ?life"),
    ("canarahsbc", r"canara hsbc"),
    ("indiafirst", r"india ?first life"),
    ("sud", r"star union dai|\bsud life"),
    ("ageasfederal", r"a[ge]{2}as federal|ageas federal|aegas federal|idbi federal"),
    ("indusindnippon", r"(indusind|reliance) nippon"),
    ("bharti", r"bharti[ -]?(axa )?life|bharti axa"),
    ("generalicentral", r"generali central|future generali india life|future generali life"),
    ("edelweiss", r"edelweiss( tokio)? life"),
    ("pramerica", r"pramerica|dhfl pramerica"),
    ("aviva", r"aviva life"),
    ("shriram", r"shriram life"),
    ("bandhan", r"bandhan life|aegon life"),
    ("creditaccess", r"credit ?access life"),
    ("godigit", r"go digit life|\bdigit life"),
    ("acko", r"acko life"),
    ("sahara", r"sahara india life|sahara life"),
    ("indiapost", r"postal life insurance|india post"),
]
_COMPILED = [(cid, re.compile(p, re.I)) for cid, p in PATTERNS]


def insurer_id(name):
    """Return the company id for an insurer name, or None (totals, headings, non-life insurers)."""
    if not name:
        return None
    s = " ".join(str(name).replace("\n", " ").split())
    if re.search(r"general insurance|health insurance|\btotal\b|industry", s, re.I):
        return None
    for cid, rx in _COMPILED:
        if rx.search(s):
            return cid
    return None


def num(tok):
    """Parse a number as printed in Indian statistical tables: 1,43,255.23 · (12.5) · - · $ · NA."""
    if tok is None:
        return None
    if isinstance(tok, (int, float)):
        return float(tok)
    t = str(tok).strip().replace(",", "")
    if t in ("", "-", "--", "$", "NA", "N.A.", "na", "*", "#"):
        return None
    neg = t.startswith("(") and t.endswith(")")
    t = t.strip("()%")
    try:
        v = float(t)
    except ValueError:
        return None
    return -v if neg else v
