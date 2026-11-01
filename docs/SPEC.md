# Indian Life Insurance Product Catalogue — Research Spec (v1, 2026-10-28)

## Your job
Research ALL products of the insurer(s) assigned to you and write ONE JSON file per insurer to
`/home/claude/research/out/<company_id>.json`, following the schema below exactly. Then run
`python3 /home/claude/research/validate.py /home/claude/research/out/<company_id>.json`
and fix every ERROR (warnings: fix where reasonable).

Coverage — all four segments:
1. **Individual products currently on sale** — FULL specs (this is the core of the dashboard).
2. **Riders** — name, UIN, category, one-line description; eligibility basics if quickly available.
3. **Group products** (incl. credit life, gratuity/superannuation, group annuity, PMJJBY) — name, UIN, category, one-line description.
4. **Withdrawn / discontinued products** — list only (name, UIN, withdrawal date if shown, best-guess segment/category).
Also include IRDAI **micro-insurance** products if the insurer has any (segment "Micro").

## Tools & constraints
- The shell has NO internet access. Use WebSearch and WebFetch only. Do not retry blocked URLs via curl.
- WebFetch returns a small model's answer to your prompt, not raw HTML. Ask for exact values in compact
  pipe-separated rows. Long lists get truncated — ask in chunks (per category, or "rows 1–40", "rows 41–80")
  and reconcile counts against what the page says.
- Brochure PDFs usually work in WebFetch — use them for specs (eligibility tables are usually on page 1–3).
- If an official page is blocked, try another official page (product page, brochure, sales literature,
  policy wording, public disclosures) before aggregators (Policybazaar, InsuranceDekho, BankBazaar, Ditto,
  Coverfox). Aggregator data is acceptable but must be listed in `sources`.
- NEVER invent values. Unknown → null. Never guess a UIN.
- Write `description`, `key_features`, variant summaries in your own words (no copied sentences).
- Save progress to the output file after every ~10 products so work survives interruptions.
- Budget: aim to finish within ~150 tool calls. Priority order:
  (a) full inventory of all segments (list-only rows are fine at first) →
  (b) full specs for ACTIVE INDIVIDUAL products →
  (c) light details for riders & group.
  If you run short, leave specs `partial` and say so in `notes`. Never pad with guesses.

## Where to look (typical)
- Insurer site: "All products", "Product list", "List of products with UIN", "Download centre / brochures",
  "Public disclosures", "Withdrawn products / Discontinued plans / Closed products", "Riders", "Group insurance".
- WebSearch patterns: `<insurer> list of products UIN`, `<insurer> withdrawn products list`,
  `site:<domain> brochure UIN`, `<product name> brochure pdf`, `<insurer> new plan launch 2026`.
- Version note: a product's UIN = <3-digit IRDAI reg no><letter><3-digit product no>V<2-digit version>
  (e.g. 116N170V04). The same product number with a newer version is the same product revised.

## Company IDs (use exactly)
lic, hdfc, axismax, icici, kotak, absli, tataaia, sbi, bajaj, pnbmetlife, indusindnippon, aviva, sahara,
shriram, bharti, generalicentral, ageasfederal, canarahsbc, bandhan, pramerica, sud, indiafirst, edelweiss,
creditaccess, acko, godigit, indiapost

## File schema
```json
{
  "company_id": "<as assigned>",
  "company_name": "<current name, e.g. 'Bharti Life Insurance'>",
  "researched_on": "2026-10-28",
  "urls": {
    "website": "https://...",
    "product_list_url": "<page or PDF listing current products WITH UINs; the weekly scraper re-reads it — prefer static HTML or PDF>",
    "withdrawn_list_url": "...or null",
    "riders_url": "...or null",
    "group_url": "...or null",
    "newsroom_url": "<press releases page> or null"
  },
  "products": [ <product>, ... ],
  "notes": "gaps, conflicts, anything the weekly refresh should know"
}
```

`<product>` — include EVERY key; use null / [] where unknown:
```json
{
  "uin": "101N145V08",
  "name": "Official product name",
  "segment": "Individual | Group | Rider | Micro",
  "category": "<taxonomy below; must match segment>",
  "plan_structure": "<list below> or null",
  "sub_category": "short free text e.g. 'Term with return of premium' or null",
  "linkage": "Linked | Non-Linked | null",
  "participation": "Par | Non-Par | null",
  "need_tags": ["Protection", "Savings", "Wealth", "Retirement", "Child", "Health", "Legacy"],
  "standard_product": "Saral Jeevan Bima | Saral Pension | Bima Jyoti | ... or null (IRDAI standard products only)",
  "status": "Active | Withdrawn",
  "launch_date": "YYYY-MM-DD | YYYY-MM | YYYY | null",
  "withdrawn_date": "same format or null",
  "variants": [{"name": "Life Option", "summary": "one line"}],
  "eligibility": {
    "entry_age_min_years": 18,
    "entry_age_max_years": 65,
    "maturity_age_max_years": 85,
    "policy_term_min_years": 5,
    "policy_term_max_years": 40,
    "whole_life": false,
    "ppt_options": ["Single", "Limited 5", "Limited 10", "Regular"],
    "premium_modes": ["Annual", "Half-yearly", "Quarterly", "Monthly", "Single"],
    "min_annual_premium_inr": 5000,
    "min_single_premium_inr": null,
    "max_premium_text": "No limit, subject to underwriting",
    "min_sum_assured_inr": 2500000,
    "max_sum_assured_text": "No limit",
    "notes": "variant-specific ranges etc. or null"
  },
  "benefits": {
    "death": "1-2 lines or null",
    "maturity": "1-2 lines or null",
    "survival_income": "1-2 lines or null",
    "guaranteed": true,
    "return_of_premium": false,
    "loan": true,
    "partial_withdrawal": false,
    "other": "or null"
  },
  "category_details": {
    "term": {"rop_option": null, "whole_life_cover_option": null, "ci_or_accelerated_benefit": null,
             "payout_options": "Lump sum / Monthly income / Lump sum + income or null",
             "women_or_nonsmoker_discount": null, "increasing_cover_option": null},
    "ulip": {"funds_count": null, "fmc_max_pct": null, "loyalty_additions": null,
             "return_of_mortality_charges": null, "free_switches_per_year": null,
             "premium_allocation_charge": null, "policy_admin_charge": null},
    "savings": {"payout_type": "Lump sum | Income | Lump sum + Income | null", "income_duration": null,
                "bonus_type": "Reversionary | Cash bonus | Reversionary + Cash | None | null",
                "deferment_option": null, "illustrative_return": "as published, e.g. 'IRR up to 6.1%', or null"},
    "annuity": {"annuity_options_count": null, "immediate_or_deferred": "Immediate | Deferred | Both | null",
                "joint_life": null, "return_of_purchase_price": null, "min_purchase_price_inr": null,
                "max_deferment_years": null},
    "health": {"conditions_covered": null, "benefit_type": null, "waiting_period_days": null,
               "survival_period_days": null}
  },
  "key_features": ["3-6 short bullets, own words"],
  "riders_available": ["rider names"],
  "online_purchase": true,
  "channels": ["Agency", "Bancassurance", "Direct/Online", "Broker", "POSP", "Corporate Agent"],
  "tax_benefits": "short text or null",
  "description": "one sentence: what it is and who it is for",
  "urls": {"product_page": "... or null", "brochure": "... or null"},
  "sources": ["url", "..."],
  "completeness": "full | partial | list-only",
  "last_verified": "2026-10-28"
}
```
Optional extra key: `"alt_code"` — another official identifier customers use (e.g. LIC "Plan 914",
India Post scheme code); omit or null otherwise.

Field rules:
- Do not edit SPEC.md or validate.py, and do not touch other insurers' output files.
- Numbers are plain numbers in rupees/years (2500000, not "25 lakh"). Ages in days/months → decimal years
  (30 days = 0.08, 90 days = 0.25). Whole-life cover: `whole_life: true`, `maturity_age_max_years` = 99/100 as stated.
- `category_details`: fill only the block(s) that apply; set the others to null.
- `need_tags`: 1–3 tags from the list.
- ULIPs → linkage "Linked", participation "Non-Par".
- completeness: **full** = entry ages + policy term + PPT + (min premium or min SA) + death/maturity benefit +
  key_features filled. **partial** = some specs. **list-only** = name/UIN/category only (fine for withdrawn,
  riders/group as last resort).

## Taxonomy
**Individual** category: `Term` | `ULIP` | `Savings - Par` | `Savings - Non-Par` | `Pension & Annuity` | `Health & CI`
- Child plans: categorise by construct (ULIP / Savings) and add need tag "Child".
- Pension ULIPs and pension par/non-par plans, immediate & deferred annuities → `Pension & Annuity`
  (linkage/participation distinguish them).
- Saral Jeevan Bima → `Term`; Saral Pension → `Pension & Annuity`; set `standard_product`.
- Whole-life savings plans → Savings with plan_structure `Whole Life`.
- Non-linked variable plans → `Savings - Non-Par`, sub_category "Variable".

**Group** category: `Group Term` | `Credit Life` | `Group Fund (Gratuity/Superannuation/Leave)` | `Group Annuity` |
`Group Health & Accident` | `Govt Scheme` | `Group Other`  (PMJJBY → `Govt Scheme`)

**Rider** category: `Accidental Death/Disability` | `Critical Illness` | `Waiver of Premium` | `Term Rider` |
`Health/Hospital` | `Other Rider`

**Micro** category: `Micro Insurance`

**plan_structure**: `Pure Term` | `Term with ROP` | `Endowment` | `Money Back` | `Whole Life` | `Guaranteed Income` |
`Unit Linked` | `Immediate Annuity` | `Deferred Annuity` | `Pension Accumulation` | `Fixed Benefit Health` |
`Group Scheme` | `Rider` | `Other`

## Final report (your last message, ≤120 words, no other prose)
Per company_id: counts by segment × status; active Individual products full/partial/list-only;
product_list_url; top 2–3 gaps.
