# Weekly research run (Claude scheduled task)

Runs every Monday after the GitHub Action (`.github/workflows/weekly-refresh.yml`, 08:00 IST) has
re-read the insurers' product lists and refreshed app ratings. The Action flags; this run researches
and fixes. Keep the run lean — about 120 tool calls, 4–6 WebFetch calls per message, search only when a
fetched page cannot give the answer. Push before the budget runs out; unfinished items stay open for
next week.

Dashboard artifact: https://claude.ai/artifact/HpLvASohtx8BPfGpCPiqjh
Repository: https://github.com/ninjapotato069/Insurance_Products (default branch `main`)

## 0. Set up
- Attach the repo with `add_repo` (owner `ninjapotato069`, repo `Insurance_Products`, access `push`),
  clone it to `/home/claude/insurance_products`, `git pull`.
- Read `docs/SPEC.md` (schema, taxonomy, the WebFetch extraction prompt) once.

## 1. Resolve flagged items — up to 15, oldest first
`python3 scripts/changelog.py list` shows open `needs_review` items; `data/refresh/last_run.json`
shows which product pages failed or had no UINs.
- `new_uin` / `new_version`: find the product (fetch the `source` page; search the UIN if needed), save
  it with full specs through `scripts/add_products.py <company_id> <batch.json>`, then
  `python3 scripts/changelog.py resolve --id <id> --type launch|new_version --title "<name> launched" --details "..."`.
  An older version of the same product number is marked "replaced" automatically by the build.
- `missing_uin`: confirm on the insurer's site (withdrawn-products list, product page, newsroom).
  Confirmed → save `{"uin": ..., "status": "Withdrawn", "withdrawn_date": ...}` and resolve as
  `withdrawal`. Moved or renamed → fix the URL or name and resolve with `--dismiss`.
- Not a product (e.g. a rider of another insurer quoted on the page) → resolve with `--dismiss`.

## 1b. Coverage gaps — up to 10
`data/refresh/last_run.json` → `product_pages.unmatched` lists UINs found on an official product list the
first time the Action read that page, but missing from the catalogue. Research and add them as in step 1
(log nothing unless the product launched in the last 60 days, then log it as `launch`).
Tata AIA's official list shows active and withdrawn products together, so most of its unmatched UINs are
withdrawn plans: add them as `"status": "Withdrawn"` list-only rows in batches of 50 from that one page.

## 2. Insurers the Action could not read
For each insurer in `last_run.json` → `product_pages.failed` / `no_uin`: one search for launches or
withdrawals in the last 14 days ("<insurer> launches plan"). Add anything found as in step 1 and log it
with `python3 scripts/changelog.py add ...`.

## 3. Spec backlog — up to 20 products
First give a category to any active product the validator reports as "no category yet". Then
`python3 scripts/backlog.py 20` lists active individual products without full specs, largest insurers
first. Fetch each brochure/product page with the extraction prompt from `docs/SPEC.md`, save through
`scripts/add_products.py`.

## 4. Rotating deep check — 2 insurers
Take positions `(ISO week number) mod 27` and `(ISO week number + 13) mod 27` in `data/companies.json`.
Re-read their full product lists (all segments, withdrawn list). Add missing products, mark confirmed
withdrawals, correct names/URLs, and update `urls.product_list_url` if the page moved.

## 5. Metrics — first run of each month only
Check for newer periods and update `data/metrics.json` (`{"value", "period", "source", "note"}` per
metric, keys in `docs/METRICS_SPEC.md`): monthly new business premium and share (Life Insurance
Council / IRDAI), quarterly public disclosures (solvency, persistency, AUM), IRDAI annual report
(claims settled, grievances), Insurance Ombudsman annual report. Log each update as `metric_update`.

Also refresh `data/ownership.json` (schema in its first lines; Ownership tab): FPI % from the latest quarterly
shareholding pattern of listed insurers, and any stake sale, partner entry or exit, listing or rename in the
news, each as an event with date, type and source.

## 6. Reviews — 3 insurers per week (rotation as in step 4, offsets 5, 14, 23)
Refresh `positives`, `negatives`, `review_summary`, `third_party` in `data/reviews.json`
(`docs/REVIEWS_SPEC.md`). App ratings are already refreshed by the Action.

## 6b. Verify auto-matched apps — up to 4 per week
`data/companies.json` → `apps_auto` lists stores whose app id was matched by store search, not checked.
Confirm on the insurer's website ("download our app" links) that it is the customer-servicing app.
Correct → remove that store from `apps_auto`. Wrong (agent/sales/wellness app) → put the right id in
`apps`, drop the store from `apps_auto`, and delete that store's block in `data/reviews.json` so the
Action fetches the right rating next Monday.

## 7. Build, publish, report
```
python3 scripts/validate.py data/products/*.json     # fix every ERROR
python3 scripts/build.py && python3 scripts/make_site.py
git add -A && git commit -m "Weekly research update YYYY-MM-DD" && git push
```
Republish the dashboard: `Artifact` action `read` on https://claude.ai/artifact/HpLvASohtx8BPfGpCPiqjh, then `publish` with
`url` = https://claude.ai/artifact/HpLvASohtx8BPfGpCPiqjh, `file_path` = `src/dashboard.html`,
`files` = `{"data/dashboard.json": "data/dashboard.json"}`.
Finish with at most five lines: launches, withdrawals, specs filled, metrics updated, open items.
