import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from config import (C_ACCENT, C_DOWN, C_UP, C_BORDER, C_BORDER2,
                    C_TEXT, C_TEXT2, C_TEXT3, CHART_BASE)
from analysis.liquidity import compute_liquidity, altman_zone
from data.edgar import fetch_liquidity_xbrl
from ui.components import make_bar, make_line
from utils import fmt_currency, safe


# ── Helpers ────────────────────────────────────────────────────────────────────

def _nv(v, decimals=2, suffix=""):
    """Format a number or return em-dash."""
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return "—"
    return f"{v:.{decimals}f}{suffix}"


def _liq_kpi(col, label, value_str, sub=None, color=None):
    color = color or C_TEXT
    col.markdown(f"""
    <div class="metric-block">
        <div class="metric-label">{label}</div>
        <div class="metric-value" style="color:{color}">{value_str}</div>
        {"" if not sub else f'<div style="font-size:0.68rem;color:#999;margin-top:2px">{sub}</div>'}
    </div>""", unsafe_allow_html=True)


def _icr_color(v):
    if v is None: return C_TEXT
    if v >= 3.0:  return C_UP
    if v >= 1.5:  return "#D4800A"
    return C_DOWN


def _nd_ebitda_color(v):
    if v is None: return C_TEXT
    if v < 0:     return C_UP      # net cash position
    if v <= 2.0:  return C_UP
    if v <= 4.0:  return "#D4800A"
    return C_DOWN


def _ratio_color(v, good_above):
    if v is None: return C_TEXT
    return C_UP if v >= good_above else C_DOWN


def _latest(lst):
    return next((v for v in reversed(lst) if v is not None), None)


# ── Debt structure stacked bar ─────────────────────────────────────────────────

def _debt_structure_chart(years, m, ccy):
    fig = go.Figure()
    has_st  = any(v for v in m["st_debt"]      if v)
    has_lc  = any(v for v in m["ltd_current"]  if v)
    has_lnc = any(v for v in m["ltd_noncurrent"] if v)

    def b(vals, name, color):
        fig.add_trace(go.Bar(
            name=name,
            x=years,
            y=[v / 1e9 if v else 0 for v in vals],
            marker_color=color, marker_line_width=0,
            hovertemplate=f"%{{x}} {name}: {ccy}%{{y:.2f}}B<extra></extra>",
        ))

    if has_st:  b(m["st_debt"],        "Short-term Debt",       "#CCCCCC")
    if has_lc:  b(m["ltd_current"],    "Current LT Debt",       "#888888")
    if has_lnc: b(m["ltd_noncurrent"], "Long-term Debt",        C_ACCENT)

    fig.update_layout(**CHART_BASE)
    fig.update_layout(
        barmode="stack", height=280, bargap=0.35,
        title=dict(text="Debt Composition  ($B)", font=dict(size=11, color=C_TEXT2, weight=500),
                   x=0, xanchor="left"),
        legend=dict(orientation="h", y=1.12, x=0, font=dict(size=10, color=C_TEXT3)),
        yaxis=dict(showgrid=True, gridcolor=C_BORDER2, tickprefix=ccy, ticksuffix="B",
                   tickfont=dict(size=10, color=C_TEXT3), zeroline=False),
        xaxis=dict(showgrid=False, showline=True, linecolor=C_BORDER,
                   tickfont=dict(size=10, color=C_TEXT3)),
    )
    return fig


# ── ICR chart with zone bands ──────────────────────────────────────────────────

def _icr_chart(years, icr_list):
    y_clean = [v if v is not None else None for v in icr_list]
    y_vals  = [v for v in y_clean if v is not None]
    y_max   = max(max(y_vals) * 1.2, 5) if y_vals else 10
    y_min   = min(min(y_vals) * 1.1, 0) if y_vals else 0

    fig = go.Figure()

    # Coloured zone bands
    for y0, y1, color, label in [
        (0,    1.5, "rgba(192,57,43,0.08)",  "Distress"),
        (1.5,  3.0, "rgba(212,128,10,0.08)", "Caution"),
        (3.0, y_max,"rgba(26,127,75,0.06)",  "Safe"),
    ]:
        fig.add_shape(type="rect", x0=years[0], x1=years[-1],
                      y0=y0, y1=y1, fillcolor=color, line_width=0, layer="below")

    fig.add_trace(go.Scatter(
        x=years, y=y_clean, mode="lines+markers", name="ICR",
        line=dict(color=C_ACCENT, width=2),
        marker=dict(size=5, color=C_ACCENT),
        hovertemplate="%{x}<br>ICR: %{y:.1f}x<extra></extra>",
    ))
    for thresh, color, dash in [(1.5, C_DOWN, "dash"), (3.0, C_UP, "dot")]:
        fig.add_hline(y=thresh, line_dash=dash, line_color=color,
                      line_width=1, opacity=0.6)

    fig.update_layout(**CHART_BASE)
    fig.update_layout(
        height=280,
        title=dict(text="Interest Coverage Ratio  (x)", font=dict(size=11, color=C_TEXT2, weight=500),
                   x=0, xanchor="left"),
        yaxis=dict(range=[min(y_min, 0), y_max], showgrid=True, gridcolor=C_BORDER2,
                   ticksuffix="x", tickfont=dict(size=10, color=C_TEXT3), zeroline=True,
                   zerolinecolor=C_BORDER),
        xaxis=dict(showgrid=False, showline=True, linecolor=C_BORDER,
                   tickfont=dict(size=10, color=C_TEXT3)),
        showlegend=False,
    )
    return fig


# ── Altman Z-Score chart with coloured bands ───────────────────────────────────

def _altman_chart(years, z_list):
    y_clean = [v for v in z_list]
    y_vals  = [v for v in y_clean if v is not None]
    y_max   = max(max(y_vals) * 1.15, 4) if y_vals else 5
    y_min   = min(min(y_vals) * 1.1, -1) if y_vals else -1

    fig = go.Figure()

    for y0, y1, color in [
        (y_min, 1.81, "rgba(192,57,43,0.10)"),
        (1.81,  2.99, "rgba(212,128,10,0.08)"),
        (2.99,  y_max,"rgba(26,127,75,0.07)"),
    ]:
        fig.add_shape(type="rect", x0=years[0], x1=years[-1],
                      y0=y0, y1=y1, fillcolor=color, line_width=0, layer="below")

    # Colour each point by zone
    colors = []
    for v in y_clean:
        if v is None:      colors.append(C_TEXT3)
        elif v >= 2.99:    colors.append(C_UP)
        elif v >= 1.81:    colors.append("#D4800A")
        else:              colors.append(C_DOWN)

    fig.add_trace(go.Scatter(
        x=years, y=y_clean, mode="lines+markers", name="Altman Z",
        line=dict(color=C_ACCENT, width=2),
        marker=dict(size=7, color=colors),
        hovertemplate="%{x}<br>Z-Score: %{y:.2f}<extra></extra>",
    ))
    for thresh, color, dash in [(1.81, C_DOWN, "dash"), (2.99, C_UP, "dot")]:
        fig.add_hline(y=thresh, line_dash=dash, line_color=color,
                      line_width=1, opacity=0.6)

    fig.update_layout(**CHART_BASE)
    fig.update_layout(
        height=300,
        title=dict(text="Altman Z-Score (historical)", font=dict(size=11, color=C_TEXT2, weight=500),
                   x=0, xanchor="left"),
        yaxis=dict(range=[y_min, y_max], showgrid=True, gridcolor=C_BORDER2,
                   tickfont=dict(size=10, color=C_TEXT3), zeroline=True, zerolinecolor=C_BORDER),
        xaxis=dict(showgrid=False, showline=True, linecolor=C_BORDER,
                   tickfont=dict(size=10, color=C_TEXT3)),
        showlegend=False,
    )
    return fig


# ── Main render ────────────────────────────────────────────────────────────────

def render_liquidity(ticker, company, inc, bs, cf,
                     years, ccy, ccy_code,
                     oi_s, rev_s, ca_s, cl_s, inv_s,
                     price_s, shares_s):

    # ── Fetch XBRL ─────────────────────────────────────────────────────────────
    with st.spinner("Fetching EDGAR XBRL liquidity data…"):
        xbrl = fetch_liquidity_xbrl(ticker)

    # ── Compute metrics ────────────────────────────────────────────────────────
    m = compute_liquidity(
        years, oi_s, rev_s, ca_s, cl_s, inv_s, price_s, shares_s, xbrl
    )

    latest_td    = _latest(m["total_debt"])
    latest_nd    = _latest(m["net_debt"])
    latest_icr   = _latest(m["icr"])
    latest_nde   = _latest(m["nd_ebitda"])
    latest_z     = _latest(m["altman_z"])
    latest_curr  = _latest(m["current_ratio"])
    latest_quick = _latest(m["quick_ratio"])
    latest_eff   = _latest(m["eff_rate"])
    latest_int   = _latest(m["interest_exp"])

    z_label, z_color = altman_zone(latest_z)

    # ── KPI Row ────────────────────────────────────────────────────────────────
    k1, k2, k3, k4, k5 = st.columns(5)
    _liq_kpi(k1, "Total Debt",       fmt_currency(latest_td,  ccy))
    _liq_kpi(k2, "Net Debt",         fmt_currency(latest_nd,  ccy),
             sub="(negative = net cash)")
    _liq_kpi(k3, "Interest Coverage",
             _nv(latest_icr, 1, "x"), sub="EBIT / Interest",
             color=_icr_color(latest_icr))
    _liq_kpi(k4, "Net Debt / EBITDA",
             _nv(latest_nde, 1, "x"), sub="leverage ratio",
             color=_nd_ebitda_color(latest_nde))
    _liq_kpi(k5, "Altman Z-Score",
             _nv(latest_z, 2), sub=z_label, color=z_color)

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Section 1: Debt Structure ──────────────────────────────────────────────
    st.markdown('<span class="section-label">Debt Structure</span>', unsafe_allow_html=True)

    c1, c2 = st.columns(2, gap="large")
    with c1:
        st.plotly_chart(_debt_structure_chart(years, m, ccy),
                        use_container_width=True, config={"displayModeBar": False})
    with c2:
        nd_b = [v / 1e9 if v is not None else None for v in m["net_debt"]]
        fig_nd = make_bar(years, nd_b, f"Net Debt  ({ccy_code}, B)", height=280)
        fig_nd.update_layout(yaxis=dict(
            tickprefix=ccy, ticksuffix="B", showgrid=True, gridcolor=C_BORDER2,
            tickfont=dict(size=10, color=C_TEXT3), zeroline=True, zerolinecolor=C_BORDER,
        ))
        st.plotly_chart(fig_nd, use_container_width=True, config={"displayModeBar": False})

    # Debt breakdown table
    def _b(v): return fmt_currency(v, ccy) if v is not None else "—"
    debt_rows = {
        "Short-term Debt":      [_b(m["st_debt"][i])        for i in range(len(years))],
        "Current LT Debt":      [_b(m["ltd_current"][i])    for i in range(len(years))],
        "Long-term Debt":       [_b(m["ltd_noncurrent"][i]) for i in range(len(years))],
        "Total Debt":           [_b(m["total_debt"][i])     for i in range(len(years))],
        "Cash & Equivalents":   [_b(m["cash"][i])           for i in range(len(years))],
        "Net Debt":             [_b(m["net_debt"][i])       for i in range(len(years))],
    }
    debt_df = pd.DataFrame({"Metric": list(debt_rows.keys()),
                             **{years[i]: [debt_rows[k][i] for k in debt_rows]
                                for i in range(len(years))}}).set_index("Metric")
    st.dataframe(debt_df, use_container_width=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Section 2: Debt Maturity Schedule ─────────────────────────────────────
    st.markdown('<span class="section-label">Debt Maturity Schedule</span>',
                unsafe_allow_html=True)

    mat_labels = ["Within 1 Yr", "Year 2", "Year 3", "Year 4", "Year 5", "After Yr 5"]
    mat_vals   = [xbrl.get(k) for k in ["mat_y1","mat_y2","mat_y3","mat_y4","mat_y5","mat_after"]]
    mat_b      = [v / 1e9 if v else 0 for v in mat_vals]
    has_maturity = any(v for v in mat_vals if v)

    if has_maturity:
        fig_mat = go.Figure(go.Bar(
            x=mat_labels, y=mat_b,
            marker_color=[C_DOWN if i == 0 else C_ACCENT for i in range(len(mat_labels))],
            marker_line_width=0,
            text=[f"{ccy}{v:.1f}B" if v else "" for v in mat_b],
            textposition="outside",
            hovertemplate="%{x}: " + ccy + "%{y:.2f}B<extra></extra>",
        ))
        fig_mat.update_layout(**CHART_BASE)
        fig_mat.update_layout(
            height=280, bargap=0.35, showlegend=False,
            title=dict(text=f"Debt Repayment Schedule  ({ccy_code}, B) — most recent filing",
                       font=dict(size=11, color=C_TEXT2, weight=500), x=0, xanchor="left"),
            yaxis=dict(showgrid=True, gridcolor=C_BORDER2, tickprefix=ccy, ticksuffix="B",
                       tickfont=dict(size=10, color=C_TEXT3), zeroline=False),
            xaxis=dict(showgrid=False, showline=True, linecolor=C_BORDER,
                       tickfont=dict(size=10, color=C_TEXT3)),
        )
        st.plotly_chart(fig_mat, use_container_width=True, config={"displayModeBar": False})
        st.markdown(
            '<div style="font-size:0.72rem;color:#999;margin-top:-0.5rem">'
            'Sourced from EDGAR XBRL — represents contractual principal repayments '
            'as disclosed in the most recent annual filing. Red bar = imminent (within 12 months).'
            '</div>', unsafe_allow_html=True)
    else:
        st.markdown('<span style="font-size:0.82rem;color:#999">Maturity schedule not available in EDGAR XBRL for this ticker.</span>',
                    unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Section 3: Interest Burden & Coverage ─────────────────────────────────
    st.markdown('<span class="section-label">Interest Burden & Coverage</span>',
                unsafe_allow_html=True)

    c3, c4 = st.columns(2, gap="large")
    with c3:
        int_b = [v / 1e9 if v is not None else None for v in m["interest_exp"]]
        if any(v for v in int_b if v):
            fig_int = make_bar(years, int_b, f"Interest Expense  ({ccy_code}, B)", height=280,
                               color="#888888")
            fig_int.update_layout(yaxis=dict(
                tickprefix=ccy, ticksuffix="B", showgrid=True, gridcolor=C_BORDER2,
                tickfont=dict(size=10, color=C_TEXT3), zeroline=False,
            ))
            st.plotly_chart(fig_int, use_container_width=True, config={"displayModeBar": False})
        else:
            st.markdown('<span style="color:#999;font-size:0.82rem">Interest expense not available in XBRL.</span>',
                        unsafe_allow_html=True)
    with c4:
        if any(v for v in m["icr"] if v is not None):
            st.plotly_chart(_icr_chart(years, m["icr"]),
                            use_container_width=True, config={"displayModeBar": False})
            st.markdown(
                '<div style="font-size:0.70rem;color:#999;margin-top:-0.4rem">'
                '<span style="color:#1A7F4B">●</span> Safe (&gt;3x) &nbsp;'
                '<span style="color:#D4800A">●</span> Caution (1.5–3x) &nbsp;'
                '<span style="color:#C0392B">●</span> Distress (&lt;1.5x)'
                '</div>', unsafe_allow_html=True)
        else:
            st.markdown('<span style="color:#999;font-size:0.82rem">ICR not calculable — EBIT or interest expense missing.</span>',
                        unsafe_allow_html=True)

    # Interest summary row
    if latest_int or latest_eff:
        st.markdown("<br>", unsafe_allow_html=True)
        ic1, ic2, ic3 = st.columns(3)
        _liq_kpi(ic1, "Annual Interest Expense", fmt_currency(latest_int, ccy))
        _liq_kpi(ic2, "Effective Interest Rate", _nv(latest_eff, 1, "%"),
                 sub="Interest exp / Total debt")
        ebitda_l = _latest(m["ebitda"])
        _liq_kpi(ic3, "EBITDA", fmt_currency(ebitda_l, ccy), sub="EBIT + D&A")

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Section 4: Leverage Ratios ─────────────────────────────────────────────
    st.markdown('<span class="section-label">Leverage Ratios</span>', unsafe_allow_html=True)

    lev_ys, lev_names = [], []
    if any(v for v in m["nd_ebitda"] if v is not None):
        lev_ys.append(m["nd_ebitda"]); lev_names.append("Net Debt / EBITDA")
    if any(v for v in m["de_ratio"] if v is not None):
        lev_ys.append(m["de_ratio"]);  lev_names.append("Debt / Equity")

    if lev_ys:
        fig_lev = make_line(years, lev_ys, lev_names, "Leverage Ratios  (x)", height=280, suffix="x")
        fig_lev.update_layout(yaxis=dict(ticksuffix="x", showgrid=True, gridcolor=C_BORDER2,
                                         tickfont=dict(size=10, color=C_TEXT3), zeroline=True,
                                         zerolinecolor=C_BORDER))
        st.plotly_chart(fig_lev, use_container_width=True, config={"displayModeBar": False})
    else:
        st.markdown('<span style="color:#999;font-size:0.82rem">Leverage ratios not calculable — EBITDA or equity data missing.</span>',
                    unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Section 5: Short-term Liquidity ───────────────────────────────────────
    st.markdown('<span class="section-label">Short-term Liquidity</span>', unsafe_allow_html=True)

    lq1, lq2, lq3 = st.columns(3)
    _liq_kpi(lq1, "Current Ratio",
             _nv(latest_curr, 2, "x"), sub="Current Assets / Current Liabilities",
             color=_ratio_color(latest_curr, 1.5))
    _liq_kpi(lq2, "Quick Ratio",
             _nv(latest_quick, 2, "x"), sub="(CA – Inventory) / CL",
             color=_ratio_color(latest_quick, 1.0))
    _liq_kpi(lq3, "Cash & Equivalents",
             fmt_currency(_latest(m["cash"]), ccy))

    st.markdown("<br>", unsafe_allow_html=True)

    liq_ys, liq_names = [], []
    if any(v for v in m["current_ratio"] if v is not None):
        liq_ys.append(m["current_ratio"]); liq_names.append("Current Ratio")
    if any(v for v in m["quick_ratio"] if v is not None):
        liq_ys.append(m["quick_ratio"]);   liq_names.append("Quick Ratio")

    if liq_ys:
        fig_liq = make_line(years, liq_ys, liq_names, "Liquidity Ratios  (x)", height=260, suffix="x")
        fig_liq.add_hline(y=1.0, line_dash="dot", line_color=C_DOWN, line_width=1, opacity=0.5)
        fig_liq.update_layout(yaxis=dict(ticksuffix="x", showgrid=True, gridcolor=C_BORDER2,
                                          tickfont=dict(size=10, color=C_TEXT3), zeroline=False))
        st.plotly_chart(fig_liq, use_container_width=True, config={"displayModeBar": False})

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Section 6: Altman Z-Score ──────────────────────────────────────────────
    st.markdown('<span class="section-label">Bankruptcy Risk — Altman Z-Score</span>',
                unsafe_allow_html=True)
    st.markdown(
        '<div style="font-size:0.78rem;color:#777;line-height:1.7;margin-bottom:1rem;max-width:820px">'
        'The Altman Z-Score (1968) is a quantitative model for predicting corporate bankruptcy. '
        'It combines five financial ratios into a single score. '
        '<strong style="color:#1A7F4B">Safe Zone: Z &gt; 2.99</strong> — '
        '<strong style="color:#D4800A">Grey Zone: 1.81 – 2.99</strong> — '
        '<strong style="color:#C0392B">Distress Zone: Z &lt; 1.81</strong>. '
        'Originally calibrated for US manufacturing firms; scores for asset-light or financial '
        'companies should be interpreted with caution.'
        '</div>', unsafe_allow_html=True)

    za1, za2 = st.columns([1, 3], gap="large")
    with za1:
        _liq_kpi(za1, "Latest Z-Score", _nv(latest_z, 2), sub=z_label, color=z_color)

    with za2:
        if any(v for v in m["altman_z"] if v is not None):
            st.plotly_chart(_altman_chart(years, m["altman_z"]),
                            use_container_width=True, config={"displayModeBar": False})

    # Z-Score component breakdown table
    if any(v for v in m["altman_z"] if v is not None):
        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown('<span class="section-label">Z-Score Component Breakdown</span>',
                    unsafe_allow_html=True)

        def _z(lst, i, weight):
            raw = lst[i]
            if raw is None: return "—"
            component = raw / weight if weight else raw
            return f"{component:.3f}  →  {raw:.3f}"

        z_rows = {
            "Z1 = 1.2 × (Working Capital / Total Assets)":        [_z(m["z1"], i, 1.2) for i in range(len(years))],
            "Z2 = 1.4 × (Retained Earnings / Total Assets)":      [_z(m["z2"], i, 1.4) for i in range(len(years))],
            "Z3 = 3.3 × (EBIT / Total Assets)":                   [_z(m["z3"], i, 3.3) for i in range(len(years))],
            "Z4 = 0.6 × (Market Cap / Total Liabilities)":        [_z(m["z4"], i, 0.6) for i in range(len(years))],
            "Z5 = 1.0 × (Revenue / Total Assets)":                [_z(m["z5"], i, 1.0) for i in range(len(years))],
            "Altman Z-Score (sum)": [_nv(m["altman_z"][i], 2) for i in range(len(years))],
        }
        z_df = pd.DataFrame({"Component": list(z_rows.keys()),
                              **{years[i]: [z_rows[k][i] for k in z_rows]
                                 for i in range(len(years))}}).set_index("Component")
        st.dataframe(z_df, use_container_width=True)
