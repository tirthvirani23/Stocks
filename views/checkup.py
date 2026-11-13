"""Checkup page: one stock, in depth."""

import datetime as dt

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import analysis as a
import report
import ui
from ui import AQUA, BAD, BLUE, GOOD, ORANGE, base_layout, crore, fmt

st.title("Indian Stock Checkup")

with st.form("search", border=False):
    c1, c2 = st.columns([5, 1], vertical_alignment="bottom")
    if "symbol" not in st.session_state:
        st.session_state["symbol"] = st.session_state.get("last_symbol", "RELIANCE")
    query = c1.text_input("Stock symbol or company name", key="symbol",
                          placeholder="e.g. RELIANCE, TCS, HDFCBANK, INFY")
    c2.form_submit_button("Analyse", type="primary", width="stretch")

if not query.strip():
    st.info("Type a stock symbol above, for example RELIANCE, TCS or HDFCBANK.")
    st.stop()

with st.spinner(f"Fetching data and analysing {query.strip().upper()}…"):
    r = ui.load(query)
if r is None:
    st.stop()
st.session_state["last_symbol"] = query.strip()

f, t, d = r["f"], r["t"], r["hist"]
val, gro, risk = r["valuation"], r["growth"], r["risk"]

# ------------------------------------------------------------------ name, price, actions

left, right = st.columns([3, 2], vertical_alignment="top")
with left:
    st.subheader(f"{f['name'] or r['symbol']}")
    st.markdown(f'<span class="muted">{r["exchange"]}: {r["symbol"]}'
                f'{" · " + f["sector"] if f["sector"] else ""}'
                f'{" · " + f["industry"] if f["industry"] else ""}</span>', unsafe_allow_html=True)
    b1, b2, _ = st.columns([1.3, 1.3, 2])
    watch = ui.watchlist()
    if r["symbol"] in watch:
        if b1.button("★ In watchlist", help="Click to remove from your watchlist", width="stretch"):
            watch.remove(r["symbol"])
            st.rerun()
    elif b1.button("☆ Add to watchlist", width="stretch"):
        watch.append(r["symbol"])
        st.rerun()
    b2.download_button("Download PDF", data=report.build(r), file_name=f"{r['symbol']}-checkup.pdf",
                       mime="application/pdf", width="stretch")
with right:
    ch = r["change_pct"]
    colour = GOOD if (ch or 0) >= 0 else BAD
    arrow = "▲" if (ch or 0) >= 0 else "▼"
    change_txt = (f'<span style="color:{colour}; font-weight:600;">{arrow} '
                  f'₹{abs(r["price"] - r["prev_close"]):,.2f} ({ch:+.2f}%)</span>') if ch is not None else ""
    st.markdown(f'<div class="price-big">₹{r["price"]:,.2f}</div>{change_txt}'
                f'<div class="muted">Last traded price, as of {r["last_date"]:%d %b %Y}. '
                'May be delayed by about 15 minutes.</div>', unsafe_allow_html=True)

# ------------------------------------------------------------------ summary and scores

sm = r["summary"]
st.markdown(f'<div class="headline">{sm["headline"]}</div>', unsafe_allow_html=True)

s1, s2, s3 = st.columns(3)
with s1:
    ui.score_card("Valuation", "valuation", val, "Higher is better: the price is low compared with profits, assets, growth and peers.")
with s2:
    ui.score_card("Growth potential", "growth", gro, "Higher is better: sales and profit growth, return on equity and price trend.")
with s3:
    ui.score_card("Risk", "risk", risk, "Higher means riskier: price swings, debt, company size and profit stability.")

if sm["strengths"] or sm["concerns"]:
    st.write("")
    g, b = st.columns(2)
    with g:
        st.markdown("**Strengths**")
        st.markdown("\n".join(f"- {m}: {txt}" for m, txt in sm["strengths"]) or "- None stand out")
    with b:
        st.markdown("**Watch out for**")
        st.markdown("\n".join(f"- {m}: {txt}" for m, txt in sm["concerns"]) or "- Nothing stands out")

if f["is_fund"]:
    st.info("This looks like an ETF or fund, so there are no company financials. Only the price chart, "
            "risk and past returns apply; valuation and growth are not scored.")
elif f["is_financial"]:
    st.info("This is a bank or financial company. Debt ratios, current ratio and EV/EBITDA do not apply "
            "to lenders, so they are left out of the scores and P/B counts for more.")

# ------------------------------------------------------------------ tabs

tab_scores, tab_ta, tab_fa, tab_peers, tab_ret, tab_news = st.tabs(
    ["Score details", "Technical", "Fundamentals", "Peers", "Past returns", "News and events"])


def breakdown(card: a.Scorecard, points_label):
    df = pd.DataFrame(card.items)
    used = df["Points"].notna()
    df["Share of score"] = (df["Weight"] / df.loc[used, "Weight"].sum() * 100).where(used)
    df = df.rename(columns={"Points": points_label})
    st.dataframe(
        df[["Type", "Metric", "Value", points_label, "Share of score", "Comment"]],
        hide_index=True, width="stretch",
        column_config={
            "Type": st.column_config.TextColumn(width="small", help="FA = fundamental analysis, TA = technical analysis"),
            points_label: st.column_config.ProgressColumn(min_value=0, max_value=100, format="%d"),
            "Share of score": st.column_config.NumberColumn(format="%.0f%%", help="How much this metric counts towards the score"),
        },
    )


with tab_scores:
    st.markdown("Each metric earns points out of 100. The score is the weighted average of the metrics that have data. "
                "**FA** rows come from the company's financials, **TA** rows from its price chart.")
    for title, card, lab in [("Valuation", val, "Points (higher = cheaper)"),
                             ("Growth potential", gro, "Points (higher = stronger)"),
                             ("Risk", risk, "Risk points (higher = riskier)")]:
        if card.score() is not None:
            st.markdown(f"##### {title}: {card.score()} / 100")
            breakdown(card, lab)

# ------------------------------------------------------------------ technical

with tab_ta:
    signals = pd.DataFrame(r["signals"])
    counts = signals["Signal"].value_counts()
    st.markdown(f"**Signal count:** {counts.get('Bullish', 0)} bullish · {counts.get('Bearish', 0)} bearish · "
                f"{counts.get('Caution', 0)} caution · {counts.get('Neutral', 0)} neutral")

    o1, o2 = st.columns([3, 2])
    periods = {"6 months": 126, "1 year": 252, "2 years": 504, "5 years": 1260, "10 years": len(d)}
    period = o1.radio("Chart period", list(periods), index=1, horizontal=True)
    kind = o2.radio("Chart type", ["Line", "Candlestick"], horizontal=True)
    v = d.tail(periods[period])
    lv = r["levels"]

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=v.index, y=v["BBupper"], line=dict(width=0), showlegend=False, hoverinfo="skip"))
    fig.add_trace(go.Scatter(x=v.index, y=v["BBlower"], line=dict(width=0), fill="tonexty",
                             fillcolor="rgba(128,128,128,0.13)", name="Bollinger band", hoverinfo="skip"))
    if kind == "Candlestick":
        fig.add_trace(go.Candlestick(x=v.index, open=v["Open"], high=v["High"], low=v["Low"], close=v["Close"],
                                     name="Price", increasing_line_color=GOOD, decreasing_line_color=BAD))
        fig.update_layout(xaxis_rangeslider_visible=False)
    else:
        fig.add_trace(go.Scatter(x=v.index, y=v["Close"], name="Price", line=dict(color=BLUE, width=2),
                                 hovertemplate="₹%{y:,.2f}"))
    fig.add_trace(go.Scatter(x=v.index, y=v["SMA50"], name="50-day average", line=dict(color=ORANGE, width=1.5),
                             hovertemplate="₹%{y:,.2f}"))
    fig.add_trace(go.Scatter(x=v.index, y=v["SMA200"], name="200-day average", line=dict(color=AQUA, width=1.5),
                             hovertemplate="₹%{y:,.2f}"))
    if lv["supports"]:
        fig.add_hline(y=lv["supports"][0][0], line_dash="dot", line_color="gray",
                      annotation_text=f"Support ₹{lv['supports'][0][0]:,.0f}", annotation_position="bottom left")
    if lv["resistances"]:
        fig.add_hline(y=lv["resistances"][0][0], line_dash="dot", line_color="gray",
                      annotation_text=f"Resistance ₹{lv['resistances'][0][0]:,.0f}", annotation_position="top left")
    base_layout(fig, 440, "Price with moving averages (₹)")
    st.plotly_chart(fig, width="stretch")

    g1, g2 = st.columns(2)
    with g1:
        fig = go.Figure(go.Scatter(x=v.index, y=v["RSI"], line=dict(color=BLUE, width=2), name="RSI",
                                   hovertemplate="%{y:.1f}"))
        fig.add_hline(y=70, line_dash="dot", line_color="gray", annotation_text="Overbought (70)")
        fig.add_hline(y=30, line_dash="dot", line_color="gray", annotation_text="Oversold (30)",
                      annotation_position="bottom right")
        base_layout(fig, 280, "RSI (14)", legend=False)
        fig.update_yaxes(range=[0, 100])
        st.plotly_chart(fig, width="stretch")
    with g2:
        fig = go.Figure()
        fig.add_trace(go.Bar(x=v.index, y=v["MACDhist"], name="Gap", marker_color="rgba(128,128,128,0.45)",
                             hovertemplate="%{y:.2f}"))
        fig.add_trace(go.Scatter(x=v.index, y=v["MACD"], name="MACD", line=dict(color=BLUE, width=2),
                                 hovertemplate="%{y:.2f}"))
        fig.add_trace(go.Scatter(x=v.index, y=v["MACDsignal"], name="Signal line", line=dict(color=ORANGE, width=1.5),
                                 hovertemplate="%{y:.2f}"))
        base_layout(fig, 280, "MACD (12, 26, 9)")
        st.plotly_chart(fig, width="stretch")

    st.markdown("##### Indicator readings")
    st.dataframe(signals, hide_index=True, width="stretch")

    st.markdown("##### Support and resistance")
    st.caption("Support is a price where falls have tended to stop; resistance is where rises have tended to stall. "
               "Chart levels come from turning points in the last year; pivot levels come from the last trading day.")
    k1, k2 = st.columns(2)
    with k1:
        rows = ([{"Level": "Resistance", "Price": f"₹{z[0]:,.2f}", "Distance": (z[0] / r["price"] - 1) * 100, "Times tested": z[1]}
                 for z in reversed(lv["resistances"])] +
                [{"Level": "Support", "Price": f"₹{z[0]:,.2f}", "Distance": (z[0] / r["price"] - 1) * 100, "Times tested": z[1]}
                 for z in lv["supports"]])
        if rows:
            st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch", column_config={
                "Price": st.column_config.TextColumn("Chart level"),
                "Distance": st.column_config.NumberColumn("From current price", format="%+.1f%%")})
        else:
            st.write("No clear chart levels in the last year.")
    with k2:
        piv = pd.DataFrame([{"Level": k, "Price": f"₹{v_:,.2f}"} for k, v_ in reversed(lv["pivot"].items())])
        st.dataframe(piv, hide_index=True, width="stretch", column_config={
            "Level": st.column_config.TextColumn("Pivot level", help="R = resistance, S = support"),
            "Price": st.column_config.TextColumn("Price")})

    st.markdown("##### Returns and price behaviour")
    m = st.columns(4)
    for col, (lab, key) in zip(m, [("1 month", "ret_1m"), ("3 months", "ret_3m"), ("6 months", "ret_6m"), ("1 year", "ret_1y")]):
        col.metric(f"Return, {lab}", fmt(t[key], "{:+.1f}%"))
    m = st.columns(4)
    m[0].metric("Volatility (yearly)", fmt(t["volatility"], "{:.1f}%"))
    m[1].metric("Beta vs Nifty 50", fmt(t["beta"]))
    m[2].metric("Biggest fall in 1 year", fmt(t["max_drawdown"], "-{:.1f}%"))
    m[3].metric("Average daily range (ATR)", fmt(t["atr_pct"], "{:.1f}%"))

# ------------------------------------------------------------------ fundamentals


def bars(col, series, title, labels=None, unit_crore=True):
    vals = (series / 1e7).round(0) if unit_crore else series.round(2)
    labels = labels or [f"FY{x.year}" for x in series.index]
    fig = go.Figure(go.Bar(x=labels, y=vals, marker_color=BLUE, width=0.5,
                           text=[f"{x:,.0f}" if unit_crore else f"{x:,.2f}" for x in vals], textposition="outside",
                           hovertemplate=("₹%{y:,.0f} crore" if unit_crore else "₹%{y:,.2f}") + "<extra></extra>"))
    base_layout(fig, 290, title, legend=False)
    fig.update_layout(hovermode="closest")
    fig.update_yaxes(rangemode="tozero", showticklabels=False)
    fig.update_xaxes(type="category")
    col.plotly_chart(fig, width="stretch")


with tab_fa:
    if f["is_fund"]:
        st.write("Company financials do not apply to ETFs and funds.")
    else:
        st.markdown("##### Valuation")
        m = st.columns(4)
        m[0].metric("P/E", fmt(f["pe"], "{:.1f}"))
        m[1].metric("Forward P/E", fmt(f["forward_pe"], "{:.1f}"))
        m[2].metric("P/B", fmt(f["pb"]))
        m[3].metric("EV/EBITDA", fmt(f["ev_ebitda"], "{:.1f}"))
        m = st.columns(4)
        m[0].metric("Industry peers' median P/E", fmt(r["industry_pe"], "{:.1f}"))
        ph = r["pe_history"]
        m[1].metric(f"Own average P/E ({len(ph['by_year'])} years)" if ph else "Own average P/E",
                    fmt(ph["average"] if ph else None, "{:.1f}"),
                    help="Approximate: price at each financial year-end × today's share count ÷ that year's profit.")
        m[2].metric("PEG", fmt(f["peg"]))
        m[3].metric("Dividend yield", fmt(f["div_yield"], "{:.2f}%"))

        fv = r["fair_value"]
        if fv:
            st.markdown("##### Rough fair-value estimate")
            m = st.columns(4)
            for col, row in zip(m, fv["rows"]):
                col.metric(f"{row['case']} case", f"₹{row['value']:,.0f}", delta=f"{row['vs_price']:+.0f}% vs price")
            m[3].metric("Current price", f"₹{r['price']:,.2f}")
            with st.expander("How this is estimated"):
                st.markdown(
                    f"Earnings per share (₹{fv['eps']:,.2f}) are grown for {fv['years']} years, valued at an exit P/E, "
                    f"then discounted back at {fv['discount']}% a year (the return an investor would want).\n\n"
                    + "\n".join(f"- **{x['case']}**: growth {x['growth']:.0f}% a year, exit P/E {x['exit_pe']:.0f}"
                                for x in fv["rows"]) +
                    "\n\nGrowth is the average of past profit growth, past sales growth and analysts' expected growth, "
                    "capped at 20%. The exit P/E is the average of the industry median and the stock's own past average. "
                    "Small changes in these assumptions move the answer a lot, so read it as a range and not a target.")

        st.markdown("##### Profitability and growth")
        m = st.columns(4)
        m[0].metric("ROE", fmt(f["roe"], "{:.1f}%"))
        m[1].metric("ROA", fmt(f["roa"], "{:.1f}%"))
        m[2].metric("Operating margin", fmt(f["op_margin"], "{:.1f}%"))
        m[3].metric("Net profit margin", fmt(f["profit_margin"], "{:.1f}%"))
        m = st.columns(4)
        m[0].metric(f"Sales growth / year ({f['rev_cagr_years']}y)", fmt(f["rev_cagr"], "{:+.1f}%"))
        m[1].metric(f"Profit growth / year ({f['profit_cagr_years']}y)", fmt(f["profit_cagr"], "{:+.1f}%"))
        m[2].metric("Latest quarter sales, YoY", fmt(f["rev_growth_q"], "{:+.1f}%"))
        m[3].metric("Latest quarter profit, YoY", fmt(f["earn_growth_q"], "{:+.1f}%"))

        st.markdown("##### Financial strength")
        m = st.columns(4)
        m[0].metric("Market value", crore(f["market_cap"]))
        m[1].metric("Debt ÷ equity", fmt(f["debt_equity"]))
        m[2].metric("Interest cover", fmt(f["interest_cover"], "{:.1f}x"))
        m[3].metric("Current ratio", fmt(f["current_ratio"]))
        m = st.columns(4)
        m[0].metric("Total debt", crore(f["total_debt"]))
        m[1].metric("Cash", crore(f["total_cash"]))
        m[2].metric("Operating cash flow", crore(f["op_cashflow"]))
        m[3].metric("Free cash flow", crore(f["fcf"]))

        st.markdown("##### Ownership and analyst view")
        m = st.columns(4)
        m[0].metric("Promoters / insiders", fmt(f["promoter"], "{:.1f}%"))
        m[1].metric("Institutions", fmt(f["institutions"], "{:.1f}%"))
        m[2].metric("Analyst target price", fmt(f["target"], "₹{:,.0f}"),
                    delta=fmt(f["upside"], "{:+.1f}%") if f["upside"] is not None else None)
        rec = (f["recommendation"] or "").replace("_", " ").title()
        m[3].metric("Analyst consensus", rec if rec and rec != "None" else "Not available",
                    help=f"{int(f['analysts'])} analysts" if f["analysts"] else None)

        rev, prof = f["revenue_hist"], f["profit_hist"]
        if rev is not None or prof is not None:
            st.markdown("##### Yearly results (₹ crore)")
            g1, g2 = st.columns(2)
            if rev is not None:
                bars(g1, rev, "Sales")
            if prof is not None:
                bars(g2, prof, "Net profit")

        qr, qp = f["q_revenue"], f["q_profit"]
        if qr is not None and len(qr) >= 3:
            st.markdown("##### Quarterly results (₹ crore)")
            g1, g2 = st.columns(2)
            qlab = [x.strftime("%b %Y") for x in qr.index]
            bars(g1, qr, "Sales", qlab)
            if qp is not None:
                bars(g2, qp, "Net profit", [x.strftime("%b %Y") for x in qp.index])

        if r["dividends"] is not None:
            st.markdown("##### Dividends per share (₹)")
            g1, _ = st.columns(2)
            bars(g1, r["dividends"], "By financial year", list(r["dividends"].index), unit_crore=False)

        if f["summary"]:
            with st.expander("About the company"):
                st.write(f["summary"])

# ------------------------------------------------------------------ peers

with tab_peers:
    pl = r["peers"]
    if not pl:
        st.write("No peer list is available for this stock.")
    else:
        st.caption(f"Largest NSE-listed companies that Yahoo Finance places in the same industry ({f['industry']}). "
                   "For conglomerates the grouping can be a loose fit.")
        df = pd.DataFrame(pl)
        if r["ticker"] not in set(df["ticker"]):
            me = {"ticker": r["ticker"], "symbol": r["symbol"], "name": f["name"], "price": r["price"],
                  "market_cap": f["market_cap"], "pe": f["pe"], "forward_pe": f["forward_pe"], "pb": f["pb"],
                  "div_yield": f["div_yield"], "change_1y": t["ret_1y"]}
            df = pd.concat([pd.DataFrame([me]), df], ignore_index=True)
        df = df.head(10)
        df["Company"] = [("➤ " if tk == r["ticker"] else "") + n for tk, n in zip(df["ticker"], df["name"])]
        df["Market value (₹ cr)"] = df["market_cap"] / 1e7
        table = df[["Company", "symbol", "price", "Market value (₹ cr)", "pe", "pb", "div_yield", "change_1y"]].rename(
            columns={"symbol": "Symbol", "price": "Price (₹)", "pe": "P/E", "pb": "P/B",
                     "div_yield": "Dividend yield", "change_1y": "1-year return"})
        cfg = {"Price (₹)": st.column_config.NumberColumn(format="₹%.2f"),
               "Market value (₹ cr)": st.column_config.NumberColumn(format="localized"),
               "P/E": st.column_config.NumberColumn(format="%.1f"),
               "P/B": st.column_config.NumberColumn(format="%.2f"),
               "Dividend yield": st.column_config.NumberColumn(format="%.2f%%"),
               "1-year return": st.column_config.NumberColumn(format="%+.1f%%")}

        if st.toggle("Also score each peer (takes up to a minute)"):
            scores = {}
            with st.spinner("Scoring peers…"):
                for sym in df["ticker"].head(6):
                    try:
                        pr = ui.run(sym, True)
                        scores[sym[:-3]] = (pr["valuation"].score(), pr["growth"].score(), pr["risk"].score())
                    except Exception:
                        pass
            for i, name in enumerate(["Valuation", "Growth", "Risk"]):
                table[name] = [scores.get(s, (None, None, None))[i] for s in table["Symbol"]]
            cfg.update({k: ui.SCORE_COLUMNS[k] for k in ("Valuation", "Growth", "Risk")})
            st.caption("Scores are shown for the six largest companies in the list.")
        table["Market value (₹ cr)"] = table["Market value (₹ cr)"].round(0)
        st.dataframe(table, hide_index=True, width="stretch", column_config=cfg)
        if r["industry_pe"]:
            st.markdown(f"Median P/E of these peers: **{r['industry_pe']:.1f}**. "
                        f"This stock: **{fmt(f['pe'], '{:.1f}')}**.")

# ------------------------------------------------------------------ past returns

with tab_ret:
    c1, _ = st.columns([1, 3])
    amount = c1.number_input("Amount invested (₹)", min_value=1000, value=100000, step=10000)
    rows = a.past_returns(d, r["bench"], amount)
    if not rows:
        st.write("Not enough price history yet.")
    else:
        tbl = pd.DataFrame([{
            "Invested": f"{x['years']} year{'s' if x['years'] > 1 else ''} ago",
            "This stock": f"₹{x['stock']:,.0f}",
            "Nifty 50": "Not available" if x["nifty"] is None else f"₹{x['nifty']:,.0f}",
            "Fixed deposit at 7%": f"₹{x['fd']:,.0f}",
            "Stock return per year": x["stock_cagr"]} for x in rows])
        st.dataframe(tbl, hide_index=True, width="stretch", column_config={
            "Stock return per year": st.column_config.NumberColumn(format="%+.1f%%")})
        st.caption(f"What ₹{amount:,.0f} would be worth today. The stock figure includes dividends; "
                   "the Nifty 50 figure does not; taxes and costs are ignored.")
        yrs = st.radio("Chart", [f"{x['years']} year{'s' if x['years'] > 1 else ''}" for x in rows],
                       index=len(rows) - 1, horizontal=True, label_visibility="collapsed")
        curves = a.growth_curves(d, r["bench"], amount, int(yrs.split()[0]))
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=curves.index, y=curves["Stock"], name=r["symbol"], line=dict(color=BLUE, width=2),
                                 hovertemplate="₹%{y:,.0f}"))
        if "Nifty 50" in curves:
            fig.add_trace(go.Scatter(x=curves.index, y=curves["Nifty 50"], name="Nifty 50",
                                     line=dict(color=ORANGE, width=1.5), hovertemplate="₹%{y:,.0f}"))
        base_layout(fig, 360, f"Value of ₹{amount:,.0f} over time")
        st.plotly_chart(fig, width="stretch")

# ------------------------------------------------------------------ news and events

with tab_news:
    today = dt.date.today()
    ev = f["events"]
    lines = []
    for d_ in ev.get("Earnings Date") or []:
        if isinstance(d_, dt.date) and d_ >= today:
            lines.append(f"- Next results expected: **{d_:%d %b %Y}**")
    xd = ev.get("Ex-Dividend Date")
    if isinstance(xd, dt.date) and xd >= today:
        lines.append(f"- Next ex-dividend date: **{xd:%d %b %Y}**")
    for when, ratio in r["splits"][-3:]:
        lines.append(f"- Split or bonus on {when}: each share became {ratio:g}")
    st.markdown("##### Events")
    st.markdown("\n".join(lines) if lines else "No upcoming events listed.")

    st.markdown("##### Recent headlines")
    if r["news"]:
        for n in r["news"]:
            when = f" · {n['date']:%d %b %Y}" if pd.notna(n["date"]) else ""
            st.markdown(f"- [{n['title']}]({n['url']})  \n  <span class='muted'>{n['source']}{when}</span>",
                        unsafe_allow_html=True)
    else:
        st.write("No recent headlines found for this stock.")
