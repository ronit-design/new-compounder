import re
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from config import (C_ACCENT, C_DOWN, C_UP, C_BORDER, C_BORDER2,
                    C_TEXT, C_TEXT3, CHART_BASE)
from data.fetchers import (fetch_fundamental, fetch_prices,
                            fetch_year_end_price, fetch_annual_average_prices,
                            fetch_last_4_transcripts, format_financials_for_prompt)
from data.edgar import (edgar_get_cik, edgar_list_annual_filings,
                         fetch_rsu_tax_xbrl, fetch_forensic_xbrl, fetch_10k_text)
from analysis.forensic import (build_forensic_dataset, _fmt_xbrl_table,
                                _fetch_notes_concurrent, _extract_signals_concurrent,
                                _fmt_notes_signals, generate_forensic_report)
from analysis.research import generate_report_nvidia, generate_report_haiku
from reports.pdf import build_report_pdf
from ui.components import kpi_block, make_bar, make_line
from utils import (safe, align, latest, prev, yoy, ccy_symbol,
                   fmt_currency, fmt_pct, fmt_multiple, fmt_eps, to_pct_list)


WATCHLIST_FE = {
    "RYAAY": 3, "CPRT": 7, "CSU.TO": 12,
    "FICO": 9, "SPGI": 12, "MCO": 12, "ASML": 12,
}


def render_company(ticker, company):
    fe_month = WATCHLIST_FE.get(ticker, 12)

    with st.spinner(f"Loading {ticker}..."):
        inc = fetch_fundamental("fundamental/income-statement", ticker)
        bs  = fetch_fundamental("fundamental/balance-sheet",    ticker)
        cf  = fetch_fundamental("fundamental/cash-flow",        ticker)

    if inc.empty:
        st.error(f"No data returned for {ticker}. Check the ticker is correct and listed on a supported exchange.")
        st.stop()

    years    = inc["Date"].dt.year.astype(str).tolist() if "Date" in inc.columns else [str(i) for i in range(len(inc))]
    cf_years = cf["Date"].dt.year.astype(str).tolist()  if not cf.empty and "Date" in cf.columns else years
    n        = len(years)

    ccy_code = str(inc["currency"].iloc[-1]) if "currency" in inc.columns and len(inc) > 0 else "USD"
    ccy      = ccy_symbol(ccy_code)

    rev_s    = align(safe(inc, "is_sales_revenue_turnover", "is_sales_and_services_revenues"), n)
    ni_s     = align(safe(inc, "is_net_income", "is_ni_including_minority_int_ratio"), n)
    oi_s     = align(safe(inc, "ebit", "is_oper_income"), n)
    gp_s     = align(safe(inc, "is_gross_profit"), n)
    gm_s     = align(safe(inc, "gross_margin"), n)
    opm_s    = align(safe(inc, "oper_margin"), n)
    npm_s    = align(safe(inc, "profit_margin"), n)
    eps_s    = align(safe(inc, "diluted_eps", "eps"), n)
    shares_s = align(safe(inc, "is_sh_for_diluted_eps", "is_avg_num_sh_for_eps"), n)
    cogs_s   = align(safe(inc, "is_cogs", "is_cog_and_services_sold"), n)

    price_series, price_years = fetch_year_end_price(ticker, fe_month)
    price_s = pd.Series([
        float(price_series.loc[int(y)]) if not price_series.empty and int(y) in price_series.index else float("nan")
        for y in years
    ], dtype=float)

    n_cf  = len(cf) if not cf.empty else 0
    fcf_s = align(safe(cf, "cf_free_cash_flow") if n_cf else pd.Series(dtype=float), n)
    cfo_s = align(safe(cf, "cf_cash_from_oper") if n_cf else pd.Series(dtype=float), n)

    avg_price_s = fetch_annual_average_prices(ticker, inc["Date"]) if "Date" in inc.columns else pd.Series([None] * n)

    _cf = lambda *cols: align(safe(cf, *cols) if n_cf else pd.Series(dtype=float), n)
    sbc_s      = _cf("cf_stock_based_compensation")
    incr_cap_s = _cf("cf_incr_cap_stock")
    decr_cap_s = _cf("cf_decr_cap_stock")
    rsu_tax_s  = _cf("cf_taxes_related_to_net_share_settlement", "cf_taxes_net_share_settlement",
                      "cf_payment_for_taxes_net_share_settlement", "cf_employee_withholding_taxes")

    bs_years = bs["Date"].dt.year.astype(str).tolist() if not bs.empty and "Date" in bs.columns else years
    n_bs  = len(bs) if not bs.empty else 0
    nd_s  = align(safe(bs, "net_debt") if n_bs else pd.Series(dtype=float), n)
    ar_s  = safe(bs, "bs_acct_note_rcv", "bs_accts_rec_excl_notes_rec") if n_bs else pd.Series(dtype=float)
    inv_s = safe(bs, "bs_inventories")  if n_bs else pd.Series(dtype=float)
    ap_s  = safe(bs, "bs_acct_payable") if n_bs else pd.Series(dtype=float)
    ca_s  = safe(bs, "bs_cur_asset_report") if n_bs else pd.Series(dtype=float)
    cl_s  = safe(bs, "bs_cur_liab")     if n_bs else pd.Series(dtype=float)

    rev_list   = rev_s.tolist()
    rev_growth = [None] + [
        (rev_list[i] - rev_list[i-1]) / abs(rev_list[i-1]) * 100
        if (rev_list[i] and rev_list[i-1] and rev_list[i-1] != 0
            and not pd.isna(rev_list[i]) and not pd.isna(rev_list[i-1]))
        else None
        for i in range(1, len(rev_list))
    ]

    rev_l = latest(rev_s); rev_p = prev(rev_s)
    fcf_l = latest(fcf_s); fcf_p = prev(fcf_s)
    eps_l = latest(eps_s); eps_p = prev(eps_s)
    opm_l = latest(opm_s)
    npm_l = latest(npm_s)
    gm_l  = latest(gm_s)

    st.markdown(f'<div class="page-title">{company}</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="page-sub">{ticker}</div>', unsafe_allow_html=True)

    k1, k2, k3, k4, k5, k6 = st.columns(6)
    kpi_block(k1, "Revenue",          fmt_currency(rev_l, ccy), yoy(rev_l, rev_p))
    kpi_block(k2, "Free Cash Flow",   fmt_currency(fcf_l, ccy), yoy(fcf_l, fcf_p))
    kpi_block(k3, "Gross Margin",     fmt_pct(gm_l))
    kpi_block(k4, "Operating Margin", fmt_pct(opm_l))
    kpi_block(k5, "Net Margin",       fmt_pct(npm_l))
    kpi_block(k6, "EPS",              fmt_eps(eps_l, ccy), yoy(eps_l, eps_p))

    st.markdown("<br>", unsafe_allow_html=True)
    tab1, tab2, tab3, tab4, tab5, tab6, tab7, tab8 = st.tabs([
        "Revenue", "Margins", "Cash Flow", "Valuation",
        "Working Capital", "Owners' Earnings", "Forensic Accounting", "Research Report",
    ])

    # ── Tab 1: Revenue ─────────────────────────────────────────────────────────
    with tab1:
        c1, c2 = st.columns(2, gap="large")
        with c1:
            vals_b = [v/1e9 if v and not pd.isna(v) else None for v in rev_s]
            st.plotly_chart(make_bar(years, vals_b, "Revenue  ($B)", height=260),
                            use_container_width=True, config={"displayModeBar": False})
        with c2:
            st.plotly_chart(make_bar(years, rev_growth, "Revenue Growth  (%)", height=260, color="#555555"),
                            use_container_width=True, config={"displayModeBar": False})

        st.markdown("<br>", unsafe_allow_html=True)
        c3, c4 = st.columns(2, gap="large")
        with c3:
            ni_b = [v/1e9 if v and not pd.isna(v) else None for v in ni_s]
            st.plotly_chart(make_bar(years, ni_b, "Net Income  ($B)", height=260),
                            use_container_width=True, config={"displayModeBar": False})
        with c4:
            st.plotly_chart(make_bar(years, eps_s.tolist(), "EPS  ($)", height=260, color="#555555"),
                            use_container_width=True, config={"displayModeBar": False})

    # ── Tab 2: Margins ─────────────────────────────────────────────────────────
    with tab2:
        gm_pct  = to_pct_list(gm_s)
        opm_pct = to_pct_list(opm_s)
        npm_pct = to_pct_list(npm_s)

        fig_mg = make_line(years, [gm_pct, opm_pct, npm_pct],
                           ["Gross", "Operating", "Net"], "Profit Margins  (%)", height=340, suffix="%")
        fig_mg.update_layout(yaxis=dict(ticksuffix="%", showgrid=True, gridcolor=C_BORDER2,
                                        tickfont=dict(size=10, color=C_TEXT3), zeroline=False, showline=False))
        st.plotly_chart(fig_mg, use_container_width=True, config={"displayModeBar": False})

        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown('<span class="section-label">Historical</span>', unsafe_allow_html=True)
        margin_df = pd.DataFrame({
            "Metric": ["Gross Margin", "Operating Margin", "Net Margin"],
            **{y: [
                f"{gm_pct[i]:.1f}%"  if gm_pct[i]  else "—",
                f"{opm_pct[i]:.1f}%" if opm_pct[i] else "—",
                f"{npm_pct[i]:.1f}%" if npm_pct[i] else "—",
            ] for i, y in enumerate(years)}
        }).set_index("Metric")
        st.dataframe(margin_df, use_container_width=True)

    # ── Tab 3: Cash Flow ───────────────────────────────────────────────────────
    with tab3:
        c1, c2 = st.columns(2, gap="large")
        with c1:
            if fcf_s.notna().any():
                fcf_b   = [v/1e9 if v and not pd.isna(v) else None for v in fcf_s]
                fig_fcf = make_bar(cf_years, fcf_b, f"Free Cash Flow  ({ccy_code}, B)", height=260)
                fig_fcf.update_layout(yaxis=dict(showgrid=True, gridcolor=C_BORDER2, tickprefix=ccy,
                                                  ticksuffix="B", tickfont=dict(size=10, color=C_TEXT3),
                                                  zeroline=False, showline=True, linecolor=C_BORDER))
                st.plotly_chart(fig_fcf, use_container_width=True, config={"displayModeBar": False})
            else:
                st.markdown('<span style="color:#999;font-size:0.82rem">No free cash flow data</span>',
                            unsafe_allow_html=True)
        with c2:
            if cfo_s.notna().any():
                cfo_b   = [v/1e9 if v and not pd.isna(v) else None for v in cfo_s]
                fig_cfo = make_bar(cf_years, cfo_b, f"Operating Cash Flow  ({ccy_code}, B)", height=260, color="#555555")
                fig_cfo.update_layout(yaxis=dict(showgrid=True, gridcolor=C_BORDER2, tickprefix=ccy,
                                                  ticksuffix="B", tickfont=dict(size=10, color=C_TEXT3),
                                                  zeroline=False, showline=True, linecolor=C_BORDER))
                st.plotly_chart(fig_cfo, use_container_width=True, config={"displayModeBar": False})

        if fcf_s.notna().any() and ni_s.notna().any():
            st.markdown("<br>", unsafe_allow_html=True)
            min_len = min(len(fcf_s), len(ni_s))
            fig_cmp = make_line(
                years[-min_len:],
                [[v/1e9 if v and not pd.isna(v) else None for v in fcf_s.tolist()[-min_len:]],
                 [v/1e9 if v and not pd.isna(v) else None for v in ni_s.tolist()[-min_len:]]],
                ["Free Cash Flow", "Net Income"],
                "FCF vs Net Income  ($B)", height=300,
            )
            st.plotly_chart(fig_cmp, use_container_width=True, config={"displayModeBar": False})

    # ── Tab 4: Valuation ───────────────────────────────────────────────────────
    with tab4:
        if price_s.notna().any():
            fig_px = make_line(years, [price_s.tolist()], ["Price"],
                               "Year-End Stock Price  ($)", height=300)
            fig_px.update_layout(yaxis=dict(tickprefix=ccy, showgrid=True, gridcolor=C_BORDER2,
                                            tickfont=dict(size=10, color=C_TEXT3), zeroline=False,
                                            showline=True, linecolor=C_BORDER))
            st.plotly_chart(fig_px, use_container_width=True, config={"displayModeBar": False})
        else:
            with st.spinner(""):
                prices = fetch_prices(ticker)
            if not prices.empty:
                close_col = next((c for c in ["adj_close", "adjusted_close", "close"]
                                  if c in prices.columns), prices.columns[1])
                fig_px = go.Figure(go.Scatter(
                    x=prices["date"], y=prices[close_col], mode="lines", name="Price",
                    line=dict(color=C_ACCENT, width=1.5),
                    hovertemplate="%{x|%d %b %Y}<br>$%{y:.2f}<extra></extra>",
                ))
                fig_px.update_layout(**CHART_BASE)
                fig_px.update_layout(height=300, showlegend=False,
                    yaxis=dict(tickprefix=ccy, showgrid=True, gridcolor=C_BORDER2,
                               tickfont=dict(size=10, color=C_TEXT3), zeroline=False,
                               showline=True, linecolor=C_BORDER))
                st.plotly_chart(fig_px, use_container_width=True, config={"displayModeBar": False})
            else:
                st.markdown('<span style="color:#999;font-size:0.82rem">Price data not available.</span>',
                            unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown('<span class="section-label">Multiples</span>', unsafe_allow_html=True)

        pe_list, pfcf_list, evebit_list = [], [], []
        for i in range(len(years)):
            def _g(s):
                return float(s.iloc[i]) if i < len(s) and pd.notna(s.iloc[i]) else None
            price = _g(price_s); eps = _g(eps_s); fcf = _g(fcf_s)
            ebit  = _g(oi_s);    nd  = _g(nd_s);  sh  = _g(shares_s)

            try:    pe_list.append(price / eps if price and eps and eps != 0 else None)
            except: pe_list.append(None)

            try:
                mc = price * sh if price and sh else None
                pfcf_list.append(mc / fcf if mc and fcf and fcf > 0 else None)
            except: pfcf_list.append(None)

            try:
                mc = price * sh if price and sh else None
                ev = (mc + nd) if mc and nd else mc
                evebit_list.append(ev / ebit if ev and ebit and ebit > 0 else None)
            except: evebit_list.append(None)

        val_ys, val_names = [], []
        if any(v for v in pe_list     if v): val_ys.append(pe_list);     val_names.append("P/E")
        if any(v for v in pfcf_list   if v): val_ys.append(pfcf_list);   val_names.append("P/FCF")
        if any(v for v in evebit_list if v): val_ys.append(evebit_list); val_names.append("EV/EBIT")

        if val_ys:
            fig_v = make_line(years, val_ys, val_names, "Valuation Multiples", height=300, suffix="x")
            st.plotly_chart(fig_v, use_container_width=True, config={"displayModeBar": False})

            val_display = pd.DataFrame({
                "Metric": val_names,
                **{y: [val_ys[j][i] if val_ys[j][i] else None for j in range(len(val_names))]
                   for i, y in enumerate(years)}
            }).set_index("Metric")
            val_display = val_display.map(lambda v: fmt_multiple(v) if v else "—")
            st.dataframe(val_display, use_container_width=True)
        else:
            st.markdown('<span style="color:#999;font-size:0.82rem">Stock price required to calculate multiples.</span>',
                        unsafe_allow_html=True)

    # ── Tab 5: Working Capital ─────────────────────────────────────────────────
    with tab5:
        def days(numerator_s, denominator_s):
            n_s = pd.to_numeric(numerator_s,   errors="coerce").reset_index(drop=True)
            d_s = pd.to_numeric(denominator_s, errors="coerce").reset_index(drop=True)
            n_s = n_s.iloc[:len(bs_years)]
            d_s = d_s.iloc[:len(bs_years)]
            return (n_s / d_s.where(d_s > 0)) * 365

        dso_s  = days(ar_s,  rev_s)
        inv_s_ = days(inv_s, cogs_s)
        dpo_s  = days(ap_s,  cogs_s)

        ccc_full   = dso_s + inv_s_ - dpo_s
        ccc_no_inv = dso_s - dpo_s
        ccc_s      = ccc_full.where(inv_s_.notna(), ccc_no_inv)
        ccc_s      = ccc_s.where(dso_s.notna() & dpo_s.notna())

        ca    = pd.to_numeric(ca_s, errors="coerce").reset_index(drop=True).iloc[:len(bs_years)]
        cl    = pd.to_numeric(cl_s, errors="coerce").reset_index(drop=True).iloc[:len(bs_years)]
        nwc_s = (ca - cl).where(ca.notna() & cl.notna())

        def _to_list(s):
            return [None if pd.isna(v) else float(v) for v in s]

        dso_list  = _to_list(dso_s)
        inv_list  = _to_list(inv_s_)
        dpo_list  = _to_list(dpo_s)
        ccc_list  = _to_list(ccc_s)
        nwc_list  = _to_list(nwc_s)

        def latest_days(lst):
            vals = [v for v in lst if v is not None]
            return vals[-1] if vals else None

        def fmt_days(val):
            if val is None: return "—"
            return f"{val:.0f} days"

        def fmt_days_delta(lst):
            vals = [v for v in lst if v is not None]
            if len(vals) < 2: return None
            return vals[-1] - vals[-2]

        w1, w2, w3, w4, w5 = st.columns(5)
        dso_l = latest_days(dso_list)
        inv_l = latest_days(inv_list)
        dpo_l = latest_days(dpo_list)
        ccc_l = latest_days(ccc_list)
        nwc_l = latest(pd.Series(nwc_list, dtype=float))

        def wc_kpi(col, label, val_str, delta_days=None):
            if delta_days is not None:
                sign   = "+" if delta_days >= 0 else ""
                cls    = "delta-up" if delta_days <= 0 else "delta-down"
                d_html = f'<span class="metric-delta {cls}">{sign}{delta_days:.0f} days YoY</span>'
            else:
                d_html = ""
            col.markdown(
                f'<div class="metric-block"><div class="metric-label">{label}</div>'
                f'<div class="metric-value">{val_str}</div>{d_html}</div>',
                unsafe_allow_html=True,
            )

        wc_kpi(w1, "DSO",            fmt_days(dso_l), fmt_days_delta(dso_list))
        wc_kpi(w2, "Inventory Days", fmt_days(inv_l), fmt_days_delta(inv_list))
        wc_kpi(w3, "DPO",            fmt_days(dpo_l), fmt_days_delta(dpo_list))
        wc_kpi(w4, "Cash Cycle",     fmt_days(ccc_l), fmt_days_delta(ccc_list))
        wc_kpi(w5, "NWC (Latest)",   fmt_currency(nwc_l, ccy))

        st.markdown("<br>", unsafe_allow_html=True)

        days_ys, days_names = [], []
        if any(v for v in dso_list if v is not None):  days_ys.append(dso_list);  days_names.append("DSO")
        if any(v for v in inv_list if v is not None):  days_ys.append(inv_list);  days_names.append("Inventory Days")
        if any(v for v in dpo_list if v is not None):  days_ys.append(dpo_list);  days_names.append("DPO")
        if any(v for v in ccc_list if v is not None):  days_ys.append(ccc_list);  days_names.append("Cash Cycle")

        if days_ys:
            fig_wc = make_line(bs_years, days_ys, days_names, "Working Capital Days", height=320, suffix=" days")
            fig_wc.update_layout(yaxis=dict(ticksuffix=" d", showgrid=True, gridcolor=C_BORDER2,
                                            tickfont=dict(size=10, color=C_TEXT3), zeroline=True,
                                            zerolinecolor=C_BORDER, showline=False))
            st.plotly_chart(fig_wc, use_container_width=True, config={"displayModeBar": False})
        else:
            st.markdown('<span style="color:#999;font-size:0.82rem">Insufficient balance sheet data.</span>',
                        unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)
        if any(v for v in nwc_list if v is not None):
            fig_nwc = make_bar(bs_years,
                               [v/1e9 if v is not None else None for v in nwc_list],
                               f"Net Working Capital  ({ccy_code}, B)", height=260)
            fig_nwc.update_layout(yaxis=dict(tickprefix=ccy, ticksuffix="B", showgrid=True,
                                             gridcolor=C_BORDER2, tickfont=dict(size=10, color=C_TEXT3),
                                             zeroline=True, zerolinecolor=C_BORDER, showline=False))
            st.plotly_chart(fig_nwc, use_container_width=True, config={"displayModeBar": False})

        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown('<span class="section-label">Historical</span>', unsafe_allow_html=True)
        _wc_n = min(len(bs_years), len(dso_list), len(inv_list),
                    len(dpo_list), len(ccc_list), len(nwc_list))
        wc_display = pd.DataFrame({
            "Metric": ["DSO", "Inventory Days", "DPO", "Cash Cycle", "NWC"],
            **{bs_years[i]: [
                fmt_days(dso_list[i]), fmt_days(inv_list[i]), fmt_days(dpo_list[i]),
                fmt_days(ccc_list[i]), fmt_currency(nwc_list[i], ccy),
            ] for i in range(_wc_n)}
        }).set_index("Metric")
        st.dataframe(wc_display, use_container_width=True)

    # ── Tab 6: Owners' Earnings ────────────────────────────────────────────────
    with tab6:
        def _v(s, i):
            try:
                v = s.iloc[i]
                return float(v) if pd.notna(v) else None
            except: return None

        def _absv(s, i):
            v = _v(s, i)
            return abs(v) if v is not None else None

        sh_s     = pd.to_numeric(shares_s, errors="coerce").reset_index(drop=True)
        sh_list  = sh_s.tolist()
        dil_list = [None] + [None if pd.isna(v) else float(v)
                             for v in (sh_s.pct_change() * 100).iloc[1:]]
        ni_list  = [None if pd.isna(v) else float(v)
                    for v in pd.to_numeric(ni_s, errors="coerce")]

        decr_v     = pd.to_numeric(decr_cap_s, errors="coerce").abs().reset_index(drop=True)
        incr_v     = pd.to_numeric(incr_cap_s, errors="coerce").abs().reset_index(drop=True)
        both_miss  = decr_v.isna() & incr_v.isna()
        net_bb_vec = (decr_v.fillna(0) - incr_v.fillna(0)).where(~both_miss)
        net_bb_list = [None if pd.isna(v) else float(v) for v in net_bb_vec]

        px_avg_vals   = avg_price_s.tolist()
        maint_bb_vals = []
        for i in range(len(years)):
            bb_net  = net_bb_list[i] if net_bb_list[i] is not None else 0.0
            sh_curr = sh_list[i]
            sh_prev = sh_list[i-1] if i > 0 else sh_curr
            px_avg  = px_avg_vals[i]
            if pd.notna(sh_curr) and pd.notna(sh_prev) and pd.notna(px_avg) and px_avg > 0:
                delta_shares  = sh_prev - sh_curr
                val_reduction = max(0, delta_shares) * px_avg
                maint_bb      = max(0, bb_net - val_reduction)
            else:
                maint_bb = max(0, bb_net)
            maint_bb_vals.append(maint_bb)

        maint_bb_vec = pd.Series(maint_bb_vals, dtype=float)
        ni_vec  = pd.to_numeric(ni_s,  errors="coerce").reset_index(drop=True)
        sbc_vec = pd.to_numeric(sbc_s, errors="coerce").abs().reset_index(drop=True)

        sec_rsu_data = st.session_state.get(f"rsu_tax_{ticker}", {})
        if sec_rsu_data:
            rsu_sec_s       = pd.Series(sec_rsu_data, dtype=float)
            rsu_sec_s.index = rsu_sec_s.index.astype(str)
            years_idx       = pd.Index([str(y) for y in years])
            rsu_sec_aligned = rsu_sec_s.reindex(years_idx).values
            rsu_sec_vec     = pd.Series(rsu_sec_aligned).abs().reset_index(drop=True)
        else:
            rsu_sec_vec = pd.Series([None] * len(years), dtype=float)

        rsu_roic_vec = pd.to_numeric(rsu_tax_s, errors="coerce").abs().reset_index(drop=True)
        rsu_vec      = rsu_sec_vec.combine_first(rsu_roic_vec)

        oe_vec  = (ni_vec + sbc_vec.fillna(0) - maint_bb_vec.fillna(0) - rsu_vec.fillna(0)).where(ni_vec.notna())
        oe_list = [None if pd.isna(v) else float(v) for v in oe_vec]

        latest_oe   = next((v for v in reversed(oe_list)       if v is not None), None)
        latest_ni   = next((v for v in reversed(ni_list)       if v is not None), None)
        latest_dil  = next((v for v in reversed(dil_list)      if v is not None), None)
        latest_m_bb = next((v for v in reversed(maint_bb_vals) if v is not None), None)

        oe_pct_gaap = (latest_oe / latest_ni * 100) if (latest_oe and latest_ni and latest_ni != 0) else None

        st.markdown(
            '<div style="font-size:0.78rem;color:#777;line-height:1.7;margin-bottom:1.2rem;max-width:780px">'
            'Owners\' Earnings adjusts GAAP net income for the <em>true</em> economic cost of stock-based compensation. '
            'GAAP adds back SBC as a non-cash item in operating cash flow — but the real cost is the cash spent on '
            'buybacks to prevent dilution, plus RSU tax withholding payments.<br><br>'
            'Formula: <strong>Net Income + GAAP SBC − Maintenance Buybacks − RSU Tax Withholdings</strong>.<br>'
            '<em>Maintenance Buybacks</em> isolates the cash spent specifically to offset employee stock issuance dilution. '
            'Calculated as Total Net Buybacks minus the actual dollar value of the net share reduction using VWAP.'
            '</div>', unsafe_allow_html=True)

        rsu_cache_key = f"rsu_tax_{ticker}"
        sec_rsu       = st.session_state.get(rsu_cache_key, {})
        _has_suffix   = bool(re.search(r"[.][A-Z]{1,4}$", ticker.upper()))

        _rc1, _rc2 = st.columns([2, 5])
        with _rc1:
            _fetch_btn = st.button(
                "Fetch RSU Tax from SEC (XBRL)",
                disabled=_has_suffix,
                help=("Pulls RSU tax withholding directly from EDGAR's structured XBRL data. "
                      "Instant, no AI needed. US-listed tickers only."
                      if not _has_suffix else "SEC EDGAR only covers US-listed tickers."),
            )
        with _rc2:
            if _has_suffix:
                st.markdown('<span style="font-size:0.72rem;color:#999">SEC EDGAR not available for non-US tickers.</span>',
                            unsafe_allow_html=True)
            elif sec_rsu:
                years_found = sorted(sec_rsu.keys())
                _is_net_loaded = st.session_state.get(f"{rsu_cache_key}_net", False)
                _net_note = " (net figure — withholding minus option proceeds)" if _is_net_loaded else ""
                st.markdown(f'<span style="font-size:0.72rem;color:{C_UP}">XBRL data loaded for: {", ".join(years_found)}{_net_note}</span>',
                            unsafe_allow_html=True)
            else:
                st.markdown('<span style="font-size:0.72rem;color:#999">RSU tax withholdings not yet fetched — click to pull from EDGAR XBRL data.</span>',
                            unsafe_allow_html=True)

        if _fetch_btn:
            try:
                with st.spinner("Fetching XBRL data from EDGAR..."):
                    _fetched = fetch_rsu_tax_xbrl(ticker)
                _is_net = _fetched.pop("_net_figure", False)
                st.session_state[rsu_cache_key] = _fetched
                st.session_state[f"{rsu_cache_key}_net"] = _is_net
                if _fetched:
                    years_str = ", ".join(sorted(_fetched.keys()))
                    if _is_net:
                        st.success(f"Found data for {len(_fetched)} years: {years_str}")
                        st.info(
                            "This company reports **net payments related to stock-based award activities** "
                            "(RSU tax withholdings net of stock option exercise proceeds). "
                            "The net figure is used as a proxy — gross withholding will be slightly higher.",
                            icon="ℹ️",
                        )
                    else:
                        st.success(f"Found RSU tax data for {len(_fetched)} years: {years_str}")
                else:
                    st.warning("No RSU tax withholding data found on EDGAR for this ticker.")
            except Exception as e:
                st.error(f"EDGAR fetch failed: {e}")
            st.rerun()

        st.markdown("<br>", unsafe_allow_html=True)

        ek1, ek2, ek3, ek4 = st.columns(4)

        def oe_kpi(col, label, val, sub=None, highlight=False):
            color = "#111" if not highlight else (
                C_UP if (val or "").startswith("+") or (val or "") not in ["—", ""] else C_DOWN
            )
            col.markdown(f"""
            <div class="metric-block">
                <div class="metric-label">{label}</div>
                <div class="metric-value" style="color:{color}">{val or "—"}</div>
                {"" if not sub else f'<div style="font-size:0.68rem;color:#999;margin-top:2px">{sub}</div>'}
            </div>""", unsafe_allow_html=True)

        oe_kpi(ek1, "Owners' Earnings",    fmt_currency(latest_oe, ccy), "latest year")
        oe_kpi(ek2, "OE as % of GAAP NI",  f"{oe_pct_gaap:.0f}%" if oe_pct_gaap else "—", "latest year")
        oe_kpi(ek3, "Annual Dilution",
               (f"+{latest_dil:.2f}%" if latest_dil and latest_dil >= 0 else f"{latest_dil:.2f}%")
               if latest_dil is not None else "—", "YoY share count change")
        oe_kpi(ek4, "Maintenance Buybacks", fmt_currency(latest_m_bb, ccy), "offsetting dilution")

        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown('<span class="section-label">Share Dilution</span>', unsafe_allow_html=True)

        c1, c2 = st.columns(2, gap="large")
        with c1:
            sh_b   = [v/1e6 if v and not pd.isna(v) else None for v in sh_list]
            fig_sh = make_bar(years, sh_b, "Shares Outstanding  (M)", height=260, color="#555555")
            fig_sh.update_layout(yaxis=dict(ticksuffix="M", showgrid=True, gridcolor=C_BORDER2,
                                            tickfont=dict(size=10, color=C_TEXT3), zeroline=False))
            st.plotly_chart(fig_sh, use_container_width=True, config={"displayModeBar": False})
        with c2:
            dil_colors = [C_DOWN if (v or 0) > 0 else C_UP for v in dil_list]
            fig_dil    = go.Figure(go.Bar(
                x=years, y=dil_list, marker_color=dil_colors, marker_line_width=0,
                hovertemplate="%{x}: %{y:.2f}%<extra></extra>",
            ))
            fig_dil.update_layout(**CHART_BASE)
            fig_dil.update_layout(
                height=260, title_text="Annual Dilution Rate  (%)",
                yaxis=dict(ticksuffix="%", showgrid=True, gridcolor=C_BORDER2,
                           tickfont=dict(size=10, color=C_TEXT3), zeroline=True, zerolinecolor=C_BORDER),
            )
            st.plotly_chart(fig_dil, use_container_width=True, config={"displayModeBar": False})

        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown('<span class="section-label">SBC Cost Analysis</span>', unsafe_allow_html=True)

        sbc_b      = [abs(_v(sbc_s, i))/1e9  if _v(sbc_s, i)  is not None else None for i in range(len(years))]
        maint_bb_b = [maint_bb_vals[i]/1e9   if maint_bb_vals[i] is not None else None for i in range(len(years))]
        rst_b      = [_absv(rsu_tax_s, i)/1e9 if _absv(rsu_tax_s, i) is not None else None for i in range(len(years))]

        has_sbc    = any(v is not None for v in sbc_b)
        has_net_bb = any(v is not None for v in maint_bb_b)
        has_rsu    = any(v is not None for v in rst_b)

        if has_sbc or has_net_bb:
            sbc_traces = []
            if has_sbc:
                sbc_traces.append(go.Bar(name="GAAP SBC Expense", x=years, y=sbc_b,
                                         marker_color="#AAAAAA", marker_line_width=0,
                                         hovertemplate="%{x}: " + ccy + "%{y:.2f}B<extra></extra>"))
            if has_net_bb:
                sbc_traces.append(go.Bar(name="Maintenance Buybacks", x=years, y=maint_bb_b,
                                         marker_color=C_DOWN, marker_line_width=0,
                                         hovertemplate="%{x}: " + ccy + "%{y:.2f}B<extra></extra>"))
            if has_rsu:
                sbc_traces.append(go.Bar(name="RSU Tax Withholdings", x=years, y=rst_b,
                                         marker_color="#8B1A1A", marker_line_width=0,
                                         hovertemplate="%{x}: " + ccy + "%{y:.2f}B<extra></extra>"))
            fig_sbc = go.Figure(data=sbc_traces)
            fig_sbc.update_layout(**CHART_BASE)
            fig_sbc.update_layout(
                height=300, barmode="group", title_text="GAAP SBC vs True SBC Cost  ($B)",
                legend=dict(orientation="h", y=1.08, x=0, font=dict(size=10)),
                yaxis=dict(tickprefix=ccy, ticksuffix="B", showgrid=True, gridcolor=C_BORDER2,
                           tickfont=dict(size=10, color=C_TEXT3), zeroline=True, zerolinecolor=C_BORDER),
            )
            st.plotly_chart(fig_sbc, use_container_width=True, config={"displayModeBar": False})
            if not has_rsu and not sec_rsu:
                st.markdown('<div style="font-size:0.72rem;color:#999;margin-top:-0.5rem">RSU tax withholding not in ROIC data — use "Fetch RSU Tax from SEC (XBRL)" above to load it from EDGAR.</div>',
                            unsafe_allow_html=True)
        else:
            st.markdown('<span style="color:#999;font-size:0.82rem">SBC and buyback data not available for this ticker.</span>',
                        unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown('<span class="section-label">Owners\' Earnings vs GAAP Net Income — Per Share</span>',
                    unsafe_allow_html=True)

        ni_ps_list, oe_ps_list = [], []
        for i in range(len(years)):
            ni     = ni_list[i]
            oe     = oe_list[i]
            sh_cur = sh_list[i]   if (i < len(sh_list) and sh_list[i] and not pd.isna(sh_list[i])) else None
            sh_prv = sh_list[i-1] if (i > 0 and sh_list[i-1] and not pd.isna(sh_list[i-1])) else sh_cur
            ni_ps_list.append(ni / sh_prv if (ni is not None and sh_prv) else None)
            oe_ps_list.append(oe / sh_cur  if (oe is not None and sh_cur)  else None)

        if any(v is not None for v in oe_ps_list):
            fig_oe = make_line(
                years,
                [ni_ps_list, oe_ps_list],
                ["GAAP NI per Share (prior yr shares)", "Owners' Earnings per Share (current yr shares)"],
                f"Per Share  ({ccy_code})", height=320,
            )
            fig_oe.update_layout(yaxis=dict(tickprefix=ccy, showgrid=True, gridcolor=C_BORDER2,
                                            tickfont=dict(size=10, color=C_TEXT3), zeroline=True,
                                            zerolinecolor=C_BORDER, showline=False))
            st.plotly_chart(fig_oe, use_container_width=True, config={"displayModeBar": False})

        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown('<span class="section-label">Historical Breakdown</span>', unsafe_allow_html=True)

        def _fmt_b(v):
            if v is None: return "—"
            return f"{ccy}{v/1e9:.2f}B"

        def _fmt_pct_oe(v):
            if v is None: return "—"
            sign = "+" if v >= 0 else ""
            return f"{sign}{v:.1f}%"

        oe_rows = {
            "Net Income (GAAP)":         [_fmt_b(_v(ni_s, i))         for i in range(len(years))],
            "GAAP SBC (add back)":       [_fmt_b(abs(_v(sbc_s, i)))   if _v(sbc_s, i)  is not None else "—" for i in range(len(years))],
            "Total Net Buybacks (info)": [_fmt_b(net_bb_list[i])      if net_bb_list[i] is not None else "—" for i in range(len(years))],
            "Maintenance Buybacks (sub)":[_fmt_b(-maint_bb_vals[i])   if maint_bb_vals[i] is not None else "—" for i in range(len(years))],
            "RSU Tax Withholdings (sub)":[
                _fmt_b(-sec_rsu.get(years[i])) if sec_rsu.get(years[i]) is not None
                else (_fmt_b(-_absv(rsu_tax_s, i)) if _absv(rsu_tax_s, i) is not None else "n/a (fetch from SEC)")
                for i in range(len(years))
            ],
            "Owners' Earnings":          [_fmt_b(oe_list[i]) for i in range(len(years))],
            "OE as % of GAAP NI":        [
                (f"{oe_list[i]/ni_list[i]*100:.0f}%"
                 if (oe_list[i] is not None and ni_list[i] and not pd.isna(ni_list[i]) and ni_list[i] != 0)
                 else "—")
                for i in range(len(years))
            ],
            "GAAP NI / Share (prior yr sh)": [
                f"{ccy}{ni_ps_list[i]:.2f}" if ni_ps_list[i] is not None else "—"
                for i in range(len(years))
            ],
            "OE / Share (current yr sh)": [
                f"{ccy}{oe_ps_list[i]:.2f}" if oe_ps_list[i] is not None else "—"
                for i in range(len(years))
            ],
            "Annual Dilution": [_fmt_pct_oe(dil_list[i]) for i in range(len(years))],
        }

        oe_display = pd.DataFrame({
            "Metric": list(oe_rows.keys()),
            **{years[i]: [oe_rows[m][i] for m in oe_rows] for i in range(len(years))}
        }).set_index("Metric")
        st.dataframe(oe_display, use_container_width=True)

    # ── Tab 7: Forensic Accounting ────────────────────────────────────────────
    with tab7:
        _is_non_us = bool(re.search(r"[.][A-Z]{1,4}$", ticker.upper()))

        st.markdown(
            '<div style="font-size:0.82rem;color:#555;margin-bottom:1rem;line-height:1.6">'
            'Benjamin Graham / David Dodd forensic analysis: Tax-Accrual Sanity Check, '
            'Depreciation Manipulation, Total-Deductions Coverage, Debt Safety, '
            'Off-Balance Sheet SPVs/VIEs, Revenue Front-Running, Owners\' Earnings quality. '
            'Quantitative data from ROIC (already loaded) + EDGAR XBRL. '
            'Notes analysis requires SEC EDGAR — US tickers only. Takes ~60–90 seconds.</div>',
            unsafe_allow_html=True,
        )

        _fa_key  = f"forensic_report_{ticker}"
        _run_btn = st.button("Generate Forensic Report", key="btn_forensic")

        if _run_btn or _fa_key in st.session_state:
            if _run_btn:
                st.session_state.pop(_fa_key, None)

            if _fa_key not in st.session_state:
                _fa_progress = st.progress(0, text="Phase 1 / 4 — Fetching XBRL quantitative data…")
                _xbrl        = fetch_forensic_xbrl(ticker)
                _fa_progress.progress(0.12, text="Phase 1 / 4 — XBRL fetched. Merging with ROIC data…")

                _dataset   = build_forensic_dataset(
                    _xbrl, years, bs_years,
                    rev_s, ni_s, oi_s, cfo_s, fcf_s, cogs_s,
                    ar_s, inv_s, nd_s,
                    sbc_s, incr_cap_s, decr_cap_s, rsu_tax_s,
                    price_s, avg_price_s, shares_s,
                )
                _data_table = _fmt_xbrl_table(_dataset)

                _notes_summary = ""
                _nvidia_key    = st.secrets.get("NVIDIA_API_KEY", "")
                if not _is_non_us:
                    _cik          = edgar_get_cik(ticker)
                    _filings      = edgar_list_annual_filings(_cik, n=5) if _cik else []
                    _fa_progress.progress(0.25, text="Phase 2 / 4 — Fetching Item 8 notes (parallel)…")
                    _notes_raw    = _fetch_notes_concurrent(_cik, _filings)
                    _fa_progress.progress(0.55, text="Phase 3 / 4 — Extracting signals (parallel)…")
                    _signals      = _extract_signals_concurrent(_notes_raw, company, _nvidia_key)
                    _notes_summary = _fmt_notes_signals(_signals)

                _fa_progress.progress(0.85, text="Phase 4 / 4 — Generating forensic report…")
                _forensic_text = generate_forensic_report(company, ticker, _data_table, _notes_summary, _nvidia_key)
                _fa_progress.empty()

                st.session_state[_fa_key] = {
                    "report":        _forensic_text,
                    "data_table":    _data_table,
                    "notes_summary": _notes_summary,
                }

            _fa_result  = st.session_state[_fa_key]
            _fa_text    = _fa_result["report"]

            _sp_match   = re.search(r"<forensic_scratchpad>([\s\S]*?)</forensic_scratchpad>",
                                    _fa_text, re.IGNORECASE)
            _report_body = re.sub(r"<forensic_scratchpad>[\s\S]*?</forensic_scratchpad>", "",
                                   _fa_text, flags=re.IGNORECASE).strip()

            if _sp_match:
                with st.expander("Forensic Scratchpad (raw calculations)", expanded=False):
                    st.markdown(
                        f'<pre style="font-size:0.72rem;line-height:1.5;white-space:pre-wrap">'
                        f'{_sp_match.group(1).strip()}</pre>',
                        unsafe_allow_html=True,
                    )

            st.markdown("---")
            _report_display = (_report_body or _fa_text).replace("$", r"\$")
            st.markdown(_report_display)
            st.markdown("---")

            with st.expander("Quantitative Data Table (XBRL + ROIC)", expanded=False):
                st.markdown(f'<pre style="font-size:0.72rem;line-height:1.5">{_fa_result["data_table"]}</pre>',
                            unsafe_allow_html=True)
            if _fa_result["notes_summary"]:
                with st.expander("Notes Signals — Pass 1 extraction (US only)", expanded=False):
                    st.markdown(f'<pre style="font-size:0.72rem;line-height:1.5">{_fa_result["notes_summary"]}</pre>',
                                unsafe_allow_html=True)

    # ── Tab 8: Research Report ─────────────────────────────────────────────────
    with tab8:
        st.markdown(
            '<div style="font-size:0.82rem;color:#555;margin-bottom:1.5rem;line-height:1.6">'
            'Generates a comprehensive equity research report in the style of a Berkshire Hathaway analyst. '
            'Uses the last 20 years of financial statements, last 4 earnings call transcripts, and web research. '
            'Takes approximately 30–60 seconds.</div>',
            unsafe_allow_html=True,
        )

        generate_btn = st.button("Generate Report")

        if generate_btn:
            _has_suffix = bool(re.search(r"[.][A-Z]{1,4}$", ticker.upper()))

            with st.spinner("Fetching earnings transcripts..."):
                transcripts = fetch_last_4_transcripts(ticker)

            if _has_suffix:
                _filing_text, _form_preview, _date_preview = None, None, None
                spin_msg = f"{ticker} is non-US listed — generating report with Haiku + web search..."
            else:
                with st.spinner("Searching EDGAR for 10-K / 20-F..."):
                    _filing_text, _form_preview, _date_preview = fetch_10k_text(ticker)
                if _filing_text:
                    spin_msg = f"Found {_form_preview} ({_date_preview}) — generating report with NVIDIA..."
                else:
                    spin_msg = "No SEC filing found — generating report with Haiku + web search..."

            with st.spinner(spin_msg):
                financials_text = format_financials_for_prompt(inc, bs, cf, years)
                if _filing_text:
                    report_text = generate_report_nvidia(
                        company, ticker, financials_text, transcripts,
                        _filing_text, _form_preview, _date_preview,
                    )
                    model_used, form_used = "nvidia", _form_preview
                else:
                    report_text = generate_report_haiku(company, ticker, financials_text, transcripts)
                    model_used, form_used = "haiku", None

            st.markdown("---")
            st.markdown(report_text)
            st.markdown("---")

            with st.spinner("Building PDF..."):
                chart_figs  = []
                rev_b = [v/1e9 if v and not pd.isna(v) else None for v in rev_s]
                if any(v for v in rev_b if v):
                    chart_figs.append(("Revenue (USD billions)", make_bar(years, rev_b, "Annual Revenue")))
                if fcf_s.notna().any():
                    fcf_b_pdf = [v/1e9 if v and not pd.isna(v) else None for v in fcf_s]
                    chart_figs.append(("Free Cash Flow (USD billions)", make_bar(years, fcf_b_pdf, "Free Cash Flow")))
                gm_pct_pdf  = to_pct_list(gm_s)
                opm_pct_pdf = to_pct_list(opm_s)
                npm_pct_pdf = to_pct_list(npm_s)
                if any(v for v in gm_pct_pdf if v):
                    chart_figs.append(("Profit Margins (%)", make_line(
                        years, [gm_pct_pdf, opm_pct_pdf, npm_pct_pdf],
                        ["Gross", "Operating", "Net"], "Margins",
                    )))
                pdf_bytes = build_report_pdf(company, ticker, report_text, transcripts, chart_figs)

            st.download_button(
                label="Download PDF", data=pdf_bytes,
                file_name=f"{ticker}_research_report.pdf", mime="application/pdf",
            )

            meta_parts = []
            if model_used == "nvidia" and form_used:
                meta_parts.append(f"Model: NVIDIA Nemotron  ·  Filing: {form_used} ({_date_preview})")
            else:
                meta_parts.append("Model: Claude Haiku  ·  Source: web search + financial data")
            if transcripts:
                labels = ", ".join([f"Q{t['quarter']} {t['year']}" for t in transcripts])
                meta_parts.append(f"Transcripts: {labels}")
            st.markdown(
                f'<div style="font-size:0.72rem;color:#999;margin-top:0.5rem">'
                f'{" &nbsp;·&nbsp; ".join(meta_parts)}</div>',
                unsafe_allow_html=True,
            )

    # ── Raw data ───────────────────────────────────────────────────────────────
    st.markdown("<br>", unsafe_allow_html=True)
    with st.expander("Raw data"):
        t1, t2, t3 = st.tabs(["Income Statement", "Balance Sheet", "Cash Flow"])
        with t1: st.dataframe(inc, use_container_width=True)
        with t2:
            if not bs.empty: st.dataframe(bs, use_container_width=True)
            else: st.markdown('<span style="color:#999;font-size:0.82rem">No data</span>', unsafe_allow_html=True)
        with t3:
            if not cf.empty: st.dataframe(cf, use_container_width=True)
            else: st.markdown('<span style="color:#999;font-size:0.82rem">No data</span>', unsafe_allow_html=True)
