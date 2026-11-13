# Indian Stock Checkup

A small website for checking Indian stocks (NSE / BSE). Three pages, switched from the bar at the top:

**Checkup**: type a symbol (for example `RELIANCE`, `TCS`, `HDFCBANK`) or a company name and get
- the latest price and a one-line summary with the main strengths and concerns
- three scores out of 100: **Valuation** (higher = cheaper), **Growth potential** (higher = stronger), **Risk** (higher = riskier)
- Score details: every metric behind each score
- Technical: line or candlestick chart up to 10 years, moving averages, RSI, MACD, Bollinger bands, support and resistance
- Fundamentals: ratios, rough fair-value range, yearly and quarterly results, dividends
- Peers: the largest companies in the same industry
- Past returns: what an investment made 1, 3, 5 or 10 years ago would be worth, against the Nifty 50 and a fixed deposit
- News and events: next results date, ex-dividend date, splits and bonuses, headlines
- buttons to add the stock to your watchlist and to download a PDF summary

**Compare**: two or three stocks side by side.

**Watchlist**: your saved stocks with price and scores in one table. Bookmark the page to keep the list (it is stored in the page address).

Data comes from Yahoo Finance. This is an educational tool, not investment advice.

## Put it online for free (no coding, about 5 minutes)

1. Open https://share.streamlit.io and choose **Continue with GitHub**. Sign in with the GitHub account that owns this repository and allow access.
2. Click **Create app**, then **Deploy a public app from GitHub**.
3. Fill in:
   - **Repository**: `tirthvirani23/Stocks`
   - **Branch**: the branch that contains `app.py`
   - **Main file path**: `app.py`
4. Click **Deploy**. After two or three minutes you get a web link.

Once deployed, the site updates itself within a few minutes whenever this repository changes. The link stays the same.

## Run it on your own computer instead

Install Python 3.10 or newer, then in this folder:

```
pip install -r requirements.txt
streamlit run app.py
```

## Files

- `app.py`: start-up and the page menu
- `views/`: the three pages
- `analysis.py`: data download, indicators and scoring rules (the point tables are plain lists you can adjust)
- `ui.py`: shared look and helpers
- `report.py`: the PDF summary
