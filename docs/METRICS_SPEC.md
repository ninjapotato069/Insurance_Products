# Company Profiles & Metrics — Research Spec (v1, 2026-10-28)

Write `/home/claude/research/out/_metrics.json` covering all 27 company IDs:
lic, hdfc, axismax, icici, kotak, absli, tataaia, sbi, bajaj, pnbmetlife, indusindnippon, aviva, sahara,
shriram, bharti, generalicentral, ageasfederal, canarahsbc, bandhan, pramerica, sud, indiafirst, edelweiss,
creditaccess, acko, godigit, indiapost (India Post PLI & RPLI — government, outside IRDAI).

Rules: shell has no internet (WebSearch/WebFetch only). Never invent numbers; unknown → omit the metric.
Every metric carries its own period and source URL. Prefer one consistent cross-insurer source per metric
(e.g. a single IRDAI / Life Insurance Council table) over 26 separate pages; if you mix periods, say so in `note`.
Save progress to the file as you go. Budget ~150 tool calls.

Priority: (1) profile fields → (2) NBP & market share FY2025-26 → (3) claim settlement ratios & grievances →
(4) solvency & AUM → (5) persistency → (6) rest.

```json
{
  "researched_on": "2026-10-28",
  "industry": {
    "life_insurers_count": 26,
    "metrics": { "<metric_key>": {"value": 0, "period": "FY2025-26", "source": "url", "note": null} },
    "notes": "context worth showing on a market overview (e.g. LIC vs private share trend)"
  },
  "companies": {
    "<company_id>": {
      "legal_name": "Bajaj Life Insurance Limited",
      "brand_name": "Bajaj Life",
      "former_names": ["Bajaj Allianz Life Insurance Company Ltd"],
      "irdai_reg_no": "116",
      "sector": "Public | Private | Government (non-IRDAI)",
      "listed": "Listed (NSE: XXX) | Parent listed (Name) | Unlisted",
      "ownership": "short text with key stakes",
      "foreign_partner": "Name (country), stake % — or null",
      "bank_linkage": "promoter bank / anchor banca partner — or null",
      "established_year": 2001,
      "hq_city": "Pune",
      "md_ceo": "Name",
      "website": "https://...",
      "status_note": "e.g. 'Under administration, no new business' or null",
      "metrics": {
        "<metric_key>": {"value": 12.3, "period": "FY2025-26", "source": "https://...", "note": null}
      }
    }
  }
}
```

Metric keys (use exactly; values are plain numbers):
- `nbp_cr` — new business premium (first-year incl. single; individual + group), ₹ crore, FY2025-26
- `nbp_market_share_pct` — % of industry NBP, FY2025-26
- `nbp_growth_pct` — YoY growth in NBP FY2025-26 vs FY2024-25
- `individual_nbp_cr` — individual new business premium, ₹ crore
- `new_individual_policies` — count of individual policies issued
- `gross_premium_cr` — total/gross written premium, ₹ crore
- `aum_cr` — assets under management, ₹ crore (latest)
- `solvency_ratio` — as a ratio (2.05 = 205%), latest quarter
- `csr_count_pct` — individual death claims settled, % by number
- `csr_amount_pct` — individual death claims settled, % by amount
- `claims_repudiated_pct` — individual death claims repudiated/rejected, % by number
- `grievances_per_10k` — grievances per 10,000 policies (IRDAI definition)
- `grievances_total` — grievances reported in the year
- `ombudsman_complaints` — complaints received by Insurance Ombudsman against the insurer
- `persistency_13m_pct`, `persistency_61m_pct` — by premium, individual, latest FY
- `agents_count` — individual agents; `branches_count` — offices/branches
- `pat_cr` — profit after tax, ₹ crore
- `vnb_margin_pct` — value of new business margin (listed / disclosing insurers only)
- `ulip_share_pct`, `par_share_pct`, `nonpar_savings_share_pct`, `protection_share_pct`, `annuity_share_pct`
  — product mix of individual new business (APE or NBP; say which in `note`)

For indiapost: capture whatever exists (policies in force, sum assured, premium income, current bonus rates
per scheme) using the same structure with sensible `note`s.

Final message (≤150 words): coverage table — for each metric key, how many companies filled + period used;
biggest gaps.
