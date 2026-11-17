"""Top 20 page: the best overall scores among large and mid-size companies, refreshed once a month."""

import datetime as dt

import pandas as pd
import streamlit as st

import ui

st.title("Top 20 stocks")
data = ui.monthly_scores()
if not data or not data.get("rows"):
    st.info("The monthly list has not been generated yet. It is created automatically on the 1st of each month.")
    st.stop()

updated = dt.date.fromisoformat(data["updated"])
next_run = (updated.replace(day=1) + dt.timedelta(days=32)).replace(day=1)
st.markdown(f"**Last updated: {updated:%d %B %Y}** · next update {next_run:%d %B %Y}")
st.caption(f"The 20 highest overall scores among NSE companies worth more than ₹{data['min_cap_crore']:,} crore. "
           "Overall = average of Valuation, Growth and (100 − Risk). Scores and prices are as of the update date.")

rows = [r for r in data["rows"] if r.get("Coverage", 1) >= 0.7]
df = pd.DataFrame(rows[:20])
df.insert(0, "Rank", range(1, len(df) + 1))
show = df[["Rank", "Company", "Symbol", "Industry", "Overall", "Valuation", "Growth", "Risk", "Price (₹)",
           "Market value (₹ cr)"]]
event = st.dataframe(show, hide_index=True, width="stretch", height=35 * (len(show) + 1) + 3,
                     column_config={**ui.COMPACT_COLUMNS, "Rank": st.column_config.NumberColumn(width="small")},
                     on_select="rerun", selection_mode="single-row", key="top20_table")
if event.selection.rows:
    sym = show.iloc[event.selection.rows[0]]["Symbol"]
    if st.button(f"Open {sym} checkup", type="primary"):
        st.session_state["symbol"] = sym
        st.switch_page("views/checkup.py")
else:
    st.caption("Tick a row to open that stock's full, live checkup.")

st.caption(f"{len(data['rows']):,} companies were scored. A high score means the numbers look good by this site's "
           "fixed rules on the update date; it is a list to research further, not a list to buy.")
