import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from config import C_ACCENT, C_BORDER2, C_TEXT3, C_UP, C_DOWN, CHART_BASE
from data.fetchers import fetch_fundamental, fetch_fundamental_quarterly, fetch_prices
from utils import safe, latest, ccy_symbol, fmt_currency, fmt_pct, to_pct_list


def _calc_cagr(s):
    vals = [v for v in s.dropna().tolist() if v is not None and v > 0]
    if len(vals) < 2:
        return None, 0
    start, end = vals[0], vals[-1]
    n = len(vals) - 1
    if start <= 0 or n == 0:
        return None, 0
    return ((end / start) ** (1.0 / n) - 1) * 100, n


def _fmt_cagr(val, n):
    if val is None:
        return "—"
    sign = "+" if val >= 0 else ""
    return f"{sign}{val:.1f}%"


def render_overview():
    st.markdown('<div class="page-title">Overview</div>', unsafe_allow_html=True)
    st.markdown('<div class="page-sub">Quality compounders — latest annual figures</div>', unsafe_allow_html=True)

    with st.expander("Edit Watchlist", expanded=False):
        edited_df = st.data_editor(
            pd.DataFrame(st.session_state.stocks_list),
            num_rows="dynamic", use_container_width=True, hide_index=True,
            column_config={
                "Name":   st.column_config.TextColumn("Company Name", width="medium"),
                "Ticker": st.column_config.TextColumn("Ticker",       width="small"),
            },
            key="stocks_editor",
        )
        if st.button("Apply Changes"):
            new_list = [
                {"Name": r["Name"], "Ticker": str(r["Ticker"]).strip().upper()}
                for _, r in edited_df.iterrows()
                if r["Ticker"] and str(r["Ticker"]).strip()
            ]
            if new_list != st.session_state.stocks_list:
                st.session_state.stocks_list = new_list
                st.cache_data.clear()
                st.rerun()

    rows = []
    for s in st.session_state.stocks_list:
        company, ticker = s["Name"], s["Ticker"]
        with st.spinner(f"Loading {company}..."):
            inc = fetch_fundamental("fundamental/income-statement", ticker)
            cf  = fetch_fundamental("fundamental/cash-flow",        ticker)
        if inc.empty:
            rows.append({"Company": company, "Ticker": ticker})
            continue

        rev_s    = safe(inc, "is_sales_revenue_turnover", "is_sales_and_services_revenues")
        gp_s     = safe(inc, "is_gross_profit")
        oi_s     = safe(inc, "ebit", "is_oper_income")
        ni_s     = safe(inc, "is_net_income", "is_ni_including_minority_int_ratio")
        gm_s     = safe(inc, "gross_margin")
        opm_s    = safe(inc, "oper_margin")
        npm_s    = safe(inc, "profit_margin")
        eps_s    = safe(inc, "diluted_eps", "eps")
        shares_s = safe(inc, "is_sh_for_diluted_eps", "is_avg_num_sh_for_eps")
        fcf_s    = safe(cf, "cf_free_cash_flow") if not cf.empty else pd.Series(dtype=float)

        ccy_code = inc["currency"].iloc[-1] if "currency" in inc.columns and len(inc) > 0 else "USD"
        ccy      = ccy_symbol(ccy_code)

        rev_cagr, rev_n = _calc_cagr(rev_s)
        oi_cagr,  oi_n  = _calc_cagr(oi_s)

        prices      = fetch_prices(ticker)
        latest_price = None
        if not prices.empty:
            close_col = next((c for c in ["adj_close", "adjusted_close", "close"]
                              if c in prices.columns), None)
            if close_col:
                latest_price = float(prices[close_col].dropna().iloc[-1])

        inc_q   = fetch_fundamental_quarterly("fundamental/income-statement", ticker)
        ttm_eps = None
        if not inc_q.empty:
            eps_q = safe(inc_q, "diluted_eps", "eps").dropna()
            if len(eps_q) >= 4:   ttm_eps = float(eps_q.iloc[-4:].sum())
            elif len(eps_q) > 0:  ttm_eps = float(eps_q.iloc[-len(eps_q):].sum())

        latest_shares = latest(shares_s)
        latest_fcf    = latest(fcf_s)

        def _pe():
            if latest_price and ttm_eps and ttm_eps != 0:
                return f"{latest_price / ttm_eps:.1f}x"
            return "—"

        def _fcf_yield():
            if latest_price and latest_shares and latest_shares > 0 and latest_fcf:
                mc = latest_price * latest_shares
                if mc > 0:
                    return f"{(latest_fcf / mc) * 100:.1f}%"
            return "—"

        rows.append({
            "Company":      company,       "Ticker":       ticker,
            "Revenue":      fmt_currency(latest(rev_s), ccy),
            "Gross Profit": fmt_currency(latest(gp_s), ccy),
            "GP Margin":    fmt_pct(latest(gm_s)),
            "Op Profit":    fmt_currency(latest(oi_s), ccy),
            "Op Margin":    fmt_pct(latest(opm_s)),
            "Net Profit":   fmt_currency(latest(ni_s), ccy),
            "Net Margin":   fmt_pct(latest(npm_s)),
            "Rev CAGR":     _fmt_cagr(rev_cagr, rev_n),
            "OI CAGR":      _fmt_cagr(oi_cagr,  oi_n),
            "P/E":          _pe(),
            "FCF Yield":    _fcf_yield(),
            "_rev":  latest(rev_s), "_oi":  latest(oi_s), "_ni":   latest(ni_s),
            "_opm":  latest(opm_s), "_npm": latest(npm_s),
            "_ccy":  ccy, "_ccy_code": str(ccy_code),
        })

    header_cols = ["Company", "Ticker", "Revenue", "Gross Profit", "GP Margin",
                   "Op Profit", "Op Margin", "Net Profit", "Net Margin",
                   "Rev CAGR", "OI CAGR", "P/E", "FCF Yield"]

    header_html = "".join(f'<span class="tbl-header">{h}</span>' for h in header_cols)
    st.markdown(f'<div class="tbl-row tbl-header-row">{header_html}</div>', unsafe_allow_html=True)

    for r in rows:
        def cell(key, cls="tbl-cell"):
            return f'<span class="{cls}">{r.get(key, "—")}</span>'

        def cagr_span(val):
            if val == "—":
                return '<span class="tbl-cell" style="color:#ccc">—</span>'
            is_pos = not val.startswith("-")
            color  = C_UP if is_pos else C_DOWN
            return f'<span class="tbl-cell" style="color:{color};font-weight:500">{val}</span>'

        st.markdown(f'''
        <div class="tbl-row">
            <span class="tbl-cell tbl-name">{r.get("Company","")}</span>
            <span class="tbl-ticker">{r.get("Ticker","")}</span>
            {cell("Revenue")} {cell("Gross Profit")} {cell("GP Margin")}
            {cell("Op Profit")} {cell("Op Margin")} {cell("Net Profit")}
            {cell("Net Margin")} {cagr_span(r.get("Rev CAGR", "—"))} {cagr_span(r.get("OI CAGR", "—"))}
            {cell("P/E")} {cell("FCF Yield")}
        </div>''', unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    chart_names = [r["Company"] for r in rows if r.get("_rev")]
    chart_rev   = [r["_rev"]   for r in rows if r.get("_rev")]
    chart_opm   = [to_pct_list([r.get("_opm")])[0] if r.get("_opm") is not None else 0
                   for r in rows if r.get("_rev")]
    chart_npm   = [to_pct_list([r.get("_npm")])[0] if r.get("_npm") is not None else 0
                   for r in rows if r.get("_rev")]

    st.markdown('<span class="section-label">Revenue</span>', unsafe_allow_html=True)
    if chart_names:
        hover_texts = []
        for r in [r for r in rows if r.get("_rev")]:
            ccy = r.get("_ccy", "$")
            v   = r.get("_rev", 0)
            hover_texts.append(f"{ccy}{v/1e9:.1f}B")
        fig_rev = go.Figure(go.Bar(
            x=chart_names, y=[v / 1e9 for v in chart_rev],
            marker_color=C_ACCENT, marker_line_width=0,
            text=hover_texts,
            hovertemplate="%{x}<br>%{text}<extra></extra>",
        ))
        fig_rev.update_layout(**CHART_BASE)
        fig_rev.update_layout(
            height=260, bargap=0.45, showlegend=False,
            yaxis=dict(showgrid=True, gridcolor=C_BORDER2, ticksuffix="B",
                       tickfont=dict(size=10, color=C_TEXT3), zeroline=False,
                       showline=True, linecolor="#E8E8E8"),
        )
        st.plotly_chart(fig_rev, use_container_width=True, config={"displayModeBar": False})

    st.markdown('<span class="section-label">Margins</span>', unsafe_allow_html=True)
    if chart_names:
        fig_m = go.Figure()
        fig_m.add_trace(go.Bar(
            name="Operating", x=chart_names, y=chart_opm,
            marker_color=C_ACCENT, marker_line_width=0,
            hovertemplate="%{x}<br>Operating: %{y:.1f}%<extra></extra>",
        ))
        fig_m.add_trace(go.Bar(
            name="Net", x=chart_names, y=chart_npm,
            marker_color="#BBBBBB", marker_line_width=0,
            hovertemplate="%{x}<br>Net: %{y:.1f}%<extra></extra>",
        ))
        fig_m.update_layout(**CHART_BASE)
        fig_m.update_layout(
            height=260, barmode="group", bargap=0.35, bargroupgap=0.08,
            yaxis=dict(showgrid=True, gridcolor=C_BORDER2, ticksuffix="%",
                       tickfont=dict(size=10, color=C_TEXT3), zeroline=False, showline=False),
        )
        st.plotly_chart(fig_m, use_container_width=True, config={"displayModeBar": False})
