import requests


def _call_nvidia(messages, api_key, max_tokens=32000):
    r = requests.post(
        "https://integrate.api.nvidia.com/v1/chat/completions",
        headers={"Content-Type": "application/json",
                 "Authorization": f"Bearer {api_key}"},
        json={
            "model":       "deepseek-ai/deepseek-r1",
            "max_tokens":  max_tokens,
            "temperature": 0.6,
            "top_p":       0.95,
            "messages":    messages,
        },
        timeout=300,
    )
    r.raise_for_status()
    msg = r.json()["choices"][0]["message"]
    return str(msg.get("content") or msg.get("reasoning_content") or msg.get("text") or "").strip()


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
