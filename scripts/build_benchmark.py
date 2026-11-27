#!/usr/bin/env python3
"""Build data/benchmark.json: every KPI in data/benchmark/framework.json for every insurer, with period and source,
percentile scores, pillar scores, an overall index, peer groups, trend series, strategy profiles and the daily feeds.

Inputs (all optional except the framework):
  data/benchmark/sources/irdai_handbook_<FY>.json   IRDAI Handbook tables (scripts/parse_irdai_handbook.py)
  data/benchmark/sources/irdai_annual_<FY>.json     IRDAI Annual Report statements (scripts/parse_irdai_annual.py)
  data/benchmark/auto/monthly_nb.json               IRDAI monthly new business (scripts/irdai_monthly.py, daily job)
  data/benchmark/auto/{news,digital,market}.json    daily feeds
  data/benchmark/research.json                      hand-researched values {cid: {kpi: {v, p, src, note}}}
  data/benchmark/strategy.json                      strategy profiles
  data/metrics.json, data/reviews.json, data/ownership.json, data/dashboard.json, data/products/*.json, data/changelog.json
"""
import datetime as dt
import json
import math
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
B = ROOT / "data" / "benchmark"
OUT = ROOT / "data" / "benchmark.json"


def jload(p, default=None):
    p = Path(p)
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else default


def latest_source(prefix):
    files = sorted((B / "sources").glob(f"{prefix}_*.json"))
    return jload(files[-1]) if files else None


def r(x, nd=2):
    return None if x is None or (isinstance(x, float) and (math.isnan(x) or math.isinf(x))) else round(x, nd)


def div(a, b, k=1.0):
    return None if a is None or b in (None, 0) else a / b * k


def installs_num(s):
    if not s:
        return None
    m = re.match(r"([\d,]+)", str(s))
    return int(m.group(1).replace(",", "")) if m else None


def fy_label(fy):
    return f"FY{fy}" if fy else ""


def main():
    fw = jload(B / "framework.json")
    hbsrc = latest_source("irdai_handbook") or {"companies": {}, "fy": None}
    arsrc = latest_source("irdai_annual") or {"companies": {}, "fy": None}
    hb, ar = hbsrc["companies"], arsrc["companies"]
    FY = hbsrc.get("fy") or "2024-25"
    y1, y0 = FY, f"{int(FY[:4]) - 1}-{FY[2:4]}"                       # '2024-25', '2023-24'
    y3 = f"{int(FY[:4]) - 3}-{str(int(FY[:4]) - 2)[2:]}"              # '2021-22'
    mar1, mar0, mar_5 = str(int(FY[:4]) + 1), FY[:4], str(int(FY[:4]) - 4)  # '2025', '2024', '2020'
    monthly = jload(B / "auto" / "monthly_nb.json", {"periods": {}, "latest": None})
    news = jload(B / "auto" / "news.json", {"companies": {}})
    digital = jload(B / "auto" / "digital.json", {"companies": {}})
    market = jload(B / "auto" / "market.json", {"companies": {}})
    research = jload(B / "research.json", {}) or {}
    strategy = jload(B / "strategy.json", {"companies": {}})
    metrics = jload(ROOT / "data" / "metrics.json", {"companies": {}})["companies"]
    reviews = jload(ROOT / "data" / "reviews.json", {"companies": {}})["companies"]
    ownership = jload(ROOT / "data" / "ownership.json", {"companies": {}})["companies"]
    dash = jload(ROOT / "data" / "dashboard.json")
    changelog = jload(ROOT / "data" / "changelog.json", [])
    companies = dash["companies"]
    ids = [c["id"] for c in companies]
    today = dt.date.today()

    # full product records for catalogue KPIs (active = dashboard status_label Active)
    active_uins = {(p["company_id"], p.get("uin") or p.get("name")): p for p in dash["products"] if p.get("status_label") == "Active"}
    full = {}
    for f in (ROOT / "data" / "products").glob("*.json"):
        d = jload(f)
        for p in d.get("products", []):
            key = (d.get("company_id"), p.get("uin") or p.get("name"))
            if key in active_uins:
                full[key] = p

    V = {}  # kpi -> cid -> {v, p, src, note?}

    def put(kpi, cid, v, period, src, note=None, nd=2):
        if v is None:
            return
        if isinstance(v, float):
            v = r(v, nd)
        rec = {"v": v, "p": period, "src": src}
        if note:
            rec["note"] = note
        V.setdefault(kpi, {})[cid] = rec

    # ---------- monthly new business ----------
    mp = monthly.get("periods", {}).get(monthly.get("latest") or "", None)
    if mp:
        per = "FYTD " + dt.date.fromisoformat(mp["as_on"]).strftime("%b %Y")
        tot = mp["totals"].get("industry", {})
        prv = mp["totals"].get("private", {})
        tseg = tot.get("segments", {})
        ind_tot = sum((tseg.get(s, {}).get("fyp_ytd") or 0) for s in ("ind_single", "ind_nonsingle"))
        for cid, c in mp["companies"].items():
            seg = c.get("segments", {})
            ind = sum((seg.get(s, {}).get("fyp_ytd") or 0) for s in ("ind_single", "ind_nonsingle"))
            ind_prev = sum((seg.get(s, {}).get("fyp_ytd_prev") or 0) for s in ("ind_single", "ind_nonsingle"))
            ind_pol = sum((seg.get(s, {}).get("pol_ytd") or 0) for s in ("ind_single", "ind_nonsingle"))
            ind_pol_prev = sum((seg.get(s, {}).get("pol_ytd_prev") or 0) for s in ("ind_single", "ind_nonsingle"))
            ind_sa = sum((seg.get(s, {}).get("sa_ytd") or 0) for s in ("ind_single", "ind_nonsingle"))
            reg = seg.get("ind_nonsingle", {})
            src = "irdai_monthly"
            put("nbp_ytd_cr", cid, c.get("fyp_ytd"), per, src, nd=0)
            put("nbp_share_pct", cid, c.get("fyp_share"), per, src)
            if cid != "lic":
                put("nbp_private_share_pct", cid, div(c.get("fyp_ytd"), prv.get("fyp_ytd"), 100), per, src)
            put("ind_nbp_ytd_cr", cid, ind or None, per, src, nd=0)
            put("ind_nbp_share_pct", cid, div(ind, ind_tot, 100), per, src)
            put("sa_ytd_cr", cid, c.get("sa_ytd"), per, src, nd=0)
            put("lives_ytd", cid, c.get("lives_ytd"), per, src, nd=0)
            put("nbp_ytd_growth_pct", cid, c.get("fyp_ytd_growth"), per, src, nd=1)
            if ind_prev > 1:
                put("ind_nbp_growth_pct", cid, (ind / ind_prev - 1) * 100, per, src, nd=1)
            if (reg.get("fyp_ytd_prev") or 0) > 1:
                put("ind_regular_growth_pct", cid, (reg["fyp_ytd"] / reg["fyp_ytd_prev"] - 1) * 100, per, src, nd=1)
            if ind_pol_prev > 100:
                put("ind_policies_growth_pct", cid, (ind_pol / ind_pol_prev - 1) * 100, per, src, nd=1)
            if tot.get("fyp_ytd") and tot.get("fyp_ytd_prev") and c.get("fyp_ytd_prev") is not None:
                put("share_change_bps", cid, (c["fyp_ytd"] / tot["fyp_ytd"] - c["fyp_ytd_prev"] / tot["fyp_ytd_prev"]) * 10000, per, src, nd=0)
            put("month_growth_pct", cid, c.get("fyp_month_growth"), dt.date.fromisoformat(mp["as_on"]).strftime("%b %Y"), src, nd=1)
            if ind_pol > 100:
                put("ind_ticket_inr", cid, ind * 1e7 / ind_pol, per, src, nd=0)
            if ind > 1:
                put("regular_share_pct", cid, div(reg.get("fyp_ytd"), ind, 100), per, src, nd=1)
                put("protection_intensity", cid, ind_sa / ind, per, src, nd=1)
            put("ind_share_of_nbp_pct", cid, div(ind, c.get("fyp_ytd"), 100), per, src, nd=1)

    # ---------- IRDAI handbook ----------
    hper, mper = fy_label(FY), f"31 Mar {mar1}"
    S = "irdai_handbook"
    for cid, h in hb.items():
        tp = h.get("total_premium_cr", {})
        put("gwp_cr", cid, tp.get(y1), hper, S, nd=0)
        if tp.get(y0):
            put("gwp_growth_pct", cid, (tp[y1] / tp[y0] - 1) * 100 if tp.get(y1) else None, hper, S, nd=1)
        if tp.get(y3) and tp.get(y1) and tp[y3] > 0:
            put("gwp_cagr3_pct", cid, ((tp[y1] / tp[y3]) ** (1 / 3) - 1) * 100, f"FY{y3[:4]}-{FY[5:]}", S, nd=1)
        aum = h.get("aum_cr", {})
        put("aum_cr", cid, aum.get(mar1), mper, S, nd=0)
        if aum.get(mar0):
            put("aum_growth_pct", cid, (aum[mar1] / aum[mar0] - 1) * 100 if aum.get(mar1) else None, hper, S, nd=1)
        put("ulip_aum_share_pct", cid, div(h.get("aum_ulip_cr", {}).get(mar1), aum.get(mar1), 100), mper, S, nd=1)
        put("aum_to_premium_x", cid, div(aum.get(mar1), tp.get(y1)), mper, S, nd=1)
        pif = h.get("policies_in_force_000", {}).get(y1)
        pif_n = pif * 1000 if pif else None
        put("pif_lakh", cid, pif / 100 if pif else None, mper, S, nd=1)
        ra = h.get("revenue_account_lakh", {}).get(y1, {})
        prem = ra.get("premium")
        pat = h.get("pat_lakh", {}).get(y1)
        nw = h.get("net_worth_lakh", {})
        put("pat_cr", cid, pat / 100 if pat is not None else None, hper, S, nd=0)
        if pat is not None and nw.get(mar1) and nw.get(mar0) and nw[mar1] + nw[mar0] > 0:
            put("roe_pct", cid, pat / ((nw[mar1] + nw[mar0]) / 2) * 100, hper, S, nd=1)
        put("pat_margin_pct", cid, div(pat, prem, 100), hper, S, nd=1)
        put("ph_surplus_pct", cid, div(ra.get("surplus"), prem, 100), hper, S, nd=1)
        put("net_worth_cr", cid, nw.get(mar1) / 100 if nw.get(mar1) else None, mper, S, nd=0)
        if nw.get(mar0) and nw.get(mar0) > 0 and nw.get(mar1):
            put("net_worth_growth_pct", cid, (nw[mar1] / nw[mar0] - 1) * 100, hper, S, nd=1)
        sol = h.get("solvency", {})
        sk = [k for k in sol if re.match(r"[A-Za-z]+ \d{4}$", k)]
        if sk:
            order = sorted(sk, key=lambda k: dt.datetime.strptime(k, "%B %Y"))
            put("solvency_ratio", cid, sol[order[-1]], order[-1], S)
            if len(order) >= 5:
                put("solvency_change", cid, sol[order[-1]] - sol[order[-5]], f"{order[-5]} to {order[-1]}", S)
        put("reinsurance_ceded_pct", cid, div(abs(ra.get("ri_ceded") or 0) or None, prem, 100), hper, S, nd=1)
        # channels
        ch = (h.get("channels_individual") or {}).get("by_channel", {})
        total = (ch.get("Total Individual New Business") or {}).get("premium")
        if total and total > 1:
            g = lambda *ks: sum((ch.get(k) or {}).get("premium", 0) or 0 for k in ks)
            agency, banca, oca, broker = g("Individual Agents"), g("Corporate Agents - Banks"), g("Corporate Agents - Others"), g("Brokers")
            direct = g("Direct Selling", "Online")
            other = total - agency - banca - oca - broker - direct
            for k, v in (("ch_agency_pct", agency), ("ch_banca_pct", banca), ("ch_other_ca_pct", oca), ("ch_broker_pct", broker), ("ch_direct_pct", direct), ("ch_other_pct", other)):
                put(k, cid, v / total * 100, hper, S, nd=1)
            shares = [((v or {}).get("premium") or 0) / total for k, v in ch.items() if k not in ("Total Individual New Business", "Referrals")]
            put("channel_diversity", cid, 100 * (1 - sum(s * s for s in shares)), hper, S, nd=1)
            put("online_nb_pct", cid, g("Online", "Web Aggregators") / total * 100, hper, S, nd=1)
        ag = h.get("individual_agents", {})
        put("agents_count", cid, ag.get(mar1), mper, S, nd=0)
        if ag.get(mar0) and ag.get(mar0) > 50 and ag.get(mar1) is not None:
            put("agents_growth_pct", cid, (ag[mar1] / ag[mar0] - 1) * 100, hper, S, nd=1)
        ap = (h.get("agent_nbp_lakh_avg") or {}).get("individual", {}).get(y1)
        if ag.get(mar1):
            put("agent_nbp_lakh", cid, ap, hper, S)
            put("agent_policies", cid, (h.get("agent_policies_avg") or {}).get("individual", {}).get(y1), hper, S, nd=1)
        put("corporate_agents", cid, h.get("corporate_agents", {}).get(mar1), mper, S, nd=0)
        off = h.get("offices", {}).get(y1)
        if off:
            put("offices", cid, off, mper, S, nd=0)
            put("nbp_per_office_cr", cid, div(h.get("nbp_cr", {}).get(y1), off), hper, S)
            put("premium_per_office_cr", cid, div(tp.get(y1), off), hper, S)
            put("agents_per_office", cid, div(ag.get(mar1), off), mper, S, nd=0)
        ss = h.get("state_spread")
        if ss:
            put("states_present", cid, ss["states_with_business"], hper, S, nd=0)
            put("top3_state_share_pct", cid, ss["top3_share_pct"], hper, S, note=f"Largest: {ss['top_state']} ({ss['top_state_share_pct']}%)")
        # claims
        dc = (h.get("death_claims_ind") or {}).get(y1, {})
        if (dc.get("total_no") or 0) >= 10:
            put("csr_count_pct", cid, div(dc.get("paid_no"), dc["total_no"], 100), hper, S)
            put("repudiation_pct", cid, div(dc.get("repudiated_no"), dc["total_no"], 100), hper, S)
            put("rejected_pct", cid, div(dc.get("rejected_no"), dc["total_no"], 100), hper, S)
            put("claims_pending_pct", cid, div(dc.get("pending_end_no"), dc["total_no"], 100), hper, S)
            if (dc.get("total_amt") or 0) > 0:
                put("csr_amount_pct", cid, div(dc.get("paid_amt"), dc["total_amt"], 100), hper, S)
                put("repudiation_amt_pct", cid, div(dc.get("repudiated_amt"), dc["total_amt"], 100), hper, S)
        du = (h.get("claims_duration_ind") or {}).get(y1, {})
        if (du.get("total") or 0) >= 10:
            put("claims_30d_pct", cid, div(du.get("d30"), du["total"], 100), hper, S)
        gc = (h.get("death_claims_grp") or {}).get(y1, {})
        if (gc.get("total_no") or 0) >= 10:
            put("group_csr_pct", cid, div(gc.get("paid_no"), gc["total_no"], 100), hper, S)
            put("group_repudiation_pct", cid, div(gc.get("repudiated_no"), gc["total_no"], 100), hper, S)
        # service
        pers = h.get("persistency_pct", {})
        p1 = pers.get(mar1, {})
        for m in ("13", "25", "37", "49", "61"):
            v = p1.get(m)
            if v is not None and 0 < v <= 100:
                put(f"persistency_{m}", cid, v, mper, S, nd=1)
        p5 = pers.get(mar_5, {})
        if p1.get("13") and p5.get("13") and p1["13"] <= 100 and p5["13"] <= 100:
            put("persistency_13_change", cid, p1["13"] - p5["13"], f"Mar {mar_5} to Mar {mar1}", S, nd=1)
        lr = h.get("lapse_ratio_pct", {}).get(y1)
        if lr is not None and lr > 0:
            put("lapse_ratio_pct", cid, lr, hper, S)
        gr = h.get("grievances", {}).get(y1, {})
        if gr and pif_n and pif_n > 10000:
            rep = gr.get("actual_reported", gr.get("reported"))
            put("grievances_per_10k", cid, div(rep, pif_n, 10000), hper, S)
        if gr and ((gr.get("os_start") or 0) + (gr.get("reported") or 0)) > 0:
            put("grievance_resolution_pct", cid, div(gr.get("resolved"), (gr.get("os_start") or 0) + (gr.get("actual_reported", gr.get("reported")) or 0), 100), hper, S, nd=1)
        omb = (metrics.get(cid, {}).get("metrics", {}).get("ombudsman_complaints") or {})
        if omb.get("value") is not None and pif_n and pif_n > 10000:
            put("ombudsman_per_lakh", cid, omb["value"] / pif_n * 1e5, omb.get("period") or hper, "ombudsman", note="Complaints from the Ombudsman report; policies in force from the IRDAI handbook")
        # efficiency
        if prem:
            put("opex_ratio_pct", cid, div(ra.get("opex"), prem, 100), hper, S, nd=1)
            put("total_cost_ratio_pct", cid, div((ra.get("opex") or 0) + (ra.get("commission") or 0), prem, 100), hper, S, nd=1)
            put("benefits_ratio_pct", cid, div(ra.get("benefits"), prem, 100), hper, S, nd=1)
        cp = h.get("commission_pct_premium", {})
        put("commission_ratio_pct", cid, cp.get(y1), hper, S, nd=1)
        if cp.get(y1) is not None and cp.get(y3) is not None:
            put("commission_ratio_change", cid, cp[y1] - cp[y3], f"FY{y3[:4]}-{y3[5:]} to {hper}", S, nd=1)
        if ra.get("opex") and pif_n and pif_n > 10000:
            put("opex_per_policy_inr", cid, ra["opex"] * 1e5 / pif_n, hper, S, nd=0)


    # ---------- state-level network ----------
    stsrc = latest_source("irdai_states")
    NET = None
    if stsrc:
        sfy = stsrc["fy"]; sprev = f"{int(sfy[:4]) - 1}-{sfy[2:4]}"; s5 = f"{int(sfy[:4]) - 5}-{str(int(sfy[:4]) - 4)[2:]}"
        sper = fy_label(sfy)
        ind_tot = {st: x.get("premium_cr", {}) for st, x in stsrc["industry"].items()}
        NET = {"fy": sfy, "prev": sprev, "source": stsrc["source"], "regions": stsrc["regions"], "region_of": stsrc["region_of"],
               "industry": {st: {"premium_cr": r(x.get("premium_cr", {}).get(sfy)), "premium_prev_cr": r(x.get("premium_cr", {}).get(sprev)),
                                 "policies": x.get("policies", {}).get(sfy), "premium_hist": {k: r(v) for k, v in x.get("premium_cr", {}).items()}}
                            for st, x in stsrc["industry"].items()},
               "companies": {}}
        for cid, c in stsrc["companies"].items():
            offs = c.get("offices", {}); prem = c.get("ind_premium_cr", {}); pol = c.get("ind_policies", {}); grp = c.get("grp_premium_cr", {})
            states = sorted(set(offs) | set(prem) | set(grp))
            rows = {}
            for st in states:
                o = offs.get(st, {}); p_ = prem.get(st, {})
                it = (ind_tot.get(st) or {})
                sh = div(p_.get(sfy), it.get(sfy), 100); shp = div(p_.get(sprev), it.get(sprev), 100)
                rows[st] = {"offices": o.get(sfy), "offices_5y": o.get(s5), "ind_premium_cr": r(p_.get(sfy)), "ind_premium_prev_cr": r(p_.get(sprev)),
                            "ind_policies": (pol.get(st) or {}).get(sfy), "grp_premium_cr": r(grp.get(st)), "share_pct": r(sh, 3), "share_prev_pct": r(shp, 3)}
            NET["companies"][cid] = {"states": rows, "office_mix": c.get("office_mix")}
            tot_off = sum((x["offices"] or 0) for x in rows.values()); tot5 = sum((x["offices_5y"] or 0) for x in rows.values())
            put("office_states", cid, sum(1 for x in rows.values() if (x["offices"] or 0) > 0), f"31 Mar {int(sfy[:4]) + 1}", S, nd=0)
            if tot5 >= 5:
                put("offices_growth_5y_pct", cid, (tot_off / tot5 - 1) * 100, f"Mar {int(s5[:4]) + 1} to Mar {int(sfy[:4]) + 1}", S, nd=1)
            mix = c.get("office_mix") or {}
            cl = sum(v for k, v in mix.items() if k != "Unclassified")
            if cl >= 5:
                put("rural_semiurban_office_pct", cid, ((mix.get("Semi Urban") or 0) + (mix.get("Rural") or 0)) / cl * 100, f"31 Mar {int(sfy[:4]) + 1}", S, nd=1)
            ip = sum((x["ind_premium_cr"] or 0) for x in rows.values())
            if tot_off and ip:
                put("ind_premium_per_office_cr", cid, ip / tot_off, sper, S)
            if ip > 1:
                put("state_share_gain_states", cid, sum(1 for x in rows.values() if x["share_pct"] is not None and x["share_prev_pct"] is not None and x["share_pct"] > x["share_prev_pct"] and (x["ind_premium_cr"] or 0) > 0.5), sper, S, nd=0)

    # ---------- IRDAI annual report ----------
    for cid, a in ar.items():
        aper = fy_label(arsrc.get("fy"))
        put("products_filed", cid, a.get("products_filed"), aper, "irdai_annual", nd=0)
        put("renewal_share_pct", cid, div(a.get("all_renewal_cr"), a.get("all_total_cr"), 100), aper, "irdai_annual", nd=1)
        put("linked_nb_share_pct", cid, div(a.get("linked_new_business_cr") or 0, a.get("all_new_business_cr"), 100) if a.get("all_new_business_cr") else None, aper, "irdai_annual", nd=1)

    # ---------- catalogue ----------
    year_ago = (today - dt.timedelta(days=365)).isoformat()
    launches = {}
    for e in changelog if isinstance(changelog, list) else changelog.get("entries", []):
        if e.get("type") == "launch" and (e.get("date") or "") >= year_ago and not e.get("needs_review"):
            launches[e.get("company_id")] = launches.get(e.get("company_id"), 0) + 1
    for c in companies:
        cid, st = c["id"], c.get("stats") or {}
        per = "On sale now"
        if st.get("active_individual") is not None:
            put("active_individual", cid, st["active_individual"], per, "catalogue", nd=0)
            put("category_breadth", cid, sum(1 for v in (st.get("by_category") or {}).values() if v), per, "catalogue", nd=0)
            put("riders_active", cid, st.get("active_rider"), per, "catalogue", nd=0)
            put("group_products", cid, st.get("active_group"), per, "catalogue", nd=0)
            put("micro_products", cid, st.get("active_micro"), per, "catalogue", nd=0)
            put("launches_12m", cid, launches.get(cid, st.get("launches_12m") or 0), "Last 12 months", "catalogue", nd=0)
        act = [p for (co, _), p in full.items() if co == cid and p.get("segment") == "Individual"]
        known = [p for p in act if p.get("online_purchase") is not None]
        if len(known) >= 3:
            put("online_pct", cid, sum(1 for p in known if p["online_purchase"]) / len(known) * 100, per, "catalogue", nd=0,
                note=f"{len(known)} of {len(act)} plans have this recorded")
        std = {p.get("standard_product") for p in act if p.get("standard_product")}
        if act:
            put("standard_products", cid, len(std), per, "catalogue", nd=0)
        terms = [(p.get("eligibility") or {}).get("maturity_age_max_years") for p in act if p.get("category") == "Term"]
        terms = [t for t in terms if isinstance(t, (int, float)) and t <= 100]
        if terms:
            put("term_max_cover_age", cid, max(terms), per, "catalogue", nd=0)

    # ---------- app stores, reviews ----------
    for cid, rv in reviews.items():
        a, i = rv.get("android") or {}, rv.get("ios") or {}
        if a.get("rating"):
            put("android_rating", cid, a["rating"], a.get("observed_on") or "", "app_stores")
            put("app_installs", cid, installs_num(a.get("installs")), a.get("observed_on") or "", "app_stores", nd=0)
            if a.get("last_updated"):
                try:
                    put("app_freshness_days", cid, (today - dt.date.fromisoformat(a["last_updated"][:10])).days, "Today", "app_stores", nd=0)
                except ValueError:
                    pass
        if i.get("rating"):
            put("ios_rating", cid, i["rating"], i.get("observed_on") or "", "app_stores")
        na, ni = a.get("ratings_count") or 0, i.get("ratings_count") or 0
        if na + ni:
            put("review_volume", cid, na + ni, "Today", "app_stores", nd=0)
            put("app_rating_blend", cid, ((a.get("rating") or 0) * na + (i.get("rating") or 0) * ni) / (na + ni), "Today", "app_stores")
        tp = [x.get("rating") for x in rv.get("third_party") or [] if x.get("rating")]
        if tp:
            put("third_party_rating", cid, sum(tp) / len(tp), (rv.get("third_party") or [{}])[0].get("observed_on") or "", "research", nd=1)

    # ---------- news, web audit, market ----------
    for cid, n in news.get("companies", {}).items():
        if n.get("status", "ok") == "ok" or n.get("items"):
            put("news_30d", cid, n.get("mentions_30d"), "Last 30 days", "news", nd=0)
            put("news_sov_pct", cid, n.get("share_of_voice_pct"), "Last 30 days", "news", nd=1)
    for cid, w in digital.get("companies", {}).items():
        if w.get("readable") and w.get("signals"):
            put("web_signals", cid, w.get("score"), w.get("checked_on") or "", "web_audit", nd=0)
            put("social_platforms", cid, len(w.get("social") or []), w.get("checked_on") or "", "web_audit", nd=0)
        if w.get("load_seconds") is not None and w.get("status") == 200:
            put("web_load_seconds", cid, w["load_seconds"], w.get("checked_on") or "", "web_audit")
    for cid, mk in market.get("companies", {}).items():
        if mk and mk.get("ret_1y_pct") is not None:
            put("ret_1y_pct", cid, mk["ret_1y_pct"], f"To {mk.get('as_of')}", "market", nd=1,
                note=None if mk.get("pure_play", True) else f"Listed parent: {mk.get('entity')}")

    # ---------- metrics.json (latest disclosed), ownership ----------
    for cid, c in metrics.items():
        m = c.get("metrics", {})
        for kpi, key in (("vnb_margin_pct", "vnb_margin_pct"), ("csr_latest_pct", "csr_count_pct"), ("persistency_13_premium", "persistency_13m_pct")):
            if m.get(key, {}).get("value") is not None:
                put(kpi, cid, m[key]["value"], m[key].get("period") or "", "disclosures", nd=1)
        if c.get("listed"):
            put("listed", cid, bool(re.match(r"(yes|listed on|nse|bse)", str(c["listed"]), re.I)) and not re.match(r"parent", str(c["listed"]), re.I), "Now", "research")
    for cid, o in ownership.items():
        if isinstance(o, dict) and o.get("foreign_stake_pct") is not None:
            put("foreign_stake_pct", cid, o["foreign_stake_pct"], (o.get("as_of") or ""), "research", nd=2)

    # ---------- department KPIs (channels, operations, investments) ----------
    for cid, h in hb.items():
        hper, mper = fy_label(FY), f"31 Mar {mar1}"
        ch = (h.get("channels_individual") or {}).get("by_channel", {})
        tot = (ch.get("Total Individual New Business") or {})
        g = lambda key, *ks: sum(((ch.get(k) or {}).get(key) or 0) for k in ks)
        if (tot.get("premium") or 0) > 1:
            for kid, chans in (("agency", ("Individual Agents",)), ("banca", ("Corporate Agents - Banks",)), ("direct", ("Direct Selling", "Online"))):
                pr, po = g("premium", *chans), g("policies", *chans)
                put(f"{kid}_premium_cr", cid, pr, hper, S, nd=0)
                put(f"{kid}_policies", cid, po, hper, S, nd=0)
                if po >= 100:
                    put(f"{kid}_ticket_inr", cid, pr * 1e7 / po, hper, S, nd=0)
            put("broker_premium_cr", cid, g("premium", "Brokers"), hper, S, nd=1)
            put("other_ca_premium_cr", cid, g("premium", "Corporate Agents - Others"), hper, S, nd=1)
            put("proprietary_share_pct", cid, g("premium", "Individual Agents", "Direct Selling", "Online") / tot["premium"] * 100, hper, S, nd=1)
            offs = (h.get("offices") or {}).get(y1)
            if offs and (tot.get("policies") or 0) > 100:
                put("policies_per_office", cid, tot["policies"] / offs, hper, S, nd=0)
        gch = (h.get("channels_group") or {}).get("by_channel", {})
        gtot = (gch.get("Total Group New Business") or {}).get("premium") or 0
        if gtot > 1:
            put("group_banca_pct", cid, ((gch.get("Corporate Agents - Banks") or {}).get("premium") or 0) / gtot * 100, hper, S, nd=1)
            put("group_direct_pct", cid, ((gch.get("Direct Selling") or {}).get("premium") or 0) / gtot * 100, hper, S, nd=1)
        put("agent_premium_per_policy", cid, (h.get("agent_premium_per_policy_inr") or {}).get("individual", {}).get(y1) or None, hper, S, nd=0)
        if (h.get("corporate_agents") or {}).get(mar1):
            put("ca_nbp_lakh", cid, (h.get("agent_nbp_lakh_avg") or {}).get("corporate", {}).get(y1) or None, hper, S)
            put("ca_policies", cid, (h.get("agent_policies_avg") or {}).get("corporate", {}).get(y1) or None, hper, S, nd=1)
        tp, nb = h.get("total_premium_cr", {}), h.get("nbp_cr", {})
        ren = {y: tp[y] - nb[y] for y in tp if y in nb and tp[y] is not None and nb[y] is not None}
        if ren.get(y1) is not None and ren[y1] > 0:
            put("renewal_premium_cr", cid, ren[y1], hper, S, nd=0)
            if (ren.get(y0) or 0) > 1:
                put("renewal_growth_pct", cid, (ren[y1] / ren[y0] - 1) * 100, hper, S, nd=1)
            if (ren.get(y3) or 0) > 1:
                put("renewal_cagr3_pct", cid, ((ren[y1] / ren[y3]) ** (1 / 3) - 1) * 100, f"FY{y3[:4]}-{FY[5:]}", S, nd=1)
        ra = (h.get("revenue_account_lakh") or {}).get(y1, {})
        if ra.get("benefits") is not None:
            put("benefits_paid_cr", cid, ra["benefits"] / 100, hper, S, nd=0)
        dcl = (h.get("death_claims_ind") or {}).get(y1, {})
        put("death_claims_paid_cr", cid, dcl.get("paid_amt"), hper, S, nd=0)
        pif = (h.get("policies_in_force_000") or {}).get(y1)
        offs = (h.get("offices") or {}).get(y1)
        if pif and offs:
            put("pif_per_office", cid, pif * 1000 / offs, mper, S, nd=0)
        aum = h.get("aum_cr", {})
        inc = (ra.get("inv_income") or 0) + ((h.get("sh_inv_income_lakh") or {}).get(y1) or 0)
        if inc > 0 and aum.get(mar1) and aum.get(mar0):
            put("investment_income_yield_pct", cid, inc / 100 / ((aum[mar1] + aum[mar0]) / 2) * 100, hper, S, nd=2)
        mix = (h.get("aum_mix") or {}).get(mar1) or {}
        lf, pg, ul = mix.get("life", {}), mix.get("pension_group", {}), mix.get("ulip", {})
        nonlinked = (lf.get("Total (Life Fund)") or 0) + (pg.get("Total (Pension & General Annuity & Group Fund)") or 0)
        if nonlinked > 10:
            gsec = sum((d.get(k) or 0) for d in (lf, pg) for k in d if "government" in k.lower() or "govt" in k.lower())
            put("gsec_share_pct", cid, gsec / nonlinked * 100, mper, S, nd=1)
        if (lf.get("Total (Life Fund)") or 0) > 10:
            put("infra_share_pct", cid, (lf.get("Housing & Infrastructure Investments") or 0) / lf["Total (Life Fund)"] * 100, mper, S, nd=1)
        if aum.get(mar1):
            put("other_inv_share_pct", cid, ((lf.get("Other Investments") or 0) + (ul.get("Other Investments") or 0)) / aum[mar1] * 100, mper, S, nd=2)
        hp = (h.get("health_products_nb") or {}).get(y1) or {}
        if hp.get("premium_lakh") is not None:
            put("health_products_premium_cr", cid, hp["premium_lakh"] / 100, hper, S, nd=1)
        hr = (h.get("health_riders_nb") or {}).get(y1) or {}
        if hr.get("persons") is not None:
            put("health_rider_lives", cid, hr["persons"], hper, S, nd=0)
    if mp:
        per = "FYTD " + dt.date.fromisoformat(mp["as_on"]).strftime("%b %Y")
        for cid, c in mp["companies"].items():
            seg = c.get("segments", {})
            gs = [seg.get(k, {}) for k in ("grp_single", "grp_nonsingle", "grp_yrt")]
            gf, gp = sum((x.get("fyp_ytd") or 0) for x in gs), sum((x.get("fyp_ytd_prev") or 0) for x in gs)
            if gf > 0:
                put("group_nbp_ytd_cr", cid, gf, per, "irdai_monthly", nd=0)
                put("group_share_of_nbp_pct", cid, div(gf, c.get("fyp_ytd"), 100), per, "irdai_monthly", nd=1)
                if gp > 1:
                    put("group_nbp_growth_pct", cid, (gf / gp - 1) * 100, per, "irdai_monthly", nd=1)
                if (c.get("lives_ytd") or 0) > 100:
                    put("group_premium_per_life_inr", cid, gf * 1e7 / c["lives_ytd"], per, "irdai_monthly", nd=0)
            ip = sum((seg.get(s, {}).get("pol_ytd") or 0) for s in ("ind_single", "ind_nonsingle"))
            if ip:
                put("ind_policies_ytd", cid, ip, per, "irdai_monthly", nd=0)
            ind = sum((seg.get(s, {}).get("fyp_ytd") or 0) for s in ("ind_single", "ind_nonsingle"))
            if ind > 1:
                put("single_premium_share_pct", cid, (seg.get("ind_single", {}).get("fyp_ytd") or 0) / ind * 100, per, "irdai_monthly", nd=1)
    for cid, w in digital.get("companies", {}).items():
        sg = w.get("signals") or {}
        if not (w.get("readable") and sg):
            continue
        d = w.get("checked_on") or ""
        b = lambda k: 1 if sg.get(k) else 0
        put("onboarding_digital", cid, b("buy_online") + b("video_kyc") + b("ai_tools"), d, "web_audit", nd=0)
        put("payments_digital", cid, b("pay_premium") + b("upi_autopay") + b("android_app") + b("ios_app"), d, "web_audit", nd=0)
        put("servicing_digital", cid, b("customer_login") + b("claims_online") + b("whatsapp") + b("chatbot"), d, "web_audit", nd=0)
        put("communication_reach", cid, b("whatsapp") + b("chatbot") + b("regional_language") + (1 if len(w.get("social") or []) >= 4 else 0), d, "web_audit", nd=0)
        for kpi_id, key in (("pay_online", "pay_premium"), ("upi_autopay", "upi_autopay"), ("claims_online", "claims_online"), ("whatsapp", "whatsapp"), ("regional_language", "regional_language"), ("ai_tools", "ai_tools")):
            put(kpi_id, cid, bool(sg.get(key)), d, "web_audit")
    revs = {}
    for e in changelog if isinstance(changelog, list) else []:
        if e.get("type") == "new_version" and (e.get("date") or "") >= year_ago and e.get("status") != "dismissed":
            revs[e.get("company_id")] = revs.get(e.get("company_id"), 0) + 1
    for c in companies:
        if (c.get("stats") or {}).get("active_individual"):
            put("revisions_12m", c["id"], revs.get(c["id"], 0), "Last 12 months", "catalogue", nd=0)

    # ---------- research overrides ----------
    for cid, kv in research.get("companies", {}).items():
        for kpi, rec in kv.items():
            if isinstance(rec, dict) and rec.get("v") is not None:
                V.setdefault(kpi, {})[cid] = {"v": rec["v"], "p": rec.get("p", ""), "src": rec.get("src_key", "research"),
                                              **({"note": rec["note"]} if rec.get("note") else {}), **({"url": rec["url"]} if rec.get("url") else {})}

    # ---------- peer groups ----------
    comp_rows = []
    for c in companies:
        cid = c["id"]
        share = (V.get("nbp_share_pct", {}).get(cid) or {}).get("v")
        tier = None if share is None else "Leader" if share >= 10 else "Large" if share >= 3 else "Mid" if share >= 1 else "Small" if share >= 0.3 else "Emerging"
        sh = {k: (V.get(k, {}).get(cid) or {}).get("v") for k in ("ch_agency_pct", "ch_banca_pct", "ch_direct_pct")}
        model = None
        if sh["ch_agency_pct"] is not None:
            model = "Agency-led" if sh["ch_agency_pct"] >= 50 else "Banca-led" if (sh["ch_banca_pct"] or 0) >= 50 else "Direct-led" if (sh["ch_direct_pct"] or 0) >= 40 else "Multi-channel"
        no_new_business = cid == "sahara"
        comp_rows.append({"id": cid, "name": c.get("name"), "short": c.get("short") or c.get("name"), "sector": c.get("sector"),
                          "tier": tier, "model": model, "scored": not no_new_business,
                          "note": "No new business (under administration); excluded from scores" if no_new_business else None})
    scored = {x["id"] for x in comp_rows if x["scored"]}

    # ---------- scoring ----------
    kpi_meta = {k["id"]: {**k, "pillar": p["id"]} for p in fw["pillars"] for k in p["kpis"]}
    SC, STATS = {}, {}
    sector = {c["id"]: c.get("sector") for c in companies}
    for kpi, vals in V.items():
        nums = {cid: x["v"] for cid, x in vals.items() if isinstance(x["v"], (int, float)) and not isinstance(x["v"], bool)}
        if not nums:
            continue
        xs = sorted(nums.values())
        q = lambda p: xs[min(len(xs) - 1, max(0, int(round(p * (len(xs) - 1)))))]
        priv = sorted(v for c, v in nums.items() if sector.get(c) == "Private")
        STATS[kpi] = {"n": len(xs), "min": xs[0], "max": xs[-1], "p25": q(0.25), "median": q(0.5), "p75": q(0.75),
                      "private_median": priv[len(priv) // 2] if priv else None}
        meta = kpi_meta.get(kpi)
        if not meta or not meta.get("core") or meta.get("better") not in ("high", "low"):
            continue
        pool = {c: v for c, v in nums.items() if c in scored}
        if len(pool) < 5:
            continue
        order = sorted(pool.items(), key=lambda kv: kv[1])
        n = len(order)
        ranks, i = {}, 0
        while i < n:
            j = i
            while j + 1 < n and order[j + 1][1] == order[i][1]:
                j += 1
            avg = (i + j) / 2
            for k in range(i, j + 1):
                ranks[order[k][0]] = avg
            i = j + 1
        SC[kpi] = {c: round((rk / (n - 1) * 100) if meta["better"] == "high" else (100 - rk / (n - 1) * 100), 1) for c, rk in ranks.items()}

    PS, INDEX = {}, {}
    sc_rules = fw["scoring"]
    for p in fw["pillars"]:
        if p.get("qualitative"):
            continue
        core = [k["id"] for k in p["kpis"] if k.get("core")]
        for cid in scored:
            got = [SC[k][cid] for k in core if k in SC and cid in SC[k]]
            if len(got) >= sc_rules["min_kpis_per_pillar"]:
                PS.setdefault(p["id"], {})[cid] = {"score": round(sum(got) / len(got), 1), "kpis": len(got), "of": len(core)}
    for cid in scored:
        got = [PS[p][cid]["score"] for p in PS if cid in PS[p]]
        if len(got) >= sc_rules["min_pillars_for_index"]:
            INDEX[cid] = {"score": round(sum(got) / len(got), 1), "pillars": len(got)}
    for rank, (cid, _) in enumerate(sorted(INDEX.items(), key=lambda kv: -kv[1]["score"]), 1):
        INDEX[cid]["rank"] = rank
    for p in PS:
        for rank, (cid, _) in enumerate(sorted(PS[p].items(), key=lambda kv: -kv[1]["score"]), 1):
            PS[p][cid]["rank"] = rank

    # ---------- data view per insurer ----------
    PROF = {}
    pname = {p["id"]: p["name"] for p in fw["pillars"]}
    for cid in scored:
        ps = sorted(((PS[p][cid]["score"], p) for p in PS if cid in PS[p]), reverse=True)
        kp = sorted(((SC[k][cid], k) for k in SC if cid in SC[k]), reverse=True)
        PROF[cid] = {
            "strengths": [{"pillar": p, "name": pname[p], "score": s} for s, p in ps[:3] if s >= 60],
            "gaps": [{"pillar": p, "name": pname[p], "score": s} for s, p in ps[::-1][:3] if s <= 40],
            "standouts": [{"kpi": k, "pct": s} for s, k in kp if s >= 90][:6],
            "watch": [{"kpi": k, "pct": s} for s, k in kp[::-1] if s <= 10][:6],
        }

    # ---------- trend series ----------
    SER = {}

    def series(sid, label, unit, getter, years):
        by = {}
        for cid, h in hb.items():
            pts = [[y, r(getter(h, y), 2)] for y in years]
            pts = [p for p in pts if p[1] is not None]
            if len(pts) >= 2:
                by[cid] = pts
        if by:
            SER[sid] = {"label": label, "unit": unit, "by": by}
    fys = [f"{y}-{str(y + 1)[2:]}" for y in range(int(FY[:4]) - 9, int(FY[:4]) + 1)]
    mars = [str(int(m[:4]) + 1) for m in fys]
    series("total_premium", "Total premium", "cr", lambda h, y: h.get("total_premium_cr", {}).get(y), fys)
    series("nbp", "New business premium", "cr", lambda h, y: h.get("nbp_cr", {}).get(y), fys)
    series("persistency_13", "13th-month persistency (by policies)", "pct", lambda h, y: (h.get("persistency_pct", {}).get(y, {}) or {}).get("13"), mars)
    series("persistency_61", "61st-month persistency (by policies)", "pct", lambda h, y: (h.get("persistency_pct", {}).get(y, {}) or {}).get("61"), mars)
    series("commission_ratio", "Commission to premium", "pct", lambda h, y: h.get("commission_pct_premium", {}).get(y), fys)
    series("lapse_ratio", "Lapse ratio (non-linked)", "pct", lambda h, y: h.get("lapse_ratio_pct", {}).get(y), fys)
    series("agents", "Individual agents", "count", lambda h, y: h.get("individual_agents", {}).get(y), mars)
    series("offices", "Offices", "count", lambda h, y: h.get("offices", {}).get(y), fys)
    series("grievances", "Grievances reported", "count", lambda h, y: (h.get("grievances", {}).get(y) or {}).get("actual_reported", (h.get("grievances", {}).get(y) or {}).get("reported")), fys)
    sol_keys = sorted({k for h in hb.values() for k in h.get("solvency", {}) if re.match(r"[A-Za-z]+ \d{4}$", k)}, key=lambda k: dt.datetime.strptime(k, "%B %Y"))[-12:]
    series("solvency", "Solvency ratio (quarter end)", "x", lambda h, y: h.get("solvency", {}).get(y), sol_keys)
    # monthly new business share, from the monthly statements kept so far
    mby = {}
    for key in sorted(monthly.get("periods", {})):
        pm = monthly["periods"][key]
        for cid, c in pm["companies"].items():
            if c.get("fyp_share") is not None:
                mby.setdefault(cid, []).append([key, r(c["fyp_share"], 2)])
    if any(len(v) >= 2 for v in mby.values()):
        SER["nbp_share_monthly"] = {"label": "Share of new business, year to date", "unit": "pct", "by": mby}

    # ---------- feeds for the app ----------
    news_out = {}
    for cid, n in news.get("companies", {}).items():
        news_out[cid] = {"mentions_30d": n.get("mentions_30d"), "share_of_voice_pct": n.get("share_of_voice_pct"),
                         "themes_30d": n.get("themes_30d"), "items": (n.get("items") or [])[:15]}
    out = {
        "built_at": dt.datetime.now(dt.timezone(dt.timedelta(hours=5, minutes=30))).isoformat(timespec="minutes"),
        "framework": fw,
        "companies": comp_rows,
        "values": V, "scores": SC, "stats": STATS, "pillar_scores": PS, "index": INDEX, "series": SER, "profiles": PROF,
        "strategy": strategy.get("companies", {}),
        "strategy_meta": {k: v for k, v in strategy.items() if k != "companies"},
        "news": news_out, "news_updated": news.get("updated"), "network": NET, "global": jload(B / "global.json"),
        "digital": {"updated": digital.get("updated"), "signals": digital.get("signals"),
                    "companies": {cid: {k: w.get(k) for k in ("signals", "score", "readable", "social", "checked_on", "status", "note")} for cid, w in digital.get("companies", {}).items()}},
        "market": {cid: {k: v for k, v in (mk or {}).items()} for cid, mk in market.get("companies", {}).items()},
        "market_updated": market.get("updated"),
        "monthly": {"latest": monthly.get("latest"), "as_on": mp.get("as_on") if mp else None, "source": mp.get("source") if mp else None,
                    "industry": (mp or {}).get("totals", {}).get("industry"), "private": (mp or {}).get("totals", {}).get("private")},
        "periods": {"handbook": FY, "annual_report": arsrc.get("fy"), "monthly": monthly.get("latest")},
    }
    OUT.write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")))
    filled = sum(len(v) for v in V.values())
    print(f"built {OUT.relative_to(ROOT)}: {len(V)} KPIs with data, {filled} values, {len(SC)} scored KPIs, "
          f"{len(INDEX)} insurers indexed ({OUT.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
