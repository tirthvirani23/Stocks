"""Portfolio Builder: pick industries, get the best-scored stocks in each as a sample portfolio."""

import pandas as pd
import streamlit as st

import ui

# What the user sees -> the Yahoo Finance industries behind it
CATEGORIES = {
    "Banks": ["Banks—Regional"],
    "NBFCs and lending": ["Credit Services"],
    "Insurance": ["Insurance—Life"],
    "Brokers and capital markets": ["Capital Markets"],
    "IT services": ["Information Technology Services"],
    "Pharma": ["Drug Manufacturers—Specialty & Generic"],
    "Hospitals": ["Medical Care Facilities"],
    "Automobiles": ["Auto Manufacturers"],
    "Auto parts": ["Auto Parts"],
    "Packaged foods": ["Packaged Foods"],
    "Personal and home care": ["Household & Personal Products"],
    "Consumer durables": ["Furnishings, Fixtures & Appliances", "Consumer Electronics"],
    "Jewellery and luxury": ["Luxury Goods"],
    "Hotels": ["Lodging"],
    "Oil and gas": ["Oil & Gas Refining & Marketing"],
    "Power": ["Utilities—Regulated Electric", "Utilities—Independent Power Producers", "Utilities—Renewable"],
    "Metals": ["Steel", "Aluminum", "Other Industrial Metals & Mining"],
    "Cement and building materials": ["Building Materials"],
    "Chemicals": ["Specialty Chemicals", "Chemicals"],
    "Infrastructure and construction": ["Engineering & Construction"],
    "Capital goods": ["Specialty Industrial Machinery", "Electrical Equipment & Parts"],
    "Defence": ["Aerospace & Defense"],
    "Telecom": ["Telecom Services"],
    "Real estate": ["Real Estate—Development"],
}
DEFAULT = {"Banks", "IT services", "Pharma"}
PER_CATEGORY = 3

st.title("Portfolio Builder")
st.caption("Tick the industries you want. The builder scores the companies in each one and picks the "
           f"{PER_CATEGORY} with the best overall score to form a sample portfolio.")

with st.form("builder", border=False):
    st.markdown("**Industries**")
    cols = st.columns(4)
    ticked = [name for i, name in enumerate(CATEGORIES)
              if cols[i % 4].checkbox(name, value=name in DEFAULT, key=f"cat_{name}")]
    c1, c2, c3 = st.columns([2, 3, 1.3], vertical_alignment="bottom")
    amount = c1.number_input("Amount to invest (₹)", min_value=10000, value=100000, step=10000)
    size = c2.radio("Company size", ["Large and mid-size only (above ₹5,000 crore)", "All sizes"], horizontal=True)
    go = c3.form_submit_button("Build portfolio", type="primary", width="stretch")

if go:
    st.session_state["builder_request"] = (tuple(ticked), amount, size)
if "builder_request" not in st.session_state:
    st.info("Choose your industries and press Build portfolio. Scoring an industry for the first time takes "
            "up to a minute; after that it is quick.")
    st.stop()

ticked, amount, size = st.session_state["builder_request"]
if not ticked:
    st.warning("Tick at least one industry.")
    st.stop()
min_cap = 5000 if size.startswith("Large") else 0

picks, failed = [], []
bar = st.progress(0.0, text="Scoring…")
for n, cat in enumerate(ticked):
    bar.progress(n / len(ticked), text=f"Scoring {cat}…")
    rows = []
    for industry in CATEGORIES[cat]:
        try:
            rows += ui.industry_scores(industry, ui.BUILDER_LIMIT)[0]
        except Exception:
            pass
    rows = [x for x in rows if (x["Market value (₹ cr)"] or 0) >= min_cap]
    best = sorted(rows, key=lambda x: (-x["Overall"], x["Risk"]))[:PER_CATEGORY]
    if best:
        picks += [{"Industry": cat, **x} for x in best]
    else:
        failed.append(cat)
bar.empty()

if failed:
    st.warning("No stocks could be scored for: " + ", ".join(failed) + ". Try again in a minute.")
if not picks:
    st.stop()

df = pd.DataFrame(picks)
each = amount / len(df)
df["Shares"] = (each // df["Price (₹)"]).astype(int)
df["Amount (₹)"] = df["Shares"] * df["Price (₹)"]
invested = df["Amount (₹)"].sum()

st.markdown("##### Sample portfolio")
m = st.columns(5)
m[0].metric("Stocks", len(df))
m[1].metric("Average overall score", f"{df['Overall'].mean():.0f}")
m[2].metric("Average valuation", f"{df['Valuation'].mean():.0f}")
m[3].metric("Average growth", f"{df['Growth'].mean():.0f}")
m[4].metric("Average risk", f"{df['Risk'].mean():.0f}", help="Higher = riskier")

show = df[["Industry", "Company", "Symbol", "Overall", "Valuation", "Growth", "Risk", "Price (₹)", "Shares", "Amount (₹)"]]
event = st.dataframe(show, hide_index=True, width="stretch", height=35 * (len(show) + 1) + 3,
                     column_config={**ui.COMPACT_COLUMNS, "Amount (₹)": st.column_config.NumberColumn(format="₹%.0f")},
                     on_select="rerun", selection_mode="single-row", key="builder_table")
if event.selection.rows:
    sym = show.iloc[event.selection.rows[0]]["Symbol"]
    if st.button(f"Open {sym} checkup", type="primary"):
        st.session_state["symbol"] = sym
        st.switch_page("views/checkup.py")

st.markdown(f"Money is split equally: about **₹{each:,.0f}** per stock, rounded down to whole shares. "
            f"Invested **₹{invested:,.0f}** of ₹{amount:,.0f}; **₹{amount - invested:,.0f}** stays as cash.")
if (df["Shares"] == 0).any():
    st.caption("Some stocks show 0 shares because one share costs more than the amount set aside for it. "
               "Increase the amount or tick fewer industries.")
st.caption("Overall = average of Valuation, Growth and (100 − Risk). The best three are chosen from the "
           f"{ui.BUILDER_LIMIT} largest companies in each industry group. This is a sample built by fixed rules, "
           "not a recommendation: it ignores your goals, existing holdings and tax position.")
