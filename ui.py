"""Shared look, cached data loading and small display helpers."""

import pandas as pd
import streamlit as st

import analysis as a

BLUE, ORANGE, AQUA = "#2a78d6", "#eb6834", "#1baf7a"
GOOD, WARN, BAD = "#1a9d6c", "#d48a00", "#d8433f"
GRID = "rgba(128,128,128,0.18)"


def style():
    st.markdown(
        """
<style>
.block-container {padding-top: 3.6rem; max-width: 1150px;}
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
.headline {font-size: 1.1rem; font-weight: 600; margin: 4px 0 2px;}
</style>
""",
        unsafe_allow_html=True,
    )


# ------------------------------------------------------------------ data (cached)

@st.cache_data(ttl=3600, show_spinner=False)
def nifty():
    try:
        return a._history(a.NIFTY)
    except Exception:
        return None


@st.cache_data(ttl=6 * 3600, show_spinner=False)
def peers(industry):
    return a.peers(industry)


INDUSTRY_LIMIT = 100   # Checkup page: how many of an industry's largest stocks are scored
BUILDER_LIMIT = 40     # Portfolio Builder: per Yahoo industry


@st.cache_data(ttl=12 * 3600, show_spinner=False)
def industry_scores(industry, limit=INDUSTRY_LIMIT):
    """Scores for the largest NSE stocks in an industry. Returns (rows, number of stocks in the list)."""
    universe = a.peers(industry, size=limit)
    rows = a.score_industry(universe, nifty(), peers(industry))
    if len(rows) < max(1, len(universe) // 2):
        raise RuntimeError("too few stocks could be scored")  # do not keep a half-empty result
    return rows, len(universe)


@st.cache_data(ttl=600, show_spinner=False)
def run(query: str, light: bool = False):
    return a.analyse(query, bench=nifty(), peers_fn=peers, light=light)


def load(query: str, light: bool = False):
    """Analyse a stock, showing a friendly message instead of a crash. Returns None on failure."""
    try:
        return run(query.strip(), light)
    except ValueError as e:
        st.error(str(e))
    except Exception:
        st.error(f"The market data service did not respond for {query.strip().upper()}. "
                 "Wait a minute and try again.")
    return None


# ------------------------------------------------------------------ formatting

def crore(x):
    return "Not available" if x is None else f"₹{x / 1e7:,.0f} cr"


def fmt(x, pattern="{:.2f}"):
    return "Not available" if x is None else pattern.format(x)


def score_colour(score, higher_is_better=True):
    goodness = score if higher_is_better else 100 - score
    return GOOD if goodness >= 60 else (WARN if goodness >= 40 else BAD)


def score_card(title, kind, card, note):
    score = card.score()
    if score is None:
        st.markdown(f'<div class="score-card"><div class="score-title">{title}</div>'
                    '<div class="score-note">Not scored for this kind of security.</div></div>',
                    unsafe_allow_html=True)
        return
    colour = score_colour(score, kind != "risk")
    low_data = "" if card.coverage() >= 0.7 else " Some data was missing, so treat this score with extra caution."
    st.markdown(
        f"""<div class="score-card">
<div class="score-title">{title}</div>
<div class="score-num">{score}<small> / 100</small></div>
<div class="score-bar"><div style="width:{score}%; background:{colour};"></div></div>
<span class="score-pill" style="background:{colour};">{a.label(kind, score)}</span>
<div class="score-note">{note}{low_data}</div>
</div>""",
        unsafe_allow_html=True,
    )


def base_layout(fig, height, title=None, legend=True):
    fig.update_layout(
        height=height, margin=dict(l=10, r=10, t=40 if title else 10, b=10), title=title,
        hovermode="x unified", showlegend=legend,
        legend=dict(orientation="h", yanchor="top", y=-0.12, x=0),
        xaxis=dict(gridcolor=GRID), yaxis=dict(gridcolor=GRID),
    )
    return fig


def watchlist() -> list:
    """The saved list lives in the session and, on the Watchlist page, in the page address."""
    if "watch" not in st.session_state:
        raw = st.query_params.get("list", "")
        st.session_state["watch"] = [s for s in dict.fromkeys(x.strip().upper() for x in raw.split(",")) if s][:30]
    return st.session_state["watch"]


def summary_row(r) -> dict:
    """One line per stock, used by the Watchlist and Compare pages."""
    f, t = r["f"], r["t"]
    return {
        "Symbol": r["symbol"],
        "Company": f["name"] or r["symbol"],
        "Price (₹)": r["price"],
        "Day change": r["change_pct"],
        "Valuation": r["valuation"].score(),
        "Growth": r["growth"].score(),
        "Risk": r["risk"].score(),
        "1-year return": t["ret_1y"],
    }


SCORE_COLUMNS = {
    "Price (₹)": st.column_config.NumberColumn(format="₹%.2f"),
    "Day change": st.column_config.NumberColumn(format="%+.2f%%"),
    "1-year return": st.column_config.NumberColumn(format="%+.1f%%"),
    "Overall": st.column_config.ProgressColumn(min_value=0, max_value=100, format="%d",
                                               help="Average of Valuation, Growth and (100 − Risk). Higher = better"),
    "Market value (₹ cr)": st.column_config.NumberColumn(format="localized"),
    "Valuation": st.column_config.ProgressColumn(min_value=0, max_value=100, format="%d", help="Higher = cheaper"),
    "Growth": st.column_config.ProgressColumn(min_value=0, max_value=100, format="%d", help="Higher = stronger"),
    "Risk": st.column_config.ProgressColumn(min_value=0, max_value=100, format="%d", help="Higher = riskier"),
}

# Narrow version for wide tables: a bar for Overall, plain numbers for the three scores
COMPACT_COLUMNS = {
    **SCORE_COLUMNS,
    "Valuation": st.column_config.NumberColumn(help="Out of 100. Higher = cheaper"),
    "Growth": st.column_config.NumberColumn(help="Out of 100. Higher = stronger"),
    "Risk": st.column_config.NumberColumn(help="Out of 100. Higher = riskier"),
}
