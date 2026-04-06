import streamlit as st
import pandas as pd
import requests
from datetime import datetime

from config import API_KEY, BASE_URL


# ── Fundamental data ──────────────────────────────────────────────────────────

@st.cache_data(ttl=3600, show_spinner=False)
def fetch_fundamental(endpoint, ticker):
    """Fetch income-statement, balance-sheet, or cash-flow from roic.ai."""
    url = f"{BASE_URL}/{endpoint}/{ticker}"
    params = {"period": "annual", "limit": 20, "order": "desc", "apikey": API_KEY}
    try:
        r = requests.get(url, params=params, timeout=15)
        r.raise_for_status()
        raw = r.json()
        rows = raw if isinstance(raw, list) else raw.get("data", [])
        if not rows:
            return pd.DataFrame()
        df = pd.DataFrame(rows)
        for col in ["date", "Date", "period_end", "fiscal_year_end"]:
            if col in df.columns:
                df[col] = pd.to_datetime(df[col], errors="coerce")
                df = df.rename(columns={col: "Date"})
                break
        skip = {"Date", "ticker", "Ticker", "period", "Period",
                "period_label", "currency", "Currency"}
        for col in df.columns:
            if col not in skip:
                df[col] = pd.to_numeric(df[col], errors="coerce")
        df = df.sort_values("Date").reset_index(drop=True)
        return df
    except Exception:
        return pd.DataFrame()


@st.cache_data(ttl=3600, show_spinner=False)
def fetch_fundamental_quarterly(endpoint, ticker):
    """Fetch quarterly data from roic.ai."""
    url = f"{BASE_URL}/{endpoint}/{ticker}"
    params = {"period": "quarterly", "limit": 8, "order": "desc", "apikey": API_KEY}
    try:
        r = requests.get(url, params=params, timeout=15)
        r.raise_for_status()
        raw = r.json()
        rows = raw if isinstance(raw, list) else raw.get("data", [])
        if not rows:
            return pd.DataFrame()
        df = pd.DataFrame(rows)
        for col in ["date", "Date", "period_end", "fiscal_year_end"]:
            if col in df.columns:
                df[col] = pd.to_datetime(df[col], errors="coerce")
                df = df.rename(columns={col: "Date"})
                break
        skip = {"Date", "ticker", "Ticker", "period", "Period",
                "period_label", "currency", "Currency"}
        for col in df.columns:
            if col not in skip:
                df[col] = pd.to_numeric(df[col], errors="coerce")
        df = df.sort_values("Date").reset_index(drop=True)
        return df
    except Exception:
        return pd.DataFrame()


@st.cache_data(ttl=3600, show_spinner=False)
def fetch_prices(ticker):
    """Fetch full daily price history."""
    url = f"{BASE_URL}/stock-prices/{ticker}"
    params = {"limit": 100000, "order": "asc", "apikey": API_KEY}
    try:
        r = requests.get(url, params=params, timeout=15)
        r.raise_for_status()
        raw = r.json()
        rows = raw if isinstance(raw, list) else raw.get("data", [])
        df = pd.DataFrame(rows)
        if "date" in df.columns:
            df["date"] = pd.to_datetime(df["date"])
        return df
    except:
        return pd.DataFrame()


@st.cache_data(ttl=3600, show_spinner=False)
def fetch_year_end_price(ticker, month):
    """Return a Series of year-end closing prices aligned to fiscal year end month."""
    prices = fetch_prices(ticker)
    if prices.empty or "date" not in prices.columns:
        return pd.Series(dtype=float), []
    close_col = next((c for c in ["adj_close", "adjusted_close", "close"]
                      if c in prices.columns), None)
    if not close_col:
        return pd.Series(dtype=float), []
    prices = prices.dropna(subset=["date", close_col])
    prices["year"]  = prices["date"].dt.year
    prices["month"] = prices["date"].dt.month
    monthly = prices[prices["month"] == month]
    if monthly.empty:
        return pd.Series(dtype=float), []
    idx = monthly.groupby("year")["date"].idxmax()
    result = monthly.loc[idx].set_index("year")[close_col].sort_index()
    return result, result.index.astype(str).tolist()


@st.cache_data(ttl=3600, show_spinner=False)
def fetch_annual_average_prices(ticker, dates_series):
    """Calculate the average stock price (VWAP) for the exact 1-year fiscal period
    ending on each reporting date."""
    prices = fetch_prices(ticker)
    if prices.empty or "date" not in prices.columns:
        return pd.Series([None] * len(dates_series))

    prices = prices.set_index("date").sort_index()
    val_col = next((c for c in ["vwap", "adj_close", "close"]
                    if c in prices.columns), None)
    if not val_col:
        return pd.Series([None] * len(dates_series))

    prices[val_col] = pd.to_numeric(prices[val_col], errors="coerce")

    avg_prices = []
    for d in dates_series:
        if pd.isna(d):
            avg_prices.append(None)
            continue
        end_date   = d
        start_date = d - pd.DateOffset(years=1)
        mask = (prices.index > start_date) & (prices.index <= end_date)
        period_prices = prices.loc[mask, val_col]
        if not period_prices.empty and not period_prices.isna().all():
            avg_prices.append(float(period_prices.mean()))
        else:
            avg_prices.append(None)

    return pd.Series(avg_prices)


# ── Earnings transcripts ───────────────────────────────────────────────────────

@st.cache_data(ttl=3600, show_spinner=False)
def fetch_transcript(ticker, year, quarter):
    """Fetch a single earnings call transcript."""
    url = f"{BASE_URL}/company/earnings-calls/transcript/{ticker}"
    params = {"year": year, "quarter": quarter, "apikey": API_KEY}
    try:
        r = requests.get(url, params=params, timeout=15)
        r.raise_for_status()
        data = r.json()
        if isinstance(data, dict):
            return data.get("transcript", data.get("text", str(data)))
        return str(data)
    except:
        return None


def fetch_last_4_transcripts(ticker):
    transcripts = []
    now     = datetime.now()
    year    = now.year
    quarter = (now.month - 1) // 3 + 1
    attempts = 0
    while len(transcripts) < 4 and attempts < 12:
        text = fetch_transcript(ticker, year, quarter)
        if text and len(str(text)) > 100:
            transcripts.append({"year": year, "quarter": quarter,
                                 "text": str(text)[:8000]})
        quarter -= 1
        if quarter < 1:
            quarter = 4
            year -= 1
        attempts += 1
    return transcripts


# ── Prompt helper ──────────────────────────────────────────────────────────────

def format_financials_for_prompt(inc, bs, cf, years):
    def s(df, *cols):
        for c in cols:
            if c in df.columns:
                return pd.to_numeric(df[c], errors="coerce")
        return pd.Series(dtype=float)

    lines = ["=== INCOME STATEMENT (last 5 years) ==="]
    recent_years = years[-5:] if len(years) >= 5 else years
    recent_idx   = slice(-len(recent_years), None)

    rev  = s(inc, "is_sales_revenue_turnover", "is_sales_and_services_revenues").iloc[recent_idx].tolist()
    gp   = s(inc, "is_gross_profit").iloc[recent_idx].tolist()
    ebit = s(inc, "ebit").iloc[recent_idx].tolist()
    ni   = s(inc, "is_net_income").iloc[recent_idx].tolist()
    eps  = s(inc, "diluted_eps").iloc[recent_idx].tolist()
    gm   = s(inc, "gross_margin").iloc[recent_idx].tolist()
    opm  = s(inc, "oper_margin").iloc[recent_idx].tolist()
    npm  = s(inc, "profit_margin").iloc[recent_idx].tolist()

    for i, y in enumerate(recent_years):
        def v(lst):
            try: return f"{lst[i]/1e9:.2f}B" if lst[i] and not pd.isna(lst[i]) else "N/A"
            except: return "N/A"
        def pct(lst):
            try: return f"{lst[i]:.1f}%" if lst[i] and not pd.isna(lst[i]) else "N/A"
            except: return "N/A"
        def ep(lst):
            try: return f"${lst[i]:.2f}" if lst[i] and not pd.isna(lst[i]) else "N/A"
            except: return "N/A"
        lines.append(
            f"{y}: Rev={v(rev)}, GrossProfit={v(gp)}, EBIT={v(ebit)}, "
            f"NetIncome={v(ni)}, EPS={ep(eps)}, GM={pct(gm)}, OM={pct(opm)}, NM={pct(npm)}"
        )

    lines.append("\n=== BALANCE SHEET (latest year) ===")
    if not bs.empty:
        def bv(col):
            try:
                val = float(bs[col].iloc[-1]) if col in bs.columns and pd.notna(bs[col].iloc[-1]) else None
                return f"{val/1e9:.2f}B" if val else "N/A"
            except: return "N/A"
        lines.append(f"Total Assets={bv('bs_tot_asset')}, Total Equity={bv('bs_total_equity')}, Net Debt={bv('net_debt')}")
        lines.append(f"Current Assets={bv('bs_cur_asset_report')}, Current Liabilities={bv('bs_cur_liab')}")

    lines.append("\n=== CASH FLOW (last 5 years) ===")
    if not cf.empty:
        fcf = s(cf, "cf_free_cash_flow").iloc[recent_idx].tolist()
        cfo = s(cf, "cf_cash_from_oper").iloc[recent_idx].tolist()
        dep = s(cf, "cf_depr_amort").iloc[recent_idx].tolist()
        cap = s(cf, "cf_cap_expenditures").iloc[recent_idx].tolist()
        cf_years = cf["Date"].dt.year.astype(str).tolist() if "Date" in cf.columns else recent_years
        cf_recent = cf_years[-5:] if len(cf_years) >= 5 else cf_years
        for i, y in enumerate(cf_recent):
            def cv(lst):
                try: return f"{lst[i]/1e9:.2f}B" if lst[i] and not pd.isna(lst[i]) else "N/A"
                except: return "N/A"
            lines.append(f"{y}: CFO={cv(cfo)}, FCF={cv(fcf)}, D&A={cv(dep)}, CapEx={cv(cap)}")

    return "\n".join(lines)
