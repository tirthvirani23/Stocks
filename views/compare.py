"""Compare page: two or three stocks side by side."""

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import ui
from ui import AQUA, BLUE, ORANGE, base_layout, crore, fmt

st.title("Compare stocks")

with st.form("compare", border=False):
    c = st.columns([2, 2, 2, 1], vertical_alignment="bottom")
    q1 = c[0].text_input("First stock", value="TCS", key="cmp1")
    q2 = c[1].text_input("Second stock", value="INFY", key="cmp2")
    q3 = c[2].text_input("Third stock (optional)", value="", key="cmp3")
    c[3].form_submit_button("Compare", type="primary", width="stretch")

queries = [q for q in (q1, q2, q3) if q.strip()]
if len(queries) < 2:
    st.info("Enter at least two stock symbols.")
    st.stop()

results = []
with st.spinner("Analysing…"):
    for q in queries:
        r = ui.load(q, light=True)
        if r is not None and r["ticker"] not in [x["ticker"] for x in results]:
            results.append(r)
if len(results) < 2:
    st.stop()

cols = st.columns(len(results))
for col, r in zip(cols, results):
    with col:
        st.subheader(r["symbol"])
        st.markdown(f'<span class="muted">{r["f"]["name"] or ""}</span>', unsafe_allow_html=True)
        st.markdown(f'<div class="price-big" style="font-size:1.6rem">₹{r["price"]:,.2f}</div>', unsafe_allow_html=True)
        ui.score_card("Valuation", "valuation", r["valuation"], "Higher = cheaper")
        st.write("")
        ui.score_card("Growth potential", "growth", r["growth"], "Higher = stronger")
        st.write("")
        ui.score_card("Risk", "risk", r["risk"], "Higher = riskier")

st.write("")
st.markdown("##### Key numbers")
rows = [
    ("Market value", lambda r: crore(r["f"]["market_cap"])),
    ("P/E", lambda r: fmt(r["f"]["pe"], "{:.1f}")),
    ("P/B", lambda r: fmt(r["f"]["pb"])),
    ("ROE", lambda r: fmt(r["f"]["roe"], "{:.1f}%")),
    ("Net profit margin", lambda r: fmt(r["f"]["profit_margin"], "{:.1f}%")),
    ("Sales growth per year", lambda r: fmt(r["f"]["rev_cagr"], "{:+.1f}%")),
    ("Profit growth per year", lambda r: fmt(r["f"]["profit_cagr"], "{:+.1f}%")),
    ("Debt ÷ equity", lambda r: fmt(r["f"]["debt_equity"])),
    ("Dividend yield", lambda r: fmt(r["f"]["div_yield"], "{:.2f}%")),
    ("1-year return", lambda r: fmt(r["t"]["ret_1y"], "{:+.1f}%")),
    ("Volatility (yearly)", lambda r: fmt(r["t"]["volatility"], "{:.1f}%")),
    ("Beta vs Nifty 50", lambda r: fmt(r["t"]["beta"])),
    ("Price vs 200-day average", lambda r: fmt(r["t"]["vs_sma200"], "{:+.1f}%")),
    ("RSI (14)", lambda r: fmt(r["t"]["rsi"], "{:.0f}")),
]
table = pd.DataFrame({"Measure": [n for n, _ in rows], **{r["symbol"]: [fn(r) for _, fn in rows] for r in results}})
st.dataframe(table, hide_index=True, width="stretch", height=35 * (len(table) + 1) + 3)

period = st.radio("Price performance", ["1 year", "3 years", "5 years"], horizontal=True)
n = {"1 year": 252, "3 years": 756, "5 years": 1260}[period]
fig = go.Figure()
for r, colour in zip(results, [BLUE, ORANGE, AQUA]):
    s = r["hist"]["Adj Close"].dropna().tail(n)
    fig.add_trace(go.Scatter(x=s.index, y=s / s.iloc[0] * 100, name=r["symbol"], line=dict(color=colour, width=2),
                             hovertemplate="%{y:.0f}"))
base_layout(fig, 380, "Growth of ₹100 (dividends included)")
st.plotly_chart(fig, width="stretch")
