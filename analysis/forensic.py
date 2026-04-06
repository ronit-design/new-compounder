import json
import re
import pandas as pd
import streamlit as st
from concurrent.futures import ThreadPoolExecutor, as_completed

from ai.nvidia import _call_nvidia
from data.edgar import edgar_get_cik, edgar_list_annual_filings, edgar_fetch_item8_notes


# ── Notes signal extraction ───────────────────────────────────────────────────

@st.cache_data(ttl=86400, show_spinner=False)
def forensic_notes_extract(notes_text, fiscal_year, company, api_key):
    prompt = f"""You are a forensic accounting assistant. Extract ONLY the data points below from the notes to financial statements for {company} (FY{fiscal_year}). Return ONLY valid compact JSON — no explanation, no markdown fences, no extra keys.

{{
  "inventory_method": "<LIFO, FIFO, weighted-average, or null if not disclosed>",
  "lifo_reserve_change": "<direction and magnitude of LIFO reserve change this year, or null>",
  "nonrecurring_gains_disclosed": "<asset sales, investment gains, or debt extinguishment gains mentioned in narrative, max 200 chars, or null>",
  "reserve_accounting": "<nature of contingency/warranty/litigation reserves and how they are classified — Chrysler-style deduction vs vague appropriated surplus, max 200 chars, or null>",
  "vies_spvs": "<guaranteed obligations or unconsolidated VIEs/SPVs, max 200 chars, or null>",
  "pension_assumed_return_pct": <number or null>,
  "pension_discount_rate_pct": <number or null>,
  "intangible_useful_lives": "<amortization periods for major acquired intangibles (customer relationships, patents, etc.), max 150 chars, or null>",
  "ppe_useful_lives": "<key PP&E asset classes with stated useful lives, max 150 chars, or null>",
  "revenue_recognition_policy": "<one sentence on when/how revenue is recognized, or null>",
  "explicit_policy_changes": "<any accounting policy changes explicitly disclosed this year, or null>",
  "oci_buried_losses": "<OCI items that may represent buried operating losses, max 150 chars, or null>",
  "contingent_liabilities": "<top contingent liability descriptions, max 200 chars, or null>",
  "auditor_name": "<auditor firm name or null>",
  "auditor_qualification": "<going concern, emphasis of matter, or null>"
}}

NOTES (FY{fiscal_year}):
{notes_text[:11000]}"""
    try:
        raw = _call_nvidia([{"role": "user", "content": prompt}], api_key, max_tokens=1000)
        m   = re.search(r'\{{[\s\S]*\}}', raw)
        return json.loads(m.group(0)) if m else {}
    except Exception:
        return {}


# ── Concurrent helpers ────────────────────────────────────────────────────────

def _fetch_notes_concurrent(cik: str, filings: list) -> dict:
    def _fetch_one(args):
        acc, fdate, yr = args
        return yr, edgar_fetch_item8_notes(cik, acc)

    results: dict = {}
    with ThreadPoolExecutor(max_workers=5) as pool:
        futures = {pool.submit(_fetch_one, f): f for f in filings}
        for fut in as_completed(futures):
            try:
                yr, text = fut.result()
                results[yr] = text
            except Exception:
                _, _, yr = futures[fut]
                results[yr] = None
    return results


def _extract_signals_concurrent(notes_raw: dict, company: str, api_key: str) -> dict:
    def _extract_one(args):
        yr, ntxt = args
        return yr, (forensic_notes_extract(ntxt, yr, company, api_key) if ntxt else {})

    results: dict = {}
    with ThreadPoolExecutor(max_workers=5) as pool:
        futures = {pool.submit(_extract_one, item): item for item in notes_raw.items()}
        for fut in as_completed(futures):
            try:
                yr, signals = fut.result()
                results[yr] = signals
            except Exception:
                yr, _ = futures[fut]
                results[yr] = {}
    return results


# ── Dataset builder ───────────────────────────────────────────────────────────

def build_forensic_dataset(xbrl, years, bs_years,
                           rev_s, ni_s, oi_s, cfo_s, fcf_s, cogs_s,
                           ar_s, inv_s, nd_s,
                           sbc_s, incr_cap_s, decr_cap_s, rsu_tax_s,
                           price_s, avg_price_s, shares_s):
    def _to_dict(series, year_labels, n=5):
        pairs = list(zip([str(y)[:4] for y in year_labels], series.tolist()))
        return {
            yr: (float(v) if pd.notna(v) and v is not None else None)
            for yr, v in pairs[-n:]
        }

    def _merge(xbrl_data, roic_data):
        return xbrl_data if xbrl_data else roic_data

    r_rev  = _to_dict(rev_s,     years)
    r_ni   = _to_dict(ni_s,      years)
    r_oi   = _to_dict(oi_s,      years)
    r_cfo  = _to_dict(cfo_s,     years)
    r_fcf  = _to_dict(fcf_s,     years)
    r_cogs = _to_dict(cogs_s,    years)
    r_sbc  = _to_dict(sbc_s,     years)
    r_nd   = _to_dict(nd_s,      years)
    r_rsu  = _to_dict(rsu_tax_s, years)

    r_ar  = _to_dict(ar_s,  bs_years)
    r_inv = _to_dict(inv_s, bs_years)

    mc_vals = [
        p * s if (pd.notna(p) and pd.notna(s) and p is not None and s is not None) else None
        for p, s in zip(price_s.tolist(), shares_s.tolist())
    ]
    r_mktcap = _to_dict(pd.Series(mc_vals, dtype=float), years)

    # ── Net buybacks & Maintenance Buybacks ───────────────────────────────────
    net_bb = [
        (abs(d) if pd.notna(d) else 0.0) - (abs(i) if pd.notna(i) else 0.0)
        for d, i in zip(decr_cap_s.tolist(), incr_cap_s.tolist())
    ]
    r_net_bb = _to_dict(pd.Series(net_bb, dtype=float), years)

    sh_vals     = shares_s.tolist()
    px_avg_vals = avg_price_s.tolist()
    maint_bb_vals = []

    for i in range(len(years)):
        bb_net  = net_bb[i]
        sh_curr = sh_vals[i]
        sh_prev = sh_vals[i-1] if i > 0 else sh_curr
        px_avg  = px_avg_vals[i]

        if pd.notna(sh_curr) and pd.notna(sh_prev) and pd.notna(px_avg) and px_avg > 0:
            delta_shares  = sh_prev - sh_curr
            val_reduction = max(0, delta_shares) * px_avg
            maint_bb      = max(0, bb_net - val_reduction)
        else:
            maint_bb = max(0, bb_net)

        maint_bb_vals.append(maint_bb)

    r_maint_bb = _to_dict(pd.Series(maint_bb_vals, dtype=float), years)

    # ── Owners' Earnings ──────────────────────────────────────────────────────
    oe_vals = []
    for yr in sorted(r_ni):
        ni_v   = r_ni.get(yr) or 0.0
        sbc_v  = r_sbc.get(yr) or 0.0
        m_bb_v = r_maint_bb.get(yr) or 0.0
        rsu_v  = r_rsu.get(yr) or 0.0
        oe_vals.append((yr, ni_v + abs(sbc_v) - m_bb_v - abs(rsu_v)))
    r_oe = {yr: v for yr, v in oe_vals}

    return {
        "net_income":           _merge(xbrl.get("net_income",    {}), r_ni),
        "revenue":              _merge(xbrl.get("revenue",       {}), r_rev),
        "cogs":                 _merge(xbrl.get("cogs",          {}), r_cogs),
        "cfo":                  _merge(xbrl.get("cfo",           {}), r_cfo),
        "accounts_rec":         _merge(xbrl.get("accounts_rec",  {}), r_ar),
        "inventory":            _merge(xbrl.get("inventory",     {}), r_inv),
        "pretax_income":        xbrl.get("pretax_income",    {}),
        "tax_expense":          xbrl.get("tax_expense",      {}),
        "asset_sale_gains":     xbrl.get("asset_sale_gains",  {}),
        "investment_gains":     xbrl.get("investment_gains",  {}),
        "debt_extinguish":      xbrl.get("debt_extinguish",   {}),
        "gross_ppe":            xbrl.get("gross_ppe",         {}),
        "depreciation":         xbrl.get("depreciation",      {}),
        "amort_intangibles":    xbrl.get("amort_intangibles", {}),
        "intangibles":          xbrl.get("intangibles",       {}),
        "goodwill":             xbrl.get("goodwill",          {}),
        "goodwill_impair":      xbrl.get("goodwill_impair",   {}),
        "capitalized_sw":       xbrl.get("capitalized_sw",    {}),
        "lifo_reserve":         xbrl.get("lifo_reserve",      {}),
        "allow_doubtful":       xbrl.get("allow_doubtful",    {}),
        "interest_expense":     xbrl.get("interest_expense",  {}),
        "lease_expense":        xbrl.get("lease_expense",     {}),
        "long_term_debt":       xbrl.get("long_term_debt",    {}),
        "preferred_div":        xbrl.get("preferred_div",     {}),
        "oci":                  xbrl.get("oci",               {}),
        "retained_earnings":    xbrl.get("retained_earnings", {}),
        "operating_income":     r_oi,
        "free_cash_flow":       r_fcf,
        "net_debt":             r_nd,
        "market_cap":           r_mktcap,
        "sbc":                  r_sbc,
        "net_buybacks":         r_net_bb,
        "maintenance_buybacks": r_maint_bb,
        "rsu_tax":              r_rsu,
        "owners_earnings":      r_oe,
    }


# ── Formatting helpers ────────────────────────────────────────────────────────

def _fmt_xbrl_table(dataset):
    if not dataset:
        return "No quantitative data available."

    all_years: set = set()
    for v in dataset.values():
        if isinstance(v, dict):
            all_years.update(v.keys())
    years = sorted(all_years)[-5:]

    def fv(val):
        if val is None: return "    n/a"
        return f"{val / 1e9:>7.2f}B"

    def section(title, keys_labels):
        rows = [f"\n{title}"]
        for key, lbl in keys_labels:
            series = dataset.get(key, {})
            rows.append(f"  {lbl:<26}" + "  ".join(fv(series.get(y)) for y in years))
        return rows

    header = f"{'Metric':<28} " + "  ".join(f"{y:>9}" for y in years)
    rows   = [header, "=" * len(header)]

    rows += section("── P&L & Cash Flow ─────────────────────────────────────────", [
        ("revenue",          "Revenue"),
        ("cogs",             "Cost of Goods Sold"),
        ("net_income",       "Net Income (GAAP)"),
        ("pretax_income",    "Pre-tax Income"),
        ("tax_expense",      "Tax Expense"),
        ("operating_income", "Operating Income [ROIC]"),
        ("cfo",              "Cash from Operations"),
        ("free_cash_flow",   "Free Cash Flow [ROIC]"),
    ])
    rows += section("── Nonrecurring Items (strip from normalized earnings) ───────", [
        ("asset_sale_gains", "Gains: Asset Sales"),
        ("investment_gains", "Gains: Investments"),
        ("debt_extinguish",  "Gains: Debt Extinguishment"),
        ("goodwill_impair",  "Goodwill Impairments"),
    ])
    rows += section("── PP&E, D&A & Intangibles ──────────────────────────────────", [
        ("gross_ppe",         "Gross PP&E"),
        ("depreciation",      "Total D&A"),
        ("amort_intangibles", "Amort. of Intangibles"),
        ("capitalized_sw",    "Capitalized Software"),
        ("intangibles",       "Intangible Assets (net)"),
        ("goodwill",          "Goodwill"),
    ])
    rows += section("── Inventory & Reserve Quality ──────────────────────────────", [
        ("inventory",      "Inventory"),
        ("lifo_reserve",   "LIFO Reserve (0=FIFO)"),
        ("accounts_rec",   "Accounts Receivable"),
        ("allow_doubtful", "Allowance: Doubtful Accts"),
    ])
    rows += section("── Capital Structure & Fixed Charges ────────────────────────", [
        ("interest_expense", "Interest Expense"),
        ("lease_expense",    "Lease/Rental Expense"),
        ("long_term_debt",   "Long-Term Debt"),
        ("net_debt",         "Net Debt [ROIC]"),
        ("preferred_div",    "Preferred Dividends"),
        ("market_cap",       "Market Cap [ROIC: P×Sh]"),
    ])
    rows += section("── Equity Quality (OCI / Retained Earnings) ─────────────────", [
        ("oci",              "OCI (net)"),
        ("retained_earnings","Retained Earnings"),
    ])
    rows += section("── Owners' Earnings & Dilution [ROIC] ───────────────────────", [
        ("sbc",                  "Stock-Based Compensation"),
        ("maintenance_buybacks", "Maintenance Buybacks"),
        ("rsu_tax",              "RSU Tax Withholdings"),
        ("owners_earnings",      "Owners' Earnings"),
    ])

    return "\n".join(rows)


def _fmt_notes_signals(signals_by_year):
    lines = []
    for yr in sorted(signals_by_year.keys()):
        sig = signals_by_year[yr]
        if not sig:
            continue
        lines.append(f"FY{yr}:")
        for k, v in sig.items():
            if v and str(v).lower() not in ("null", "none", ""):
                lines.append(f"  {k.replace('_',' ')}: {v}")
    return "\n".join(lines) if lines else "Notes extraction unavailable."


# ── Report generation ─────────────────────────────────────────────────────────

@st.cache_data(ttl=3600, show_spinner=False)
def generate_forensic_report(company, ticker, xbrl_table, notes_summary, api_key):
    prompt = f"""SYSTEM ROLE:
You are a strict, quantitative security analyst and forensic auditor, operating on the principles of Benjamin Graham and David Dodd. Your job is to extract the mathematical truth of a company's earning power and financial integrity — cutting through accounting noise to tell an investor exactly what is really going on.

YOUR DIRECTIVE:
Analyze the last 5 years of financial data for {company} ({ticker}). Systematically dismantle the reported income account and recalculate true economic reality using the forensic tests below. Where Graham refers to the "Surplus Account," scrutinize Retained Earnings and Accumulated OCI for buried losses.

EXECUTION STEPS (perform all calculations in the scratchpad):

1. Tax-Accrual Sanity Check: Calculate implied taxable profit from tax accrued (Tax Expense ÷ effective rate). Compare with reported pre-tax income. Flag wide divergences.

2. Normalizing the Income Account: Strip nonrecurrent items. Average any extraordinary write-downs over the full period, even if buried below the line or in equity.

3. Total-Deductions Coverage: Combine interest expense + preferred dividends + one-third of annual lease/rental expense. Calculate coverage ratio against normalized operating income.

4. Debt-to-Equity Safety: Calculate equity cushion vs total funded debt (long-term debt).

5. Depreciation Manipulation: Calculate implied depreciation rate (D&A ÷ Gross PP&E) each year. If the rate drops without justification, recalculate using the historical average and note the earnings inflation.

6. Forensic Red Flags:
   a. Capitalizing Operating Expenses: Flag persistent NI vs CFO divergence. Check for intangible/capitalized software spikes.
   b. Revenue Front-Running: If Accounts Receivable grows significantly faster than Revenue over multiple years, note the implied earnings quality risk.
   c. Pension Return Fictions: If assumed return on plan assets is disclosed and appears disconnected from current bond yields, flag the illusionary profit component.
   d. Off-Balance Sheet (SPVs/VIEs): Note any guaranteed obligations or unconsolidated entities that should be considered.

REQUIRED OUTPUT FORMAT:

First, open a <forensic_scratchpad> block. Show all raw numbers pulled from the data, step-by-step arithmetic for each test above, and write "DATA INSUFFICIENT" where a variable is missing. Be explicit with every calculation.

Then write a Forensic Analysis Report — written in plain English for a sophisticated but non-technical investor. The report must explain what each finding actually means in practice, not just state a number. Structure it as:

## Earnings Quality
Explain whether reported earnings are a reliable measure of the company's true earning power. Cover normalized earnings, the tax sanity check result, and NI vs CFO divergence. Write at least 3 substantial paragraphs.

## Accounting Integrity
Explain what the notes to the financial statements reveal. Cover any policy changes, unusual capitalizations, changes in useful life estimates, or revenue recognition concerns. Write at least 2 substantial paragraphs.

## Balance Sheet & Debt Safety
Explain the company's debt position, coverage ratios, and whether the balance sheet has been obscured by off-balance sheet items or operating lease commitments. Write at least 2 substantial paragraphs.

## Red Flags & Anomalies
Summarise the most important discrepancies found — depreciation manipulation, buried OCI losses, receivables front-running, pension fictions, or auditor qualifications. If none were found, say so explicitly and explain why the data is clean. Write at least 2 substantial paragraphs.

## Summary
A concise 1-paragraph summary of the overall picture: is this a company with transparent, reliable financials, or are there material concerns an investor must investigate further? Do not comment on valuation.

=== 5-YEAR QUANTITATIVE DATA (USD) ===
{xbrl_table}

=== NOTES TO FINANCIAL STATEMENTS — FORENSIC SIGNALS (5 YEARS) ===
{notes_summary}"""
    return _call_nvidia([{"role": "user", "content": prompt}], api_key, max_tokens=32000)
