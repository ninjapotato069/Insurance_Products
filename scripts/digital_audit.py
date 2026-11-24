#!/usr/bin/env python3
"""Digital storefront audit: what each insurer's homepage offers a visitor, read from its HTML.

    python3 scripts/digital_audit.py                  # fetch every homepage, update data/benchmark/auto/digital.json
    python3 scripts/digital_audit.py --html-dir DIR   # audit saved pages named <company_id>.html (testing)

Signals are found in the page's own HTML (links, scripts, text). Pages that render everything with JavaScript, or
that block automated visits, show fewer signals: those are recorded as 'not readable', never as 'absent'.
"""
import argparse
import datetime as dt
import json
import re
import sys
import time
from pathlib import Path
from urllib.parse import urljoin, urlparse

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "benchmark" / "auto" / "digital.json"
UA = "Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Mobile Safari/537.36"

CHATBOTS = r"\b(?:haptik|yellow\.ai|yellowmessenger|gupshup|verloop|freshchat|intercom|kore\.ai|botpenguin|engati|" \
           r"senseforth|avaamo|chat-?bot|virtual assistant|live chat|chat with us)\b"
SIGNALS = [
    ("whatsapp", "WhatsApp service", lambda h, t, L: bool(re.search(r"wa\.me/|api\.whatsapp\.com|whatsapp\.com/send", h, re.I))
     or bool(re.search(r"whatsapp", t, re.I) and re.search(r"\b[6-9]\d{9}\b|\+91", t))),
    ("chatbot", "Chat assistant", lambda h, t, L: bool(re.search(CHATBOTS, h, re.I))),
    ("android_app", "Android app link", lambda h, t, L: "play.google.com/store/apps" in h),
    ("ios_app", "iOS app link", lambda h, t, L: "apps.apple.com" in h or "itunes.apple.com" in h),
    ("pay_premium", "Pay or renew premium online", lambda h, t, L: any(re.search(r"pay (?:your )?premium|renew|premium payment|quick ?pay|pay now|pay online", x, re.I) for x in L)),
    ("claims_online", "Claim intimation or tracking online", lambda h, t, L: any(re.search(r"claim", x, re.I) and re.search(r"intimat|register|track|status|file|raise|submit", x, re.I) for x in L)),
    ("customer_login", "Customer login / self-service portal", lambda h, t, L: any(re.search(r"log ?in|sign ?in|my account|customer portal|policy owner|e-?services|self[- ]service", x, re.I) for x in L)),
    ("buy_online", "Buy online / instant quote", lambda h, t, L: any(re.search(r"buy (?:now|online)|get (?:a )?quote|calculate premium|check premium|premium calculator|get started", x, re.I) for x in L)),
    ("regional_language", "Regional-language site", lambda h, t, L: bool(re.search(r'hreflang="(?:hi|mr|ta|te|bn|kn|ml|gu)', h, re.I)) or bool(re.search(r"हिंदी|हिन्दी|मराठी|தமிழ்|తెలుగు|ಕನ್ನಡ|বাংলা", t))),
    ("video_kyc", "Video KYC / e-KYC / DigiLocker", lambda h, t, L: bool(re.search(r"video ?kyc|v-?kyc|e-?kyc|digilocker|ckyc", t, re.I))),
    ("upi_autopay", "UPI / auto-pay mandate", lambda h, t, L: bool(re.search(r"\bupi\b|auto-?pay|e-?mandate|\bnach\b|standing instruction", t, re.I))),
    ("ai_tools", "AI / digital advisor tools", lambda h, t, L: bool(re.search(r"\bai\b|artificial intelligence|gen ?ai|robo|digital advisor|need analysis|financial planner", t, re.I))),
]
SOCIAL = {"facebook": "facebook.com", "instagram": "instagram.com", "linkedin": "linkedin.com", "youtube": "youtube.com",
          "x": r"(?:twitter|x)\.com/"}


def audit_html(html, url):
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, "html.parser")
    for s in soup(["style", "noscript"]):
        s.decompose()
    text = " ".join(soup.get_text(" ", strip=True).split())
    links = [" ".join(a.get_text(" ", strip=True).split()) + " " + (a.get("title") or "") + " " + a["href"]
             for a in soup.find_all("a", href=True)]
    h = html if isinstance(html, str) else html.decode("utf-8", "ignore")
    found = {k: bool(fn(h, text, links)) for k, _, fn in SIGNALS}
    social = sorted(k for k, pat in SOCIAL.items() if re.search(pat, h, re.I))
    readable = len(text) > 1500 and len(links) > 25
    return {"url": url, "readable": readable, "text_chars": len(text), "links": len(links),
            "signals": found, "score": sum(found.values()), "max_score": len(SIGNALS),
            "social": social, "https": url.startswith("https://"), "html_kb": round(len(h.encode()) / 1024)}


def websites():
    m = json.loads((ROOT / "data" / "metrics.json").read_text())["companies"]
    return {cid: c.get("website") for cid, c in m.items() if c.get("website")}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--html-dir")
    a = ap.parse_args()
    state = json.loads(OUT.read_text()) if OUT.exists() else {"companies": {}}
    today = dt.date.today().isoformat()
    sites = websites()
    if a.html_dir:
        for p in Path(a.html_dir).glob("*.html"):
            cid = p.stem
            res = audit_html(p.read_text(encoding="utf-8", errors="ignore"), sites.get(cid, ""))
            res.update({"checked_on": today, "status": 200})
            state["companies"][cid] = res
    else:
        import requests
        s = requests.Session()
        s.headers.update({"User-Agent": UA, "Accept-Language": "en-IN,en;q=0.9"})
        for cid, url in sorted(sites.items()):
            prev = state["companies"].get(cid, {})
            try:
                t0 = time.time()
                r = s.get(url, timeout=45)
                secs = round(time.time() - t0, 2)
                if r.status_code == 200 and len(r.text) > 2000:
                    res = audit_html(r.text, r.url)
                    res.update({"status": 200, "load_seconds": secs, "checked_on": today})
                else:
                    res = {**prev, "status": r.status_code, "readable": False, "checked_on": today,
                           "note": f"page returned HTTP {r.status_code}; earlier signals kept" if prev.get("signals") else f"page returned HTTP {r.status_code}"}
            except Exception as e:
                res = {**prev, "status": None, "readable": False, "checked_on": today, "note": f"not reachable: {type(e).__name__}"}
            state["companies"][cid] = res
            time.sleep(1)
    state["updated"] = today
    state["signals"] = [{"key": k, "label": lab} for k, lab, _ in SIGNALS]
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(state, indent=1, ensure_ascii=False))
    ok = sum(1 for c in state["companies"].values() if c.get("readable"))
    print(f"digital audit: {ok}/{len(state['companies'])} homepages readable")


if __name__ == "__main__":
    sys.exit(main())
