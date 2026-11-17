"""Portfolio Review: upload a screenshot or type your holdings, get a rating, return scenarios and suggestions."""

import pandas as pd
import streamlit as st

import portfolio
import ui

EXAMPLE = [{"Symbol": "RELIANCE", "Quantity": 25.0, "Buy price": 1210.0},
           {"Symbol": "HDFCBANK", "Quantity": 40.0, "Buy price": 760.0},
           {"Symbol": "TCS", "Quantity": 10.0, "Buy price": 3105.0},
           {"Symbol": "INFY", "Quantity": 30.0, "Buy price": 1420.0},
           {"Symbol": "ITC", "Quantity": 120.0, "Buy price": 398.0}]

st.title("Portfolio Review")
st.caption("Upload a screenshot of your holdings or type them in. Each stock gets the full fundamental and technical "
           "checkup, then the portfolio is rated as a whole.")

if "pf_rows" not in st.session_state:
    st.session_state["pf_rows"] = EXAMPLE
    st.session_state["pf_example"] = True

up = st.file_uploader("Screenshot of your portfolio (optional)", type=["png", "jpg", "jpeg", "webp"])
if up is not None and st.session_state.get("pf_image") != (up.name, up.size):
    st.session_state["pf_image"] = (up.name, up.size)
    try:
        import ocr
        with st.spinner("Reading the image…"):
            found = ocr.parse_holdings(ocr.read_text(up.getvalue()))
    except Exception:
        found = None
    if found:
        st.session_state["pf_rows"] = found
        st.session_state["pf_example"] = False
        st.session_state["pf_editor_version"] = st.session_state.get("pf_editor_version", 0) + 1
        st.session_state["pf_message"] = ("success", f"Found {len(found)} stock{'s' if len(found) != 1 else ''} in "
                                          "the image. Check the table below and correct anything misread, especially "
                                          "quantities and prices.")
    else:
        st.session_state["pf_message"] = ("warning", "No stocks could be read from that image. Type your holdings in "
                                          "the table below instead.")
if "pf_message" in st.session_state:
    kind, text = st.session_state["pf_message"]
    getattr(st, kind)(text)

st.markdown("**Your holdings**" + (" (example shown: replace with your own)" if st.session_state.get("pf_example") else ""))
edited = st.data_editor(
    pd.DataFrame(st.session_state["pf_rows"], columns=["Symbol", "Quantity", "Buy price"]),
    num_rows="dynamic", hide_index=True, width="stretch", key=f"pf_editor_{st.session_state.get('pf_editor_version', 0)}",
    column_config={
        "Symbol": st.column_config.TextColumn("Stock symbol or name", required=True),
        "Quantity": st.column_config.NumberColumn("Quantity", min_value=0, help="Leave all blank to weigh stocks equally"),
        "Buy price": st.column_config.NumberColumn("Average buy price (₹, optional)", min_value=0, format="%.2f"),
    })
go = st.button("Review portfolio", type="primary")

if go:
    rows = [{"symbol": str(x["Symbol"]).strip(), "qty": x["Quantity"] if pd.notna(x["Quantity"]) and x["Quantity"] > 0 else None,
             "avg": x["Buy price"] if pd.notna(x["Buy price"]) and x["Buy price"] > 0 else None}
            for x in edited.to_dict("records") if isinstance(x["Symbol"], str) and x["Symbol"].strip()]
    st.session_state["pf_request"] = rows[:40]
if "pf_request" not in st.session_state:
    st.stop()
request = st.session_state["pf_request"]
if not request:
    st.warning("Add at least one stock.")
    st.stop()

holdings, seen = [], set()
bar = st.progress(0.0, text="Analysing…")
for i, h in enumerate(request):
    bar.progress(i / len(request), text=f"Analysing {h['symbol'].upper()}…")
    r = ui.load(h["symbol"], light=True)
    if r is not None and r["ticker"] not in seen:
        seen.add(r["ticker"])
        holdings.append({"r": r, "qty": h["qty"], "avg": h["avg"]})
bar.empty()
if not holdings:
    st.stop()

rev = portfolio.review(holdings)

# ------------------------------------------------------------------ rating

st.divider()
st.markdown("#### Portfolio rating")
c = st.columns(4)
with c[0]:
    ui.score_card("Portfolio score", "overall", ui.FixedScore(rev["score"]),
                  "Weighted overall score" + (f", less {rev['penalty']} points for concentration." if rev["penalty"] else "."))
with c[1]:
    ui.score_card("Valuation", "valuation", ui.FixedScore(rev["valuation"]), "Higher = cheaper")
with c[2]:
    ui.score_card("Growth potential", "growth", ui.FixedScore(rev["growth"]), "Higher = stronger")
with c[3]:
    ui.score_card("Risk", "risk", ui.FixedScore(rev["risk"]), "Higher = riskier")
st.caption("Each score is the average of the holdings' scores, weighted by "
           + ("current value." if rev["have_qty"] else "equal amounts, because quantities were not given for every stock."))

# ------------------------------------------------------------------ expected return

st.markdown("#### Return scenarios")
total = rev["total"] if rev["have_qty"] else 100000.0
e = rev["expected"]
table = pd.DataFrame([{
    "Case": name,
    "Next 1 year": f"{e['y1'][key]:+.1f}%",
    "Value after 1 year": f"₹{total * (1 + e['y1'][key] / 100):,.0f}",
    "Next 5 years (per year)": f"{e['y5'][key]:+.1f}%",
    "Value after 5 years": f"₹{total * (1 + e['y5'][key] / 100) ** 5:,.0f}",
} for name, key in (("Bear", "bear"), ("Neutral", "neutral"), ("Bull", "bull"))])
st.dataframe(table, hide_index=True, width="stretch")
st.caption(f"Starting value: ₹{total:,.0f}" + ("" if rev["have_qty"] else " (illustrative)") + ". "
           "These are rule-based scenarios, not predictions. Actual results can fall outside the bear-bull range.")
with st.expander("How the scenarios are calculated"):
    st.markdown(
        "- **5 years (fundamental analysis):** each company's profit is grown for five years, valued at a fair P/E "
        "(average of its industry's P/E and its own past average), and dividends are added. Neutral uses its recent "
        "and expected growth rate; bear uses 4 points less growth and a 20% lower P/E; bull uses 4 points more and a "
        "20% higher P/E. Companies without steady profits get a market-average rate adjusted by their overall score.\n"
        "- **1 year (adds technical analysis):** starts from the 5-year neutral rate, blends in the analysts' target "
        "price when at least three analysts cover the stock, and adds or subtracts 3 points for an established "
        "up- or down-trend (price and 50-day average versus the 200-day average). The bear and bull cases are that "
        "figure minus and plus about one year's typical price swing (volatility) for the stock.\n"
        "- **Portfolio:** the weighted average of the holdings. This treats all stocks as falling or rising "
        "together, so the range is on the wide side for a well-spread portfolio.")

# ------------------------------------------------------------------ holdings

st.markdown("#### Holding by holding")
hold = pd.DataFrame([{
    "Symbol": x["symbol"], "Weight": x["weight"], "Verdict": x["verdict"], "Overall": x["overall"],
    "Valuation": x["valuation"], "Growth": x["growth"], "Risk": x["risk"],
    "1 year": x["er"]["y1"]["neutral"], "5 years / yr": x["er"]["y5"]["neutral"],
    "Your gain": x["gain"], "Main reason": x["why"]} for x in rev["rows"]])
if hold["Your gain"].isna().all():
    hold = hold.drop(columns=["Your gain"])
pct = st.column_config.NumberColumn(format="%+.1f%%")
event = st.dataframe(hold, hide_index=True, width="stretch", height=35 * (len(hold) + 1) + 3,
                     column_config={**ui.COMPACT_COLUMNS, "Weight": st.column_config.NumberColumn(format="%.0f%%"),
                                    "1 year": st.column_config.NumberColumn(format="%+.1f%%", help="Neutral case"),
                                    "5 years / yr": st.column_config.NumberColumn(format="%+.1f%%", help="Neutral case"),
                                    "Your gain": pct, "Main reason": st.column_config.TextColumn(width="large")},
                     on_select="rerun", selection_mode="single-row", key="pf_table")
if event.selection.rows:
    sym = hold.iloc[event.selection.rows[0]]["Symbol"]
    if st.button(f"Open {sym} checkup", type="primary"):
        st.session_state["symbol"] = sym
        st.switch_page("views/checkup.py")

# ------------------------------------------------------------------ suggestions

st.markdown("#### Suggested changes")
weak = [x for x in rev["rows"] if x["verdict"] == "Consider reducing"]
watch = [x for x in rev["rows"] if x["verdict"] == "Review"]
lines = list(rev["notes"])
for x in weak:
    lines.append(f"**Consider reducing or removing {x['symbol']}** ({x['weight']:.0f}% of portfolio, overall {x['overall']}): {x['why']}.")
for x in watch:
    lines.append(f"**Keep an eye on {x['symbol']}** (overall {x['overall']}): {x['why']}.")
if not lines:
    lines.append("Nothing stands out as needing a change: no holding has weak scores and the portfolio is reasonably spread.")
st.markdown("\n".join(f"- {t}" for t in lines))

monthly = ui.monthly_scores()
if monthly:
    ideas = portfolio.additions(rev, [r for r in monthly["rows"] if r.get("Coverage", 1) >= 0.7])
    if ideas["swaps"]:
        st.markdown("**Better-scored alternatives in the same industry**")
        st.markdown("\n".join(
            f"- Instead of {x['symbol']} (overall {x['overall']}): "
            + ", ".join(f"**{s['Symbol']}** {s['Company']} (overall {s['Overall']})" for s in best)
            for x, best in ideas["swaps"]))
    if ideas["new_sectors"]:
        st.markdown("**Top-scored stocks from sectors you do not hold**")
        st.markdown("\n".join(f"- **{s['Symbol']}** {s['Company']} · {s['Sector']} (overall {s['Overall']}, "
                              f"valuation {s['Valuation']}, growth {s['Growth']}, risk {s['Risk']})"
                              for s in ideas["new_sectors"]))
    st.caption(f"Alternatives come from the monthly scores of large and mid-size companies (updated {monthly['updated']}). "
               "They are starting points for your own research. This review does not know your goals, time horizon "
               "or tax position.")
