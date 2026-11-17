"""Portfolio-level logic: expected-return scenarios, portfolio review and the performance tracker."""

from __future__ import annotations

import datetime as dt

import numpy as np
import pandas as pd

import analysis as a


def _clip(x, lo, hi):
    return float(min(max(x, lo), hi))


# ----------------------------------------------------------------------------
# Expected return scenarios for one stock
# ----------------------------------------------------------------------------

def expected_returns(r: dict) -> dict:
    """Bear / neutral / bull return scenarios, in percent per year.

    5 years: profit growth + change in P/E towards a fair level + dividends (FA).
    1 year: the 5-year neutral rate, blended with the analyst target when there is one,
            nudged by the price trend (TA); the bear-bull range is the stock's own yearly volatility.
    These are rule-based scenarios, not forecasts.
    """
    f, t, price = r["f"], r["t"], r["price"]
    ov = a.overall(r["valuation"].score(), r["growth"].score(), r["risk"].score())
    dy = min(f["div_yield"] or 0, 6)
    fv = r.get("fair_value")

    if fv:
        basis = "earnings"
        y5 = {}
        for key, row in zip(("bear", "neutral", "bull"), fv["rows"]):
            terminal = fv["eps"] * (1 + row["growth"] / 100) ** 5 * row["exit_pe"]
            y5[key] = _clip(((terminal / price) ** 0.2 - 1) * 100 + dy, -20, 35)
    else:
        basis = "score"  # no stable earnings to project: lean on the long-run market return and the scores
        base = 11.0 if ov is None else 3 + 0.16 * ov
        y5 = {"bear": base - 8, "neutral": base, "bull": base + 8}

    n1 = y5["neutral"]
    if f["upside"] is not None and (f["analysts"] or 0) >= 3:
        n1 = 0.6 * n1 + 0.4 * _clip(f["upside"], -30, 30)
    if t["vs_sma200"] is not None and t["sma50"] and t["sma200"]:
        if t["vs_sma200"] > 0 and t["sma50"] > t["sma200"]:
            n1 += 3
        elif t["vs_sma200"] < 0 and t["sma50"] < t["sma200"]:
            n1 -= 3
    vol = t["volatility"] or 30
    y1 = {"bear": max(n1 - 0.9 * vol, -60), "neutral": n1, "bull": n1 + 0.9 * vol}
    return {"y1": y1, "y5": y5, "basis": basis}


# ----------------------------------------------------------------------------
# Portfolio review
# ----------------------------------------------------------------------------

def verdict(r: dict) -> tuple[str, str]:
    v, g, k = r["valuation"].score(), r["growth"].score(), r["risk"].score()
    ov = a.overall(v, g, k)
    t = r["t"]
    downtrend = (t["vs_sma200"] is not None and t["vs_sma200"] < 0 and t["sma50"] and t["sma200"]
                 and t["sma50"] < t["sma200"])
    concerns = "; ".join(f"{m} {txt}" for m, txt in r["summary"]["concerns"][:2])
    strengths = "; ".join(f"{m} {txt}" for m, txt in r["summary"]["strengths"][:2])
    if ov is None:
        return "Not scored", "No company financials (ETF or fund)"
    if ov < 40 or (k is not None and k >= 70) or (v < 30 and g < 45):
        return "Consider reducing", concerns or "Weak scores overall"
    if ov < 50 or (downtrend and g < 50):
        return "Review", concerns or "Middling scores and a falling price trend"
    if ov >= 62:
        return "Strong", strengths
    return "Keep", strengths or "Balanced scores"


def review(holdings: list[dict]) -> dict:
    """holdings: [{"r": analysis result, "qty": number or None, "avg": buy price or None}]"""
    rows = []
    have_qty = all(h["qty"] for h in holdings)
    for h in holdings:
        r = h["r"]
        value = r["price"] * h["qty"] if have_qty else 1.0
        er = expected_returns(r)
        v, g, k = r["valuation"].score(), r["growth"].score(), r["risk"].score()
        verd, why = verdict(r)
        rows.append({
            "symbol": r["symbol"], "name": r["f"]["name"] or r["symbol"], "sector": r["f"]["sector"] or "Other",
            "industry": r["f"]["industry"], "price": r["price"], "qty": h["qty"], "avg": h["avg"], "value": value,
            "gain": (r["price"] / h["avg"] - 1) * 100 if h["avg"] else None,
            "overall": a.overall(v, g, k), "valuation": v, "growth": g, "risk": k,
            "beta": r["t"]["beta"], "er": er, "verdict": verd, "why": why,
        })
    total = sum(x["value"] for x in rows)
    for x in rows:
        x["weight"] = x["value"] / total * 100

    def wavg(key):
        pairs = [(x[key], x["weight"]) for x in rows if x[key] is not None]
        w = sum(p[1] for p in pairs)
        return sum(p[0] * p[1] for p in pairs) / w if w else None

    exp = {h: {c: sum(x["er"][h][c] * x["weight"] for x in rows) / 100 for c in ("bear", "neutral", "bull")}
           for h in ("y1", "y5")}

    sectors = {}
    for x in rows:
        sectors[x["sector"]] = sectors.get(x["sector"], 0) + x["weight"]
    top_stock = max(rows, key=lambda x: x["weight"])
    top_sector = max(sectors.items(), key=lambda kv: kv[1])

    notes, penalty = [], 0
    if len(rows) < 5:
        penalty += 5
        notes.append(f"Only {len(rows)} holding{'s' if len(rows) != 1 else ''}: one bad result can hurt the whole "
                     "portfolio. 8 to 15 stocks across industries spreads the risk.")
    if top_stock["weight"] > 30 and len(rows) > 1:
        penalty += 5
        notes.append(f"{top_stock['symbol']} is {top_stock['weight']:.0f}% of the portfolio. "
                     "Above 25–30% in one stock is a concentrated bet.")
    if top_sector[1] > 50 and len(rows) > 2:
        penalty += 5
        notes.append(f"{top_sector[1]:.0f}% of the money is in {top_sector[0]}. "
                     "Adding other sectors would reduce the damage from a sector-wide fall.")
    if len(rows) > 25:
        notes.append(f"{len(rows)} holdings is a lot to follow; the smallest positions barely affect the result.")

    w_overall = wavg("overall")
    return {
        "rows": sorted(rows, key=lambda x: -x["weight"]), "total": total, "have_qty": have_qty,
        "valuation": wavg("valuation"), "growth": wavg("growth"), "risk": wavg("risk"), "beta": wavg("beta"),
        "overall": w_overall, "penalty": penalty,
        "score": None if w_overall is None else max(round(w_overall - penalty), 0),
        "expected": exp, "sectors": dict(sorted(sectors.items(), key=lambda kv: -kv[1])), "notes": notes,
    }


def additions(rev: dict, scored: list[dict], limit: int = 5) -> dict:
    """Ideas from the monthly scores file: better stocks in the same industry as weak holdings,
    and top-scored stocks from sectors the portfolio does not hold."""
    held = {x["symbol"] for x in rev["rows"]}
    usable = [s for s in scored if s["Symbol"] not in held]
    swaps = []
    for x in rev["rows"]:
        if x["verdict"] in ("Consider reducing", "Review") and x["industry"]:
            ind = x["industry"].replace(" - ", "—")
            best = sorted([s for s in usable if s["Industry"] == ind and s["Overall"] > (x["overall"] or 0) + 5],
                          key=lambda s: -s["Overall"])[:2]
            if best:
                swaps.append((x, best))
    sectors_held = set(rev["sectors"])
    fresh, seen = [], set()
    for s in sorted(usable, key=lambda s: -s["Overall"]):
        if s["Sector"] not in sectors_held and s["Sector"] not in seen:
            fresh.append(s)
            seen.add(s["Sector"])
        if len(fresh) >= limit:
            break
    return {"swaps": swaps, "new_sectors": fresh}


# ----------------------------------------------------------------------------
# Performance tracker (used by the Daily Email page and the daily email job)
# ----------------------------------------------------------------------------

def _since(close: pd.Series, date: dt.date):
    """Percent change from the first trading day on or after `date` to the latest close."""
    s = close[close.index >= pd.Timestamp(date)]
    if s.empty or close.index[0] > pd.Timestamp(date) + pd.Timedelta(days=10):
        return None
    return (close.iloc[-1] / s.iloc[0] - 1) * 100


def track(holdings: list[dict], bench: pd.DataFrame | None, history_fn=a.resolve) -> dict:
    """holdings: [{"symbol", "buy_price", "buy_date" (date), "qty" (optional)}]"""
    nifty = None
    if bench is not None and not bench.empty:
        nifty = bench["Close"].dropna()
        nifty.index = nifty.index.tz_localize(None).normalize()
    rows, errors = [], []
    for h in holdings:
        try:
            ticker, hist = history_fn(h["symbol"])
        except Exception:
            errors.append(str(h["symbol"]).upper())
            continue
        close = hist["Close"].dropna()
        price, prev = float(close.iloc[-1]), float(close.iloc[-2])
        qty = h.get("qty") or 1
        nifty_pct = _since(nifty, h["buy_date"]) if nifty is not None else None
        gain = (price / h["buy_price"] - 1) * 100
        rows.append({
            "symbol": ticker.rsplit(".", 1)[0], "buy_price": h["buy_price"], "buy_date": h["buy_date"], "qty": qty,
            "price": price, "day": (price / prev - 1) * 100, "gain": gain, "nifty": nifty_pct,
            "vs_nifty": None if nifty_pct is None else gain - nifty_pct,
            "invested": h["buy_price"] * qty, "value": price * qty,
        })
    out = {"rows": rows, "errors": errors, "as_of": None, "nifty_day": None}
    if rows:
        invested, value = sum(x["invested"] for x in rows), sum(x["value"] for x in rows)
        prev_value = sum(x["value"] / (1 + x["day"] / 100) for x in rows)
        known = [x for x in rows if x["nifty"] is not None]
        nifty_value = sum(x["invested"] * (1 + x["nifty"] / 100) for x in known)
        out.update({
            "invested": invested, "value": value, "gain": (value / invested - 1) * 100,
            "day": (value / prev_value - 1) * 100,
            "nifty_gain": (nifty_value / sum(x["invested"] for x in known) - 1) * 100 if known else None,
        })
    if nifty is not None and len(nifty) > 1:
        out["nifty_day"] = float((nifty.iloc[-1] / nifty.iloc[-2] - 1) * 100)
        out["as_of"] = nifty.index[-1].date()
    return out


def email_html(result: dict, unsubscribe_url: str, app_url: str) -> str:
    def pct(x, digits=1):
        if x is None:
            return "–"
        colour = "#1a9d6c" if x >= 0 else "#d8433f"
        return f'<span style="color:{colour}">{x:+.{digits}f}%</span>'

    cell = 'style="padding:6px 10px;border-bottom:1px solid #e6e6e6;text-align:right"'
    left = 'style="padding:6px 10px;border-bottom:1px solid #e6e6e6;text-align:left"'
    body = "".join(
        f"<tr><td {left}><b>{x['symbol']}</b><br><span style='color:#777;font-size:12px'>"
        f"bought {x['buy_date']:%d %b %Y} at ₹{x['buy_price']:,.2f}</span></td>"
        f"<td {cell}>₹{x['price']:,.2f}</td><td {cell}>{pct(x['day'], 2)}</td><td {cell}>{pct(x['gain'])}</td>"
        f"<td {cell}>{pct(x['nifty'])}</td><td {cell}>{pct(x['vs_nifty'])}</td></tr>"
        for x in result["rows"])
    verdict_txt = ""
    if result.get("nifty_gain") is not None:
        diff = result["gain"] - result["nifty_gain"]
        verdict_txt = (f"The same money put into the Nifty 50 on the same dates would be {pct(result['nifty_gain'])}. "
                       f"You are {'ahead of' if diff >= 0 else 'behind'} the Nifty by <b>{abs(diff):.1f}</b> percentage points.")
    as_of = f"{result['as_of']:%d %b %Y}" if result.get("as_of") else ""
    return f"""<div style="font-family:Arial,Helvetica,sans-serif;max-width:640px;color:#222">
<h2 style="margin:0 0 4px">Your stocks today</h2>
<div style="color:#777;font-size:13px">Prices as of {as_of} (latest available, may be delayed)</div>
<p style="font-size:15px">Portfolio value <b>₹{result['value']:,.0f}</b> on ₹{result['invested']:,.0f} invested:
{pct(result['gain'])} overall, {pct(result['day'], 2)} today.
Nifty 50 today: {pct(result['nifty_day'], 2)}.<br>{verdict_txt}</p>
<table style="border-collapse:collapse;width:100%;font-size:14px">
<tr style="background:#f4f4f4"><th {left}>Stock</th><th {cell}>Price</th><th {cell}>Today</th>
<th {cell}>Since you bought</th><th {cell}>Nifty, same period</th><th {cell}>Versus Nifty</th></tr>
{body}</table>
<p style="color:#777;font-size:12px;margin-top:18px">Sent by Indian Stock Checkup (<a href="{app_url}">open the site</a>).
Data: Yahoo Finance. Educational only, not investment advice.<br>
<a href="{unsubscribe_url}">Stop these emails</a></p></div>"""
