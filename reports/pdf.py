import io
import re
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed


def build_report_pdf(company, ticker, report_text, transcripts, chart_figs=None):
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import cm, mm
    from reportlab.lib import colors
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, HRFlowable,
        KeepTogether, Image as RLImage,
    )
    from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_JUSTIFY, TA_RIGHT

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

    s_cover_co   = S("cco",  fontName="Helvetica",           fontSize=10,   textColor=MUTED,    spaceAfter=2)
    s_cover_name = S("cnm",  fontName="Helvetica-Bold",       fontSize=26,   textColor=INK,      leading=30, spaceAfter=6)
    s_cover_sub  = S("csb",  fontName="Helvetica",            fontSize=12,   textColor=MID,      spaceAfter=4)
    s_cover_meta = S("cmt",  fontName="Helvetica",            fontSize=8.5,  textColor=MUTED)
    s_disc       = S("dsc",  fontName="Helvetica-Oblique",    fontSize=7.5,  textColor=MUTED,    spaceAfter=12, leading=11)
    s_sec        = S("sec",  fontName="Helvetica-Bold",       fontSize=11,   textColor=INK,      spaceBefore=20, spaceAfter=6, leading=14)
    s_body       = S("bdy",  fontName="Helvetica",            fontSize=9.5,  textColor=BODY_CLR, leading=15, spaceAfter=8, alignment=TA_JUSTIFY)
    s_caption    = S("cap",  fontName="Helvetica-Oblique",    fontSize=8,    textColor=MUTED,    spaceBefore=3, spaceAfter=10, alignment=TA_CENTER)
    s_footer     = S("ftr",  fontName="Helvetica",            fontSize=7.5,  textColor=MUTED,    alignment=TA_CENTER)

    story = []
    now   = datetime.now().strftime("%d %B %Y")
    lm    = 2.2 * cm
    rm    = 2.2 * cm

    def hr(thick=0.5, color=RULE_CLR, before=4, after=8):
        return HRFlowable(width="100%", thickness=thick, color=color,
                          spaceBefore=before * mm, spaceAfter=after * mm)

    # Cover
    story.append(Spacer(1, 1.2 * cm))
    story.append(Paragraph("EQUITY RESEARCH", s_cover_co))
    story.append(Paragraph(company, s_cover_name))
    story.append(Paragraph(ticker, s_cover_sub))
    story.append(Spacer(1, 0.4 * cm))
    story.append(hr(thick=1.5, color=INK, before=0, after=4))
    tc = f"{len(transcripts)} earnings transcript(s)" if transcripts else "No transcripts available"
    story.append(Paragraph(f"Generated {now}  ·  {tc}  ·  Fundamental analysis", s_cover_meta))
    story.append(Spacer(1, 0.5 * cm))
    story.append(Paragraph(
        "This report is AI-generated for informational purposes only and does not constitute "
        "investment advice. All financial figures are sourced from roic.ai. "
        "Verify all data independently before making investment decisions.",
        s_disc))
    story.append(hr())

    # Pre-render charts in parallel
    import plotly.io as pio

    def _render_one(args):
        idx, (title, fig) = args
        try:
            img_bytes = pio.to_image(fig, format="png", width=900, height=380, scale=2, engine="kaleido")
            return idx, img_bytes
        except Exception:
            return idx, None

    _pre_rendered: dict = {}
    if chart_figs:
        with ThreadPoolExecutor(max_workers=3) as _pool:
            _futures = {_pool.submit(_render_one, item): item for item in enumerate(chart_figs)}
            for _fut in as_completed(_futures):
                _idx, _img = _fut.result()
                _pre_rendered[_idx] = _img

    def add_chart(fig, title, width_cm=16, _chart_idx=None):
        img_bytes = _pre_rendered.get(_chart_idx) if _chart_idx is not None else None
        if img_bytes is None:
            return
        img_buf = io.BytesIO(img_bytes)
        img_w   = width_cm * cm
        img_h   = img_w * (380 / 900)
        story.append(RLImage(img_buf, width=img_w, height=img_h))
        story.append(Paragraph(title, s_caption))

    # Report body
    section_re = re.compile(r"(?m)^(\d+[.\)]\s+(?:THE\s+)?[A-Z][A-Z0-9 :&'\-\/\(\),]{4,})\s*$")
    parts      = section_re.split(report_text)

    if parts[0].strip():
        for para in parts[0].strip().split("\n\n"):
            if para.strip():
                story.append(Paragraph(para.strip(), s_body))

    SECTION_CHART_MAP = {"1": 0, "5": 1}
    i = 1
    while i < len(parts) - 1:
        heading  = parts[i].strip()
        body_txt = parts[i + 1] if i + 1 < len(parts) else ""
        sec_num  = heading[0]

        story.append(KeepTogether([
            hr(thick=0.5, before=4, after=3),
            Paragraph(heading, s_sec),
        ]))

        paragraphs = [p.strip() for p in re.split(r"\n\n+", body_txt) if p.strip()]
        for para in paragraphs:
            if re.match(r"^[A-Z][A-Z\s&:]{4,}:?\s*$", para) and len(para) < 80:
                story.append(Spacer(1, 3 * mm))
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
                story.append(Spacer(1, 4 * mm))
                add_chart(c_fig, c_title, _chart_idx=chart_idx)

        i += 2

    placed    = set(SECTION_CHART_MAP.values())
    remaining = [(idx, t, f) for idx, (t, f) in enumerate(chart_figs or []) if idx not in placed]
    if remaining:
        story.append(hr(before=6, after=4))
        story.append(Paragraph("FINANCIAL CHARTS", s_sec))
        for c_idx, c_title, c_fig in remaining:
            add_chart(c_fig, c_title, _chart_idx=c_idx)

    # Footer
    story.append(Spacer(1, 1 * cm))
    story.append(hr(thick=0.4, before=0, after=2))
    story.append(Paragraph(
        f"Compounder  ·  {company} ({ticker})  ·  {now}  ·  For informational use only",
        s_footer,
    ))

    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=lm, rightMargin=rm,
                            topMargin=2.2 * cm, bottomMargin=2.2 * cm)
    doc.build(story)
    buf.seek(0)
    return buf.read()
