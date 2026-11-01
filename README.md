# Insurance_Products

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
Claude artifact built from the same source. Views: market overview, insurer profiles with metrics
against the industry median, product catalogue with category-specific columns, product detail with
UIN decoding, side-by-side compare (products and insurers), change log.

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
