"""Watchlist page: your saved stocks and their scores in one table."""

import pandas as pd
import streamlit as st

import ui

st.title("Watchlist")
watch = ui.watchlist()

with st.form("add", border=False, clear_on_submit=True):
    c1, c2 = st.columns([5, 1], vertical_alignment="bottom")
    new = c1.text_input("Add a stock", placeholder="e.g. TCS, HDFCBANK, ITC")
    if c2.form_submit_button("Add", type="primary", width="stretch") and new.strip():
        for q in new.split(","):
            r = ui.load(q, light=True) if q.strip() else None
            if r is not None and r["symbol"] not in watch:
                watch.append(r["symbol"])

st.query_params["list"] = ",".join(watch)

if not watch:
    st.info("Your watchlist is empty. Add a symbol above, or press “Add to watchlist” on the Checkup page. "
            "Each stock will appear here with its price and three scores.")
    st.stop()

rows = []
with st.spinner("Updating your watchlist…"):
    for sym in watch:
        r = ui.load(sym, light=True)
        if r is not None:
            rows.append(ui.summary_row(r))

if rows:
    df = pd.DataFrame(rows)
    event = st.dataframe(df, hide_index=True, width="stretch", column_config=ui.SCORE_COLUMNS,
                         on_select="rerun", selection_mode="single-row", key="watch_table")
    picked = event.selection.rows
    if picked:
        sym = df.iloc[picked[0]]["Symbol"]
        b1, b2, _ = st.columns([1.5, 1.5, 4])
        if b1.button(f"Open {sym} checkup", type="primary", width="stretch"):
            st.session_state["symbol"] = sym
            st.switch_page("views/checkup.py")
        if b2.button(f"Remove {sym}", width="stretch"):
            watch.remove(sym)
            st.rerun()
    else:
        st.caption("Tick a row to open its full checkup or remove it. Click a column heading to sort.")

st.caption("To keep this list, bookmark this page: the list is saved in the page address, not in an account.")
