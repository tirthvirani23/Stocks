"""Data fetching, indicators and scoring for Indian stocks (NSE / BSE).

Everything the app shows is calculated here. The scoring rules are written as
plain tables (value -> points) so they are easy to read and adjust.
"""

from __future__ import annotations

import math
import time

import numpy as np
import pandas as pd
import yfinance as yf

NIFTY = "^NSEI"
FINANCIAL_SECTORS = {"Financial Services"}


# ----------------------------------------------------------------------------
# Small helpers
# ----------------------------------------------------------------------------

def num(x):
    """Return x as a float, or None if it is missing / not a number."""
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return v if math.isfinite(v) else None


def interp(value, table):
    """Convert a value to points using a (value, points) table, with straight
    lines between the listed values and flat ends beyond them."""
    xs = [p[0] for p in table]
    ys = [p[1] for p in table]
    return float(np.interp(value, xs, ys))


def cagr(first, last, years):
    """Compound annual growth rate in percent."""
    if first is None or last is None or years <= 0 or first <= 0 or last <= 0:
        return None
    return ((last / first) ** (1 / years) - 1) * 100


# ----------------------------------------------------------------------------
# Finding the stock
# ----------------------------------------------------------------------------

def _history(ticker, period="10y"):
    h = yf.Ticker(ticker).history(period=period, auto_adjust=False)
    if h is None or h.empty:
        return pd.DataFrame()
    return h.dropna(subset=["Close"])


def resolve(query: str):
    """Turn what the user typed into a Yahoo ticker plus up to 10 years of prices.

    Tries NSE first, then BSE, then a name search limited to Indian listings.
    """
    q = query.strip().upper().replace(" ", "")
    if not q:
        raise ValueError("Please type a stock symbol, for example RELIANCE or TCS.")

    if q.endswith((".NS", ".BO")):
        candidates = [q]
    else:
        candidates = [q + ".NS", q + ".BO"]

    for c in candidates:
        h = _history(c)
        if len(h) >= 30:
            return c, h

    # Fall back to searching by company name.
    try:
        term = query.strip()
        if term.upper().endswith((".NS", ".BO")):
            term = term[:-3]
        quotes = yf.Search(term, max_results=10).quotes
    except Exception:
        quotes = []
    for item in quotes:
        sym = item.get("symbol", "")
        if sym.endswith((".NS", ".BO")) and item.get("quoteType") == "EQUITY":
            h = _history(sym)
            if len(h) >= 30:
                return sym, h

    raise ValueError(
        f"Could not find '{query}' on NSE or BSE. Check the symbol "
        "(for example HDFCBANK, INFY, ITC) and try again."
    )


# ----------------------------------------------------------------------------
# Technical analysis
# ----------------------------------------------------------------------------

def add_indicators(h: pd.DataFrame) -> pd.DataFrame:
    d = h.copy()
    c = d["Close"]
    d["SMA20"] = c.rolling(20).mean()
    d["SMA50"] = c.rolling(50).mean()
    d["SMA200"] = c.rolling(200).mean()

    # RSI (14), Wilder's smoothing
    delta = c.diff()
    gain = delta.clip(lower=0).ewm(alpha=1 / 14, adjust=False).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1 / 14, adjust=False).mean()
    d["RSI"] = 100 - 100 / (1 + gain / loss.replace(0, np.nan))
    d.loc[loss == 0, "RSI"] = 100

    # MACD (12, 26, 9)
    d["MACD"] = c.ewm(span=12, adjust=False).mean() - c.ewm(span=26, adjust=False).mean()
    d["MACDsignal"] = d["MACD"].ewm(span=9, adjust=False).mean()
    d["MACDhist"] = d["MACD"] - d["MACDsignal"]

    # Bollinger bands (20, 2)
    sd = c.rolling(20).std()
    d["BBupper"] = d["SMA20"] + 2 * sd
    d["BBlower"] = d["SMA20"] - 2 * sd

    # ATR (14)
    prev = c.shift(1)
    tr = pd.concat(
        [d["High"] - d["Low"], (d["High"] - prev).abs(), (d["Low"] - prev).abs()], axis=1
    ).max(axis=1)
    d["ATR"] = tr.ewm(alpha=1 / 14, adjust=False).mean()
    return d


def _ret(c: pd.Series, days: int):
    if len(c) <= days:
        return None
    return (c.iloc[-1] / c.iloc[-1 - days] - 1) * 100


def technicals(d: pd.DataFrame, bench: pd.DataFrame | None) -> dict:
    c = d["Close"]
    last = d.iloc[-1]
    price = float(last["Close"])
    year = d.tail(252)
    rets = year["Close"].pct_change().dropna()

    t = {
        "price": price,
        "sma20": num(last["SMA20"]),
        "sma50": num(last["SMA50"]),
        "sma200": num(last["SMA200"]),
        "rsi": num(last["RSI"]),
        "macd": num(last["MACD"]),
        "macd_signal": num(last["MACDsignal"]),
        "bb_upper": num(last["BBupper"]),
        "bb_lower": num(last["BBlower"]),
        "atr_pct": num(last["ATR"] / price * 100),
        "ret_1m": _ret(c, 21),
        "ret_3m": _ret(c, 63),
        "ret_6m": _ret(c, 126),
        "ret_1y": _ret(c, 252),
        "high_52w": float(year["High"].max()),
        "low_52w": float(year["Low"].min()),
        "volatility": float(rets.std() * math.sqrt(252) * 100) if len(rets) > 20 else None,
        "vol_ratio": None,
        "beta": None,
        "nifty_1y": None,
    }
    t["from_high"] = (price / t["high_52w"] - 1) * 100
    t["vs_sma200"] = (price / t["sma200"] - 1) * 100 if t["sma200"] else None
    t["vs_sma50"] = (price / t["sma50"] - 1) * 100 if t["sma50"] else None

    # Largest fall from a peak during the last year
    running_max = year["Close"].cummax()
    t["max_drawdown"] = float(-(year["Close"] / running_max - 1).min() * 100)

    vol20 = d["Volume"].tail(20).mean()
    if vol20 and vol20 > 0:
        t["vol_ratio"] = float(d["Volume"].tail(5).mean() / vol20)

    # Beta against Nifty 50, from one year of daily moves
    if bench is not None and not bench.empty:
        s = c.pct_change().copy()
        b = bench["Close"].pct_change().copy()
        s.index = s.index.tz_localize(None).normalize()
        b.index = b.index.tz_localize(None).normalize()
        both = pd.concat([s, b], axis=1, keys=["s", "b"]).dropna().tail(252)
        if len(both) > 60 and both["b"].var() > 0:
            t["beta"] = float(both["s"].cov(both["b"]) / both["b"].var())
        t["nifty_1y"] = _ret(bench["Close"], 252)
    return t


def technical_signals(t: dict) -> list[dict]:
    """Plain-language reading of each indicator."""
    p = t["price"]
    rows = []

    def add(name, value, reading, verdict):
        rows.append({"Indicator": name, "Value": value, "What it means": reading, "Signal": verdict})

    for label, key in [("20-day average", "sma20"), ("50-day average", "sma50"), ("200-day average", "sma200")]:
        v = t[key]
        if v:
            above = p > v
            add(label, f"₹{v:,.2f}",
                f"Price is {abs(p / v - 1) * 100:.1f}% {'above' if above else 'below'} it",
                "Bullish" if above else "Bearish")

    if t["sma50"] and t["sma200"]:
        golden = t["sma50"] > t["sma200"]
        add("Long-term trend (50 vs 200-day)", "Golden cross" if golden else "Death cross",
            "50-day average is above the 200-day average (uptrend)" if golden
            else "50-day average is below the 200-day average (downtrend)",
            "Bullish" if golden else "Bearish")

    r = t["rsi"]
    if r is not None:
        if r >= 70:
            add("RSI (14)", f"{r:.1f}", "Overbought: has risen fast, may pause or pull back", "Caution")
        elif r <= 30:
            add("RSI (14)", f"{r:.1f}", "Oversold: has fallen fast, may bounce", "Caution")
        elif r >= 50:
            add("RSI (14)", f"{r:.1f}", "Buyers have the upper hand", "Bullish")
        else:
            add("RSI (14)", f"{r:.1f}", "Sellers have the upper hand", "Bearish")

    if t["macd"] is not None and t["macd_signal"] is not None:
        up = t["macd"] > t["macd_signal"]
        add("MACD (12, 26, 9)", f"{t['macd']:.2f} vs signal {t['macd_signal']:.2f}",
            "Momentum is turning up" if up else "Momentum is turning down",
            "Bullish" if up else "Bearish")

    if t["bb_upper"] and t["bb_lower"]:
        if p > t["bb_upper"]:
            add("Bollinger bands", f"₹{t['bb_lower']:,.0f} to ₹{t['bb_upper']:,.0f}",
                "Price is above the upper band (stretched)", "Caution")
        elif p < t["bb_lower"]:
            add("Bollinger bands", f"₹{t['bb_lower']:,.0f} to ₹{t['bb_upper']:,.0f}",
                "Price is below the lower band (stretched down)", "Caution")
        else:
            add("Bollinger bands", f"₹{t['bb_lower']:,.0f} to ₹{t['bb_upper']:,.0f}",
                "Price is inside its normal range", "Neutral")

    add("52-week range", f"₹{t['low_52w']:,.2f} to ₹{t['high_52w']:,.2f}",
        f"Price is {abs(t['from_high']):.1f}% below its 52-week high",
        "Bullish" if t["from_high"] > -10 else ("Neutral" if t["from_high"] > -25 else "Bearish"))

    if t["vol_ratio"] is not None:
        vr = t["vol_ratio"]
        add("Volume (5-day vs 20-day)", f"{vr:.2f}x",
            "Trading activity is higher than usual" if vr > 1.3
            else ("Trading activity is lower than usual" if vr < 0.7 else "Trading activity is normal"),
            "Neutral")

    if t["ret_1y"] is not None and t["nifty_1y"] is not None:
        diff = t["ret_1y"] - t["nifty_1y"]
        add("1-year return vs Nifty 50", f"{t['ret_1y']:+.1f}% vs {t['nifty_1y']:+.1f}%",
            f"{'Beat' if diff > 0 else 'Lagged'} the Nifty 50 by {abs(diff):.1f} percentage points",
            "Bullish" if diff > 0 else "Bearish")
    return rows


# ----------------------------------------------------------------------------
# Fundamental analysis
# ----------------------------------------------------------------------------

def _row(df, names):
    if df is None or df.empty:
        return None
    for n in names:
        if n in df.index:
            s = df.loc[n].dropna()
            if not s.empty:
                return s.sort_index()  # oldest -> newest
    return None


def fundamentals(tk: yf.Ticker, price: float, light: bool = False) -> dict:
    info = {}
    for attempt in range(2):
        try:
            info = tk.info or {}
        except Exception:
            info = {}
        if info.get("longName") or info.get("shortName"):
            break
        time.sleep(1.5)

    def safe(attr):
        try:
            return getattr(tk, attr)
        except Exception:
            return None

    inc = safe("income_stmt")

    f = {
        "name": info.get("longName") or info.get("shortName"),
        "sector": info.get("sector"),
        "industry": info.get("industry"),
        "summary": info.get("longBusinessSummary"),
        "pe": num(info.get("trailingPE")),
        "forward_pe": num(info.get("forwardPE")),
        "pb": num(info.get("priceToBook")),
        "ev_ebitda": num(info.get("enterpriseToEbitda")),
        "eps": num(info.get("trailingEps")),
        "forward_eps": num(info.get("forwardEps")),
        "book_value": num(info.get("bookValue")),
        "div_yield": num(info.get("dividendYield")),  # already in percent
        "roe": num(info.get("returnOnEquity")),
        "roa": num(info.get("returnOnAssets")),
        "profit_margin": num(info.get("profitMargins")),
        "op_margin": num(info.get("operatingMargins")),
        "rev_growth_q": num(info.get("revenueGrowth")),
        "earn_growth_q": num(info.get("earningsGrowth")),
        "debt_equity": num(info.get("debtToEquity")),  # percent
        "current_ratio": num(info.get("currentRatio")),
        "total_debt": num(info.get("totalDebt")),
        "total_cash": num(info.get("totalCash")),
        "fcf": num(info.get("freeCashflow")),
        "op_cashflow": num(info.get("operatingCashflow")),
        "promoter": num(info.get("heldPercentInsiders")),
        "institutions": num(info.get("heldPercentInstitutions")),
        "target": num(info.get("targetMeanPrice")),
        "analysts": num(info.get("numberOfAnalystOpinions")),
        "recommendation": info.get("recommendationKey"),
        "market_cap": num(info.get("marketCap")),
        "prev_close": num(info.get("previousClose") or info.get("regularMarketPreviousClose")),
        "live_price": num(info.get("currentPrice") or info.get("regularMarketPrice")),
        "market_time": info.get("regularMarketTime"),
    }
    for k in ("roe", "roa", "profit_margin", "op_margin", "rev_growth_q", "earn_growth_q",
              "promoter", "institutions"):
        if f[k] is not None:
            f[k] *= 100
    if f["debt_equity"] is not None:
        f["debt_equity"] /= 100  # as a ratio, e.g. 0.44

    if f["market_cap"] is None:
        shares = num(info.get("sharesOutstanding"))
        if shares is None:
            try:
                shares = num(tk.fast_info["shares"])
            except Exception:
                shares = None
        if shares:
            f["market_cap"] = shares * price

    # Yearly history (up to 4 years)
    revenue = _row(inc, ["Total Revenue", "Operating Revenue"])
    profit = _row(inc, ["Net Income", "Net Income Common Stockholders"])
    eps_hist = _row(inc, ["Diluted EPS", "Basic EPS"])
    ebit = _row(inc, ["EBIT", "Operating Income"])
    interest = _row(inc, ["Interest Expense"])
    f["revenue_hist"], f["profit_hist"], f["eps_hist"] = revenue, profit, eps_hist

    def growth(s):
        if s is None or len(s) < 2:
            return None, 0
        yrs = len(s) - 1
        return cagr(num(s.iloc[0]), num(s.iloc[-1]), yrs), yrs

    f["rev_cagr"], f["rev_cagr_years"] = growth(revenue)
    f["profit_cagr"], f["profit_cagr_years"] = growth(profit)
    f["eps_cagr"], _ = growth(eps_hist)
    f["loss_years"] = int((profit < 0).sum()) if profit is not None else None
    f["years_of_data"] = len(profit) if profit is not None else 0

    f["interest_cover"] = None
    if ebit is not None and interest is not None:
        e, i = num(ebit.iloc[-1]), num(interest.iloc[-1])
        if e is not None and i and abs(i) > 0:
            f["interest_cover"] = e / abs(i)

    # Our own PEG: P/E divided by profit growth rate
    f["peg"] = None
    g = f["eps_cagr"] if f["eps_cagr"] is not None else f["profit_cagr"]
    if f["pe"] and f["pe"] > 0 and g and g > 0:
        f["peg"] = f["pe"] / g
    f["peg_growth"] = g

    f["upside"] = (f["target"] / price - 1) * 100 if f["target"] else None
    f["exp_eps_growth"] = None
    if f["eps"] and f["eps"] > 0 and f["forward_eps"]:
        f["exp_eps_growth"] = (f["forward_eps"] / f["eps"] - 1) * 100

    f["is_financial"] = f["sector"] in FINANCIAL_SECTORS
    f["is_fund"] = f["sector"] is None and revenue is None
    f["shares"] = num(info.get("sharesOutstanding")) or num(info.get("impliedSharesOutstanding"))
    if f["shares"] is None and f["market_cap"]:
        f["shares"] = f["market_cap"] / price

    f["q_revenue"] = f["q_profit"] = None
    f["events"] = {}
    if not light:
        q = safe("quarterly_income_stmt")
        f["q_revenue"] = _row(q, ["Total Revenue", "Operating Revenue"])
        f["q_profit"] = _row(q, ["Net Income", "Net Income Common Stockholders"])
        cal = safe("calendar")
        if isinstance(cal, dict):
            f["events"] = cal
    return f


# ----------------------------------------------------------------------------
# Scoring
# ----------------------------------------------------------------------------

class Scorecard:
    """Collects metrics, each with points out of 100 and a weight. The final
    score is the weighted average of whichever metrics have data."""

    def __init__(self):
        self.items = []

    def add(self, basis, metric, value, display, table, weight, note):
        if value is None:
            self.items.append({"Type": basis, "Metric": metric, "Value": "Not available",
                               "Points": None, "Weight": weight, "Comment": "Skipped (no data)"})
            return
        self.items.append({"Type": basis, "Metric": metric, "Value": display,
                           "Points": round(interp(value, table)), "Weight": weight, "Comment": note})

    def add_fixed(self, basis, metric, display, points, weight, note):
        self.items.append({"Type": basis, "Metric": metric, "Value": display,
                           "Points": points, "Weight": weight, "Comment": note})

    def score(self):
        used = [i for i in self.items if i["Points"] is not None]
        w = sum(i["Weight"] for i in used)
        if not used or w == 0:
            return None
        return round(sum(i["Points"] * i["Weight"] for i in used) / w)

    def coverage(self):
        total = sum(i["Weight"] for i in self.items)
        used = sum(i["Weight"] for i in self.items if i["Points"] is not None)
        return used / total if total else 0


def band(v, cuts, labels):
    for c, l in zip(cuts, labels):
        if v < c:
            return l
    return labels[-1]


def score_valuation(f, t, industry_pe=None) -> Scorecard:
    """Higher = cheaper relative to earnings, assets, growth and industry peers."""
    s = Scorecard()
    fin = f["is_financial"]

    pe = f["pe"]
    if pe is not None and pe <= 0:
        s.add_fixed("FA", "P/E (price ÷ earnings)", "Negative", 5, 26, "Company is loss-making")
    elif pe is None and f["eps"] is not None and f["eps"] <= 0:
        s.add_fixed("FA", "P/E (price ÷ earnings)", "Loss-making", 5, 26, "No earnings to value")
    else:
        s.add("FA", "P/E (price ÷ earnings)", pe, f"{pe:.1f}" if pe else "",
              [(5, 100), (10, 90), (15, 80), (20, 65), (30, 45), (45, 25), (70, 8), (100, 0)], 26,
              band(pe or 0, [15, 25, 40], ["Cheap", "Fair", "Expensive", "Very expensive"]))

    rel = pe / industry_pe if pe and pe > 0 and industry_pe else None
    s.add("FA", "P/E compared with industry peers", rel,
          f"{pe:.1f} vs peer median {industry_pe:.1f}" if rel else "",
          [(0.4, 100), (0.7, 82), (1, 58), (1.3, 38), (1.8, 15), (2.5, 0)], 12,
          band(rel or 0, [0.8, 1.2], ["Cheaper than peers", "In line with peers", "Costlier than peers"]))

    fpe = f["forward_pe"] if f["forward_pe"] and f["forward_pe"] > 0 else None
    s.add("FA", "Forward P/E (on next year's expected earnings)", fpe, f"{fpe:.1f}" if fpe else "",
          [(5, 100), (10, 90), (15, 78), (20, 60), (30, 38), (45, 18), (70, 0)], 12,
          band(fpe or 0, [14, 22, 35], ["Cheap", "Fair", "Expensive", "Very expensive"]))

    peg = f["peg"]
    s.add("FA", "PEG (P/E ÷ profit growth %)", peg,
          f"{peg:.2f} (growth {f['peg_growth']:.0f}%/yr)" if peg else "",
          [(0.5, 100), (1, 80), (1.5, 60), (2, 40), (3, 15), (4, 0)], 16,
          band(peg or 0, [1, 2], ["Price is justified by growth", "Fair for its growth", "Price runs ahead of growth"]))

    pb = f["pb"] if f["pb"] and f["pb"] > 0 else None
    s.add("FA", "P/B (price ÷ book value)", pb, f"{pb:.2f}" if pb else "",
          [(0.7, 100), (1, 92), (2, 75), (3, 62), (5, 45), (8, 25), (15, 5)], 20 if fin else 10,
          band(pb or 0, [1.5, 4, 8], ["Close to asset value", "Moderate premium", "High premium", "Very high premium"]))

    if not fin:
        ev = f["ev_ebitda"] if f["ev_ebitda"] and f["ev_ebitda"] > 0 else None
        s.add("FA", "EV/EBITDA (whole-business value ÷ operating profit)", ev, f"{ev:.1f}" if ev else "",
              [(5, 100), (8, 85), (12, 65), (18, 40), (25, 20), (40, 0)], 14,
              band(ev or 0, [10, 18, 28], ["Cheap", "Fair", "Expensive", "Very expensive"]))

    dy = f["div_yield"]
    s.add("FA", "Dividend yield", dy, f"{dy:.2f}%" if dy is not None else "",
          [(0, 20), (1, 50), (2, 70), (4, 95), (6, 100)], 5,
          band(dy or 0, [1, 3], ["Low payout", "Reasonable payout", "High payout"]))

    up = f["upside"]
    s.add("FA", "Analyst target price vs current price", up,
          f"{up:+.1f}% (target ₹{f['target']:,.0f})" if up is not None else "",
          [(-20, 0), (0, 35), (10, 55), (20, 75), (40, 100)], 5,
          "Analysts see upside" if (up or 0) > 5 else "Analysts see little upside")
    return s


def score_growth(f, t) -> Scorecard:
    """Higher = stronger business growth and price trend."""
    s = Scorecard()
    g_table = [(-10, 0), (0, 20), (5, 40), (10, 60), (15, 75), (25, 92), (35, 100)]

    def g_note(v):
        return band(v or 0, [0, 8, 15, 25], ["Shrinking", "Slow", "Steady", "Strong", "Very strong"])

    rc = f["rev_cagr"]
    s.add("FA", f"Sales growth per year ({f['rev_cagr_years']}-year)", rc, f"{rc:+.1f}%" if rc is not None else "",
          g_table, 18, g_note(rc))
    pc = f["profit_cagr"]
    if pc is None and f["profit_hist"] is not None and len(f["profit_hist"]) >= 2:
        first, last = num(f["profit_hist"].iloc[0]), num(f["profit_hist"].iloc[-1])
        if last is not None and last <= 0:
            s.add_fixed("FA", "Profit growth per year", "Now loss-making", 5, 18, "Latest year was a loss")
        elif first is not None and first <= 0:
            s.add_fixed("FA", "Profit growth per year", "Turned profitable", 75, 18, "Moved from loss to profit")
        else:
            s.add("FA", "Profit growth per year", None, "", g_table, 18, "")
    else:
        s.add("FA", f"Profit growth per year ({f['profit_cagr_years']}-year)", pc,
              f"{pc:+.1f}%" if pc is not None else "", g_table, 18, g_note(pc))

    q_table = [(-30, 0), (-10, 15), (0, 30), (10, 55), (20, 75), (40, 95), (60, 100)]
    rq = f["rev_growth_q"]
    s.add("FA", "Latest quarter sales vs a year ago", rq, f"{rq:+.1f}%" if rq is not None else "", q_table, 8, g_note(rq))
    eq = f["earn_growth_q"]
    s.add("FA", "Latest quarter profit vs a year ago", eq, f"{eq:+.1f}%" if eq is not None else "", q_table, 8, g_note(eq))

    eg = f["exp_eps_growth"]
    s.add("FA", "Expected earnings growth next year (analysts)", eg, f"{eg:+.1f}%" if eg is not None else "",
          g_table, 10, g_note(eg))

    roe = f["roe"]
    s.add("FA", "ROE (profit earned on shareholders' money)", roe, f"{roe:.1f}%" if roe is not None else "",
          [(0, 0), (8, 30), (12, 50), (15, 65), (20, 80), (30, 100)], 13,
          band(roe or 0, [10, 15, 22], ["Weak", "Average", "Good", "Excellent"]))

    r6 = t["ret_6m"]
    s.add("TA", "Price change over 6 months", r6, f"{r6:+.1f}%" if r6 is not None else "",
          [(-30, 0), (-10, 25), (0, 45), (10, 65), (25, 85), (50, 100)], 8,
          "Rising" if (r6 or 0) > 3 else ("Falling" if (r6 or 0) < -3 else "Flat"))

    v200 = t["vs_sma200"]
    s.add("TA", "Price vs 200-day average", v200, f"{v200:+.1f}%" if v200 is not None else "",
          [(-25, 0), (-10, 25), (0, 50), (10, 75), (25, 95), (40, 100)], 7,
          "In a long-term uptrend" if (v200 or 0) > 0 else "In a long-term downtrend")

    if t["sma50"] and t["sma200"]:
        golden = t["sma50"] > t["sma200"]
        s.add_fixed("TA", "50-day vs 200-day average", "Golden cross" if golden else "Death cross",
                    80 if golden else 25, 5, "Uptrend intact" if golden else "Downtrend in place")
    if t["macd"] is not None and t["macd_signal"] is not None:
        up = t["macd"] > t["macd_signal"]
        s.add_fixed("TA", "MACD momentum", "Above signal line" if up else "Below signal line",
                    70 if up else 35, 5, "Momentum improving" if up else "Momentum weakening")
    return s


def score_risk(f, t) -> Scorecard:
    """Higher = RISKIER. Points here are risk points."""
    s = Scorecard()
    fin = f["is_financial"]

    v = t["volatility"]
    s.add("TA", "Volatility (yearly swing in price)", v, f"{v:.1f}%" if v is not None else "",
          [(12, 5), (20, 25), (30, 50), (40, 70), (55, 90), (70, 100)], 20,
          band(v or 0, [22, 35, 50], ["Calm", "Normal", "Jumpy", "Very jumpy"]))

    b = t["beta"]
    s.add("TA", "Beta vs Nifty 50 (1 = moves like the market)", b, f"{b:.2f}" if b is not None else "",
          [(0.3, 10), (0.8, 30), (1, 45), (1.3, 65), (1.7, 85), (2.2, 100)], 12,
          band(b or 0, [0.8, 1.2], ["Moves less than the market", "Moves with the market", "Amplifies market moves"]))

    dd = t["max_drawdown"]
    s.add("TA", "Biggest fall from a peak in the last year", dd, f"-{dd:.1f}%" if dd is not None else "",
          [(8, 5), (15, 25), (25, 50), (35, 70), (50, 90), (65, 100)], 13,
          band(dd or 0, [15, 30, 45], ["Shallow", "Moderate", "Deep", "Severe"]))

    v200 = t["vs_sma200"]
    s.add("TA", "Price vs 200-day average", v200, f"{v200:+.1f}%" if v200 is not None else "",
          [(-30, 95), (-10, 70), (0, 45), (10, 30), (30, 40), (60, 65)], 7,
          "Below long-term trend" if (v200 or 0) < 0 else "Above long-term trend")

    if not fin:
        de = f["debt_equity"]
        s.add("FA", "Debt ÷ equity", de, f"{de:.2f}" if de is not None else "",
              [(0, 5), (0.3, 20), (0.7, 40), (1, 55), (2, 80), (3, 100)], 15,
              band(de if de is not None else 0, [0.3, 1, 2], ["Almost debt-free", "Comfortable debt", "High debt", "Very high debt"]))
        ic = f["interest_cover"]
        s.add("FA", "Interest cover (operating profit ÷ interest)", ic, f"{ic:.1f}x" if ic is not None else "",
              [(0, 100), (1, 95), (1.5, 85), (3, 60), (6, 35), (10, 20), (20, 5)], 8,
              band(ic if ic is not None else 0, [1.5, 4, 10], ["Struggles to pay interest", "Thin cushion", "Comfortable", "Very comfortable"]))
        cr = f["current_ratio"]
        s.add("FA", "Current ratio (short-term assets ÷ short-term dues)", cr, f"{cr:.2f}" if cr is not None else "",
              [(0.5, 95), (1, 65), (1.5, 40), (2, 25), (3, 10)], 5,
              band(cr if cr is not None else 0, [1, 1.5], ["Tight liquidity", "Adequate liquidity", "Comfortable liquidity"]))

    mc = f["market_cap"]
    if mc:
        crore = mc / 1e7
        s.add("FA", "Company size (market value)", math.log10(max(crore, 1)), f"₹{crore:,.0f} crore",
              [(2.5, 98), (3.3, 80), (3.7, 68), (4.3, 50), (5, 28), (5.7, 10)], 12,
              band(crore, [5000, 20000, 100000], ["Small cap", "Mid cap", "Large cap", "Very large cap"]))
    else:
        s.add("FA", "Company size (market value)", None, "", [(0, 0)], 12, "")

    ly, n = f["loss_years"], f["years_of_data"]
    if ly is not None and n:
        s.add_fixed("FA", f"Loss-making years (last {n})", f"{ly} of {n}",
                    [5, 55, 80, 95, 100][min(ly, 4)], 8,
                    "Consistently profitable" if ly == 0 else "Has reported losses")
    else:
        s.add("FA", "Loss-making years", None, "", [(0, 0)], 8, "")

    pm = f["profit_margin"]
    s.add("FA", "Net profit margin", pm, f"{pm:.1f}%" if pm is not None else "",
          [(-10, 100), (0, 85), (3, 65), (8, 45), (15, 25), (25, 10)], 5,
          band(pm if pm is not None else 0, [0, 5, 15], ["Loss-making", "Thin cushion", "Healthy cushion", "Thick cushion"]))
    return s


# ----------------------------------------------------------------------------
# Peers (same industry, largest companies on NSE)
# ----------------------------------------------------------------------------

def peers(industry: str | None, size: int = 12) -> list[dict]:
    if not industry:
        return []
    from yfinance import EquityQuery as Q

    name = industry.replace(" - ", "—")
    try:
        res = yf.screen(
            Q("and", [Q("eq", ["region", "in"]), Q("eq", ["industry", name]), Q("eq", ["exchange", "NSI"])]),
            sortField="intradaymarketcap", sortAsc=False, size=size,
        )
    except Exception:
        return []
    out = []
    for q in res.get("quotes", []):
        sym = q.get("symbol", "")
        if not sym.endswith(".NS"):
            continue
        out.append({
            "ticker": sym,
            "symbol": sym[:-3],
            "name": (q.get("longName") or q.get("shortName") or sym).title(),
            "price": num(q.get("regularMarketPrice")),
            "market_cap": num(q.get("marketCap")),
            "pe": num(q.get("trailingPE")),
            "forward_pe": num(q.get("forwardPE")),
            "pb": num(q.get("priceToBook")),
            "div_yield": num(q.get("dividendYield")),
            "change_1y": num(q.get("fiftyTwoWeekChangePercent")),
        })
    return out


def median_pe(peer_list: list[dict]):
    vals = [p["pe"] for p in peer_list if p["pe"] and 0 < p["pe"] < 200]
    return float(np.median(vals)) if len(vals) >= 4 else None


# ----------------------------------------------------------------------------
# Support and resistance
# ----------------------------------------------------------------------------

def support_resistance(d: pd.DataFrame, price: float) -> dict:
    v = d.tail(250)
    w = 7
    highs, lows = v["High"], v["Low"]
    levels = []
    for i in range(w, len(v) - w):
        if highs.iloc[i] == highs.iloc[i - w:i + w + 1].max():
            levels.append(float(highs.iloc[i]))
        if lows.iloc[i] == lows.iloc[i - w:i + w + 1].min():
            levels.append(float(lows.iloc[i]))
    levels.sort()
    merged = []  # group levels that sit within 2% of each other
    for lv in levels:
        if merged and lv / merged[-1][0] - 1 < 0.02:
            merged[-1].append(lv)
        else:
            merged.append([lv])
    zones = [(float(np.mean(g)), len(g)) for g in merged]
    supports = sorted([z for z in zones if z[0] < price * 0.995], key=lambda z: -z[0])[:2]
    resistances = sorted([z for z in zones if z[0] > price * 1.005], key=lambda z: z[0])[:2]

    last = d.iloc[-1]
    h, l, c = float(last["High"]), float(last["Low"]), float(last["Close"])
    p = (h + l + c) / 3
    return {
        "supports": supports,
        "resistances": resistances,
        "pivot": {"S2": p - (h - l), "S1": 2 * p - h, "Pivot": p, "R1": 2 * p - l, "R2": p + (h - l)},
    }


# ----------------------------------------------------------------------------
# Fair value, P/E history, dividends, past returns
# ----------------------------------------------------------------------------

def fair_value(f: dict, price: float, industry_pe=None, own_pe=None):
    """Project earnings 5 years ahead, value them at an exit P/E, and discount
    back at 12% a year. Three scenarios."""
    eps = f["eps"]
    if not eps or eps <= 0 or f["loss_years"] or (f["forward_eps"] is not None and f["forward_eps"] <= 0):
        return None  # earnings too unstable to project
    rates = [x for x in (f["profit_cagr"], f["exp_eps_growth"], f["rev_cagr"]) if x is not None]
    if not rates:
        return None
    g = float(np.clip(np.mean(rates), 0, 20))
    anchors = [x for x in (industry_pe, own_pe) if x]
    exit_pe = float(np.clip(np.mean(anchors) if anchors else 18, 10, 30))
    rows = []
    for label, gg, pe in [("Cautious", max(g - 4, 0), exit_pe * 0.8), ("Base", g, exit_pe),
                          ("Optimistic", g + 4, exit_pe * 1.2)]:
        value = eps * (1 + gg / 100) ** 5 * pe / 1.12 ** 5
        rows.append({"case": label, "growth": gg, "exit_pe": pe, "value": value,
                     "vs_price": (value / price - 1) * 100})
    return {"rows": rows, "eps": eps, "discount": 12, "years": 5}


def pe_history(f: dict, d: pd.DataFrame):
    """Approximate P/E at each financial year-end: (price x today's share count) / that year's profit."""
    prof, shares = f["profit_hist"], f["shares"]
    if prof is None or not shares:
        return None
    close = d["Close"].copy()
    close.index = close.index.tz_localize(None)
    out = {}
    for date, ni in prof.items():
        ni = num(ni)
        px = close[:pd.Timestamp(date)]
        if ni and ni > 0 and len(px):
            pe = float(px.iloc[-1]) * shares / ni
            if 0 < pe < 300:
                out[f"FY{pd.Timestamp(date).year}"] = pe
    if len(out) < 2:
        return None
    return {"by_year": out, "average": float(np.mean(list(out.values())))}


def dividends_by_year(d: pd.DataFrame):
    div = d["Dividends"]
    div = div[div > 0]
    if div.empty:
        return None
    idx = div.index.tz_localize(None)
    fy = [f"FY{x.year + 1 if x.month >= 4 else x.year}" for x in idx]  # Indian FY: April to March
    by = div.groupby(fy).sum()
    return by.tail(6)


def splits(d: pd.DataFrame):
    sp = d["Stock Splits"]
    sp = sp[sp > 0]
    return [(i.strftime("%d %b %Y"), float(v)) for i, v in sp.items()]


def past_returns(d: pd.DataFrame, bench: pd.DataFrame | None, amount: float, fd_rate: float = 7.0):
    """What an investment made 1, 3, 5 and 10 years ago would be worth today."""
    adj = d["Adj Close"].dropna()
    adj.index = adj.index.tz_localize(None)
    b = None
    if bench is not None and not bench.empty:
        b = bench["Close"].dropna()
        b.index = b.index.tz_localize(None)
    end = adj.index[-1]
    rows = []
    for y in (1, 3, 5, 10):
        start = end - pd.DateOffset(years=y)
        if adj.index[0] > start + pd.Timedelta(days=10):
            continue
        s0 = adj[adj.index >= start]
        row = {"years": y, "start": s0.index[0], "stock": amount * adj.iloc[-1] / s0.iloc[0],
               "nifty": None, "fd": amount * (1 + fd_rate / 100) ** y}
        if b is not None and b.index[0] <= start + pd.Timedelta(days=10):
            b0 = b[b.index >= start]
            row["nifty"] = amount * b.iloc[-1] / b0.iloc[0]
        row["stock_cagr"] = ((row["stock"] / amount) ** (1 / y) - 1) * 100
        rows.append(row)
    return rows


def growth_curves(d: pd.DataFrame, bench: pd.DataFrame | None, amount: float, years: int):
    adj = d["Adj Close"].dropna()
    adj.index = adj.index.tz_localize(None).normalize()
    start = adj.index[-1] - pd.DateOffset(years=years)
    s = adj[adj.index >= start]
    out = pd.DataFrame({"Stock": s / s.iloc[0] * amount})
    if bench is not None and not bench.empty:
        b = bench["Close"].dropna()
        b.index = b.index.tz_localize(None).normalize()
        b = b[b.index >= s.index[0]]
        if len(b):
            out["Nifty 50"] = (b / b.iloc[0] * amount).reindex(out.index).ffill()
    return out


# ----------------------------------------------------------------------------
# News
# ----------------------------------------------------------------------------

def news(ticker: str, name: str | None) -> list[dict]:
    items = []
    try:
        for n in yf.Ticker(ticker).news or []:
            c = n.get("content") or n
            url = (c.get("canonicalUrl") or {}).get("url") or (c.get("clickThroughUrl") or {}).get("url") or c.get("link")
            title = c.get("title")
            if title and url:
                items.append({"title": title, "url": url,
                              "source": (c.get("provider") or {}).get("displayName") or c.get("publisher") or "",
                              "date": pd.to_datetime(c.get("pubDate") or c.get("providerPublishTime"),
                                                     unit=None if c.get("pubDate") else "s", errors="coerce")})
    except Exception:
        pass
    if not items and name:
        try:
            short = name.replace(" Limited", "").replace(" Ltd.", "").replace(" Ltd", "")
            for c in yf.Search(short, news_count=8, max_results=1).news or []:
                if ticker in (c.get("relatedTickers") or [ticker]):
                    items.append({"title": c.get("title"), "url": c.get("link"), "source": c.get("publisher") or "",
                                  "date": pd.to_datetime(c.get("providerPublishTime"), unit="s", errors="coerce")})
        except Exception:
            pass
    return [i for i in items if i["title"] and i["url"]][:8]


# ----------------------------------------------------------------------------
# Plain-language summary
# ----------------------------------------------------------------------------

LABELS = {
    "valuation": ["Expensive", "Fairly priced", "Attractively priced"],
    "growth": ["Weak growth", "Moderate growth", "Strong growth"],
    "risk": ["Low risk", "Moderate risk", "High risk"],
}


def overall(val, gro, risk):
    """One combined number: the average of Valuation, Growth and safety (100 - Risk)."""
    parts = [x for x in (val, gro, None if risk is None else 100 - risk) if x is not None]
    return round(sum(parts) / len(parts)) if len(parts) == 3 else None


def score_industry(universe: list[dict], bench, median_list: list[dict], workers: int = 4) -> list[dict]:
    """Score every stock in an industry list. Stocks whose data cannot be fetched are skipped."""
    from concurrent.futures import ThreadPoolExecutor

    def one(p):
        try:
            r = analyse(p["ticker"], bench=bench, peers_fn=lambda _i: median_list, light=True)
        except Exception:
            return None
        v, g, k = r["valuation"].score(), r["growth"].score(), r["risk"].score()
        return {"Symbol": r["symbol"], "Company": r["f"]["name"] or p["name"], "Price (₹)": r["price"],
                "Overall": overall(v, g, k), "Valuation": v, "Growth": g, "Risk": k,
                "Market value (₹ cr)": round(r["f"]["market_cap"] / 1e7) if r["f"]["market_cap"] else None}

    with ThreadPoolExecutor(max_workers=workers) as ex:
        rows = list(ex.map(one, universe))
    return [x for x in rows if x and x["Overall"] is not None]


def label(kind: str, score):
    if score is None:
        return "Not scored"
    return LABELS[kind][0 if score < 40 else (1 if score < 60 else 2)]


def summarise(r: dict) -> dict:
    val, gro, risk, t = r["valuation"], r["growth"], r["risk"], r["t"]
    parts = [label(k, c.score()).lower() for k, c in (("valuation", val), ("growth", gro), ("risk", risk))
             if c.score() is not None]
    headline = ", ".join(parts).capitalize() + "." if parts else ""
    if t["vs_sma200"] is not None:
        headline += (" The price is in a long-term uptrend." if t["vs_sma200"] > 0 and (t["sma50"] or 0) > (t["sma200"] or 0)
                     else " The price is in a long-term downtrend." if t["vs_sma200"] < 0 and (t["sma50"] or 0) < (t["sma200"] or 0)
                     else " The price trend is mixed.")

    good, bad = [], []
    for card, flip in ((val, False), (gro, False), (risk, True)):
        for i in card.items:
            if i["Points"] is None:
                continue
            goodness = 100 - i["Points"] if flip else i["Points"]
            entry = (abs(goodness - 50) * i["Weight"], i["Metric"].split(" (")[0], f"{i['Value']}: {i['Comment'].lower()}")
            if goodness >= 70:
                good.append(entry)
            elif goodness <= 35:
                bad.append(entry)

    def top(lst):
        seen, out = set(), []
        for _, metric, text in sorted(lst, reverse=True):
            if metric not in seen:
                seen.add(metric)
                out.append((metric, text))
        return out[:3]

    return {"headline": headline, "strengths": top(good), "concerns": top(bad)}


# ----------------------------------------------------------------------------
# One call that does everything
# ----------------------------------------------------------------------------

def analyse(query: str, bench: pd.DataFrame | None = None, peers_fn=peers, light: bool = False) -> dict:
    """light=True skips quarterly results, events and news (used for lists of stocks)."""
    ticker, hist = resolve(query)
    if bench is None:
        try:
            bench = _history(NIFTY)
        except Exception:
            bench = None

    d = add_indicators(hist)
    t = technicals(d, bench)
    tk = yf.Ticker(ticker)
    f = fundamentals(tk, t["price"], light=light)

    price = f["live_price"] or t["price"]
    prev = f["prev_close"]
    if prev is None or abs(prev - price) < 1e-9:
        # Yahoo sometimes repeats the price as "previous close"; use the chart instead.
        closes = d["Close"]
        prev = float(closes.iloc[-2]) if abs(float(closes.iloc[-1]) - price) / price < 0.002 else float(closes.iloc[-1])

    try:
        peer_list = peers_fn(f["industry"]) if not f["is_fund"] else []
    except Exception:
        peer_list = []
    ind_pe = median_pe(peer_list)

    val, gro, risk = score_valuation(f, t, ind_pe), score_growth(f, t), score_risk(f, t)
    if f["is_fund"]:
        val, gro = Scorecard(), Scorecard()

    r = {
        "ticker": ticker,
        "exchange": "NSE" if ticker.endswith(".NS") else "BSE",
        "symbol": ticker.rsplit(".", 1)[0],
        "price": price,
        "prev_close": prev,
        "change_pct": (price / prev - 1) * 100 if prev else None,
        "last_date": d.index[-1],
        "hist": d,
        "bench": bench,
        "t": t,
        "f": f,
        "signals": technical_signals(t),
        "valuation": val,
        "growth": gro,
        "risk": risk,
        "peers": peer_list,
        "industry_pe": ind_pe,
        "levels": support_resistance(d, price),
        "pe_history": pe_history(f, d),
        "dividends": dividends_by_year(d),
        "splits": splits(d),
        "news": [] if light else news(ticker, f["name"]),
    }
    own_pe = r["pe_history"]["average"] if r["pe_history"] else None
    r["fair_value"] = None if f["is_fund"] else fair_value(f, price, ind_pe, own_pe)
    r["summary"] = summarise(r)
    return r
