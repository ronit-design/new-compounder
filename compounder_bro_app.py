import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import requests
import io
import re
from datetime import datetime

# ── Config ────────────────────────────────────────────────────────────────────
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

# Initialise editable watchlist in session state
if "stocks_list" not in st.session_state:
    st.session_state.stocks_list = [{"Name": k, "Ticker": v} for k, v in STOCKS.items()]

# ── Design tokens ─────────────────────────────────────────────────────────────
C_BG        = "#FFFFFF"
C_SURFACE   = "#FAFAFA"
C_BORDER    = "#E8E8E8"
C_BORDER2   = "#F0F0F0"
C_TEXT      = "#111111"
C_TEXT2     = "#555555"
C_TEXT3     = "#999999"
C_ACCENT    = "#111111"   # single accent — charcoal
C_UP        = "#1A7F4B"   # muted green — not neon
C_DOWN      = "#C0392B"   # muted red
C_SIDEBAR   = "#F7F7F7"

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Compounder",
    page_icon=None,
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600&display=swap');

*, *::before, *::after {{ box-sizing: border-box; }}

html, body, [class*="css"] {{
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
    -webkit-font-smoothing: antialiased;
    background-color: {C_BG};
    color: {C_TEXT};
}}

/* ── Hide Streamlit chrome ── */
#MainMenu, footer, header {{ display: none !important; }}
.stDeployButton {{ display: none !important; }}
[data-testid="stToolbar"] {{ display: none !important; }}

/* ── Main container ── */
.block-container {{
    padding: 2.5rem 3rem 4rem 3rem !important;
    max-width: 1400px !important;
}}

/* ── Sidebar ── */
section[data-testid="stSidebar"] {{
    background-color: {C_SIDEBAR} !important;
    border-right: 1px solid {C_BORDER} !important;
}}
section[data-testid="stSidebar"] .block-container {{
    padding: 2rem 1.5rem !important;
}}
[data-testid="stSidebarNav"] {{ display: none; }}

/* ── Sidebar radio ── */
.stRadio > label {{ display: none; }}
.stRadio [data-testid="stMarkdownContainer"] p {{
    font-size: 0.82rem !important;
    font-weight: 500 !important;
    color: {C_TEXT2} !important;
    letter-spacing: 0.01em;
}}

/* ── Sidebar selectbox ── */
.stSelectbox > label {{
    font-size: 0.72rem !important;
    font-weight: 500 !important;
    color: {C_TEXT3} !important;
    text-transform: uppercase !important;
    letter-spacing: 0.08em !important;
}}

/* ── Tabs ── */
.stTabs [data-baseweb="tab-list"] {{
    gap: 0;
    border-bottom: 1px solid {C_BORDER} !important;
    background: transparent !important;
}}
.stTabs [data-baseweb="tab"] {{
    background: transparent !important;
    border: none !important;
    padding: 0.6rem 1.2rem !important;
    font-size: 0.82rem !important;
    font-weight: 500 !important;
    color: {C_TEXT3} !important;
    border-bottom: 2px solid transparent !important;
    margin-bottom: -1px;
}}
.stTabs [aria-selected="true"] {{
    color: {C_TEXT} !important;
    border-bottom: 2px solid {C_TEXT} !important;
    font-weight: 600 !important;
}}
.stTabs [data-baseweb="tab-panel"] {{
    padding-top: 1.5rem !important;
}}

/* ── Expander ── */
.streamlit-expanderHeader {{
    font-size: 0.8rem !important;
    color: {C_TEXT3} !important;
    font-weight: 500 !important;
    background: transparent !important;
    border: none !important;
    padding-left: 0 !important;
}}
.streamlit-expanderContent {{
    border: 1px solid {C_BORDER} !important;
    border-radius: 4px !important;
}}

/* ── Buttons ── */
.stButton > button {{
    background: transparent !important;
    border: 1px solid {C_BORDER} !important;
    color: {C_TEXT2} !important;
    font-size: 0.78rem !important;
    font-weight: 500 !important;
    padding: 0.4rem 1rem !important;
    border-radius: 4px !important;
    transition: border-color 0.15s, color 0.15s;
}}
.stButton > button:hover {{
    border-color: {C_TEXT} !important;
    color: {C_TEXT} !important;
}}

/* ── Divider ── */
hr {{
    border: none !important;
    border-top: 1px solid {C_BORDER} !important;
    margin: 1.5rem 0 !important;
}}

/* ── Spinner ── */
.stSpinner > div {{ border-top-color: {C_TEXT} !important; }}

/* ── Metric card ── */
.metric-block {{
    padding: 1.25rem 0;
    border-bottom: 1px solid {C_BORDER2};
}}
.metric-label {{
    font-size: 0.7rem;
    font-weight: 500;
    color: {C_TEXT3};
    text-transform: uppercase;
    letter-spacing: 0.08em;
    margin-bottom: 0.4rem;
}}
.metric-value {{
    font-size: 1.6rem;
    font-weight: 600;
    color: {C_TEXT};
    letter-spacing: -0.02em;
    line-height: 1;
}}
.metric-delta {{
    font-size: 0.72rem;
    font-weight: 500;
    margin-top: 0.3rem;
    letter-spacing: 0.01em;
}}
.delta-up   {{ color: {C_UP}; }}
.delta-down {{ color: {C_DOWN}; }}
.delta-nil  {{ color: {C_TEXT3}; }}

/* ── Page title ── */
.page-title {{
    font-size: 1.1rem;
    font-weight: 600;
    color: {C_TEXT};
    letter-spacing: -0.01em;
    margin-bottom: 0.15rem;
}}
.page-sub {{
    font-size: 0.78rem;
    color: {C_TEXT3};
    font-weight: 400;
    margin-bottom: 2rem;
}}

/* ── Section label ── */
.section-label {{
    font-size: 0.7rem;
    font-weight: 500;
    color: {C_TEXT3};
    text-transform: uppercase;
    letter-spacing: 0.08em;
    margin-bottom: 0.75rem;
    display: block;
}}

/* ── Summary table ── */
.tbl-row {{
    display: grid;
    grid-template-columns: 1.4fr 0.55fr 0.85fr 0.85fr 0.7fr 0.85fr 0.7fr 0.85fr 0.7fr 0.7fr 0.7fr 0.6fr 0.65fr;
    padding: 0.6rem 0;
    border-bottom: 1px solid {C_BORDER2};
    align-items: center;
}}
.tbl-header-row {{
    border-bottom: 1px solid {C_BORDER} !important;
    padding-bottom: 0.5rem !important;
    margin-bottom: 0.1rem;
}}
.tbl-header {{
    font-size: 0.67rem;
    font-weight: 500;
    color: {C_TEXT3};
    text-transform: uppercase;
    letter-spacing: 0.07em;
}}
.tbl-cell {{
    font-size: 0.8rem;
    color: {C_TEXT};
    font-variant-numeric: tabular-nums;
}}
.tbl-name {{ font-weight: 500; font-size: 0.82rem; }}
.tbl-ticker {{ color: {C_TEXT3}; font-size: 0.72rem; }}

/* ── Sidebar company list ── */
.nav-company {{
    font-size: 0.82rem;
    font-weight: 400;
    color: {C_TEXT2};
    padding: 0.45rem 0.6rem;
    border-radius: 4px;
    cursor: pointer;
    transition: background 0.1s;
}}
.nav-company:hover {{ background: {C_BORDER}; }}
.nav-company-active {{
    font-weight: 600;
    color: {C_TEXT};
    background: {C_BORDER};
    padding: 0.45rem 0.6rem;
    border-radius: 4px;
    font-size: 0.82rem;
}}
</style>
""", unsafe_allow_html=True)


# ── Data loaders ──────────────────────────────────────────────────────────────
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
    except Exception as e:
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
    """
    Return a Series of year-end closing prices aligned to fiscal year end month.
    """
    prices = fetch_prices(ticker)
    if prices.empty or "date" not in prices.columns:
        return pd.Series(dtype=float), []
    close_col = next((c for c in ["adj_close", "adjusted_close", "close"] if c in prices.columns), None)
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
    """
    Calculates the average stock price (VWAP) for the exact 1-year fiscal period 
    ending on each reporting date.
    """
    prices = fetch_prices(ticker)
    if prices.empty or "date" not in prices.columns:
        return pd.Series([None] * len(dates_series))
    
    prices = prices.set_index("date").sort_index()
    val_col = next((c for c in ["vwap", "adj_close", "close"] if c in prices.columns), None)
    if not val_col:
        return pd.Series([None] * len(dates_series))
        
    # ── THE FIX: Force the price column to be numeric so we can calculate the mean ──
    prices[val_col] = pd.to_numeric(prices[val_col], errors="coerce")
        
    avg_prices = []
    for d in dates_series:
        if pd.isna(d):
            avg_prices.append(None)
            continue
        
        end_date = d
        start_date = d - pd.DateOffset(years=1)
        mask = (prices.index > start_date) & (prices.index <= end_date)
        period_prices = prices.loc[mask, val_col]
        
        # Only calculate mean if the period has valid numeric data
        if not period_prices.empty and not period_prices.isna().all():
            avg_prices.append(float(period_prices.mean()))
        else:
            avg_prices.append(None)
            
    return pd.Series(avg_prices)


# ── Earnings transcript + research report ────────────────────────────────────
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
    from datetime import datetime
    transcripts = []
    now = datetime.now()
    year = now.year
    quarter = (now.month - 1) // 3 + 1
    attempts = 0
    while len(transcripts) < 4 and attempts < 12:
        text = fetch_transcript(ticker, year, quarter)
        if text and len(str(text)) > 100:
            transcripts.append({"year": year, "quarter": quarter, "text": str(text)[:8000]})
        quarter -= 1
        if quarter < 1:
            quarter = 4
            year -= 1
        attempts += 1
    return transcripts

def format_financials_for_prompt(inc, bs, cf, years):
    def s(df, *cols):
        for c in cols:
            if c in df.columns:
                return pd.to_numeric(df[c], errors="coerce")
        return pd.Series(dtype=float)

    lines = ["=== INCOME STATEMENT (last 5 years) ==="]
    recent_years = years[-5:] if len(years) >= 5 else years
    recent_idx = slice(-len(recent_years), None)

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
        lines.append(f"{y}: Rev={v(rev)}, GrossProfit={v(gp)}, EBIT={v(ebit)}, NetIncome={v(ni)}, EPS={ep(eps)}, GM={pct(gm)}, OM={pct(opm)}, NM={pct(npm)}")

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

# ── EDGAR 10-K / 20-F fetcher ────────────────────────────────────────────────

def edgar_get_cik(ticker):
    try:
        hdrs = {"User-Agent": "compounder-app research@example.com"}
        r = requests.get("https://www.sec.gov/files/company_tickers.json",
                         headers=hdrs, timeout=15)
        r.raise_for_status()
        t_upper = ticker.upper()
        for entry in r.json().values():
            if entry.get("ticker", "").upper() == t_upper:
                return str(entry["cik_str"]).zfill(10)
        return None
    except:
        return None

def edgar_latest_filing(cik, form_type):
    try:
        hdrs = {"User-Agent": "compounder-app research@example.com"}
        r = requests.get(f"https://data.sec.gov/submissions/CIK{cik}.json",
                         headers=hdrs, timeout=15)
        r.raise_for_status()
        recent = r.json().get("filings", {}).get("recent", {})
        forms   = recent.get("form", [])
        accnums = recent.get("accessionNumber", [])
        dates   = recent.get("filingDate", [])
        for i, form in enumerate(forms):
            if form in (form_type, form_type + "/A"):
                return accnums[i].replace("-", ""), dates[i]
        return None, None
    except:
        return None, None

@st.cache_data(ttl=86400, show_spinner=False)
def fetch_rsu_tax_xbrl(ticker):
    cik = edgar_get_cik(ticker)
    if not cik:
        return {}
    try:
        hdrs = {"User-Agent": "compounder-app research@example.com"}
        url  = f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"
        r    = requests.get(url, headers=hdrs, timeout=30)
        r.raise_for_status()
        us_gaap  = r.json().get("facts", {}).get("us-gaap", {})
        concept  = us_gaap.get("PaymentsRelatedToTaxWithholdingForShareBasedCompensation", {})
        entries  = concept.get("units", {}).get("USD", [])
        results  = {}
        filed_at = {}  
        for e in entries:
            if e.get("form") not in ("10-K", "20-F", "10-K/A", "20-F/A"):
                continue
            end_date = e.get("end", "")
            year     = end_date[:4] if end_date else None
            val      = e.get("val")
            filed    = e.get("filed", "")
            if year and val is not None:
                if year not in filed_at or filed > filed_at[year]:
                    results[year]  = abs(float(val))
                    filed_at[year] = filed
        return results
    except Exception:
        return {}


# ── Forensic Accounting ────────────────────────────────────────────────────────

@st.cache_data(ttl=86400, show_spinner=False)
def edgar_list_annual_filings(cik, n=5):
    try:
        hdrs    = {"User-Agent": "compounder-app research@example.com"}
        r       = requests.get(f"https://data.sec.gov/submissions/CIK{cik}.json",
                               headers=hdrs, timeout=15)
        r.raise_for_status()
        recent   = r.json().get("filings", {}).get("recent", {})
        forms    = recent.get("form", [])
        accnums  = recent.get("accessionNumber", [])
        dates    = recent.get("filingDate", [])
        rptdates = recent.get("reportDate", dates)
        results  = []
        annual_forms = {"10-K", "10-K/A", "20-F", "20-F/A"}
        for i, form in enumerate(forms):
            if form in annual_forms:
                rpt         = rptdates[i] if i < len(rptdates) else dates[i]
                report_year = str(rpt)[:4] if rpt else str(dates[i])[:4]
                results.append((accnums[i].replace("-", ""), dates[i], report_year))
            if len(results) >= n:
                break
        return results
    except Exception:
        return []

@st.cache_data(ttl=3600, show_spinner=False)
def fetch_forensic_xbrl(ticker):
    cik = edgar_get_cik(ticker)
    if not cik:
        return {}
    try:
        hdrs = {"User-Agent": "compounder-app research@example.com"}
        r    = requests.get(f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json",
                            headers=hdrs, timeout=30)
        r.raise_for_status()
        us_gaap = r.json().get("facts", {}).get("us-gaap", {})

        def get_annual(concepts, n=5):
            for name in concepts:
                entries = us_gaap.get(name, {}).get("units", {}).get("USD", [])
                if not entries:
                    continue
                by_year, filed_at = {}, {}
                for e in entries:
                    if e.get("form") not in ("10-K", "20-F", "10-K/A", "20-F/A"):
                        continue
                    yr = (e.get("end") or "")[:4]
                    fd = e.get("filed", "")
                    if yr and (yr not in filed_at or fd > filed_at[yr]):
                        by_year[yr] = e.get("val")
                        filed_at[yr] = fd
                if by_year:
                    yrs = sorted(by_year)[-n:]
                    return {y: by_year[y] for y in yrs}
            return {}

        return {
            "net_income":        get_annual(["NetIncomeLoss", "ProfitLoss"]),
            "pretax_income":     get_annual(["IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest",
                                             "IncomeLossFromContinuingOperationsBeforeIncomeTaxesMinorityInterestAndIncomeLossFromEquityMethodInvestments"]),
            "tax_expense":       get_annual(["IncomeTaxExpenseBenefit"]),
            "revenue":           get_annual(["Revenues", "RevenueFromContractWithCustomerExcludingAssessedTax", "SalesRevenueNet"]),
            "cogs":              get_annual(["CostOfRevenue", "CostOfGoodsAndServicesSold", "CostOfGoodsSold"]),
            "cfo":               get_annual(["NetCashProvidedByUsedInOperatingActivities"]),
            "asset_sale_gains":  get_annual(["GainLossOnSaleOfPropertyPlantAndEquipment", "GainLossOnDispositionOfAssets", "GainLossOnSaleOfBusiness"]),
            "investment_gains":  get_annual(["GainLossOnInvestments", "GainLossOnSaleOfInvestments", "MarketableSecuritiesGainLoss"]),
            "debt_extinguish":   get_annual(["GainsLossesOnExtinguishmentOfDebt", "GainLossOnRepurchaseOfDebtInstrument"]),
            "gross_ppe":         get_annual(["PropertyPlantAndEquipmentGross", "PropertyPlantAndEquipmentNet"]),
            "depreciation":      get_annual(["DepreciationDepletionAndAmortization", "DepreciationAndAmortization", "Depreciation", "DepreciationAmortizationAndAccretionNet"]),
            "amort_intangibles": get_annual(["AmortizationOfIntangibleAssets", "AmortizationOfAcquiredIntangibles", "AmortizationOfFiniteLivedIntangibles"]),
            "intangibles":       get_annual(["FiniteLivedIntangibleAssetsNet", "IntangibleAssetsNetExcludingGoodwill", "FiniteLivedIntangibleAssetsGross"]),
            "goodwill":          get_annual(["Goodwill"]),
            "goodwill_impair":   get_annual(["GoodwillImpairmentLoss"]),
            "capitalized_sw":    get_annual(["CapitalizedComputerSoftwareNet", "CapitalizedSoftwareDevelopmentCostsForInternalUseNet"]),
            "inventory":         get_annual(["InventoryNet", "InventoryFinishedGoodsAndWorkInProcess", "InventoryFinishedGoods"]),
            "lifo_reserve":      get_annual(["ExcessOfReplacementOrCurrentCostsOverStatedLIFOValue", "LIFOInventoryAmount"]),
            "allow_doubtful":    get_annual(["AllowanceForDoubtfulAccountsReceivableCurrent", "AllowanceForDoubtfulAccountsReceivableNoncurrent"]),
            "interest_expense":  get_annual(["InterestExpense", "InterestAndDebtExpense", "InterestExpenseDebt", "InterestPaidNet", "InterestCostsIncurred"]),
            "lease_expense":     get_annual(["OperatingLeaseExpense", "LeaseCost", "OperatingLeasesRentExpenseNet", "OperatingLeaseCost"]),
            "long_term_debt":    get_annual(["LongTermDebt", "LongTermDebtNoncurrent", "LongTermDebtAndCapitalLeaseObligations"]),
            "preferred_div":     get_annual(["DividendsPreferredStock", "PreferredStockDividendsAndOtherAdjustments"]),
            "oci":               get_annual(["OtherComprehensiveIncomeLossNetOfTax"]),
            "retained_earnings": get_annual(["RetainedEarningsAccumulatedDeficit"]),
            "accounts_rec":      get_annual(["AccountsReceivableNetCurrent", "ReceivablesNetCurrent"]),
        }
    except Exception:
        return {}


@st.cache_data(ttl=86400, show_spinner=False)
def edgar_fetch_item8_notes(cik, accession_no_dashes, max_chars=14000):
    import re as _re
    hdrs = {"User-Agent": "compounder-app research@example.com"}
    try:
        acc        = accession_no_dashes
        acc_dashes = f"{acc[:10]}-{acc[10:12]}-{acc[12:]}"
        cik_int    = int(cik)

        idx_url = f"https://www.sec.gov/Archives/edgar/data/{cik_int}/{acc}/{acc_dashes}-index.htm"
        r_idx   = requests.get(idx_url, headers=hdrs, timeout=15)
        if not r_idx.ok:
            idx_url = f"https://www.sec.gov/Archives/edgar/data/{cik_int}/{acc_dashes.replace('-','')}/{acc_dashes}-index.htm"
            r_idx   = requests.get(idx_url, headers=hdrs, timeout=15)

        doc_url = None
        if r_idx.ok:
            for row in _re.findall(r'<tr[^>]*>.*?</tr>', r_idx.text, _re.DOTALL | _re.IGNORECASE):
                hm = _re.search(r'href="(/Archives[^"]+\.htm)"', row, _re.IGNORECASE)
                tm = _re.search(r'<td[^>]*>\s*(10-K|20-F|FORM 10-K|FORM 20-F)\s*</td>', row, _re.IGNORECASE)
                if hm and tm:
                    doc_url = "https://www.sec.gov" + hm.group(1)
                    break
            if not doc_url:
                links = _re.findall(r'href="(/Archives/edgar/data/[^"]+\.htm)"', r_idx.text, _re.IGNORECASE)
                cands = ["https://www.sec.gov" + l for l in links
                         if acc.lower() in l.lower().replace("-", "").replace("/", "")]
                if cands:
                    doc_url = cands[0]

        if not doc_url: return None

        r_doc = requests.get(doc_url, headers=hdrs, timeout=60)
        if not r_doc.ok: return None

        try:
            from lxml import etree
            root = etree.fromstring(r_doc.content, parser=etree.HTMLParser())
            text = " ".join(root.itertext(with_tail=True))
        except Exception:
            text = _re.sub(r"<[^>]{1,200}>", " ", r_doc.text)
        del r_doc

        text = text.replace("\xa0", " ").replace("&amp;", "&")
        text = _re.sub(r"\s{3,}", "\n\n", text).strip()

        ms = _re.search(r"(?i)item\s*8[\s.]+financial\s+statements", text)
        me = _re.search(r"(?i)item\s*9[\s.]+", text[ms.end():]) if ms else None
        if ms:
            item8 = text[ms.start(): ms.end() + me.start() if me else ms.start() + 300000]
        else:
            item8 = text

        note_patterns = [
            r"(?i)(summary\s+of\s+significant\s+accounting\s+policies|significant\s+accounting\s+policies|basis\s+of\s+presentation)",
            r"(?i)(revenue\s+recognition|disaggregation\s+of\s+revenue|contract\s+(assets|liabilities))",
            r"(?i)(variable\s+interest\s+entit|off[\s\-]balance[\s\-]sheet|unconsolidated\s+(joint\s+venture|entit)|special\s+purpose)",
            r"(?i)(pension|defined\s+benefit|retirement\s+benefit|postretirement)",
            r"(?i)(goodwill\s+and\s+(intangible|other)|intangible\s+assets|useful\s+li(fe|ves)|amortization\s+period)",
            r"(?i)(commitments\s+and\s+contingencies|legal\s+proceedings|purchase\s+obligations|contractual\s+obligations)",
            r"(?i)(operating\s+lease|right[\s\-]of[\s\-]use|finance\s+lease)",
            r"(?i)(stock[\s\-]based\s+compensation|share[\s\-]based|equity\s+(award|plan|compensation))",
        ]

        chunks, used = [], []
        for pat in note_patterns:
            m = _re.search(pat, item8)
            if not m: continue
            s = m.start()
            if any(a <= s <= b for a, b in used): continue
            chunks.append(item8[s: s + 2500].strip())
            used.append((s, s + 2500))

        result = "\n\n---\n\n".join(chunks) if chunks else item8[:max_chars]
        return result[:max_chars]
    except Exception:
        return None

@st.cache_data(ttl=86400, show_spinner=False)
def forensic_notes_extract(notes_text, fiscal_year, company, api_key):
    import json as _json, re as _re
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
        m   = _re.search(r'\{[\s\S]*\}', raw)
        return _json.loads(m.group(0)) if m else {}
    except Exception:
        return {}


def _fetch_notes_concurrent(cik: str, filings: list) -> dict:
    from concurrent.futures import ThreadPoolExecutor, as_completed
    def _fetch_one(args):
        acc, fdate, yr = args
        return yr, edgar_fetch_item8_notes(cik, acc)

    results: dict[str, str | None] = {}
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
    from concurrent.futures import ThreadPoolExecutor, as_completed
    def _extract_one(args):
        yr, ntxt = args
        return yr, (forensic_notes_extract(ntxt, yr, company, api_key) if ntxt else {})

    results: dict[str, dict] = {}
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

    r_ar   = _to_dict(ar_s,  bs_years)
    r_inv  = _to_dict(inv_s, bs_years)

    mc_vals = [
        p * s if (pd.notna(p) and pd.notna(s) and p is not None and s is not None) else None
        for p, s in zip(price_s.tolist(), shares_s.tolist())
    ]
    r_mktcap = _to_dict(pd.Series(mc_vals, dtype=float), years)

    # ── Net buybacks & Maintenance Buybacks ──────────────────────────────────
    net_bb = [
        (abs(d) if pd.notna(d) else 0.0) - (abs(i) if pd.notna(i) else 0.0)
        for d, i in zip(decr_cap_s.tolist(), incr_cap_s.tolist())
    ]
    r_net_bb = _to_dict(pd.Series(net_bb, dtype=float), years)

    # Maintenance Buybacks = Net Buybacks - Value of Actual Share Reduction
    sh_vals = shares_s.tolist()
    px_avg_vals = avg_price_s.tolist()
    maint_bb_vals = []
    
    for i in range(len(years)):
        bb_net  = net_bb[i]
        sh_curr = sh_vals[i]
        sh_prev = sh_vals[i-1] if i > 0 else sh_curr
        px_avg  = px_avg_vals[i]
        
        if pd.notna(sh_curr) and pd.notna(sh_prev) and pd.notna(px_avg) and px_avg > 0:
            delta_shares = sh_prev - sh_curr
            # If delta_shares <= 0, shares grew, so reduction value is 0
            val_reduction = max(0, delta_shares) * px_avg 
            maint_bb = max(0, bb_net - val_reduction)
        else:
            maint_bb = max(0, bb_net)
            
        maint_bb_vals.append(maint_bb)

    r_maint_bb = _to_dict(pd.Series(maint_bb_vals, dtype=float), years)

    # ── Owners' Earnings ─────────────────────────────────────────────────────
    oe_vals = []
    for yr in sorted(r_ni):
        ni_v   = r_ni.get(yr) or 0.0
        sbc_v  = r_sbc.get(yr) or 0.0
        m_bb_v = r_maint_bb.get(yr) or 0.0
        rsu_v  = r_rsu.get(yr) or 0.0
        oe_vals.append((yr, ni_v + abs(sbc_v) - m_bb_v - abs(rsu_v)))
    r_oe = {yr: v for yr, v in oe_vals}

    return {
        "net_income":        _merge(xbrl.get("net_income",    {}), r_ni),
        "revenue":           _merge(xbrl.get("revenue",       {}), r_rev),
        "cogs":              _merge(xbrl.get("cogs",          {}), r_cogs),
        "cfo":               _merge(xbrl.get("cfo",           {}), r_cfo),
        "accounts_rec":      _merge(xbrl.get("accounts_rec",  {}), r_ar),
        "inventory":         _merge(xbrl.get("inventory",     {}), r_inv),
        "pretax_income":     xbrl.get("pretax_income",    {}),
        "tax_expense":       xbrl.get("tax_expense",      {}),
        "asset_sale_gains":  xbrl.get("asset_sale_gains",  {}),
        "investment_gains":  xbrl.get("investment_gains",  {}),
        "debt_extinguish":   xbrl.get("debt_extinguish",   {}),
        "gross_ppe":         xbrl.get("gross_ppe",         {}),
        "depreciation":      xbrl.get("depreciation",      {}),
        "amort_intangibles": xbrl.get("amort_intangibles", {}),
        "intangibles":       xbrl.get("intangibles",       {}),
        "goodwill":          xbrl.get("goodwill",          {}),
        "goodwill_impair":   xbrl.get("goodwill_impair",   {}),
        "capitalized_sw":    xbrl.get("capitalized_sw",    {}),
        "lifo_reserve":      xbrl.get("lifo_reserve",      {}),
        "allow_doubtful":    xbrl.get("allow_doubtful",    {}),
        "interest_expense":  xbrl.get("interest_expense",  {}),
        "lease_expense":     xbrl.get("lease_expense",     {}),
        "long_term_debt":    xbrl.get("long_term_debt",    {}),
        "preferred_div":     xbrl.get("preferred_div",     {}),
        "oci":               xbrl.get("oci",               {}),
        "retained_earnings": xbrl.get("retained_earnings", {}),
        "operating_income":  r_oi,
        "free_cash_flow":    r_fcf,
        "net_debt":          r_nd,
        "market_cap":        r_mktcap,
        "sbc":               r_sbc,
        "net_buybacks":      r_net_bb,
        "maintenance_buybacks": r_maint_bb,
        "rsu_tax":           r_rsu,
        "owners_earnings":   r_oe,
    }


def _fmt_xbrl_table(dataset):
    if not dataset:
        return "No quantitative data available."

    all_years: set[str] = set()
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
        ("gross_ppe",        "Gross PP&E"),
        ("depreciation",     "Total D&A"),
        ("amort_intangibles","Amort. of Intangibles"),
        ("capitalized_sw",   "Capitalized Software"),
        ("intangibles",      "Intangible Assets (net)"),
        ("goodwill",         "Goodwill"),
    ])
    rows += section("── Inventory & Reserve Quality ──────────────────────────────", [
        ("inventory",        "Inventory"),
        ("lifo_reserve",     "LIFO Reserve (0=FIFO)"),
        ("accounts_rec",     "Accounts Receivable"),
        ("allow_doubtful",   "Allowance: Doubtful Accts"),
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
        if not sig: continue
        lines.append(f"FY{yr}:")
        for k, v in sig.items():
            if v and str(v).lower() not in ("null", "none", ""):
                lines.append(f"  {k.replace('_',' ')}: {v}")
    return "\n".join(lines) if lines else "Notes extraction unavailable."

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

def edgar_fetch_filing_text(cik, accession_no_dashes, max_chars=80000):
    import re as _re
    hdrs = {"User-Agent": "compounder-app research@example.com"}
    try:
        acc = accession_no_dashes
        acc_dashes = f"{acc[:10]}-{acc[10:12]}-{acc[12:]}"
        cik_int = int(cik)

        idx_url = f"https://data.sec.gov/submissions/CIK{cik}.json"
        index_json_url = (f"https://www.sec.gov/cgi-bin/browse-edgar"
                          f"?action=getcompany&CIK={cik_int}&type=10-K"
                          f"&dateb=&owner=include&count=1&search_text=")

        idx_page_url = (f"https://www.sec.gov/Archives/edgar/data/"
                        f"{cik_int}/{acc}/{acc_dashes}-index.htm")
        r_idx = requests.get(idx_page_url, headers=hdrs, timeout=15)

        if not r_idx.ok:
            idx_page_url = (f"https://www.sec.gov/Archives/edgar/data/"
                            f"{cik_int}/{acc_dashes.replace('-','')}/{acc_dashes}-index.htm")
            r_idx = requests.get(idx_page_url, headers=hdrs, timeout=15)

        doc_url = None
        if r_idx.ok:
            rows = _re.findall(r'<tr[^>]*>.*?</tr>', r_idx.text, _re.DOTALL | _re.IGNORECASE)
            candidates = []
            for row in rows:
                href_m = _re.search(r'href="(/Archives[^"]+\.htm)"', row, _re.IGNORECASE)
                type_m = _re.search(r'<td[^>]*>\s*(10-K|20-F|FORM 10-K|FORM 20-F)\s*</td>', row, _re.IGNORECASE)
                if href_m and type_m:
                    candidates.append("https://www.sec.gov" + href_m.group(1))
            if not candidates:
                all_links = _re.findall(r'href="(/Archives/edgar/data/[^"]+\.htm)"', r_idx.text, _re.IGNORECASE)
                candidates = ["https://www.sec.gov" + l for l in all_links
                              if acc.lower() in l.lower().replace("-", "").replace("/", "")]
            if candidates:
                doc_url = candidates[0]

        if not doc_url: return None

        r_doc = requests.get(doc_url, headers=hdrs, timeout=60)
        if not r_doc.ok: return None

        try:
            from lxml import etree
            root = etree.fromstring(r_doc.content, parser=etree.HTMLParser())
            text = " ".join(root.itertext(with_tail=True))
        except Exception:
            text = _re.sub(r"<[^>]{1,200}>", " ", r_doc.text)
        del r_doc 

        text = text.replace("\xa0", " ").replace("&amp;", "&")
        text = _re.sub(r"\s{3,}", "\n\n", text).strip()

        sections = {}
        patterns = [
            ("BUSINESS", r"(?i)item\s*1[\s.]+business\b", r"(?i)item\s*1a[\s.]+risk"),
            ("MD&A", r"(?i)item\s*7[\s.]+management.{0,60}?discussion", r"(?i)item\s*7a[\s.]+"),
        ]
        for name, start_pat, end_pat in patterns:
            m_s = _re.search(start_pat, text)
            if not m_s: continue
            tail  = text[m_s.end():]
            m_e   = _re.search(end_pat, tail)
            chunk = tail[:m_e.start()] if m_e else tail[:30000]
            sections[name] = chunk[:25000].strip()

        if sections:
            out = ""
            for name, txt in sections.items():
                out += f"\n\n=== {name} ===\n{txt}"
            return out[:max_chars]

        return text[5000:5000 + max_chars]
    except Exception:
        return None

def fetch_10k_text(ticker):
    cik = edgar_get_cik(ticker)
    if not cik:
        return None, None, None
    for form in ("10-K", "20-F"):
        acc, date = edgar_latest_filing(cik, form)
        if acc:
            text = edgar_fetch_filing_text(cik, acc)
            if text and len(text) > 500:
                return text, form, date
    return None, None, None

def _build_prompt(company_name, ticker, financials_text, transcript_text,
                  extra_context="", source_note=""):
    return f"""MASTER AI INSTRUCTION: THE OBJECTIVITY MANDATE
You must remain ruthlessly objective and strictly unbiased. Your mandate is not to pitch a long or short position, but to uncover the absolute ground truth of the business. Present both structural strengths and fatal flaws with equal clinical detachment. Do not sugarcoat poor capital allocation, and do not dismiss durable moats. Analyze the data without emotion; it does not matter if the company looks good or bad to the reader.

You are writing a comprehensive research report on {company_name} ({ticker}) for a sophisticated investment committee. {source_note}

ACCURACY & SOURCING RULES — ZERO TOLERANCE:
Every financial figure must be sourced inline immediately after the number, e.g. (FY2024 Income Statement), (FY2024 Balance Sheet), (FY2024 Cash Flow Statement). Every piece of management commentary must include a direct verbatim quote where available, followed by its source, e.g. CEO John Smith stated "we expect margins to expand by 200 basis points" (Q3 2024 Earnings Call). Every fact from the SEC filing must be cited, e.g. (10-K 2024, Business Section) or (20-F 2024, MD&A). Do not state any number without a source. Do not paraphrase management when a direct quote exists — use their exact words and cite the call. Before writing any number, double-check it against the provided data.

CURRENCY: State the reporting currency explicitly for every figure — "USD 4.2B", "EUR 890M", "INR 1.47T". Never use bare currency symbols.

FORMATTING — ABSOLUTE AND NON-NEGOTIABLE:
Write exclusively in continuous flowing prose. No bullet points, no dashes as list markers, no numbered sub-lists, no tables anywhere in the body. Every section must read like a chapter from a serious investment research book — dense, analytical paragraphs that build a sustained argument. Do not write one sentence per line. Every paragraph must be at minimum five sentences, containing a point, evidence from the data, analysis of what that evidence means, and a conclusion. Begin the report immediately with the first section heading — no preamble, no meta-commentary. Section headings must appear exactly as written below on their own line with no markdown characters.

DATA PROVIDED:
{financials_text}{transcript_text}{extra_context}

1. THE FOUNDATION: BUSINESS OVERVIEW & TANGIBLE SCALE
Stripped of all corporate jargon and marketing buzzwords, explain exactly what this business does and walk through the life cycle of a single dollar from the customer's wallet to the company's bank account. Then quantify the tangible scale of the operation with precision — exact physical assets such as number of retail locations, aircraft, manufacturing plants, or logistics hubs, or digital scale such as monthly active users, data centres, or compute capacity, sourced from the filing or financial statements. For each distinct operating segment, explain the exact mechanism for making money and state precisely what percentage of total revenue and operating profit that segment represents, using real figures. Define what a single "unit" of sale is for this business and calculate the true contribution margin of that unit — revenue minus strictly variable costs — and identify at what volume the business breaks even. Spend substantial space here because understanding the precise economics of value creation and value leakage is the foundation of everything that follows.

2. THE BATTLEFIELD: INDUSTRY LANDSCAPE & COMPETITIVE PROFILE
Describe the broader industry with precision: is it consolidated or highly fragmented, experiencing secular growth or structural decline, and what phase of the industry life cycle are we in. Name the top three to five direct competitors and identify in which specific arenas — geographic regions, product tiers, customer demographics — they directly clash with this company. Analyse how competitors fundamentally differ in their operating models, cost structures, vertical integration, and target audiences, using quantitative comparisons where the data supports it. Then prove the moat — do not simply name it. If the claim is network effects, explain precisely how adding one more user or customer makes the product more valuable and why a well-funded new entrant cannot replicate this. If the claim is cost advantage, show the actual cost gap in basis points and explain the structural source of it. If switching costs, quantify the financial, operational, and psychological friction a customer endures to replace this product. A named moat without a mechanism is not an investment insight — it is a platitude.

3. THE GENERALS: MANAGEMENT, ALIGNMENT & TRACK RECORD
Identify the key decision-makers — CEO, CFO, and COO — their background prior to this company, and how long they have held their current positions. Then audit the three to four most consequential strategic or capital allocation decisions made by this specific management team over the last decade, including major acquisitions, aggressive expansions, or pivots in strategy, and deliver a clear verdict on whether each decision created or destroyed shareholder value, backed by measurable outcomes. Examine insider ownership precisely: what percentage do executives and founders own, are they buying shares on the open market, and what does the pattern of stock-based compensation and insider selling tell you about their conviction in the business. Where earnings call transcripts are available, use direct verbatim quotes from management to assess their candour, strategic clarity, and willingness to acknowledge problems — quote them precisely and cite each call. Assess whether the incentive structures disclosed in the proxy or filing align management with long-term free cash flow per share and return on invested capital, or whether they are optimising for short-term adjusted metrics that flatter performance.

4. THE CHOKEPOINTS: CUSTOMER DYNAMICS & SUPPLY CHAIN
Analyse the customer base with specificity: is revenue concentrated among a few large clients or distributed across millions of small ones, and is the purchase an operational necessity or highly discretionary. Quantify switching costs — what is the precise financial, operational, and psychological friction a customer endures to replace this product with a competitor's, and where has the company disclosed evidence of high retention, long contract durations, or high switching penalties in its filings. Examine the supply chain: does the company dictate pricing to its suppliers, or are they at the mercy of consolidated vendors with significant leverage. Identify any single points of failure in the supply chain that could halt operations or compress margins materially, and assess whether management has disclosed credible mitigation strategies, citing specific earnings call commentary or filing disclosures where available.

5. THE SCORECARD: FINANCIAL TRUTH & CAPITAL ALLOCATION
Begin with the balance sheet forensically: total assets, equity, net debt, and debt maturity profile. Calculate the interest coverage ratio using operating income against interest expense from the income statement and state what it tells you about financial fragility. Walk through the cash conversion cycle in full — days sales outstanding, days payable outstanding, and inventory days — and explain what the resulting cycle duration reveals about the quality of the business model; a negative cash conversion cycle is a mark of exceptional business quality and must be discussed explicitly if present. Perform the Owner's Earnings calculation showing every line with its source: reported net income, plus depreciation and amortisation, adjusted for working capital changes, minus maintenance capital expenditure. Compare the result to reported net income and explain any material divergence. Then analyse whether this company consistently generates a return on invested capital that exceeds its cost of capital across a full economic cycle, using multi-year ROIC data from the financial statements. Stress-test the balance sheet: could it survive a severe multi-year recession without dilutive equity issuance or insolvency risk. Finally assess capital allocation historically — acquisitions, buybacks, dividends, organic reinvestment — and deliver a verdict on whether management has been a good steward of shareholder capital.

6. THE ASYMMETRIC BET: GROWTH RUNWAY & THE KILL SHOT
Quantify the realistic serviceable obtainable market taking geographic and regulatory constraints into account, state the current penetration rate, and explain the structural drivers that could expand either the market or the company's share within it anchored in evidence from the filing, earnings call guidance, or observable revenue trends. Separate genuine structural growth from cyclical recovery or one-time tailwinds explicitly. Then deliver the bear case — the highest-probability sequence of events, whether regulatory, competitive, or macroeconomic, that could cause this company to permanently lose fifty percent or more of its intrinsic value over the next five years. This must be a specific, mechanistic argument with a plausible chain of causation, not a generic list of risks. Assess the probability and magnitude of this scenario honestly and without minimisation.

7. CATALYSTS & INFLECTION POINTS
Identify the specific, trackable events over the next six to eighteen months — product launches, contract expirations, regulatory rulings, M&A closures — that will force the market to actively reprice this asset, and explain the directional impact of each. Then describe the undeniable multi-year secular tailwinds and headwinds that are fundamentally driving revenue growth or compressing margins, distinguishing between macro forces the company cannot control and structural competitive dynamics it can influence. If the business is undergoing a fundamental transition — shifting from high-growth cash burn to mature cash cow, or experiencing structural margin degradation — quantify that inflection precisely and assess whether the current market pricing reflects it.

LENGTH MANDATE — THIS IS CRITICAL:
Each of the seven sections must be written to its full analytical depth. Do not truncate a section because you have covered the headline point — go deeper. For each section, after writing your initial analysis, ask yourself: what have I not yet examined? What nuance have I glossed over? What second-order implication have I not traced through? Then write that. A section on financial strength is not complete after one paragraph on leverage — it must cover leverage, interest coverage, cash conversion cycle mechanics with actual day counts, the full Owner's Earnings walk-through with every line sourced, ROIC versus cost of capital across multiple years, balance sheet stress testing, and a verdict on capital allocation quality. Every section should be thorough enough that a sophisticated investor could not reasonably ask "but what about X?" and find that X was not addressed. The total report should run to several thousand words. Do not stop writing a section until you have genuinely exhausted what the data and research supports saying.

Remember: every assertion must be backed by evidence. Every number must have a source. Every management quote must be verbatim and cited. Present the ground truth, not a sales pitch."""

def _call_nvidia(messages, api_key, max_tokens=32000):
    r = requests.post(
        "https://integrate.api.nvidia.com/v1/chat/completions",
        headers={"Content-Type": "application/json",
                 "Authorization": f"Bearer {api_key}"},
        json={
            "model": "deepseek-ai/deepseek-r1",
            "max_tokens": max_tokens,
            "temperature": 0.6,
            "top_p": 0.95,
            "messages": messages,
        },
        timeout=300,
    )
    r.raise_for_status()
    msg = r.json()["choices"][0]["message"]
    return str(msg.get("content") or msg.get("reasoning_content") or msg.get("text") or "").strip()

def generate_report_nvidia(company_name, ticker, financials_text, transcripts, filing_text, form_type, filing_date):
    transcript_text = _format_transcripts(transcripts)
    filing_section  = f"\n\n=== {form_type} FILING ({filing_date}) ===\n{filing_text[:60000]}" if filing_text else ""
    source_note     = f"You have been provided the {form_type} filing ({filing_date}), financial statements, and earnings transcripts."
    api_key         = st.secrets.get("NVIDIA_API_KEY", "")

    data_block = f"""You are writing one section of a comprehensive equity research report on {company_name} ({ticker}) for a sophisticated investment committee. {source_note}

OBJECTIVITY MANDATE: Remain ruthlessly objective. Present structural strengths and fatal flaws with equal clinical detachment. Analyze the data without emotion.

SOURCING RULES: Every financial figure sourced inline, e.g. (FY2024 Income Statement). Every management quote must be verbatim and cited to the specific call, e.g. (Q3 2024 Earnings Call). Every SEC filing fact cited, e.g. (10-K 2024, Business Section). State currency explicitly: "USD 4.2B", "EUR 890M".

FORMATTING: Continuous flowing prose only. No bullet points, no dashes as list markers, no sub-lists. Every paragraph minimum five sentences with a point, evidence, analysis, and conclusion. Write the section heading exactly as given on its own line with no markdown characters, then begin immediately.

LENGTH: Write this section to its absolute maximum depth. Do not stop when you have covered the headline point — go deeper into every sub-dimension. A sophisticated investor should not be able to ask "but what about X?" and find X unaddressed. Exhaust everything the data supports.

DATA:
{financials_text}{transcript_text}{filing_section}

NOW WRITE ONLY THE FOLLOWING SECTION:
"""

    sections = [
        ("1. THE FOUNDATION: BUSINESS OVERVIEW & TANGIBLE SCALE",
         "Stripped of all jargon, explain exactly what this business does and walk through the life cycle of a single dollar from the customer to the company. Quantify the exact physical or digital scale with sourced figures. For each operating segment state the exact revenue and operating profit contribution as a percentage. Define the unit of sale and calculate the true contribution margin. Trace gross profit down to operating profit and free cash flow, identifying where value is created and where it leaks. Explain the full margin structure trend over the last ten years and what it reveals about the business model."),

        ("2. THE BATTLEFIELD: INDUSTRY LANDSCAPE & COMPETITIVE PROFILE",
         "Describe the industry structure with precision — consolidated or fragmented, secular growth or decline, what phase of the cycle. Name the top three to five direct competitors and the specific arenas where they clash with this company. Analyse how they differ in operating model, cost structure, and target audience. Then prove the moat — do not name it, prove it mechanistically. Show exactly how the competitive advantage prevents a well-funded entrant from stealing share, with quantitative evidence."),

        ("3. THE GENERALS: MANAGEMENT, ALIGNMENT & TRACK RECORD",
         "Identify CEO, CFO, and COO — their background and tenure. Audit the three to four most consequential capital allocation decisions of this management team over the last decade and deliver a clear verdict on whether each created or destroyed value, with measured outcomes. Examine insider ownership precisely. Use direct verbatim quotes from earnings call transcripts where available, citing each call. Assess whether incentive structures align management with long-term free cash flow per share and ROIC, or short-term adjusted metrics."),

        ("4. THE CHOKEPOINTS: CUSTOMER DYNAMICS & SUPPLY CHAIN",
         "Analyse customer concentration precisely — is revenue distributed or whale-dependent, is the purchase a necessity or discretionary. Quantify switching costs with specific evidence from filings: contract durations, retention rates, switching penalties disclosed. Examine the supply chain — does the company dictate pricing or are they at the mercy of consolidated vendors. Identify any single points of failure that could halt operations and assess management's disclosed mitigation strategies with direct citation."),

        ("5. THE SCORECARD: FINANCIAL TRUTH & CAPITAL ALLOCATION",
         "Cover the balance sheet forensically: total assets, equity, net debt, debt maturity profile, and interest coverage ratio calculated from the income statement. Walk through the full cash conversion cycle — calculate DSO, DPO, and inventory days from the financial statements and explain what the cycle duration reveals. Perform the complete Owner's Earnings calculation showing every line with source: net income + D&A + working capital changes - maintenance capex. Analyse ROIC versus cost of capital across multiple years. Stress-test the balance sheet against a severe multi-year recession. Deliver a verdict on capital allocation quality across acquisitions, buybacks, dividends, and organic reinvestment."),

        ("6. THE ASYMMETRIC BET: GROWTH RUNWAY & THE KILL SHOT",
         "Quantify the realistic serviceable obtainable market with geographic and regulatory constraints, state current penetration, and explain the structural growth drivers anchored in evidence. Separate structural growth from cyclical recovery explicitly. Then deliver the bear case — the specific highest-probability sequence of events that could cause this company to permanently lose 50% or more of intrinsic value over five years. This must be a mechanistic argument with a causal chain, not a generic risk list. Assess probability and magnitude without minimisation."),

        ("7. CATALYSTS & INFLECTION POINTS",
         "Identify specific trackable events over the next 6 to 18 months that will force a market repricing and explain the directional impact of each with evidence. Describe the undeniable multi-year secular tailwinds and headwinds driving revenue or compressing margins, distinguishing macro forces from competitive dynamics. If the business is undergoing a fundamental transition, quantify the inflection precisely and assess whether current market pricing reflects it."),
    ]

    try:
        import re as _re_assemble
        report_parts = []

        for heading, instructions in sections:
            section_prompt = data_block + f"{heading}\n\n{instructions}"
            text = _call_nvidia([{"role": "user", "content": section_prompt}], api_key)
            if not text: continue
            text = text.strip()
            sec_num = heading.split(".")[0].strip()
            lines = text.split("\n")
            cleaned_lines = []
            for line in lines:
                stripped = line.strip().lstrip("*#").strip()
                if _re_assemble.match(rf"^{sec_num}[.\)]\s+", stripped):
                    continue
                cleaned_lines.append(line)

            body = "\n".join(cleaned_lines).strip()
            body = body.lstrip("\n").strip()
            if not body: continue

            section_text = f"{heading}\n\n{body}"
            report_parts.append(section_text)

        if not report_parts:
            return "NVIDIA returned empty responses for all sections."

        full_report = "\n\n".join(report_parts)
        return _clean_report(full_report)
    except Exception as e:
        return f"Error generating report via NVIDIA: {e}"

def generate_report_haiku(company_name, ticker, financials_text, transcripts):
    transcript_text = _format_transcripts(transcripts)
    source_note = ("No SEC filing is available for this company. "
                   "Use the web_search tool extensively to research the business model, "
                   "competitive position, and recent developments before writing.")

    prompt = _build_prompt(company_name, ticker, financials_text,
                           transcript_text, "", source_note)
    try:
        api_key = st.secrets.get("ANTHROPIC_API_KEY", "")
        headers = {
            "Content-Type": "application/json",
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
        }
        payload = {
            "model": "claude-haiku-4-5-20251001",
            "max_tokens": 16000,
            "tools": [{"type": "web_search_20250305", "name": "web_search"}],
            "messages": [{"role": "user", "content": prompt}],
        }
        r = requests.post("https://api.anthropic.com/v1/messages",
                          headers=headers, json=payload, timeout=180)
        r.raise_for_status()
        data = r.json()

        messages = [{"role": "user", "content": prompt}]
        for _ in range(8):
            messages.append({"role": "assistant", "content": data["content"]})
            if data.get("stop_reason") == "end_turn":
                break
            tool_results = [
                {"type": "tool_result", "tool_use_id": b["id"], "content": "Search completed."}
                for b in data["content"] if b.get("type") == "tool_use"
            ]
            if not tool_results: break
            messages.append({"role": "user", "content": tool_results})
            r2 = requests.post("https://api.anthropic.com/v1/messages",
                               headers=headers,
                               json={**payload, "messages": messages},
                               timeout=180)
            r2.raise_for_status()
            data = r2.json()

        text_parts = [b["text"] for b in data["content"] if b.get("type") == "text"]
        return _clean_report("\n\n".join(text_parts))
    except Exception as e:
        return f"Error generating report via Haiku: {e}"

def _format_transcripts(transcripts):
    if transcripts:
        txt = "\n\n=== EARNINGS CALL TRANSCRIPTS (last 4 quarters) ==="
        for t in transcripts:
            txt += f"\n\nQ{t['quarter']} {t['year']} Earnings Call (excerpt):\n{t['text'][:4000]}"
        return txt
    return "\n\n=== EARNINGS CALL TRANSCRIPTS ===\nNo transcripts available."

def generate_research_report(company_name, ticker, financials_text, transcripts, web_context=""):
    import re as _re
    has_suffix = bool(_re.search(r"[.][A-Z]{1,4}$", ticker.upper()))

    if has_suffix:
        return generate_report_haiku(company_name, ticker, financials_text, transcripts), "haiku", None

    filing_text, form_type, filing_date = fetch_10k_text(ticker)
    if filing_text:
        return generate_report_nvidia(company_name, ticker, financials_text, transcripts, filing_text, form_type, filing_date), "nvidia", form_type

    return generate_report_haiku(company_name, ticker, financials_text, transcripts), "haiku", None

def _clean_report(text):
    import re as _re
    text = _re.sub(r"(?m)^#{1,6}\s*", "", text)
    text = _re.sub(r"\*{2}(.+?)\*{2}", r"\1", text, flags=_re.DOTALL)
    text = _re.sub(r"\*(.+?)\*",       r"\1", text)

    def _debullet(m):
        line = m.group(1).strip()
        if _re.match(r"^\d+[.\)]\s+", line):
            return line
        if line and line[-1] not in ".!?:":
            line = line[0].upper() + line[1:] + "."
        else:
            line = line[0].upper() + line[1:]
        return line + " "

    text = _re.sub(r"(?m)^[ \t]*[-\*\u2022\u2013]\s+(.+)$", _debullet, text)
    text = _re.sub(r"[\u25a0\u25a1\ufffd](\d)", r"\1", text)
    text = _re.sub(r"\n{3,}", "\n\n", text)

    paras = text.split("\n\n")
    merged = []
    i = 0
    while i < len(paras):
        p = paras[i].strip()
        if _re.match(r"^\d+[.\)]\s+[A-Z]{3}", p):
            merged.append(p)
            i += 1
        elif len(p) < 120 and i + 1 < len(paras) and not _re.match(r"^\d+[.\)]\s+[A-Z]{3}", paras[i+1].strip()):
            combined = p.rstrip()
            if combined and combined[-1] not in ".!?":
                combined += "."
            combined += " " + paras[i+1].strip()
            paras[i+1] = combined
            i += 1
        else:
            merged.append(p)
            i += 1

    text = "\n\n".join(merged)
    return text.strip()

def build_report_pdf(company, ticker, report_text, transcripts, chart_figs=None):
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import cm, mm
    from reportlab.lib import colors
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, HRFlowable,
        KeepTogether, Image as RLImage, PageBreak
    )
    from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_JUSTIFY, TA_RIGHT
    import re, io
    from datetime import datetime

    buf = io.BytesIO()
    W, H = A4

    INK      = colors.HexColor("#111111")
    BODY_CLR = colors.HexColor("#2A2A2A")
    MID      = colors.HexColor("#555555")
    MUTED    = colors.HexColor("#888888")
    RULE_CLR = colors.HexColor("#DDDDDD")

    def S(name, **kw):
        defaults = dict(fontName="Helvetica", fontSize=10, leading=15,
                        textColor=BODY_CLR, spaceBefore=0, spaceAfter=0,
                        alignment=TA_LEFT)
        defaults.update(kw)
        return ParagraphStyle(name, **defaults)

    s_cover_co   = S("cco",  fontName="Helvetica",      fontSize=10, textColor=MUTED, spaceAfter=2)
    s_cover_name = S("cnm",  fontName="Helvetica-Bold",  fontSize=26, textColor=INK, leading=30, spaceAfter=6)
    s_cover_sub  = S("csb",  fontName="Helvetica",      fontSize=12, textColor=MID,  spaceAfter=4)
    s_cover_meta = S("cmt",  fontName="Helvetica",      fontSize=8.5, textColor=MUTED)
    s_disc       = S("dsc",  fontName="Helvetica-Oblique", fontSize=7.5, textColor=MUTED, spaceAfter=12, leading=11)
    s_sec        = S("sec",  fontName="Helvetica-Bold",  fontSize=11, textColor=INK, spaceBefore=20, spaceAfter=6, leading=14)
    s_body       = S("bdy",  fontName="Helvetica",       fontSize=9.5, textColor=BODY_CLR, leading=15, spaceAfter=8, alignment=TA_JUSTIFY)
    s_caption    = S("cap",  fontName="Helvetica-Oblique", fontSize=8, textColor=MUTED, spaceBefore=3, spaceAfter=10, alignment=TA_CENTER)
    s_footer     = S("ftr",  fontName="Helvetica",       fontSize=7.5, textColor=MUTED, alignment=TA_CENTER)

    story = []
    now   = datetime.now().strftime("%d %B %Y")
    lm    = 2.2*cm
    rm    = 2.2*cm

    def hr(thick=0.5, color=RULE_CLR, before=4, after=8):
        return HRFlowable(width="100%", thickness=thick, color=color,
                          spaceBefore=before*mm, spaceAfter=after*mm)

    story.append(Spacer(1, 1.2*cm))
    story.append(Paragraph("EQUITY RESEARCH", s_cover_co))
    story.append(Paragraph(company, s_cover_name))
    story.append(Paragraph(ticker, s_cover_sub))
    story.append(Spacer(1, 0.4*cm))
    story.append(hr(thick=1.5, color=INK, before=0, after=4))
    tc = f"{len(transcripts)} earnings transcript(s)" if transcripts else "No transcripts available"
    story.append(Paragraph(f"Generated {now}  ·  {tc}  ·  Fundamental analysis", s_cover_meta))
    story.append(Spacer(1, 0.5*cm))
    story.append(Paragraph(
        "This report is AI-generated for informational purposes only and does not constitute "
        "investment advice. All financial figures are sourced from roic.ai. "
        "Verify all data independently before making investment decisions.",
        s_disc))
    story.append(hr())

    import plotly.io as pio
    from concurrent.futures import ThreadPoolExecutor, as_completed

    def _render_one(args):
        idx, (title, fig) = args
        try:
            img_bytes = pio.to_image(fig, format="png", width=900, height=380, scale=2, engine="kaleido")
            return idx, img_bytes
        except Exception:
            return idx, None

    _pre_rendered: dict[int, bytes | None] = {}
    if chart_figs:
        with ThreadPoolExecutor(max_workers=3) as _pool:
            _futures = {_pool.submit(_render_one, item): item for item in enumerate(chart_figs)}
            for _fut in as_completed(_futures):
                _idx, _img = _fut.result()
                _pre_rendered[_idx] = _img

    def add_chart(fig, title, width_cm=16, _chart_idx=None):
        img_bytes = _pre_rendered.get(_chart_idx) if _chart_idx is not None else None
        if img_bytes is None: return
        img_buf = io.BytesIO(img_bytes)
        img_w   = width_cm * cm
        img_h   = img_w * (380 / 900)
        story.append(RLImage(img_buf, width=img_w, height=img_h))
        story.append(Paragraph(title, s_caption))

    section_re = re.compile(r"(?m)^(\d+[.\)]\s+(?:THE\s+)?[A-Z][A-Z0-9 :&'\-\/\(\),]{4,})\s*$")
    parts = section_re.split(report_text)

    if parts[0].strip():
        for para in parts[0].strip().split("\n\n"):
            if para.strip():
                story.append(Paragraph(para.strip(), s_body))

    SECTION_CHART_MAP = {"1": 0, "5": 1}
    i = 1
    while i < len(parts) - 1:
        heading  = parts[i].strip()
        body_txt = parts[i+1] if i+1 < len(parts) else ""
        sec_num  = heading[0]

        story.append(KeepTogether([
            hr(thick=0.5, before=4, after=3),
            Paragraph(heading, s_sec),
        ]))

        paragraphs = [p.strip() for p in re.split(r"\n\n+", body_txt) if p.strip()]
        for para in paragraphs:
            if re.match(r"^[A-Z][A-Z\s&:]{4,}:?\s*$", para) and len(para) < 80:
                story.append(Spacer(1, 3*mm))
                story.append(Paragraph(para, s_sec))
                continue
            para = re.sub(r"\*{2}(.+?)\*{2}", r"<b>\1</b>", para, flags=re.DOTALL)
            para = re.sub(r"\*(.+?)\*",        r"<i>\1</i>", para)
            para = re.sub(r"&(?!amp;|lt;|gt;|quot;|apos;)", "&amp;", para)
            story.append(Paragraph(para, s_body))

        if chart_figs and sec_num in SECTION_CHART_MAP:
            chart_idx = SECTION_CHART_MAP[sec_num]
            if chart_idx < len(chart_figs):
                c_title, c_fig = chart_figs[chart_idx]
                story.append(Spacer(1, 4*mm))
                add_chart(c_fig, c_title, _chart_idx=chart_idx)

        i += 2

    placed = set(SECTION_CHART_MAP.values())
    remaining = [(idx, t, f) for idx, (t, f) in enumerate(chart_figs or []) if idx not in placed]
    if remaining:
        story.append(hr(before=6, after=4))
        story.append(Paragraph("FINANCIAL CHARTS", s_sec))
        for c_idx, c_title, c_fig in remaining:
            add_chart(c_fig, c_title, _chart_idx=c_idx)

    story.append(Spacer(1, 1*cm))
    story.append(hr(thick=0.4, before=0, after=2))
    story.append(Paragraph(f"Compounder  ·  {company} ({ticker})  ·  {now}  ·  For informational use only", s_footer))

    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=lm, rightMargin=rm, topMargin=2.2*cm, bottomMargin=2.2*cm)
    doc.build(story)
    buf.seek(0)
    return buf.read()

# ── Number helpers ────────────────────────────────────────────────────────────
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


# Chart theme
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
    hoverlabel=dict(bgcolor=C_BG, bordercolor=C_BORDER, font=dict(family="Inter, sans-serif", size=11, color=C_TEXT)),
    legend=dict(bgcolor="rgba(0,0,0,0)", borderwidth=0, font=dict(size=10, color=C_TEXT3), orientation="h", yanchor="top", y=1.0, xanchor="right", x=1.0),
)

LINE_COLORS = ["#111111", "#AAAAAA", "#555555", "#CCCCCC"]

def make_bar(x, y, title, height=280, color=C_ACCENT):
    y_safe  = [v if v is not None and not pd.isna(v) else 0 for v in y]
    c_list  = [C_DOWN if v < 0 else color for v in y_safe]
    fig = go.Figure(go.Bar(x=x, y=y_safe, marker_color=c_list, marker_line_width=0, hovertemplate="%{x}<br>%{y:,.1f}<extra></extra>"))
    fig.update_layout(**CHART_BASE)
    fig.update_layout(height=height, title=dict(text=title, font=dict(size=11, color=C_TEXT2, weight=500), x=0, xanchor="left"),
        bargap=0.35,
        xaxis=dict(showgrid=False, showline=True, linecolor=C_BORDER, tickfont=dict(size=10, color=C_TEXT3), zeroline=False),
        yaxis=dict(showgrid=True, gridcolor=C_BORDER2, gridwidth=1, showline=True, linecolor=C_BORDER, zeroline=False, tickfont=dict(size=10, color=C_TEXT3)),
    )
    return fig

def make_line(x, ys, names, title, height=300, suffix=""):
    fig = go.Figure()
    for i, (y, name) in enumerate(zip(ys, names)):
        y_clean = [v if v and not pd.isna(v) else None for v in y]
        fig.add_trace(go.Scatter(x=x, y=y_clean, name=name, mode="lines", line=dict(color=LINE_COLORS[i % len(LINE_COLORS)], width=1.5),
            hovertemplate=f"%{{x}}<br>{name}: %{{y:,.1f}}{suffix}<extra></extra>", connectgaps=False))
    fig.update_layout(**CHART_BASE)
    fig.update_layout(height=height, title=dict(text=title, font=dict(size=11, color=C_TEXT2, weight=500), x=0, xanchor="left"),
        margin=dict(l=0, r=0, t=52, b=0),
        xaxis=dict(showgrid=False, showline=True, linecolor=C_BORDER, tickfont=dict(size=10, color=C_TEXT3), zeroline=False),
        yaxis=dict(showgrid=True, gridcolor=C_BORDER2, gridwidth=1, showline=True, linecolor=C_BORDER, zeroline=False, tickfont=dict(size=10, color=C_TEXT3)),
    )
    return fig

def kpi_block(col, label, value_str, delta=None):
    col.markdown(f"""
    <div class="metric-block">
        <div class="metric-label">{label}</div>
        <div class="metric-value">{value_str}</div>
        {delta_html(delta)}
    </div>""", unsafe_allow_html=True)


# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown('<div style="font-size:1rem;font-weight:600;color:#111;margin-bottom:0.2rem;letter-spacing:-0.01em">Compounder</div>', unsafe_allow_html=True)
    st.markdown('<div style="font-size:0.72rem;color:#999;margin-bottom:2rem">Quality Growth Tracker</div>', unsafe_allow_html=True)

    page = st.radio("", ["Overview", "Company"], label_visibility="collapsed")

    if page == "Company":
        st.markdown('<div style="font-size:0.68rem;color:#999;text-transform:uppercase;letter-spacing:0.08em;margin-bottom:0.5rem">Watchlist</div>', unsafe_allow_html=True)
        _wl_names = [s["Name"] for s in st.session_state.stocks_list]
        watchlist_choice = st.selectbox("", ["— Enter ticker below —"] + _wl_names, label_visibility="collapsed")

        st.markdown('<div style="font-size:0.68rem;color:#999;text-transform:uppercase;letter-spacing:0.08em;margin-top:1rem;margin-bottom:0.3rem">Any Ticker</div>', unsafe_allow_html=True)
        custom_ticker = st.text_input("", placeholder="e.g. NVDA, META, 7203.T", label_visibility="collapsed").strip().upper()

        _wl_map = {s["Name"]: s["Ticker"] for s in st.session_state.stocks_list}
        if custom_ticker:
            selected_ticker  = custom_ticker
            selected_company = custom_ticker
        elif watchlist_choice != "— Enter ticker below —":
            selected_ticker  = _wl_map.get(watchlist_choice, watchlist_choice)
            selected_company = watchlist_choice
        else:
            selected_ticker  = None
            selected_company = None

    st.markdown("<br>" * 4, unsafe_allow_html=True)
    st.markdown('<div style="font-size:0.68rem;color:#ccc">Live from roic.ai</div>', unsafe_allow_html=True)
    if st.button("Refresh"):
        st.cache_data.clear()
        st.rerun()


# ══════════════════════════════════════════════════════════════════════════════
# OVERVIEW
# ══════════════════════════════════════════════════════════════════════════════
if page == "Overview":

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

    def calc_cagr(s):
        vals = [v for v in s.dropna().tolist() if v is not None and v > 0]
        if len(vals) < 2: return None, 0
        start, end = vals[0], vals[-1]
        n = len(vals) - 1
        if start <= 0 or n == 0: return None, 0
        return ((end / start) ** (1.0 / n) - 1) * 100, n

    def fmt_cagr(val, n):
        if val is None: return "—"
        sign = "+" if val >= 0 else ""
        return f"{sign}{val:.1f}%"

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
        fcf_s    = safe(cf,  "cf_free_cash_flow") if not cf.empty else pd.Series(dtype=float)

        ccy_code = inc["currency"].iloc[-1] if "currency" in inc.columns and len(inc) > 0 else "USD"
        ccy = ccy_symbol(ccy_code)

        rev_cagr, rev_n = calc_cagr(rev_s)
        oi_cagr,  oi_n  = calc_cagr(oi_s)

        prices = fetch_prices(ticker)
        latest_price = None
        if not prices.empty:
            close_col = next((c for c in ["adj_close", "adjusted_close", "close"] if c in prices.columns), None)
            if close_col: latest_price = float(prices[close_col].dropna().iloc[-1])

        inc_q = fetch_fundamental_quarterly("fundamental/income-statement", ticker)
        ttm_eps = None
        if not inc_q.empty:
            eps_q = safe(inc_q, "diluted_eps", "eps").dropna()
            if len(eps_q) >= 4: ttm_eps = float(eps_q.iloc[-4:].sum())
            elif len(eps_q) > 0: ttm_eps = float(eps_q.iloc[-len(eps_q):].sum())

        latest_shares = latest(shares_s)
        latest_fcf    = latest(fcf_s)

        def _pe():
            if latest_price and ttm_eps and ttm_eps != 0: return f"{latest_price / ttm_eps:.1f}x"
            return "—"

        def _fcf_yield():
            if latest_price and latest_shares and latest_shares > 0 and latest_fcf:
                mc = latest_price * latest_shares
                if mc > 0: return f"{(latest_fcf / mc) * 100:.1f}%"
            return "—"

        rows.append({
            "Company":      company, "Ticker":       ticker,
            "Revenue":      fmt_currency(latest(rev_s), ccy), "Gross Profit": fmt_currency(latest(gp_s), ccy),
            "GP Margin":    fmt_pct(latest(gm_s)), "Op Profit":    fmt_currency(latest(oi_s), ccy),
            "Op Margin":    fmt_pct(latest(opm_s)), "Net Profit":   fmt_currency(latest(ni_s), ccy),
            "Net Margin":   fmt_pct(latest(npm_s)), "Rev CAGR":     fmt_cagr(rev_cagr, rev_n),
            "OI CAGR":      fmt_cagr(oi_cagr,  oi_n), "P/E":          _pe(),
            "FCF Yield":    _fcf_yield(),
            "_rev":  latest(rev_s), "_oi":   latest(oi_s), "_ni":   latest(ni_s),
            "_opm":  latest(opm_s), "_npm":  latest(npm_s),
            "_ccy":  ccy, "_ccy_code": str(ccy_code),
        })

    header_cols = ["Company", "Ticker", "Revenue", "Gross Profit", "GP Margin",
                   "Op Profit", "Op Margin", "Net Profit", "Net Margin", "Rev CAGR", "OI CAGR", "P/E", "FCF Yield"]

    header_html = "".join(f'<span class="tbl-header">{h}</span>' for h in header_cols)
    st.markdown(f'''<div class="tbl-row tbl-header-row">{header_html}</div>''', unsafe_allow_html=True)

    for r in rows:
        def cell(key, cls="tbl-cell"): return f'<span class="{cls}">{r.get(key, "—")}</span>'
        def cagr_span(val):
            if val == "—": return '<span class="tbl-cell" style="color:#ccc">—</span>'
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
    chart_rev   = [r["_rev"]  for r in rows if r.get("_rev")]
    chart_opm   = [to_pct_list([r.get("_opm")])[0] if r.get("_opm") is not None else 0 for r in rows if r.get("_rev")]
    chart_npm   = [to_pct_list([r.get("_npm")])[0] if r.get("_npm") is not None else 0 for r in rows if r.get("_rev")]

    st.markdown('<span class="section-label">Revenue</span>', unsafe_allow_html=True)
    if chart_names:
        hover_texts = []
        for r in [r for r in rows if r.get("_rev")]:
            ccy = r.get("_ccy", "$")
            v   = r.get("_rev", 0)
            hover_texts.append(f"{ccy}{v/1e9:.1f}B")
        fig_rev = go.Figure(go.Bar(
            x=chart_names, y=[v/1e9 for v in chart_rev], marker_color=C_ACCENT,
            marker_line_width=0, text=hover_texts, hovertemplate="%{x}<br>%{text}<extra></extra>",
        ))
        fig_rev.update_layout(**CHART_BASE)
        fig_rev.update_layout(height=260, bargap=0.45, showlegend=False,
            yaxis=dict(showgrid=True, gridcolor=C_BORDER2, ticksuffix="B", tickfont=dict(size=10, color=C_TEXT3), zeroline=False, showline=True, linecolor=C_BORDER),
        )
        st.plotly_chart(fig_rev, use_container_width=True, config={"displayModeBar": False})

    st.markdown('<span class="section-label">Margins</span>', unsafe_allow_html=True)
    if chart_names:
        fig_m = go.Figure()
        fig_m.add_trace(go.Bar(name="Operating", x=chart_names, y=chart_opm, marker_color=C_ACCENT, marker_line_width=0, hovertemplate="%{x}<br>Operating: %{y:.1f}%<extra></extra>"))
        fig_m.add_trace(go.Bar(name="Net", x=chart_names, y=chart_npm, marker_color="#BBBBBB", marker_line_width=0, hovertemplate="%{x}<br>Net: %{y:.1f}%<extra></extra>"))
        fig_m.update_layout(**CHART_BASE)
        fig_m.update_layout(height=260, barmode="group", bargap=0.35, bargroupgap=0.08,
            yaxis=dict(showgrid=True, gridcolor=C_BORDER2, ticksuffix="%", tickfont=dict(size=10, color=C_TEXT3), zeroline=False, showline=False),
        )
        st.plotly_chart(fig_m, use_container_width=True, config={"displayModeBar": False})


# ══════════════════════════════════════════════════════════════════════════════
# COMPANY DEEP DIVE
# ══════════════════════════════════════════════════════════════════════════════
else:
    if not selected_ticker:
        st.markdown('<div class="page-title">Company</div>', unsafe_allow_html=True)
        st.markdown('<div class="page-sub">Select a company from the watchlist or enter any ticker in the sidebar.</div>', unsafe_allow_html=True)
        st.stop()

    ticker   = selected_ticker
    company  = selected_company

    WATCHLIST_FE = {"RYAAY": 3, "CPRT": 7, "CSU.TO": 12, "FICO": 9,
                    "SPGI": 12, "MCO": 12, "ASML": 12}
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

    # ── NEW: Fetch Average Price for the Fiscal Year Window ──
    if "Date" in inc.columns:
        avg_price_s = fetch_annual_average_prices(ticker, inc["Date"])
    else:
        avg_price_s = pd.Series([None] * n)

    _cf = lambda *cols: align(safe(cf, *cols) if n_cf else pd.Series(dtype=float), n)
    sbc_s       = _cf("cf_stock_based_compensation")
    incr_cap_s  = _cf("cf_incr_cap_stock")
    decr_cap_s  = _cf("cf_decr_cap_stock")
    rsu_tax_s   = _cf("cf_taxes_related_to_net_share_settlement", "cf_taxes_net_share_settlement",
                      "cf_payment_for_taxes_net_share_settlement", "cf_employee_withholding_taxes")

    bs_years = bs["Date"].dt.year.astype(str).tolist() if not bs.empty and "Date" in bs.columns else years
    n_bs  = len(bs) if not bs.empty else 0
    nd_s  = align(safe(bs, "net_debt") if n_bs else pd.Series(dtype=float), n)
    ar_s  = safe(bs, "bs_acct_note_rcv", "bs_accts_rec_excl_notes_rec") if n_bs else pd.Series(dtype=float)
    inv_s = safe(bs, "bs_inventories") if n_bs else pd.Series(dtype=float)
    ap_s  = safe(bs, "bs_acct_payable") if n_bs else pd.Series(dtype=float)
    ca_s  = safe(bs, "bs_cur_asset_report") if n_bs else pd.Series(dtype=float)
    cl_s  = safe(bs, "bs_cur_liab") if n_bs else pd.Series(dtype=float)

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
    kpi_block(k1, "Revenue",        fmt_currency(rev_l, ccy),  yoy(rev_l, rev_p))
    kpi_block(k2, "Free Cash Flow",fmt_currency(fcf_l, ccy),  yoy(fcf_l, fcf_p))
    kpi_block(k3, "Gross Margin",   fmt_pct(gm_l))
    kpi_block(k4, "Operating Margin", fmt_pct(opm_l))
    kpi_block(k5, "Net Margin",     fmt_pct(npm_l))
    kpi_block(k6, "EPS",            fmt_eps(eps_l, ccy),  yoy(eps_l, eps_p))

    st.markdown("<br>", unsafe_allow_html=True)
    tab1, tab2, tab3, tab4, tab5, tab6, tab7, tab8 = st.tabs(["Revenue", "Margins", "Cash Flow", "Valuation", "Working Capital", "Owners' Earnings", "Forensic Accounting", "Research Report"])

    with tab1:
        c1, c2 = st.columns(2, gap="large")
        with c1:
            vals_b = [v/1e9 if v and not pd.isna(v) else None for v in rev_s]
            st.plotly_chart(make_bar(years, vals_b, "Revenue  ($B)", height=260), use_container_width=True, config={"displayModeBar": False})
        with c2:
            st.plotly_chart(make_bar(years, rev_growth, "Revenue Growth  (%)", height=260, color="#555555"), use_container_width=True, config={"displayModeBar": False})

        st.markdown("<br>", unsafe_allow_html=True)
        c3, c4 = st.columns(2, gap="large")
        with c3:
            ni_b = [v/1e9 if v and not pd.isna(v) else None for v in ni_s]
            st.plotly_chart(make_bar(years, ni_b, "Net Income  ($B)", height=260), use_container_width=True, config={"displayModeBar": False})
        with c4:
            st.plotly_chart(make_bar(years, eps_s.tolist(), "EPS  ($)", height=260, color="#555555"), use_container_width=True, config={"displayModeBar": False})

    with tab2:
        gm_pct  = to_pct_list(gm_s)
        opm_pct = to_pct_list(opm_s)
        npm_pct = to_pct_list(npm_s)

        fig_mg = make_line(years, [gm_pct, opm_pct, npm_pct], ["Gross", "Operating", "Net"], "Profit Margins  (%)", height=340, suffix="%")
        fig_mg.update_layout(yaxis=dict(ticksuffix="%", showgrid=True, gridcolor=C_BORDER2, tickfont=dict(size=10, color=C_TEXT3), zeroline=False, showline=False))
        st.plotly_chart(fig_mg, use_container_width=True, config={"displayModeBar": False})

        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown('<span class="section-label">Historical</span>', unsafe_allow_html=True)
        margin_df = pd.DataFrame({
            "Metric":    ["Gross Margin", "Operating Margin", "Net Margin"],
            **{y: [
                f"{gm_pct[i]:.1f}%"  if gm_pct[i]  else "—",
                f"{opm_pct[i]:.1f}%" if opm_pct[i] else "—",
                f"{npm_pct[i]:.1f}%" if npm_pct[i] else "—",
            ] for i, y in enumerate(years)}
        }).set_index("Metric")
        st.dataframe(margin_df, use_container_width=True)

    with tab3:
        c1, c2 = st.columns(2, gap="large")
        with c1:
            if fcf_s.notna().any():
                fcf_b = [v/1e9 if v and not pd.isna(v) else None for v in fcf_s]
                fig_fcf = make_bar(cf_years, fcf_b, f"Free Cash Flow  ({ccy_code}, B)", height=260)
                fig_fcf.update_layout(yaxis=dict(showgrid=True, gridcolor=C_BORDER2, tickprefix=ccy, ticksuffix="B", tickfont=dict(size=10, color=C_TEXT3), zeroline=False, showline=True, linecolor=C_BORDER))
                st.plotly_chart(fig_fcf, use_container_width=True, config={"displayModeBar": False})
            else:
                st.markdown('<span style="color:#999;font-size:0.82rem">No free cash flow data</span>', unsafe_allow_html=True)
        with c2:
            if cfo_s.notna().any():
                cfo_b = [v/1e9 if v and not pd.isna(v) else None for v in cfo_s]
                fig_cfo = make_bar(cf_years, cfo_b, f"Operating Cash Flow  ({ccy_code}, B)", height=260, color="#555555")
                fig_cfo.update_layout(yaxis=dict(showgrid=True, gridcolor=C_BORDER2, tickprefix=ccy, ticksuffix="B", tickfont=dict(size=10, color=C_TEXT3), zeroline=False, showline=True, linecolor=C_BORDER))
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

    with tab4:
        if price_s.notna().any():
            fig_px = make_line(years, [price_s.tolist()], ["Price"], "Year-End Stock Price  ($)", height=300)
            fig_px.update_layout(yaxis=dict(tickprefix=ccy, showgrid=True, gridcolor=C_BORDER2, tickfont=dict(size=10, color=C_TEXT3), zeroline=False, showline=True, linecolor=C_BORDER))
            st.plotly_chart(fig_px, use_container_width=True, config={"displayModeBar": False})
        else:
            with st.spinner(""):
                prices = fetch_prices(ticker)
            if not prices.empty:
                close_col = next((c for c in ["adj_close", "adjusted_close", "close"] if c in prices.columns), prices.columns[1])
                fig_px = go.Figure(go.Scatter(x=prices["date"], y=prices[close_col], mode="lines", name="Price", line=dict(color=C_ACCENT, width=1.5), hovertemplate="%{x|%d %b %Y}<br>$%{y:.2f}<extra></extra>"))
                fig_px.update_layout(**CHART_BASE)
                fig_px.update_layout(height=300, showlegend=False, yaxis=dict(tickprefix=ccy, showgrid=True, gridcolor=C_BORDER2, tickfont=dict(size=10, color=C_TEXT3), zeroline=False, showline=True, linecolor=C_BORDER))
                st.plotly_chart(fig_px, use_container_width=True, config={"displayModeBar": False})
            else:
                st.markdown('<span style="color:#999;font-size:0.82rem">Price data not available.</span>', unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown('<span class="section-label">Multiples</span>', unsafe_allow_html=True)

        pe_list, pfcf_list, evebit_list = [], [], []
        for i in range(len(years)):
            def _g(s): return float(s.iloc[i]) if i < len(s) and pd.notna(s.iloc[i]) else None
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

            val_df = pd.DataFrame({"Year": years})
            if any(v for v in pe_list     if v): val_df["P/E"]    = [fmt_multiple(v) for v in pe_list]
            if any(v for v in pfcf_list   if v): val_df["P/FCF"]  = [fmt_multiple(v) for v in pfcf_list]
            if any(v for v in evebit_list if v): val_df["EV/EBIT"]= [fmt_multiple(v) for v in evebit_list]
            val_display = pd.DataFrame({
                "Metric": val_names,
                **{y: [val_ys[j][i] if val_ys[j][i] else None for j in range(len(val_names))] for i, y in enumerate(years)}
            }).set_index("Metric")
            val_display = val_display.map(lambda v: fmt_multiple(v) if v else "—")
            st.dataframe(val_display, use_container_width=True)
        else:
            st.markdown('<span style="color:#999;font-size:0.82rem">Stock price required to calculate multiples.</span>', unsafe_allow_html=True)

    with tab5:
        def days(numerator_s, denominator_s):
            n = pd.to_numeric(numerator_s,   errors="coerce").reset_index(drop=True)
            d = pd.to_numeric(denominator_s, errors="coerce").reset_index(drop=True)
            n = n.iloc[:len(bs_years)]
            d = d.iloc[:len(bs_years)]
            return (n / d.where(d > 0)) * 365

        dso_s  = days(ar_s,  rev_s)
        inv_s_ = days(inv_s, cogs_s)
        dpo_s  = days(ap_s,  cogs_s)

        ccc_full   = (dso_s + inv_s_ - dpo_s)
        ccc_no_inv = (dso_s - dpo_s)
        ccc_s      = ccc_full.where(inv_s_.notna(), ccc_no_inv)
        ccc_s      = ccc_s.where(dso_s.notna() & dpo_s.notna())

        ca = pd.to_numeric(ca_s, errors="coerce").reset_index(drop=True).iloc[:len(bs_years)]
        cl = pd.to_numeric(cl_s, errors="coerce").reset_index(drop=True).iloc[:len(bs_years)]
        nwc_s = (ca - cl).where(ca.notna() & cl.notna())

        def _to_list(s): return [None if pd.isna(v) else float(v) for v in s]

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
        dso_l  = latest_days(dso_list)
        inv_l  = latest_days(inv_list)
        dpo_l  = latest_days(dpo_list)
        ccc_l  = latest_days(ccc_list)
        nwc_l  = latest(pd.Series(nwc_list, dtype=float))

        def wc_kpi(col, label, val_str, delta_days=None):
            if delta_days is not None:
                sign  = "+" if delta_days >= 0 else ""
                cls   = "delta-up" if delta_days <= 0 else "delta-down"
                d_html = f'<span class="metric-delta {cls}">{sign}{delta_days:.0f} days YoY</span>'
            else:
                d_html = ""
            col.markdown(f"""<div class="metric-block"><div class="metric-label">{label}</div><div class="metric-value">{val_str}</div>{d_html}</div>""", unsafe_allow_html=True)

        wc_kpi(w1, "DSO",             fmt_days(dso_l),  fmt_days_delta(dso_list))
        wc_kpi(w2, "Inventory Days", fmt_days(inv_l),  fmt_days_delta(inv_list))
        wc_kpi(w3, "DPO",             fmt_days(dpo_l),  fmt_days_delta(dpo_list))
        wc_kpi(w4, "Cash Cycle",      fmt_days(ccc_l),  fmt_days_delta(ccc_list))
        wc_kpi(w5, "NWC (Latest)",    fmt_currency(nwc_l, ccy))

        st.markdown("<br>", unsafe_allow_html=True)

        days_ys, days_names = [], []
        if any(v for v in dso_list  if v is not None): days_ys.append(dso_list);  days_names.append("DSO")
        if any(v for v in inv_list  if v is not None): days_ys.append(inv_list);  days_names.append("Inventory Days")
        if any(v for v in dpo_list  if v is not None): days_ys.append(dpo_list);  days_names.append("DPO")
        if any(v for v in ccc_list  if v is not None): days_ys.append(ccc_list);  days_names.append("Cash Cycle")

        if days_ys:
            fig_wc = make_line(bs_years, days_ys, days_names, "Working Capital Days", height=320, suffix=" days")
            fig_wc.update_layout(yaxis=dict(ticksuffix=" d", showgrid=True, gridcolor=C_BORDER2, tickfont=dict(size=10, color=C_TEXT3), zeroline=True, zerolinecolor=C_BORDER, showline=False))
            st.plotly_chart(fig_wc, use_container_width=True, config={"displayModeBar": False})
        else:
            st.markdown('<span style="color:#999;font-size:0.82rem">Insufficient balance sheet data.</span>', unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)
        if any(v for v in nwc_list if v is not None):
            fig_nwc = make_bar(bs_years, [v/1e9 if v is not None else None for v in nwc_list], f"Net Working Capital  ({ccy_code}, B)", height=260)
            fig_nwc.update_layout(yaxis=dict(tickprefix=ccy, ticksuffix="B", showgrid=True, gridcolor=C_BORDER2, tickfont=dict(size=10, color=C_TEXT3), zeroline=True, zerolinecolor=C_BORDER, showline=False))
            st.plotly_chart(fig_nwc, use_container_width=True, config={"displayModeBar": False})

        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown('<span class="section-label">Historical</span>', unsafe_allow_html=True)
        wc_display = pd.DataFrame({
            "Metric":         ["DSO", "Inventory Days", "DPO", "Cash Cycle", "NWC"],
            **{bs_years[i]: [
                fmt_days(dso_list[i]), fmt_days(inv_list[i]), fmt_days(dpo_list[i]),
                fmt_days(ccc_list[i]), fmt_currency(nwc_list[i], ccy),
            ] for i in range(len(bs_years))}
        }).set_index("Metric")
        st.dataframe(wc_display, use_container_width=True)

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
        dil_list = [None] + [None if pd.isna(v) else float(v) for v in (sh_s.pct_change() * 100).iloc[1:]]
        ni_list = [None if pd.isna(v) else float(v) for v in pd.to_numeric(ni_s, errors="coerce")]

        decr_v = pd.to_numeric(decr_cap_s, errors="coerce").abs().reset_index(drop=True)
        incr_v = pd.to_numeric(incr_cap_s, errors="coerce").abs().reset_index(drop=True)
        both_missing = decr_v.isna() & incr_v.isna()
        net_bb_vec   = (decr_v.fillna(0) - incr_v.fillna(0)).where(~both_missing)
        net_bb_list  = [None if pd.isna(v) else float(v) for v in net_bb_vec]

        px_avg_vals = avg_price_s.tolist()
        maint_bb_vals = []
        for i in range(len(years)):
            bb_net = net_bb_list[i] if net_bb_list[i] is not None else 0.0
            sh_curr = sh_list[i]
            sh_prev = sh_list[i-1] if i > 0 else sh_curr
            px_avg = px_avg_vals[i]
            
            if pd.notna(sh_curr) and pd.notna(sh_prev) and pd.notna(px_avg) and px_avg > 0:
                delta_shares = sh_prev - sh_curr
                val_reduction = max(0, delta_shares) * px_avg 
                maint_bb = max(0, bb_net - val_reduction)
            else:
                maint_bb = max(0, bb_net)
            maint_bb_vals.append(maint_bb)

        maint_bb_vec = pd.Series(maint_bb_vals, dtype=float)

        ni_vec  = pd.to_numeric(ni_s,  errors="coerce").reset_index(drop=True)
        sbc_vec = pd.to_numeric(sbc_s, errors="coerce").abs().reset_index(drop=True)

        sec_rsu_data = st.session_state.get(f"rsu_tax_{ticker}", {})
        if sec_rsu_data:
            rsu_sec_s = pd.Series(sec_rsu_data, dtype=float)
            rsu_sec_s.index = rsu_sec_s.index.astype(str)
            years_idx = pd.Index([str(y) for y in years])
            rsu_sec_aligned = rsu_sec_s.reindex(years_idx).values
            rsu_sec_vec = pd.Series(rsu_sec_aligned).abs().reset_index(drop=True)
        else:
            rsu_sec_vec = pd.Series([None] * len(years), dtype=float)

        rsu_roic_vec = pd.to_numeric(rsu_tax_s, errors="coerce").abs().reset_index(drop=True)
        rsu_vec = rsu_sec_vec.combine_first(rsu_roic_vec)

        oe_vec = (
            ni_vec
            + sbc_vec.fillna(0)
            - maint_bb_vec.fillna(0)
            - rsu_vec.fillna(0)
        ).where(ni_vec.notna())
        oe_list = [None if pd.isna(v) else float(v) for v in oe_vec]

        latest_oe     = next((v for v in reversed(oe_list)     if v is not None), None)
        latest_ni     = next((v for v in reversed(ni_list)     if v is not None), None)
        latest_dil    = next((v for v in reversed(dil_list)    if v is not None), None)
        latest_m_bb   = next((v for v in reversed(maint_bb_vals) if v is not None), None)

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
        sec_rsu = st.session_state.get(rsu_cache_key, {})
        _has_suffix = bool(__import__("re").search(r"[.][A-Z]{1,4}$", ticker.upper()))

        _rc1, _rc2 = st.columns([2, 5])
        with _rc1:
            _fetch_btn = st.button(
                "Fetch RSU Tax from SEC (XBRL)",
                disabled=_has_suffix,
                help="Pulls RSU tax withholding directly from EDGAR's structured XBRL data. Instant, no AI needed. US-listed tickers only." if not _has_suffix else "SEC EDGAR only covers US-listed tickers.",
            )
        with _rc2:
            if _has_suffix:
                st.markdown('<span style="font-size:0.72rem;color:#999">SEC EDGAR not available for non-US tickers.</span>', unsafe_allow_html=True)
            elif sec_rsu:
                years_found = sorted(sec_rsu.keys())
                st.markdown(f'<span style="font-size:0.72rem;color:{C_UP}">XBRL data loaded for: {", ".join(years_found)}</span>', unsafe_allow_html=True)
            else:
                st.markdown('<span style="font-size:0.72rem;color:#999">RSU tax withholdings not yet fetched — click to pull from EDGAR XBRL data.</span>', unsafe_allow_html=True)

        if _fetch_btn:
            with st.spinner("Fetching XBRL data from EDGAR..."):
                _fetched = fetch_rsu_tax_xbrl(ticker)
            st.session_state[rsu_cache_key] = _fetched
            if _fetched:
                st.success(f"Found RSU tax data for {len(_fetched)} years: {', '.join(sorted(_fetched.keys()))}")
            else:
                st.warning("No RSU tax withholding data found on EDGAR.")
            st.rerun()

        st.markdown("<br>", unsafe_allow_html=True)

        ek1, ek2, ek3, ek4 = st.columns(4)

        def oe_kpi(col, label, val, sub=None, highlight=False):
            color = "#111" if not highlight else (C_UP if (val or "").startswith("+") or (val or "") not in ["—", ""] else C_DOWN)
            col.markdown(f"""
            <div class="metric-block">
                <div class="metric-label">{label}</div>
                <div class="metric-value" style="color:{color}">{val or "—"}</div>
                {"" if not sub else f'<div style="font-size:0.68rem;color:#999;margin-top:2px">{sub}</div>'}
            </div>""", unsafe_allow_html=True)

        oe_kpi(ek1, "Owners' Earnings", fmt_currency(latest_oe, ccy), "latest year")
        oe_kpi(ek2, "OE as % of GAAP NI", f"{oe_pct_gaap:.0f}%" if oe_pct_gaap else "—", "latest year")
        oe_kpi(ek3, "Annual Dilution",
               (f"+{latest_dil:.2f}%" if latest_dil and latest_dil >= 0 else f"{latest_dil:.2f}%") if latest_dil is not None else "—",
               "YoY share count change")
        oe_kpi(ek4, "Maintenance Buybacks", fmt_currency(latest_m_bb, ccy), "offsetting dilution")

        st.markdown("<br>", unsafe_allow_html=True)

        st.markdown('<span class="section-label">Share Dilution</span>', unsafe_allow_html=True)
        c1, c2 = st.columns(2, gap="large")
        with c1:
            sh_b = [v/1e6 if v and not pd.isna(v) else None for v in sh_list]
            fig_sh = make_bar(years, sh_b, "Shares Outstanding  (M)", height=260, color="#555555")
            fig_sh.update_layout(yaxis=dict(ticksuffix="M", showgrid=True, gridcolor=C_BORDER2, tickfont=dict(size=10, color=C_TEXT3), zeroline=False))
            st.plotly_chart(fig_sh, use_container_width=True, config={"displayModeBar": False})
        with c2:
            dil_colors = [C_DOWN if (v or 0) > 0 else C_UP for v in dil_list]
            fig_dil = go.Figure(go.Bar(
                x=years, y=dil_list, marker_color=dil_colors, marker_line_width=0, hovertemplate="%{x}: %{y:.2f}%<extra></extra>",
            ))
            fig_dil.update_layout(**CHART_BASE)
            fig_dil.update_layout(height=260, title_text="Annual Dilution Rate  (%)", yaxis=dict(ticksuffix="%", showgrid=True, gridcolor=C_BORDER2, tickfont=dict(size=10, color=C_TEXT3), zeroline=True, zerolinecolor=C_BORDER))
            st.plotly_chart(fig_dil, use_container_width=True, config={"displayModeBar": False})

        st.markdown("<br>", unsafe_allow_html=True)

        st.markdown('<span class="section-label">SBC Cost Analysis</span>', unsafe_allow_html=True)

        sbc_b     = [abs(_v(sbc_s, i))/1e9  if _v(sbc_s, i)  is not None else None for i in range(len(years))]
        maint_bb_b= [maint_bb_vals[i]/1e9   if maint_bb_vals[i] is not None else None for i in range(len(years))]
        rst_b     = [_absv(rsu_tax_s, i)/1e9 if _absv(rsu_tax_s, i) is not None else None for i in range(len(years))]

        has_sbc    = any(v is not None for v in sbc_b)
        has_net_bb = any(v is not None for v in maint_bb_b)
        has_rsu    = any(v is not None for v in rst_b)

        if has_sbc or has_net_bb:
            sbc_traces = []
            if has_sbc:
                sbc_traces.append(go.Bar(name="GAAP SBC Expense", x=years, y=sbc_b, marker_color="#AAAAAA", marker_line_width=0, hovertemplate="%{x}: " + ccy + "%{y:.2f}B<extra></extra>"))
            if has_net_bb:
                sbc_traces.append(go.Bar(name="Maintenance Buybacks", x=years, y=maint_bb_b, marker_color=C_DOWN, marker_line_width=0, hovertemplate="%{x}: " + ccy + "%{y:.2f}B<extra></extra>"))
            if has_rsu:
                sbc_traces.append(go.Bar(name="RSU Tax Withholdings", x=years, y=rst_b, marker_color="#8B1A1A", marker_line_width=0, hovertemplate="%{x}: " + ccy + "%{y:.2f}B<extra></extra>"))
            fig_sbc = go.Figure(data=sbc_traces)
            fig_sbc.update_layout(**CHART_BASE)
            fig_sbc.update_layout(
                height=300, barmode="group", title_text="GAAP SBC vs True SBC Cost  ($B)",
                legend=dict(orientation="h", y=1.08, x=0, font=dict(size=10)),
                yaxis=dict(tickprefix=ccy, ticksuffix="B", showgrid=True, gridcolor=C_BORDER2, tickfont=dict(size=10, color=C_TEXT3), zeroline=True, zerolinecolor=C_BORDER),
            )
            st.plotly_chart(fig_sbc, use_container_width=True, config={"displayModeBar": False})
            if not has_rsu and not sec_rsu:
                st.markdown('<div style="font-size:0.72rem;color:#999;margin-top:-0.5rem">RSU tax withholding not in ROIC data — use "Fetch RSU Tax from SEC (XBRL)" above to load it from EDGAR.</div>', unsafe_allow_html=True)
        else:
            st.markdown('<span style="color:#999;font-size:0.82rem">SBC and buyback data not available for this ticker.</span>', unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)

        st.markdown('<span class="section-label">Owners\' Earnings vs GAAP Net Income — Per Share</span>', unsafe_allow_html=True)

        ni_ps_list = []
        oe_ps_list = []
        for i in range(len(years)):
            ni  = ni_list[i]
            oe  = oe_list[i]
            
            # ── THE FIX: Use sh_list instead of sh_vals ──
            sh_curr = sh_list[i]   if (i < len(sh_list) and sh_list[i] and not pd.isna(sh_list[i])) else None
            sh_prev = sh_list[i-1] if (i > 0 and sh_list[i-1] and not pd.isna(sh_list[i-1])) else sh_curr

            ni_ps_list.append(ni / sh_prev if (ni is not None and sh_prev) else None)
            oe_ps_list.append(oe / sh_curr if (oe is not None and sh_curr) else None)

        if any(v is not None for v in oe_ps_list):
            oe_series = [ni_ps_list, oe_ps_list]
            oe_names  = ["GAAP NI per Share (prior yr shares)", "Owners' Earnings per Share (current yr shares)"]
            fig_oe = make_line(years, oe_series, oe_names, f"Per Share  ({ccy_code})", height=320)
            fig_oe.update_layout(yaxis=dict(tickprefix=ccy, showgrid=True, gridcolor=C_BORDER2, tickfont=dict(size=10, color=C_TEXT3), zeroline=True, zerolinecolor=C_BORDER, showline=False))
            st.plotly_chart(fig_oe, use_container_width=True, config={"displayModeBar": False})

        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown('<span class="section-label">Historical Breakdown</span>', unsafe_allow_html=True)

        def _fmt_b(v):
            if v is None: return "—"
            return f"{ccy}{v/1e9:.2f}B"
        def _fmt_pct(v):
            if v is None: return "—"
            sign = "+" if v >= 0 else ""
            return f"{sign}{v:.1f}%"

        oe_rows = {
            "Net Income (GAAP)":        [_fmt_b(_v(ni_s, i))          for i in range(len(years))],
            "GAAP SBC (add back)":      [_fmt_b(abs(_v(sbc_s,i)))     if _v(sbc_s,i) is not None else "—"  for i in range(len(years))],
            "Total Net Buybacks (info)":[_fmt_b(net_bb_list[i])       if net_bb_list[i] is not None else "—" for i in range(len(years))],
            "Maintenance Buybacks (sub)":[_fmt_b(-maint_bb_vals[i])   if maint_bb_vals[i] is not None else "—" for i in range(len(years))],
            "RSU Tax Withholdings (sub)":[
                _fmt_b(-sec_rsu.get(years[i])) if sec_rsu.get(years[i]) is not None 
                else (_fmt_b(-_absv(rsu_tax_s,i)) if _absv(rsu_tax_s,i) is not None else "n/a (fetch from SEC)")
                for i in range(len(years))
            ],
            "Owners' Earnings":         [_fmt_b(oe_list[i])           for i in range(len(years))],
            "OE as % of GAAP NI":       [
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
            "Annual Dilution":          [_fmt_pct(dil_list[i])        for i in range(len(years))],
        }

        oe_display = pd.DataFrame({"Metric": list(oe_rows.keys()),
                                   **{years[i]: [oe_rows[m][i] for m in oe_rows] for i in range(len(years))}
                                   }).set_index("Metric")
        st.dataframe(oe_display, use_container_width=True)

    with tab7:
        import re as _re_fa
        _is_non_us = bool(_re_fa.search(r"[.][A-Z]{1,4}$", ticker.upper()))

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
            if _run_btn: st.session_state.pop(_fa_key, None)

            if _fa_key not in st.session_state:
                _fa_progress = st.progress(0, text="Phase 1 / 4 — Fetching XBRL quantitative data…")
                _xbrl = fetch_forensic_xbrl(ticker)
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
                    _cik     = edgar_get_cik(ticker)
                    _filings = edgar_list_annual_filings(_cik, n=5) if _cik else []
                    _fa_progress.progress(0.25, text="Phase 2 / 4 — Fetching Item 8 notes (parallel)…")
                    _notes_raw: dict[str, str | None] = _fetch_notes_concurrent(_cik, _filings)
                    _fa_progress.progress(0.55, text="Phase 3 / 4 — Extracting signals (parallel)…")
                    _signals_by_year: dict[str, dict] = _extract_signals_concurrent(_notes_raw, company, _nvidia_key)
                    _notes_summary = _fmt_notes_signals(_signals_by_year)

                _fa_progress.progress(0.85, text="Phase 4 / 4 — Generating forensic report…")
                _forensic_text = generate_forensic_report(company, ticker, _data_table, _notes_summary, _nvidia_key)

                _fa_progress.empty()
                st.session_state[_fa_key] = {
                    "report":      _forensic_text,
                    "data_table":  _data_table,
                    "notes_summary": _notes_summary,
                }

            _fa_result = st.session_state[_fa_key]
            _fa_text   = _fa_result["report"]

            _sp_match = _re_fa.search(r"<forensic_scratchpad>([\s\S]*?)</forensic_scratchpad>", _fa_text, _re_fa.IGNORECASE)
            _report_body = _re_fa.sub(r"<forensic_scratchpad>[\s\S]*?</forensic_scratchpad>", "", _fa_text, flags=_re_fa.IGNORECASE).strip()

            if _sp_match:
                with st.expander("Forensic Scratchpad (raw calculations)", expanded=False):
                    st.markdown(f'<pre style="font-size:0.72rem;line-height:1.5;white-space:pre-wrap">{_sp_match.group(1).strip()}</pre>', unsafe_allow_html=True)

            st.markdown("---")
            _report_display = (_report_body or _fa_text).replace("$", r"\$")
            st.markdown(_report_display)
            st.markdown("---")

            with st.expander("Quantitative Data Table (XBRL + ROIC)", expanded=False):
                st.markdown(f'<pre style="font-size:0.72rem;line-height:1.5">{_fa_result["data_table"]}</pre>', unsafe_allow_html=True)
            if _fa_result["notes_summary"]:
                with st.expander("Notes Signals — Pass 1 extraction (US only)", expanded=False):
                    st.markdown(f'<pre style="font-size:0.72rem;line-height:1.5">{_fa_result["notes_summary"]}</pre>', unsafe_allow_html=True)

    with tab8:
        st.markdown('<div style="font-size:0.82rem;color:#555;margin-bottom:1.5rem;line-height:1.6">'
                    'Generates a comprehensive equity research report in the style of a Berkshire Hathaway analyst. '
                    'Uses the last 20 years of financial statements, last 4 earnings call transcripts, and web research. '
                    'Takes approximately 30–60 seconds.</div>', unsafe_allow_html=True)

        generate_btn = st.button("Generate Report")

        if generate_btn:
            import re as _re_tab
            _has_suffix = bool(_re_tab.search(r"[.][A-Z]{1,4}$", ticker.upper()))

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
                    report_text = generate_report_nvidia(company, ticker, financials_text, transcripts, _filing_text, _form_preview, _date_preview)
                    model_used, form_used = "nvidia", _form_preview
                else:
                    report_text = generate_report_haiku(company, ticker, financials_text, transcripts)
                    model_used, form_used = "haiku", None

            st.markdown("---")
            st.markdown(report_text)
            st.markdown("---")

            with st.spinner("Building PDF..."):
                chart_figs = []
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
                    chart_figs.append(("Profit Margins (%)", make_line(years, [gm_pct_pdf, opm_pct_pdf, npm_pct_pdf], ["Gross", "Operating", "Net"], "Margins")))
                pdf_bytes = build_report_pdf(company, ticker, report_text, transcripts, chart_figs)

            st.download_button(label="Download PDF", data=pdf_bytes, file_name=f"{ticker}_research_report.pdf", mime="application/pdf")

            meta_parts = []
            if model_used == "nvidia" and form_used:
                meta_parts.append(f"Model: DeepSeek R1  ·  Filing: {form_used} ({_date_preview})")
            else:
                meta_parts.append("Model: Claude Haiku  ·  Source: web search + financial data")
            if transcripts:
                labels = ", ".join([f"Q{t['quarter']} {t['year']}" for t in transcripts])
                meta_parts.append(f"Transcripts: {labels}")
            st.markdown(f'<div style="font-size:0.72rem;color:#999;margin-top:0.5rem">{" &nbsp;·&nbsp; ".join(meta_parts)}</div>', unsafe_allow_html=True)

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
