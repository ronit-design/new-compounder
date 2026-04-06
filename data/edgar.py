import re
import streamlit as st
import requests


_HDRS = {"User-Agent": "compounder-app research@example.com"}


# ── CIK & filing index ────────────────────────────────────────────────────────

def edgar_get_cik(ticker):
    try:
        r = requests.get("https://www.sec.gov/files/company_tickers.json",
                         headers=_HDRS, timeout=15)
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
        r = requests.get(f"https://data.sec.gov/submissions/CIK{cik}.json",
                         headers=_HDRS, timeout=15)
        r.raise_for_status()
        recent  = r.json().get("filings", {}).get("recent", {})
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
def edgar_list_annual_filings(cik, n=5):
    try:
        r = requests.get(f"https://data.sec.gov/submissions/CIK{cik}.json",
                         headers=_HDRS, timeout=15)
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


# ── XBRL data ─────────────────────────────────────────────────────────────────

@st.cache_data(ttl=86400, show_spinner=False)
def fetch_rsu_tax_xbrl(ticker):
    cik = edgar_get_cik(ticker)
    if not cik:
        return {}
    try:
        url = f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"
        r   = requests.get(url, headers=_HDRS, timeout=30)
        r.raise_for_status()
        us_gaap = r.json().get("facts", {}).get("us-gaap", {})
        concept = us_gaap.get("PaymentsRelatedToTaxWithholdingForShareBasedCompensation", {})
        entries = concept.get("units", {}).get("USD", [])
        results, filed_at = {}, {}
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


@st.cache_data(ttl=3600, show_spinner=False)
def fetch_forensic_xbrl(ticker):
    cik = edgar_get_cik(ticker)
    if not cik:
        return {}
    try:
        r = requests.get(f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json",
                         headers=_HDRS, timeout=30)
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


# ── Filing text extraction ─────────────────────────────────────────────────────

@st.cache_data(ttl=86400, show_spinner=False)
def edgar_fetch_item8_notes(cik, accession_no_dashes, max_chars=14000):
    try:
        acc        = accession_no_dashes
        acc_dashes = f"{acc[:10]}-{acc[10:12]}-{acc[12:]}"
        cik_int    = int(cik)

        idx_url = f"https://www.sec.gov/Archives/edgar/data/{cik_int}/{acc}/{acc_dashes}-index.htm"
        r_idx   = requests.get(idx_url, headers=_HDRS, timeout=15)
        if not r_idx.ok:
            idx_url = f"https://www.sec.gov/Archives/edgar/data/{cik_int}/{acc_dashes.replace('-','')}/{acc_dashes}-index.htm"
            r_idx   = requests.get(idx_url, headers=_HDRS, timeout=15)

        doc_url = None
        if r_idx.ok:
            for row in re.findall(r'<tr[^>]*>.*?</tr>', r_idx.text, re.DOTALL | re.IGNORECASE):
                hm = re.search(r'href="(/Archives[^"]+\.htm)"', row, re.IGNORECASE)
                tm = re.search(r'<td[^>]*>\s*(10-K|20-F|FORM 10-K|FORM 20-F)\s*</td>', row, re.IGNORECASE)
                if hm and tm:
                    doc_url = "https://www.sec.gov" + hm.group(1)
                    break
            if not doc_url:
                links = re.findall(r'href="(/Archives/edgar/data/[^"]+\.htm)"', r_idx.text, re.IGNORECASE)
                cands = ["https://www.sec.gov" + l for l in links
                         if acc.lower() in l.lower().replace("-", "").replace("/", "")]
                if cands:
                    doc_url = cands[0]

        if not doc_url:
            return None

        r_doc = requests.get(doc_url, headers=_HDRS, timeout=60)
        if not r_doc.ok:
            return None

        try:
            from lxml import etree
            root = etree.fromstring(r_doc.content, parser=etree.HTMLParser())
            text = " ".join(root.itertext(with_tail=True))
        except Exception:
            text = re.sub(r"<[^>]{1,200}>", " ", r_doc.text)
        del r_doc

        text = text.replace("\xa0", " ").replace("&amp;", "&")
        text = re.sub(r"\s{3,}", "\n\n", text).strip()

        ms = re.search(r"(?i)item\s*8[\s.]+financial\s+statements", text)
        me = re.search(r"(?i)item\s*9[\s.]+", text[ms.end():]) if ms else None
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
            m = re.search(pat, item8)
            if not m:
                continue
            s = m.start()
            if any(a <= s <= b for a, b in used):
                continue
            chunks.append(item8[s: s + 2500].strip())
            used.append((s, s + 2500))

        result = "\n\n---\n\n".join(chunks) if chunks else item8[:max_chars]
        return result[:max_chars]
    except Exception:
        return None


def edgar_fetch_filing_text(cik, accession_no_dashes, max_chars=80000):
    try:
        acc        = accession_no_dashes
        acc_dashes = f"{acc[:10]}-{acc[10:12]}-{acc[12:]}"
        cik_int    = int(cik)

        idx_page_url = (f"https://www.sec.gov/Archives/edgar/data/"
                        f"{cik_int}/{acc}/{acc_dashes}-index.htm")
        r_idx = requests.get(idx_page_url, headers=_HDRS, timeout=15)

        if not r_idx.ok:
            idx_page_url = (f"https://www.sec.gov/Archives/edgar/data/"
                            f"{cik_int}/{acc_dashes.replace('-','')}/{acc_dashes}-index.htm")
            r_idx = requests.get(idx_page_url, headers=_HDRS, timeout=15)

        doc_url = None
        if r_idx.ok:
            rows       = re.findall(r'<tr[^>]*>.*?</tr>', r_idx.text, re.DOTALL | re.IGNORECASE)
            candidates = []
            for row in rows:
                href_m = re.search(r'href="(/Archives[^"]+\.htm)"', row, re.IGNORECASE)
                type_m = re.search(r'<td[^>]*>\s*(10-K|20-F|FORM 10-K|FORM 20-F)\s*</td>', row, re.IGNORECASE)
                if href_m and type_m:
                    candidates.append("https://www.sec.gov" + href_m.group(1))
            if not candidates:
                all_links  = re.findall(r'href="(/Archives/edgar/data/[^"]+\.htm)"', r_idx.text, re.IGNORECASE)
                candidates = ["https://www.sec.gov" + l for l in all_links
                              if acc.lower() in l.lower().replace("-", "").replace("/", "")]
            if candidates:
                doc_url = candidates[0]

        if not doc_url:
            return None

        r_doc = requests.get(doc_url, headers=_HDRS, timeout=60)
        if not r_doc.ok:
            return None

        try:
            from lxml import etree
            root = etree.fromstring(r_doc.content, parser=etree.HTMLParser())
            text = " ".join(root.itertext(with_tail=True))
        except Exception:
            text = re.sub(r"<[^>]{1,200}>", " ", r_doc.text)
        del r_doc

        text = text.replace("\xa0", " ").replace("&amp;", "&")
        text = re.sub(r"\s{3,}", "\n\n", text).strip()

        sections = {}
        patterns = [
            ("BUSINESS", r"(?i)item\s*1[\s.]+business\b", r"(?i)item\s*1a[\s.]+risk"),
            ("MD&A",     r"(?i)item\s*7[\s.]+management.{0,60}?discussion", r"(?i)item\s*7a[\s.]+"),
        ]
        for name, start_pat, end_pat in patterns:
            m_s = re.search(start_pat, text)
            if not m_s:
                continue
            tail  = text[m_s.end():]
            m_e   = re.search(end_pat, tail)
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
