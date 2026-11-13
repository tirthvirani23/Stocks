# Indian Stock Checkup

Type an NSE or BSE stock symbol (for example `RELIANCE`, `TCS`, `HDFCBANK`) and get:

- the latest price
- fundamental analysis (P/E, P/B, PEG, ROE, margins, debt, cash flow, growth, yearly results)
- technical analysis (moving averages, RSI, MACD, Bollinger bands, returns, volatility, beta vs Nifty 50)
- three scores out of 100, with every metric behind each score shown:
  - **Valuation**: higher = cheaper
  - **Growth potential**: higher = stronger
  - **Risk**: higher = riskier

Data comes from Yahoo Finance. This is an educational tool, not investment advice.

## Put it online for free (no coding, about 5 minutes)

1. Open https://share.streamlit.io and choose **Continue with GitHub**. Sign in with the GitHub account that owns this repository and allow access.
2. Click **Create app**, then **Deploy a public app from GitHub**.
3. Fill in:
   - **Repository**: `tirthvirani23/Stocks`
   - **Branch**: the branch that contains `app.py`
   - **Main file path**: `app.py`
4. Click **Deploy**. After two or three minutes you get a web link.
5. Open that link on your phone or computer any time. Bookmark it or add it to your home screen.

## Run it on your own computer instead

Install Python 3.10 or newer, then in this folder:

```
pip install -r requirements.txt
streamlit run app.py
```

## Files

- `app.py`: the screen you see
- `analysis.py`: data download, indicators and scoring rules (the point tables are plain lists you can adjust)
