# Indian Stock Checkup

A small website for checking Indian stocks (NSE / BSE). The menu at the top has two groups.

**Stocks**
- **Checkup**: type a symbol (for example `RELIANCE`, `TCS`, `HDFCBANK`) or a company name. You get the price, a one-line summary, three scores out of 100 (**Valuation**: higher = cheaper, **Growth potential**: higher = stronger, **Risk**: higher = riskier), every metric behind them, technical and fundamental analysis, peers, past returns, news, a list of better-scored stocks in the same industry, and a PDF download.
- **Compare**: two or three stocks side by side.
- **Top 20**: the 20 best overall scores among large and mid-size companies. Refreshed automatically on the 1st of each month; the page shows the update date.
- **Watchlist**: your saved stocks in one table. Bookmark the page to keep the list.

**Portfolio**
- **Portfolio Review**: upload a screenshot of your holdings (or type them). You get a portfolio rating, bear / neutral / bull return scenarios for 1 and 5 years, a verdict on each holding and suggested changes.
- **Portfolio Builder**: tick industries and get a sample portfolio of the three best-scored stocks in each.

Data comes from Yahoo Finance. This is an educational tool, not investment advice.

## Put it online for free (no coding, about 5 minutes)

1. Open https://share.streamlit.io and choose **Continue with GitHub**. Sign in with the GitHub account that owns this repository and allow access.
2. Click **Create app**, then **Deploy a public app from GitHub**.
3. Fill in:
   - **Repository**: this repository
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

## Automatic job

On the 1st of each month a job on GitHub (see the **Actions** tab of the repository) re-scores all large and mid-size companies for the Top 20 page. It needs no setup. To run it by hand: Actions tab → **Monthly scores (Top 20)** → **Run workflow**.

## Files

- `app.py`: start-up and the page menu
- `views/`: one file per page
- `analysis.py`: data download, indicators and scoring rules (the point tables are plain lists you can adjust)
- `ui.py`: shared look and helpers
- `report.py`: the PDF summary
- `portfolio.py`: return scenarios and portfolio review
- `ocr.py`: reads portfolio screenshots
- `jobs/` and `.github/workflows/`: the monthly automatic job
- `data/`: the built-in industry list and the monthly scores
