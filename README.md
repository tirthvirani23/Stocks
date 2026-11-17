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
- **Daily Email**: enter what you bought, at what price and when; see how each stock has done against the Nifty 50, and receive that by email every weekday around 12 noon India time.

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

## Automatic jobs

Two jobs run by themselves on GitHub (see the **Actions** tab of the repository):

- **Monthly scores (Top 20)**: 1st of each month. Needs no setup.
- **Daily email**: Monday to Friday at about 12 noon India time. Needs the one-time setup below.

You can also start either job by hand: Actions tab → pick the job → **Run workflow**.

## Switching on the daily email (one time, about 15 minutes)

The site needs an email account to send from, and permission to save subscribers' lists.

**1. Create a sending email account.** Make a new Gmail address used only for this (recipients will see this address). Turn on 2-Step Verification for it, then open https://myaccount.google.com/apppasswords, create an app password and copy the 16 letters.

**2. Create a GitHub access token.** GitHub → your picture → Settings → Developer settings → Personal access tokens → Fine-grained tokens → Generate new token. Under *Repository access* choose *Only select repositories* and pick this repository. Under *Permissions → Repository permissions* set **Contents** to **Read and write**. Generate and copy the token.

**3. Invent a long secret phrase** (any sentence of 20+ characters). It encrypts the subscriber list. Keep a copy: if it is lost or changed, existing subscriptions can no longer be read.

**4. Add the values to the website.** https://share.streamlit.io → ⋮ next to the app → Settings → Secrets. Paste, with your own values:

```
SMTP_USER = "your-sending-address@gmail.com"
SMTP_PASSWORD = "the 16-letter app password"
GH_TOKEN = "the GitHub token"
GH_REPO = "your-github-name/Stocks"
DATA_KEY = "your long secret phrase"
APP_URL = "https://your-app-address.streamlit.app"
```

**5. Add three of them to GitHub as well** (the daily job runs there). Repository → Settings → Secrets and variables → Actions → New repository secret. Add `SMTP_USER`, `SMTP_PASSWORD` and `DATA_KEY` with exactly the same values as in step 4. Then, on the *Variables* tab next to it, add a variable `APP_URL` with your app address.

After this the Daily Email page shows the sign-up form. Subscribers confirm their address with a 6-digit code, and every email carries a link to stop.

## Files

- `app.py`: start-up and the page menu
- `views/`: one file per page
- `analysis.py`: data download, indicators and scoring rules (the point tables are plain lists you can adjust)
- `ui.py`: shared look and helpers
- `report.py`: the PDF summary
- `portfolio.py`: return scenarios, portfolio review and the performance tracker
- `ocr.py`: reads portfolio screenshots
- `store.py`, `mailer.py`, `settings.py`: subscriber storage, email sending, configuration
- `jobs/` and `.github/workflows/`: the monthly and daily automatic jobs
- `data/`: the built-in industry list and the monthly scores
