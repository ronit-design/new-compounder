import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from config import CHART_BASE, LINE_COLORS, C_ACCENT, C_DOWN, C_BORDER, C_BORDER2, C_TEXT, C_TEXT2, C_TEXT3
from utils import delta_html


def make_bar(x, y, title, height=280, color=C_ACCENT):
    y_safe = [v if v is not None and not pd.isna(v) else 0 for v in y]
    c_list = [C_DOWN if v < 0 else color for v in y_safe]
    fig = go.Figure(go.Bar(
        x=x, y=y_safe, marker_color=c_list, marker_line_width=0,
        hovertemplate="%{x}<br>%{y:,.1f}<extra></extra>",
    ))
    fig.update_layout(**CHART_BASE)
    fig.update_layout(
        height=height,
        title=dict(text=title, font=dict(size=11, color=C_TEXT2, weight=500), x=0, xanchor="left"),
        bargap=0.35,
        xaxis=dict(showgrid=False, showline=True, linecolor=C_BORDER,
                   tickfont=dict(size=10, color=C_TEXT3), zeroline=False),
        yaxis=dict(showgrid=True, gridcolor=C_BORDER2, gridwidth=1,
                   showline=True, linecolor=C_BORDER, zeroline=False,
                   tickfont=dict(size=10, color=C_TEXT3)),
    )
    return fig


def make_line(x, ys, names, title, height=300, suffix=""):
    fig = go.Figure()
    for i, (y, name) in enumerate(zip(ys, names)):
        y_clean = [v if v and not pd.isna(v) else None for v in y]
        fig.add_trace(go.Scatter(
            x=x, y=y_clean, name=name, mode="lines",
            line=dict(color=LINE_COLORS[i % len(LINE_COLORS)], width=1.5),
            hovertemplate=f"%{{x}}<br>{name}: %{{y:,.1f}}{suffix}<extra></extra>",
            connectgaps=False,
        ))
    fig.update_layout(**CHART_BASE)
    fig.update_layout(
        height=height,
        title=dict(text=title, font=dict(size=11, color=C_TEXT2, weight=500), x=0, xanchor="left"),
        margin=dict(l=0, r=0, t=52, b=0),
        xaxis=dict(showgrid=False, showline=True, linecolor=C_BORDER,
                   tickfont=dict(size=10, color=C_TEXT3), zeroline=False),
        yaxis=dict(showgrid=True, gridcolor=C_BORDER2, gridwidth=1,
                   showline=True, linecolor=C_BORDER, zeroline=False,
                   tickfont=dict(size=10, color=C_TEXT3)),
    )
    return fig


def kpi_block(col, label, value_str, delta=None):
    col.markdown(f"""
    <div class="metric-block">
        <div class="metric-label">{label}</div>
        <div class="metric-value">{value_str}</div>
        {delta_html(delta)}
    </div>""", unsafe_allow_html=True)
