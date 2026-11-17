"""Indian Stock Checkup: entry point. Each page lives in the views/ folder."""

import streamlit as st

import ui

st.set_page_config(page_title="Indian Stock Checkup", page_icon="📈", layout="wide")
ui.style()

page = st.navigation(
    {
        "Stocks": [
            st.Page("views/checkup.py", title="Checkup", icon=":material/search:", default=True),
            st.Page("views/compare.py", title="Compare", icon=":material/compare_arrows:", url_path="compare"),
            st.Page("views/top20.py", title="Top 20", icon=":material/leaderboard:", url_path="top-20"),
            st.Page("views/watchlist.py", title="Watchlist", icon=":material/star:", url_path="watchlist"),
        ],
        "Portfolio": [
            st.Page("views/review.py", title="Portfolio Review", icon=":material/fact_check:", url_path="portfolio-review"),
            st.Page("views/builder.py", title="Portfolio Builder", icon=":material/pie_chart:", url_path="portfolio-builder"),
        ],
    },
    position="top",
)
page.run()

st.divider()
st.caption("Data source: Yahoo Finance. Some figures can be missing or out of date, especially for smaller companies. "
           "The scores follow fixed rules shown on the Checkup page and do not know about news, management quality "
           "or sector cycles. This is an educational tool and not investment advice.")
