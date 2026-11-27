# Insurance_Products — Life Insurance Benchmark (India)

**App:** https://ninjapotato069.github.io/Insurance_Products/ (installable on Android and iPhone: open it, then
*Add to Home screen* / *Install app*). Needs GitHub Pages on: Settings → Pages → Deploy from a branch → `main` / root.

## Benchmark
- `data/benchmark/framework.json` — 20 departments in six families (sales & distribution, operations, technology &
  change, product, finance & investments, leadership) plus strategy, with each KPI's definition, direction, source
  and refresh. Core KPIs are percentile-scored within a peer group; department and overall scores follow.
- Sources: IRDAI monthly new business statement (auto), IRDAI Handbook on Indian Insurance Statistics and Annual
  Report (parsed by `scripts/parse_irdai_handbook.py`, `scripts/parse_irdai_annual.py`), app stores, homepage audit,
  Google News headlines, NSE prices, desk research (`data/benchmark/research.json`, `data/benchmark/strategy.json`).
- Build: `python3 scripts/build_benchmark.py` → `data/benchmark.json` (loaded by the app).
- Daily GitHub Action `daily-refresh.yml` (06:17 IST) refreshes the automatic feeds and rebuilds; `fetch-sources.yml`
  downloads source files to the `raw-sources` branch for research sessions without web access.

Product and company intelligence for every Indian life insurer: LIC, all private insurers licensed by
IRDAI (including the 2024 entrants and Sahara India Life, under administration), and India Post's
Postal Life Insurance / Rural PLI.

- **Products**: individual plans on sale with eligibility, premium, benefit and category-specific specs;
  riders; group products; withdrawn products on record.
- **Companies**: new business premium and share, growth, claims settled, grievances, ombudsman
  complaints, solvency, persistency, AUM — each figure with its period and source.
- **Customers**: Play Store / App Store ratings, review-site ratings, recurring praise and complaints,
  digital servicing channels.

## Dashboard
`index.html` (GitHub Pages, if enabled: Settings → Pages → Deploy from branch `main`, folder `/`) and a
Claude artifact built from the same source (`src/dashboard.html`; `scripts/make_site.py` wraps it,
`scripts/make_icons.py` draws the app icons).

- **Home**: pick *My company* in the header (defaults to Bajaj Life Insurance). Shows league position, index,
  level and XP (index × 10; Rookie <35, Challenger 35, Contender 45, Pro 55, Elite 65, Legend 75), a scoreboard of
  headline KPIs with ranks, a grade per department (S 80+, A 60-80, B 40-60, C 20-40, D <20) with medals for
  top-three finishes, missions (reach the top-quartile mark on one ratio KPI and see the index gain and places
  climbed, other insurers held constant), rivals, 18 badges and a feed of competitor moves.
- **League**: podium, standings with movement since the last visit, level, medals and form (monthly change in
  year-to-date share of new business), the department heatmap and department champions.
- **Duel**: any two insurers department by department, with the KPIs where each leads.
- **Search** (`/` or Ctrl/Cmd-K): insurers, departments, KPIs, products and views from one box. Star insurers to keep
  them on the watchlist. My company, watchlist and movement history live in the browser (localStorage).
- Also: market overview, departments, state network, global peers, strategy, news, insurer profiles, ownership,
  product catalogue and detail with UIN decoding, side-by-side compare, change log.

## Weekly refresh
| When (IST) | What | Where |
|---|---|---|
| Mon 08:00 | Re-read each insurer's official product list for new / missing UINs; refresh app ratings; rebuild | GitHub Action `weekly-refresh.yml` |
| Mon ~10:30 | Research every flagged item, fill missing specs, rotate deep checks, monthly metric refresh; push and republish | Claude scheduled task, runbook `docs/WEEKLY_TASK.md` |

Run the Action by hand from the Actions tab (`workflow_dispatch`).

## Layout
```
data/companies.json        insurer master (names, former names, app ids)
data/products/<id>.json    one catalogue per insurer (schema: docs/SPEC.md)
data/metrics.json          company and industry metrics (docs/METRICS_SPEC.md)
data/reviews.json          ratings, review themes, digital servicing (docs/REVIEWS_SPEC.md)
data/ownership.json        FDI cap timeline, shareholders, foreign partners, ownership events (Ownership tab)
data/changelog.json        launches, withdrawals, flags, metric updates
data/refresh/              state of the automated checks
data/history/ratings.csv   app-rating history
data/dashboard.json        built file the dashboard loads (do not edit)
exports/*.csv              flat tables for Excel / Power BI (do not edit)
scripts/                   build, weekly check, helpers
src/dashboard.html         dashboard source
```

## Local use
```
python3 scripts/build.py && python3 scripts/make_site.py
python3 -m http.server 8000      # open http://localhost:8000
python3 scripts/add_products.py <company_id> batch.json   # add or update products
python3 scripts/validate.py data/products/*.json
python3 scripts/backlog.py 25                            # products still missing specs
```

Compiled from public information (insurer product pages and brochures, IRDAI, Life Insurance Council,
Insurance Ombudsman, app stores). Product terms change: confirm against the insurer's current brochure
and policy wording before relying on any figure.
