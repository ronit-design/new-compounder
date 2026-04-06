import pandas as pd

# ── Series helpers ─────────────────────────────────────────────────────────────

def safe(df, *cols):
    for c in cols:
        if c in df.columns:
            return pd.to_numeric(df[c], errors="coerce").reset_index(drop=True)
    return pd.Series(dtype=float)


def align(s, n):
    s = s.reset_index(drop=True) if not s.empty else s
    if len(s) == n:
        return s
    if len(s) > n:
        return s.iloc[:n].reset_index(drop=True)
    pad = pd.Series([float("nan")] * (n - len(s)))
    return pd.concat([s, pad], ignore_index=True)


def latest(s):
    v = s.dropna()
    return float(v.iloc[-1]) if len(v) > 0 else None


def prev(s):
    v = s.dropna()
    return float(v.iloc[-2]) if len(v) > 1 else None


def yoy(l, p):
    if l is not None and p is not None and p != 0:
        return (l - p) / abs(p) * 100
    return None


# ── Currency helpers ───────────────────────────────────────────────────────────

_CCY_SYMBOLS = {
    "USD": "$", "EUR": "€", "GBP": "£", "JPY": "¥", "CNY": "¥",
    "INR": "₹", "CAD": "C$", "AUD": "A$", "CHF": "CHF ", "KRW": "₩",
    "HKD": "HK$", "SGD": "S$", "SEK": "SEK ", "NOK": "NOK ", "DKK": "DKK ",
    "BRL": "R$", "MXN": "MX$", "ZAR": "R ", "TWD": "NT$", "THB": "฿",
    "IDR": "Rp", "MYR": "RM", "ILS": "₪", "SAR": "SAR ", "AED": "AED ",
}


def ccy_symbol(currency_code):
    if not currency_code:
        return "$"
    return _CCY_SYMBOLS.get(str(currency_code).upper(), str(currency_code).upper() + " ")


def fmt_currency(val, ccy="$"):
    try:
        v = float(val)
        if pd.isna(v): return "—"
        neg = v < 0
        v = abs(v)
        if v >= 1e12:   s = f"{ccy}{v/1e12:.1f}T"
        elif v >= 1e9:  s = f"{ccy}{v/1e9:.1f}B"
        elif v >= 1e6:  s = f"{ccy}{v/1e6:.0f}M"
        else:           s = f"{ccy}{v:,.0f}"
        return f"({s})" if neg else s
    except:
        return "—"


def fmt_pct(val, decimals=1):
    try:
        v = float(val)
        if pd.isna(v): return "—"
        if abs(v) <= 1: v *= 100
        return f"{v:.{decimals}f}%"
    except:
        return "—"


def fmt_multiple(val):
    try:
        v = float(val)
        if pd.isna(v): return "—"
        return f"{v:.0f}x"
    except:
        return "—"


def fmt_eps(val, ccy="$"):
    try:
        v = float(val)
        if pd.isna(v): return "—"
        return f"{ccy}{v:.2f}"
    except:
        return "—"


def to_pct_list(s):
    out = []
    for v in s:
        try:
            v = float(v)
            out.append(v * 100 if abs(v) <= 1 else v)
        except:
            out.append(None)
    return out


def delta_html(val):
    if val is None: return ""
    sign = "+" if val >= 0 else ""
    cls  = "delta-up" if val >= 0 else "delta-down"
    return f'<span class="metric-delta {cls}">{sign}{val:.1f}%</span>'
