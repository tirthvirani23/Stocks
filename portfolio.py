"""Portfolio-level logic: expected-return scenarios and portfolio review."""

from __future__ import annotations

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
