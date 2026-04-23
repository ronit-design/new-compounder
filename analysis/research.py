import re
import requests
import streamlit as st

from ai.nvidia import _call_nvidia, _build_prompt
from data.edgar import fetch_10k_text


# ── Transcript formatter ──────────────────────────────────────────────────────

def _format_transcripts(transcripts):
    if transcripts:
        txt = "\n\n=== EARNINGS CALL TRANSCRIPTS (last 4 quarters) ==="
        for t in transcripts:
            txt += f"\n\nQ{t['quarter']} {t['year']} Earnings Call (excerpt):\n{t['text'][:4000]}"
        return txt
    return "\n\n=== EARNINGS CALL TRANSCRIPTS ===\nNo transcripts available."


# ── Report cleanser ───────────────────────────────────────────────────────────

def _clean_report(text):
    text = re.sub(r"(?m)^#{1,6}\s*", "", text)
    text = re.sub(r"\*{2}(.+?)\*{2}", r"\1", text, flags=re.DOTALL)
    text = re.sub(r"\*(.+?)\*",       r"\1", text)
    text = re.sub(r"`+([^`]*)`+",     r"\1", text)   # strip inline code / backticks

    def _debullet(m):
        line = m.group(1).strip()
        if re.match(r"^\d+[.\)]\s+", line):
            return line
        if line and line[-1] not in ".!?:":
            line = line[0].upper() + line[1:] + "."
        else:
            line = line[0].upper() + line[1:]
        return line + " "

    text = re.sub(r"(?m)^[ \t]*[-\*\u2022\u2013]\s+(.+)$", _debullet, text)
    text = re.sub(r"[\u25a0\u25a1\ufffd](\d)", r"\1", text)
    text = re.sub(r"\n{3,}", "\n\n", text)

    paras  = text.split("\n\n")
    merged = []
    i = 0
    while i < len(paras):
        p = paras[i].strip()
        if re.match(r"^\d+[.\)]\s+[A-Z]{3}", p):
            merged.append(p)
            i += 1
        elif (len(p) < 120 and i + 1 < len(paras)
              and not re.match(r"^\d+[.\)]\s+[A-Z]{3}", paras[i+1].strip())):
            combined = p.rstrip()
            if combined and combined[-1] not in ".!?":
                combined += "."
            combined += " " + paras[i+1].strip()
            paras[i+1] = combined
            i += 1
        else:
            merged.append(p)
            i += 1

    return "\n\n".join(merged).strip()


# ── Polish pass (runs after initial generation for both NVIDIA and Haiku) ─────

def _polish_section(heading, body, api_key):
    """Send one report section body to NVIDIA for prose consistency editing.
    Returns only the polished body — the heading is prepended by _polish_report."""
    prompt = f"""You are a professional investment research editor preparing a final deliverable for an investment committee.

Below is a draft body of one section of an equity research report. Rewrite it as clean, publication-ready prose. Apply every rule below without exception.

EDITING RULES:
1. Convert every bullet point, dash list, or numbered sub-list into complete flowing sentences embedded in paragraphs. No item should remain as a standalone line starting with a dash, bullet, or number.
2. Fix every broken or fragmented line — merge orphaned lines into their surrounding paragraph.
3. Never write out arithmetic operations. If a formula or calculation appears (e.g. "ROIC = NOPAT / Invested Capital" or "calculated as 394.85 million divided by 2.35 billion"), state only the final result as a clean figure or percentage and explain what it represents in plain English. The reader must never see raw division, multiplication, or equation syntax.
4. Never use backticks or inline code formatting. Remove any text wrapped in backticks and write it as plain prose instead.
5. Every paragraph must contain a minimum of five sentences: a point, evidence from the data, analysis of what the evidence means, a second-order implication, and a conclusion.
6. No markdown characters anywhere — no **, no ##, no -, no >, no backticks.
7. Preserve every factual claim, financial figure, citation (e.g. FY2024 Income Statement), and verbatim management quote exactly as written. Do not add any information not present in the draft. Do not remove any information from the draft.
8. Begin your response directly with the first paragraph of body prose. Do not write the section heading.

DRAFT SECTION BODY (section heading is "{heading}"):
{body}

Rewrite the body now as polished, publication-ready prose — starting directly with the first paragraph:"""

    return _call_nvidia(
        [{"role": "user", "content": prompt}],
        api_key,
        max_tokens=8000,
    )


# Canonical section headings — single source of truth used by both polish paths
_CANONICAL_HEADINGS = [
    "1. THE FOUNDATION: BUSINESS OVERVIEW & TANGIBLE SCALE",
    "2. THE BATTLEFIELD: INDUSTRY LANDSCAPE & COMPETITIVE PROFILE",
    "3. THE GENERALS: MANAGEMENT, ALIGNMENT & TRACK RECORD",
    "4. THE CHOKEPOINTS: CUSTOMER DYNAMICS & SUPPLY CHAIN",
    "5. THE SCORECARD: FINANCIAL TRUTH & CAPITAL ALLOCATION",
    "6. THE ASYMMETRIC BET: GROWTH RUNWAY & THE KILL SHOT",
    "7. CATALYSTS & INFLECTION POINTS",
]


def _reformat_haiku_report(raw_text, api_key, on_progress=None):
    """Reformat the entire Haiku output in one NVIDIA call.

    Haiku's output is structurally unreliable — headings are fused with body
    text on the same line, preamble meta-commentary precedes the first section,
    and heading formats vary wildly.  Attempting to split it section-by-section
    always fails.  Instead we send the full raw text to NVIDIA and instruct it
    to strip preamble, restructure into exactly 7 numbered sections, and rewrite
    as polished publication-ready prose.
    """
    if on_progress:
        on_progress(1, "Reformatting and polishing full report", 1)

    section_list = "\n".join(f"  {h}" for h in _CANONICAL_HEADINGS)

    prompt = f"""You are a professional investment research editor preparing a final deliverable for an investment committee.

The draft below is a research report that was written by an AI assistant. It contains meta-commentary preambles, inconsistent section headings, bullet points, broken lines, formulas written as equations, and backtick code formatting. Your job is to produce a clean, publication-ready version.

INSTRUCTIONS — apply every rule without exception:

1. REMOVE the preamble. Delete everything before the first section heading — any text such as "I will now research...", "Let me gather information...", "I now have sufficient research...", or similar AI commentary. The report must begin directly with the first section heading.

2. RESTRUCTURE into exactly these 7 sections, using these exact headings on their own lines with nothing else on that line:
{section_list}

3. REWRITE each section body as continuous flowing prose:
   - No bullet points, dashes as list markers, numbered sub-lists, or tables.
   - No markdown characters: no **, no ##, no -, no >, no backticks.
   - No arithmetic written out: never write "calculated as X divided by Y". State only the final result as a clean figure or percentage.
   - Every paragraph minimum five sentences: a point, evidence, analysis, second-order implication, and a conclusion.

4. PRESERVE every financial figure, citation (e.g. FY2024 Income Statement), and verbatim management quote exactly as it appears in the draft. Do not add information. Do not remove substantive content.

5. OUTPUT FORMAT: begin your response directly with the first section heading. Do not write any preamble or meta-commentary.

DRAFT REPORT:
{raw_text}

Write the complete reformatted report now:"""

    result = _call_nvidia(
        [{"role": "user", "content": prompt}],
        api_key,
        max_tokens=16000,
    )
    return result if result and result.strip() else raw_text


def _polish_report(report_text, api_key, on_progress=None):
    """Polish a report that was generated section-by-section (NVIDIA path).

    Splits on the strict numbered-heading regex and sends each section body
    to NVIDIA individually.  The heading is always prepended by this function
    so the PDF splitter sees a guaranteed clean format.
    """
    section_re = re.compile(r'(?m)^(\d+\.\s+[A-Z][A-Z\s&:,\-]+)$')
    parts      = section_re.split(report_text)

    sections = []
    i = 1
    while i < len(parts) - 1:
        sections.append((parts[i].strip(), parts[i + 1].strip()))
        i += 2

    if not sections:
        return report_text

    total          = len(sections)
    polished_parts = []

    for idx, (heading, body) in enumerate(sections, 1):
        if on_progress:
            on_progress(idx, heading, total)

        polished_body = _polish_section(heading, body, api_key)
        if polished_body and polished_body.strip():
            polished_parts.append(f"{heading}\n\n{polished_body.strip()}")
        else:
            polished_parts.append(f"{heading}\n\n{body}")

    return "\n\n".join(polished_parts)


# ── NVIDIA multi-section report ───────────────────────────────────────────────

def generate_report_nvidia(company_name, ticker, financials_text, transcripts,
                            filing_text, form_type, filing_date,
                            on_section=None, on_polish=None):
    transcript_text = _format_transcripts(transcripts)
    filing_section  = (f"\n\n=== {form_type} FILING ({filing_date}) ===\n{filing_text[:60000]}"
                       if filing_text else "")
    source_note     = (f"You have been provided the {form_type} filing ({filing_date}), "
                       f"financial statements, and earnings transcripts.")
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

    total_sections = len(sections)
    try:
        report_parts = []
        for sec_idx, (heading, instructions) in enumerate(sections, 1):
            if on_section:
                on_section(sec_idx, heading, total_sections)

            section_prompt = data_block + f"{heading}\n\n{instructions}"
            text = _call_nvidia([{"role": "user", "content": section_prompt}], api_key)
            if not text:
                continue
            text    = text.strip()
            sec_num = heading.split(".")[0].strip()
            lines   = text.split("\n")
            cleaned_lines = []
            for line in lines:
                stripped = line.strip().lstrip("*#").strip()
                if re.match(rf"^{sec_num}[.\)]\s+", stripped):
                    continue
                cleaned_lines.append(line)

            body = "\n".join(cleaned_lines).strip().lstrip("\n").strip()
            if not body:
                continue

            report_parts.append(f"{heading}\n\n{body}")

        if not report_parts:
            return "NVIDIA returned empty responses for all sections."

        assembled = _clean_report("\n\n".join(report_parts))
        return _polish_report(assembled, api_key, on_progress=on_polish)
    except Exception as e:
        return f"Error generating report via NVIDIA: {e}"


# ── Haiku report (non-US tickers) ─────────────────────────────────────────────

def generate_report_haiku(company_name, ticker, financials_text, transcripts,
                          on_polish=None):
    transcript_text = _format_transcripts(transcripts)
    source_note = ("No SEC filing is available for this company. "
                   "Use the web_search tool extensively to research the business model, "
                   "competitive position, and recent developments before writing.")

    prompt = _build_prompt(company_name, ticker, financials_text,
                           transcript_text, "", source_note)
    try:
        api_key = st.secrets.get("ANTHROPIC_API_KEY", "")
        headers = {
            "Content-Type":    "application/json",
            "x-api-key":       api_key,
            "anthropic-version": "2023-06-01",
        }
        payload = {
            "model":      "claude-haiku-4-5-20251001",
            "max_tokens": 16000,
            "tools":      [{"type": "web_search_20250305", "name": "web_search"}],
            "messages":   [{"role": "user", "content": prompt}],
        }
        r = requests.post("https://api.anthropic.com/v1/messages",
                          headers=headers, json=payload, timeout=300)
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
            if not tool_results:
                break
            messages.append({"role": "user", "content": tool_results})
            r2 = requests.post("https://api.anthropic.com/v1/messages",
                               headers=headers,
                               json={**payload, "messages": messages},
                               timeout=300)
            r2.raise_for_status()
            data = r2.json()

        text_parts = [b["text"] for b in data["content"] if b.get("type") == "text"]
        assembled  = _clean_report("\n\n".join(text_parts))
        nvidia_key = st.secrets.get("NVIDIA_API_KEY", "")
        return _reformat_haiku_report(assembled, nvidia_key, on_progress=on_polish)
    except Exception as e:
        return f"Error generating report via Haiku: {e}"


# ── Router ─────────────────────────────────────────────────────────────────────

def generate_research_report(company_name, ticker, financials_text, transcripts,
                              web_context="", on_section=None, on_polish=None):
    has_suffix = bool(re.search(r"[.][A-Z]{1,4}$", ticker.upper()))

    if has_suffix:
        return (generate_report_haiku(company_name, ticker, financials_text, transcripts,
                                      on_polish=on_polish),
                "haiku", None)

    filing_text, form_type, filing_date = fetch_10k_text(ticker)
    if filing_text:
        return (generate_report_nvidia(company_name, ticker, financials_text, transcripts,
                                       filing_text, form_type, filing_date,
                                       on_section=on_section, on_polish=on_polish),
                "nvidia", form_type)

    return (generate_report_haiku(company_name, ticker, financials_text, transcripts,
                                  on_polish=on_polish),
            "haiku", None)
