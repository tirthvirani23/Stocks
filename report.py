"""Builds a short PDF summary of one stock checkup."""

from fpdf import FPDF

import analysis as a


def _t(x) -> str:
    """PDF core fonts only know Latin-1, so swap the few symbols that fall outside it."""
    s = str(x).replace("₹", "Rs ").replace("➤", ">").replace("…", "...").replace("—", "-")
    return s.encode("latin-1", "replace").decode("latin-1")


def _table(pdf, header, rows, widths):
    pdf.set_font("Helvetica", "B", 8)
    with pdf.table(col_widths=widths, line_height=5, text_align="LEFT", borders_layout="HORIZONTAL_LINES") as table:
        row = table.row()
        for h in header:
            row.cell(_t(h))
        pdf.set_font("Helvetica", "", 8)
        for r in rows:
            row = table.row()
            for c in r:
                row.cell(_t(c))
    pdf.ln(3)


def _h(pdf, text):
    pdf.set_font("Helvetica", "B", 11)
    pdf.cell(0, 8, _t(text), new_x="LMARGIN", new_y="NEXT")


def build(r: dict) -> bytes:
    f = r["f"]
    pdf = FPDF(format="A4")
    pdf.set_auto_page_break(True, margin=14)
    pdf.set_margins(14, 14, 14)
    pdf.add_page()

    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 9, _t(f["name"] or r["symbol"]), new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 9)
    pdf.cell(0, 5, _t(f"{r['exchange']}: {r['symbol']}  |  {f['sector'] or ''}  |  {f['industry'] or ''}"),
             new_x="LMARGIN", new_y="NEXT")
    ch = f" ({r['change_pct']:+.2f}%)" if r["change_pct"] is not None else ""
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 8, _t(f"Price: Rs {r['price']:,.2f}{ch}   as of {r['last_date']:%d %b %Y}"),
             new_x="LMARGIN", new_y="NEXT")

    _h(pdf, "Scores")
    rows = []
    for kind, title, note in [("valuation", "Valuation", "higher = cheaper"),
                              ("growth", "Growth potential", "higher = stronger"),
                              ("risk", "Risk", "higher = riskier")]:
        s = r[kind].score()
        rows.append([title, "Not scored" if s is None else f"{s} / 100", a.label(kind, s), note])
    _table(pdf, ["Score", "Result", "Reading", "Direction"], rows, (40, 30, 50, 40))

    sm = r["summary"]
    pdf.set_font("Helvetica", "", 9)
    pdf.multi_cell(0, 5, _t(sm["headline"]), new_x="LMARGIN", new_y="NEXT")
    for title, items in [("Strengths", sm["strengths"]), ("Watch out for", sm["concerns"])]:
        if items:
            pdf.set_font("Helvetica", "B", 9)
            pdf.cell(0, 6, title, new_x="LMARGIN", new_y="NEXT")
            pdf.set_font("Helvetica", "", 9)
            for m, txt in items:
                pdf.multi_cell(0, 5, _t(f"- {m}: {txt}"), new_x="LMARGIN", new_y="NEXT")
    pdf.ln(2)

    for kind, title in [("valuation", "Valuation"), ("growth", "Growth potential"), ("risk", "Risk")]:
        card = r[kind]
        if card.score() is None:
            continue
        _h(pdf, f"{title} score: how it was calculated")
        _table(pdf, ["Type", "Metric", "Value", "Points", "Weight", "Comment"],
               [[i["Type"], i["Metric"], i["Value"], "-" if i["Points"] is None else i["Points"], i["Weight"], i["Comment"]]
                for i in card.items], (10, 62, 36, 13, 13, 48))

    _h(pdf, "Technical indicators")
    _table(pdf, ["Indicator", "Value", "What it means", "Signal"],
           [[s["Indicator"], s["Value"], s["What it means"], s["Signal"]] for s in r["signals"]], (42, 42, 80, 18))

    pdf.set_font("Helvetica", "I", 7.5)
    pdf.multi_cell(0, 4, "Data source: Yahoo Finance. Scores follow fixed rules and do not reflect news, management "
                         "quality or sector cycles. Educational use only; not investment advice.",
                   new_x="LMARGIN", new_y="NEXT")
    return bytes(pdf.output())
