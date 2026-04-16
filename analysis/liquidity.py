import pandas as pd


def _get(d, yr):
    """Safely pull a float from a year-keyed XBRL dict."""
    if not d or yr not in d:
        return None
    v = d[yr]
    try:
        f = float(v)
        return None if pd.isna(f) else f
    except (TypeError, ValueError):
        return None


def _s(series, i):
    """Safely pull float from a pandas Series by position."""
    try:
        v = float(series.iloc[i])
        return None if pd.isna(v) else v
    except (IndexError, TypeError, ValueError):
        return None


def compute_liquidity(years, oi_s, rev_s, ca_s, cl_s, inv_s, price_s, shares_s, xbrl):
    """
    Compute all liquidity & solvency metrics for each year.

    Parameters
    ----------
    years      : list[str]  fiscal year labels
    oi_s       : pd.Series  operating income / EBIT (ROIC)
    rev_s      : pd.Series  revenue (ROIC)
    ca_s       : pd.Series  current assets (ROIC balance sheet)
    cl_s       : pd.Series  current liabilities (ROIC balance sheet)
    inv_s      : pd.Series  inventory (ROIC balance sheet)
    price_s    : pd.Series  year-end price (computed in company page)
    shares_s   : pd.Series  diluted shares outstanding
    xbrl       : dict       output of fetch_liquidity_xbrl()

    Returns
    -------
    dict of lists, one value per year position.
    """
    n = len(years)

    cash_d      = xbrl.get("cash",           {})
    st_debt_d   = xbrl.get("st_debt",        {})
    ltd_cur_d   = xbrl.get("ltd_current",    {})
    ltd_nc_d    = xbrl.get("ltd_noncurrent", {})
    ta_d        = xbrl.get("total_assets",   {})
    tl_d        = xbrl.get("total_liab",     {})
    int_d       = xbrl.get("interest_exp",   {})
    da_d        = xbrl.get("da",             {})
    re_d        = xbrl.get("retained_earnings", {})

    (cash_l, st_l, ltd_c_l, ltd_nc_l, total_debt_l, net_debt_l,
     ta_l, tl_l, int_l, da_l, ebitda_l,
     icr_l, nd_ebitda_l, de_l, eff_rate_l,
     curr_l, quick_l, re_l, mc_l, altman_l,
     z1_l, z2_l, z3_l, z4_l, z5_l) = [[] for _ in range(25)]

    for i, yr in enumerate(years):
        cash   = _get(cash_d,    yr)
        st_d   = _get(st_debt_d, yr)
        ltd_c  = _get(ltd_cur_d, yr)
        ltd_nc = _get(ltd_nc_d,  yr)
        ta     = _get(ta_d,      yr)
        tl     = _get(tl_d,      yr)
        intr   = _get(int_d,     yr)
        da     = _get(da_d,      yr)
        re     = _get(re_d,      yr)
        oi     = _s(oi_s,     i)
        rev    = _s(rev_s,    i)
        ca     = _s(ca_s,     i)
        cl     = _s(cl_s,     i)
        inv    = _s(inv_s,    i)
        px     = _s(price_s,  i)
        sh     = _s(shares_s, i)

        if intr is not None: intr = abs(intr)
        if da   is not None: da   = abs(da)
        if cash is not None: cash = abs(cash)

        # ── Total debt ──────────────────────────────────────────────────────────
        parts = [abs(v) for v in [st_d, ltd_c, ltd_nc] if v is not None]
        total_debt = sum(parts) if parts else None

        # ── Net debt ────────────────────────────────────────────────────────────
        net_debt = (total_debt - cash) if (total_debt is not None and cash is not None) else None

        # ── Market cap ──────────────────────────────────────────────────────────
        mc = (px * sh) if (px and sh) else None

        # ── EBITDA ──────────────────────────────────────────────────────────────
        ebitda = None
        if oi is not None and da is not None:
            ebitda = oi + da
        elif oi is not None:
            ebitda = oi

        # ── Interest coverage ratio ─────────────────────────────────────────────
        icr = (oi / intr) if (oi is not None and intr and intr > 0) else None

        # ── Net Debt / EBITDA ───────────────────────────────────────────────────
        nd_ebitda = (net_debt / ebitda) if (net_debt is not None and ebitda and ebitda > 0) else None

        # ── Debt / Equity ───────────────────────────────────────────────────────
        equity = (ta - tl) if (ta is not None and tl is not None) else None
        de = (total_debt / equity) if (total_debt is not None and equity and equity > 0) else None

        # ── Effective interest rate ─────────────────────────────────────────────
        eff_rate = (intr / total_debt * 100) if (intr is not None and total_debt and total_debt > 0) else None

        # ── Liquidity ratios ────────────────────────────────────────────────────
        curr  = (ca / cl) if (ca is not None and cl is not None and cl > 0) else None
        quick = ((ca - (inv or 0)) / cl) if (ca is not None and cl is not None and cl > 0) else None

        # ── Altman Z-Score (Altman 1968 — public manufacturing) ────────────────
        # Z = 1.2(WC/TA) + 1.4(RE/TA) + 3.3(EBIT/TA) + 0.6(MC/TL) + 1.0(Rev/TA)
        z1 = z2 = z3 = z4 = z5 = altman = None
        if ca is not None and cl is not None and ta and oi is not None and rev is not None:
            wc    = ca - cl
            re_v  = re    if re is not None else 0.0
            mc_v  = mc    if mc is not None else 0.0
            tl_v  = tl    if (tl is not None and tl > 0) else (ta * 0.5)

            z1 = 1.2  * (wc   / ta)
            z2 = 1.4  * (re_v / ta)
            z3 = 3.3  * (oi   / ta)
            z4 = 0.6  * (mc_v / tl_v) if tl_v > 0 else 0.0
            z5 = 1.0  * (rev  / ta)
            altman = z1 + z2 + z3 + z4 + z5

        cash_l.append(cash);    st_l.append(st_d);      ltd_c_l.append(ltd_c)
        ltd_nc_l.append(ltd_nc); total_debt_l.append(total_debt)
        net_debt_l.append(net_debt); ta_l.append(ta);   tl_l.append(tl)
        int_l.append(intr);     da_l.append(da);         ebitda_l.append(ebitda)
        icr_l.append(icr);      nd_ebitda_l.append(nd_ebitda)
        de_l.append(de);        eff_rate_l.append(eff_rate)
        curr_l.append(curr);    quick_l.append(quick)
        re_l.append(re);        mc_l.append(mc);         altman_l.append(altman)
        z1_l.append(z1);        z2_l.append(z2);         z3_l.append(z3)
        z4_l.append(z4);        z5_l.append(z5)

    return {
        "cash":            cash_l,
        "st_debt":         st_l,
        "ltd_current":     ltd_c_l,
        "ltd_noncurrent":  ltd_nc_l,
        "total_debt":      total_debt_l,
        "net_debt":        net_debt_l,
        "total_assets":    ta_l,
        "total_liab":      tl_l,
        "interest_exp":    int_l,
        "da":              da_l,
        "ebitda":          ebitda_l,
        "icr":             icr_l,
        "nd_ebitda":       nd_ebitda_l,
        "de_ratio":        de_l,
        "eff_rate":        eff_rate_l,
        "current_ratio":   curr_l,
        "quick_ratio":     quick_l,
        "retained_earnings": re_l,
        "market_cap":      mc_l,
        "altman_z":        altman_l,
        "z1": z1_l, "z2": z2_l, "z3": z3_l, "z4": z4_l, "z5": z5_l,
    }


def altman_zone(z):
    """Return (label, color) for an Altman Z-Score."""
    if z is None:
        return "N/A", "#999999"
    if z >= 2.99:
        return "Safe Zone", "#1A7F4B"
    if z >= 1.81:
        return "Grey Zone", "#D4800A"
    return "Distress Zone", "#C0392B"
