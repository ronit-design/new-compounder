API_KEY  = "73d3049608e044f1a63182f51656c760"
BASE_URL = "https://api.roic.ai/v2"

STOCKS = {
    "Ryanair":                "RYAAY",
    "Copart":                 "CPRT",
    "Constellation Software": "CSU.TO",
    "Fair Isaac":             "FICO",
    "S&P Global":             "SPGI",
    "Moody's":               "MCO",
    "ASML":                   "ASML",
}

# ── Design tokens ──────────────────────────────────────────────────────────────
C_BG      = "#FFFFFF"
C_SURFACE = "#FAFAFA"
C_BORDER  = "#E8E8E8"
C_BORDER2 = "#F0F0F0"
C_TEXT    = "#111111"
C_TEXT2   = "#555555"
C_TEXT3   = "#999999"
C_ACCENT  = "#111111"
C_UP      = "#1A7F4B"
C_DOWN    = "#C0392B"
C_SIDEBAR = "#F7F7F7"

# ── Chart theme ────────────────────────────────────────────────────────────────
CHART_BASE = dict(
    paper_bgcolor=C_BG,
    plot_bgcolor=C_BG,
    font=dict(family="Inter, -apple-system, sans-serif", color=C_TEXT3, size=11),
    xaxis=dict(
        showgrid=False, zeroline=False, showline=False,
        tickfont=dict(size=10, color=C_TEXT3), tickcolor=C_BORDER,
    ),
    margin=dict(l=0, r=0, t=48, b=0),
    hovermode="x unified",
    hoverlabel=dict(bgcolor=C_BG, bordercolor=C_BORDER,
                    font=dict(family="Inter, sans-serif", size=11, color=C_TEXT)),
    legend=dict(bgcolor="rgba(0,0,0,0)", borderwidth=0,
                font=dict(size=10, color=C_TEXT3),
                orientation="h", yanchor="top", y=1.0, xanchor="right", x=1.0),
)

LINE_COLORS = ["#111111", "#AAAAAA", "#555555", "#CCCCCC"]
