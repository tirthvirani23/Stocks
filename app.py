"""Indian Stock Checkup: type an NSE/BSE symbol, get price, FA, TA and three scores."""

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import analysis as a

st.set_page_config(page_title="Indian Stock Checkup", page_icon="📈", layout="wide")

BLUE, ORANGE, AQUA = "#2a78d6", "#eb6834", "#1baf7a"
GOOD, WARN, BAD = "#1a9d6c", "#d48a00", "#d8433f"
GRID = "rgba(128,128,128,0.18)"

st.markdown(
    """
<style>
.block-container {padding-top: 2.2rem; max-width: 1150px;}
.score-card {border: 1px solid rgba(128,128,128,0.3); border-radius: 10px; padding: 16px 18px; height: 100%;}
.score-title {font-size: 0.8rem; letter-spacing: 0.06em; text-transform: uppercase; opacity: 0.75;}
.score-num {font-size: 2.7rem; font-weight: 700; line-height: 1.15; font-variant-numeric: tabular-nums;}
.score-num small {font-size: 1rem; font-weight: 400; opacity: 0.6;}
.score-bar {height: 8px; border-radius: 4px; background: rgba(128,128,128,0.22); margin: 8px 0 10px;}
.score-bar div {height: 8px; border-radius: 4px;}
.score-pill {display: inline-block; padding: 2px 10px; border-radius: 999px; color: #fff; font-size: 0.82rem; font-weight: 600;}
.score-note {font-size: 0.85rem; opacity: 0.8; margin-top: 8px;}
.price-big {font-size: 2.4rem; font-weight: 700; font-variant-numeric: tabular-nums; line-height: 1.1;}
.muted {opacity: 0.7; font-size: 0.88rem;}
</style>
""",
    unsafe_allow_html=True,
)


@st.cache_data(ttl=600, show_spinner=False)
def run(query: str):
    return a.analyse(query)


def crore(x):
    if x is None:
        return "Not available"
    return f"₹{x / 1e7:,.0f} cr"


def fmt(x, pattern="{:.2f}"):
    return "Not available" if x is None else pattern.format(x)


def score_card(title, score, higher_is_better, labels, note, coverage):
    if score is None:
        st.markdown(f'<div class="score-card"><div class="score-title">{title}</div>'
                    '<div class="score-note">Not enough data to score.</div></div>', unsafe_allow_html=True)
        return
    goodness = score if higher_is_better else 100 - score
    colour = GOOD if goodness >= 60 else (WARN if goodness >= 40 else BAD)
    label = labels[0] if score < 40 else (labels[1] if score < 60 else labels[2])
    low_data = "" if coverage >= 0.7 else " Some data was missing, so treat this score with extra caution."
    st.markdown(
        f"""<div class="score-card">
<div class="score-title">{title}</div>
<div class="score-num">{score}<small> / 100</small></div>
<div class="score-bar"><div style="width:{score}%; background:{colour};"></div></div>
<span class="score-pill" style="background:{colour};">{label}</span>
<div class="score-note">{note}{low_data}</div>
</div>""",
        unsafe_allow_html=True,
    )


def breakdown(card: a.Scorecard, points_label):
    df = pd.DataFrame(card.items)
    used = df["Points"].notna()
    total_w = df.loc[used, "Weight"].sum()
    df["Share of score"] = (df["Weight"] / total_w * 100).where(used)
    df = df.rename(columns={"Points": points_label})
    st.dataframe(
        df[["Type", "Metric", "Value", points_label, "Share of score", "Comment"]],
        hide_index=True,
        width="stretch",
        column_config={
            "Type": st.column_config.TextColumn(width="small", help="FA = fundamental analysis, TA = technical analysis"),
            points_label: st.column_config.ProgressColumn(min_value=0, max_value=100, format="%d"),
            "Share of score": st.column_config.NumberColumn(format="%.0f%%", help="How much this metric counts towards the score"),
        },
    )


def base_layout(fig, height, title=None):
    fig.update_layout(
        height=height, margin=dict(l=10, r=10, t=40 if title else 10, b=10), title=title,
        hovermode="x unified", legend=dict(orientation="h", yanchor="top", y=-0.12, x=0),
        xaxis=dict(gridcolor=GRID), yaxis=dict(gridcolor=GRID),
    )
    return fig


# ------------------------------------------------------------------ header

st.title("Indian Stock Checkup")
st.caption("Type an NSE or BSE stock symbol to see its price, fundamental and technical analysis, "
           "and scores out of 100 for valuation, growth potential and risk.")

with st.form("search"):
    c1, c2 = st.columns([5, 1], vertical_alignment="bottom")
    query = c1.text_input("Stock symbol or company name", value="RELIANCE",
                          placeholder="e.g. RELIANCE, TCS, HDFCBANK, INFY", key="symbol")
    c2.form_submit_button("Analyse", type="primary", width="stretch")

if not query.strip():
    st.info("Type a stock symbol above, for example RELIANCE, TCS or HDFCBANK.")
    st.stop()

try:
    with st.spinner(f"Fetching data and analysing {query.strip().upper()}…"):
        r = run(query.strip())
except ValueError as e:
    st.error(str(e))
    st.stop()
except Exception:
    st.error("The market data service did not respond. Wait a minute and press Analyse again.")
    st.stop()

f, t, d = r["f"], r["t"], r["hist"]

# ------------------------------------------------------------------ price

st.divider()
left, right = st.columns([3, 2], vertical_alignment="bottom")
with left:
    st.subheader(f"{f['name'] or r['symbol']}")
    st.markdown(f'<span class="muted">{r["exchange"]}: {r["symbol"]}'
                f'{" · " + f["sector"] if f["sector"] else ""}'
                f'{" · " + f["industry"] if f["industry"] else ""}</span>', unsafe_allow_html=True)
with right:
    ch = r["change_pct"]
    colour = GOOD if (ch or 0) >= 0 else BAD
    arrow = "▲" if (ch or 0) >= 0 else "▼"
    change_txt = (f'<span style="color:{colour}; font-weight:600;">{arrow} '
                  f'₹{abs(r["price"] - r["prev_close"]):,.2f} ({ch:+.2f}%)</span>') if ch is not None else ""
    st.markdown(f'<div class="price-big">₹{r["price"]:,.2f}</div>{change_txt}'
                f'<div class="muted">Last traded price, as of {r["last_date"]:%d %b %Y}. '
                'May be delayed by about 15 minutes.</div>', unsafe_allow_html=True)

# ------------------------------------------------------------------ scores

st.markdown("#### Scores")
val, gro, risk = r["valuation"], r["growth"], r["risk"]
s1, s2, s3 = st.columns(3)
with s1:
    score_card("Valuation", val.score(), True, ["Expensive", "Fairly priced", "Attractively priced"],
               "Higher is better: a high score means the price is low compared with profits, assets and growth.",
               val.coverage())
with s2:
    score_card("Growth potential", gro.score(), True, ["Weak growth", "Moderate growth", "Strong growth"],
               "Higher is better: based on sales and profit growth, return on equity and price trend.",
               gro.coverage())
with s3:
    score_card("Risk", risk.score(), False, ["Low risk", "Moderate risk", "High risk"],
               "Higher means riskier: based on price swings, debt, company size and profit stability.",
               risk.coverage())

if f["is_financial"]:
    st.info("This is a bank or financial company. Debt ratios, current ratio and EV/EBITDA do not apply "
            "to lenders, so they are left out of the scores and P/B counts for more.")

# ------------------------------------------------------------------ tabs

tab_scores, tab_ta, tab_fa = st.tabs(["How the scores were calculated", "Technical analysis (TA)", "Fundamental analysis (FA)"])

with tab_scores:
    st.markdown("Each metric earns points out of 100. The score is the weighted average of the metrics that have data. "
                "**FA** rows come from the company's financials, **TA** rows from its price chart.")
    st.markdown(f"##### Valuation: {val.score()} / 100")
    breakdown(val, "Points (higher = cheaper)")
    st.markdown(f"##### Growth potential: {gro.score()} / 100")
    breakdown(gro, "Points (higher = stronger)")
    st.markdown(f"##### Risk: {risk.score()} / 100")
    breakdown(risk, "Risk points (higher = riskier)")

with tab_ta:
    signals = pd.DataFrame(r["signals"])
    counts = signals["Signal"].value_counts()
    st.markdown(f"**Signal count:** {counts.get('Bullish', 0)} bullish · {counts.get('Bearish', 0)} bearish · "
                f"{counts.get('Caution', 0)} caution · {counts.get('Neutral', 0)} neutral")

    period = st.radio("Chart period", ["6 months", "1 year", "2 years"], index=1, horizontal=True)
    n = {"6 months": 126, "1 year": 252, "2 years": len(d)}[period]
    v = d.tail(n)

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=v.index, y=v["BBupper"], line=dict(width=0), showlegend=False, hoverinfo="skip"))
    fig.add_trace(go.Scatter(x=v.index, y=v["BBlower"], line=dict(width=0), fill="tonexty",
                             fillcolor="rgba(128,128,128,0.13)", name="Bollinger band", hoverinfo="skip"))
    fig.add_trace(go.Scatter(x=v.index, y=v["Close"], name="Price", line=dict(color=BLUE, width=2),
                             hovertemplate="₹%{y:,.2f}"))
    fig.add_trace(go.Scatter(x=v.index, y=v["SMA50"], name="50-day average", line=dict(color=ORANGE, width=1.5),
                             hovertemplate="₹%{y:,.2f}"))
    fig.add_trace(go.Scatter(x=v.index, y=v["SMA200"], name="200-day average", line=dict(color=AQUA, width=1.5),
                             hovertemplate="₹%{y:,.2f}"))
    base_layout(fig, 420, "Price with moving averages (₹)")
    st.plotly_chart(fig, width="stretch")

    g1, g2 = st.columns(2)
    with g1:
        fig = go.Figure(go.Scatter(x=v.index, y=v["RSI"], line=dict(color=BLUE, width=2), name="RSI",
                                   hovertemplate="%{y:.1f}"))
        fig.add_hline(y=70, line_dash="dot", line_color="gray", annotation_text="Overbought (70)")
        fig.add_hline(y=30, line_dash="dot", line_color="gray", annotation_text="Oversold (30)")
        base_layout(fig, 280, "RSI (14)")
        fig.update_yaxes(range=[0, 100])
        fig.update_layout(showlegend=False)
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

    st.markdown("##### Returns and price behaviour")
    m = st.columns(4)
    for col, (label, key) in zip(m, [("1 month", "ret_1m"), ("3 months", "ret_3m"), ("6 months", "ret_6m"), ("1 year", "ret_1y")]):
        col.metric(f"Return, {label}", fmt(t[key], "{:+.1f}%"))
    m = st.columns(4)
    m[0].metric("Volatility (yearly)", fmt(t["volatility"], "{:.1f}%"))
    m[1].metric("Beta vs Nifty 50", fmt(t["beta"]))
    m[2].metric("Biggest fall in 1 year", fmt(t["max_drawdown"], "-{:.1f}%"))
    m[3].metric("Average daily range (ATR)", fmt(t["atr_pct"], "{:.1f}%"))

with tab_fa:
    st.markdown("##### Valuation ratios")
    m = st.columns(4)
    m[0].metric("P/E", fmt(f["pe"], "{:.1f}"))
    m[1].metric("Forward P/E", fmt(f["forward_pe"], "{:.1f}"))
    m[2].metric("P/B", fmt(f["pb"]))
    m[3].metric("EV/EBITDA", fmt(f["ev_ebitda"], "{:.1f}"))
    m = st.columns(4)
    m[0].metric("PEG", fmt(f["peg"]))
    m[1].metric("EPS (last 12 months)", fmt(f["eps"], "₹{:,.2f}"))
    m[2].metric("Book value per share", fmt(f["book_value"], "₹{:,.2f}"))
    m[3].metric("Dividend yield", fmt(f["div_yield"], "{:.2f}%"))

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
        for col, series, title in [(g1, rev, "Sales"), (g2, prof, "Net profit")]:
            if series is None:
                continue
            labels = [f"FY{x.year}" for x in series.index]
            vals = (series / 1e7).round(0)
            fig = go.Figure(go.Bar(x=labels, y=vals, marker_color=BLUE, width=0.5,
                                   text=[f"{x:,.0f}" for x in vals], textposition="outside",
                                   hovertemplate="₹%{y:,.0f} crore<extra></extra>"))
            base_layout(fig, 300, title)
            fig.update_layout(hovermode="closest")
            fig.update_yaxes(rangemode="tozero")
            col.plotly_chart(fig, width="stretch")

    if f["summary"]:
        with st.expander("About the company"):
            st.write(f["summary"])

st.divider()
st.caption("Data source: Yahoo Finance. Some figures can be missing or out of date, especially for smaller companies. "
           "The scores follow fixed rules shown above and do not know about news, management quality or sector cycles. "
           "This is an educational tool and not investment advice.")
