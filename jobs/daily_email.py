"""Daily job: email every subscriber how their stocks are doing, compared with the Nifty 50.

Run by GitHub Actions on weekdays around 12 noon India time (see .github/workflows/daily-email.yml).
"""

import datetime as dt
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import analysis as a  # noqa: E402
import mailer  # noqa: E402
import portfolio  # noqa: E402
import settings  # noqa: E402
import store  # noqa: E402


def main():
    if not settings.email_ready():
        print("Email is not configured yet (secrets missing). Nothing sent.")
        return
    subscribers, _ = store.load()
    print(f"{len(subscribers)} subscriber(s)")
    if not subscribers:
        return
    bench = a._history(a.NIFTY)
    app_url = settings.get("APP_URL", settings.APP_URL_DEFAULT).rstrip("/")

    cache = {}

    def history(symbol):
        key = str(symbol).upper()
        if key not in cache:
            cache[key] = a.resolve(symbol)
        return cache[key]

    sent = failed = 0
    for email, rec in subscribers.items():
        try:
            holdings = [{"symbol": h["symbol"], "buy_price": float(h["buy_price"]),
                         "buy_date": dt.date.fromisoformat(h["buy_date"]), "qty": h.get("qty")}
                        for h in rec.get("holdings", [])]
            result = portfolio.track(holdings, bench, history_fn=history)
            if not result["rows"]:
                continue
            html = portfolio.email_html(result, f"{app_url}/daily-email?unsub={rec['token']}", app_url)
            subject = f"Your stocks today: {result['day']:+.2f}% (Nifty {result['nifty_day']:+.2f}%)"
            mailer.send(email, subject, html)
            sent += 1
        except Exception as e:  # one bad address must not stop the rest
            failed += 1
            print("Failed for one subscriber:", type(e).__name__)
    print(f"Sent {sent}, failed {failed}")


if __name__ == "__main__":
    main()
