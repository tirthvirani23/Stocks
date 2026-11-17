"""Monthly job: score every large and mid-size NSE company and save the results to data/scores.json.

Run by GitHub Actions on the 1st of each month (see .github/workflows/monthly-scores.yml).
The Top 20 page and the Portfolio Review suggestions read the saved file.
"""

import datetime as dt
import json
import pathlib
import sys
from concurrent.futures import ThreadPoolExecutor

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import analysis as a  # noqa: E402

MIN_CAP = 5000e7  # ₹5,000 crore
OUT = ROOT / "data" / "scores.json"


def main():
    bench = a._history(a.NIFTY)
    universe = [(industry, block["sector"], s) for industry, block in a.static_industries().items()
                for s in block["stocks"] if (s.get("market_cap") or 0) >= MIN_CAP]
    print(f"Scoring {len(universe)} companies…", flush=True)

    median_lists = {}

    def peers_for(industry):
        if industry not in median_lists:
            median_lists[industry] = a.peers(industry)
        return median_lists[industry]

    def one(item):
        industry, sector, s = item
        try:
            r = a.analyse(s["ticker"], bench=bench, peers_fn=lambda _i: peers_for(industry), light=True)
        except Exception:
            return None
        v, g, k = r["valuation"].score(), r["growth"].score(), r["risk"].score()
        ov = a.overall(v, g, k)
        if ov is None:
            return None
        cap = r["f"]["market_cap"] or s.get("market_cap")
        extra = {} if r["f"].get("currency", "INR") == "INR" else {"Currency": r["f"]["currency"]}
        return {**extra, "Symbol": r["symbol"], "Company": r["f"]["name"] or s["name"], "Industry": industry, "Sector": sector,
                "Price (₹)": round(r["price"], 2), "Overall": ov, "Valuation": v, "Growth": g, "Risk": k,
                "Market value (₹ cr)": round(cap / 1e7) if cap else None,
                "Coverage": round(min(r["valuation"].coverage(), r["growth"].coverage(), r["risk"].coverage()), 2)}

    with ThreadPoolExecutor(max_workers=4) as ex:
        rows = [x for x in ex.map(one, universe) if x]
    print(f"Scored {len(rows)} of {len(universe)}", flush=True)
    if len(rows) < len(universe) * 0.5:
        print("Too few companies could be scored; keeping the previous file.")
        sys.exit(1)

    rows.sort(key=lambda x: (-x["Overall"], x["Risk"]))
    OUT.write_text(json.dumps({"updated": dt.date.today().isoformat(), "min_cap_crore": 5000, "rows": rows},
                              ensure_ascii=False, separators=(",", ":")), "utf-8")
    print("Top 5:", [(x["Symbol"], x["Overall"]) for x in rows[:5]])


if __name__ == "__main__":
    main()
