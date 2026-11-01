# Customer Reviews, App Ratings & Digital Servicing — Research Spec (v1, 2026-10-28)

Write `/home/claude/research/out/_reviews.json` covering all 27 company IDs:
lic, hdfc, axismax, icici, kotak, absli, tataaia, sbi, bajaj, pnbmetlife, indusindnippon, aviva, sahara,
shriram, bharti, generalicentral, ageasfederal, canarahsbc, bandhan, pramerica, sud, indiafirst, edelweiss,
creditaccess, acko, godigit, indiapost (India Post PLI & RPLI — includes the Postinfo / IPPB apps if PLI
servicing lives there).

Rules: shell has no internet (WebSearch/WebFetch only). Never invent ratings or counts; unknown → null.
Themes in your own words (no quotes). Record the date you observed each rating. Save progress as you go.
Budget ~150 tool calls.

What to capture per insurer:
1. **Official customer-servicing app** — Android package id (exact, e.g. com.hdfclife.mobileapp — the weekly
   scraper uses it), app name, Play Store rating, ratings count, installs band, last-updated date; iOS App Store
   numeric app id (exact), rating, ratings count. Try play.google.com / apps.apple.com pages via WebFetch; if
   blocked use AppBrain, AppFollow, 42matters, Sensor Tower or similar public listings and cite them.
   If an insurer has several apps, pick the main policy-servicing app and list others in `notes`.
2. **Third-party customer ratings** — any of: MouthShut, Trustpilot, Policybazaar insurer reviews,
   InsuranceDekho, Google Business (head office), Ditto/joinditto insurer review. Record rating, scale,
   review count, URL. Two sources per insurer is enough.
3. **Review themes** — 2–4 recurring positives and 2–4 recurring negatives across app and site reviews
   (e.g. "claim settlement delays", "mis-selling complaints", "smooth premium payment in app").
4. **Digital servicing** — WhatsApp servicing (and number), customer app, website chatbot, self-service portal.

```json
{
  "researched_on": "2026-10-28",
  "companies": {
    "<company_id>": {
      "android": {"package": "com.x", "app_name": "...", "rating": 4.3, "ratings_count": 12345,
                  "installs": "1M+", "last_updated": "2026-10-01", "observed_on": "2026-10-28", "source": "url"},
      "ios": {"app_id": "123456789", "app_name": "...", "rating": 4.6, "ratings_count": 5432,
              "observed_on": "2026-10-28", "source": "url"},
      "third_party": [{"site": "MouthShut", "rating": 2.3, "scale": 5, "reviews_count": 812, "url": "...",
                       "observed_on": "2026-10-28"}],
      "positives": ["..."],
      "negatives": ["..."],
      "review_summary": "two sentences, own words",
      "digital_servicing": {"whatsapp": true, "whatsapp_number": "+91 ...", "customer_app": true,
                            "web_chatbot": true, "customer_portal": true, "notes": null},
      "notes": null,
      "sources": ["url"]
    }
  }
}
```
Use null for a missing `android` / `ios` block.

Final message (≤120 words): how many insurers have Android/iOS/third-party ratings filled; any insurer
without an app; biggest gaps.
