"""Daily Email: enter what you bought and when; see performance against the Nifty 50 and get it by email each day."""

import datetime as dt
import secrets

import pandas as pd
import streamlit as st

import portfolio
import settings
import ui

st.title("Daily Email")

# ------------------------------------------------------------------ unsubscribe link from an email

token = st.query_params.get("unsub")
if token:
    if settings.email_ready():
        import store
        try:
            done = store.remove_token(token)
            st.success("You have been unsubscribed. No more emails will be sent." if done
                       else "This subscription was already removed.")
        except Exception:
            st.error("Could not unsubscribe right now. Please open the link again in a minute.")
    st.stop()

st.caption("Enter the stocks you bought, the price and the date. You will see how each has done against the Nifty 50 "
           "over the same period, and you can have this sent to your inbox every weekday around 12 noon.")

EXAMPLE = [{"Symbol": "TCS", "Buy price": 3000.0, "Buy date": dt.date(2025, 1, 10), "Quantity": 5.0},
           {"Symbol": "ITC", "Buy price": 400.0, "Buy date": dt.date(2024, 6, 3), "Quantity": 50.0}]
if "tr_rows" not in st.session_state:
    st.session_state["tr_rows"] = EXAMPLE
    st.session_state["tr_example"] = True

with st.expander("Upload a file instead of typing"):
    st.write("A CSV file with the columns: Symbol, Buy price, Buy date (YYYY-MM-DD), Quantity.")
    up = st.file_uploader("CSV file", type=["csv"], label_visibility="collapsed")
    if up is not None and st.session_state.get("tr_file") != (up.name, up.size):
        st.session_state["tr_file"] = (up.name, up.size)
        try:
            df = pd.read_csv(up)
            df.columns = [c.strip().capitalize() for c in df.columns]
            df["Buy date"] = pd.to_datetime(df["Buy date"], dayfirst=False, errors="coerce").dt.date
            if "Quantity" not in df:
                df["Quantity"] = None
            st.session_state["tr_rows"] = df[["Symbol", "Buy price", "Buy date", "Quantity"]].to_dict("records")
            st.session_state["tr_example"] = False
            st.session_state["tr_version"] = st.session_state.get("tr_version", 0) + 1
        except Exception:
            st.error("That file could not be read. Check that it has the four columns named above.")

st.markdown("**Your purchases**" + (" (example shown: replace with your own)" if st.session_state.get("tr_example") else ""))
edited = st.data_editor(
    pd.DataFrame(st.session_state["tr_rows"], columns=["Symbol", "Buy price", "Buy date", "Quantity"]),
    num_rows="dynamic", hide_index=True, width="stretch", key=f"tr_editor_{st.session_state.get('tr_version', 0)}",
    column_config={
        "Symbol": st.column_config.TextColumn("Stock symbol or name", required=True),
        "Buy price": st.column_config.NumberColumn("Buy price (₹)", min_value=0.01, format="%.2f", required=True),
        "Buy date": st.column_config.DateColumn("Buy date", max_value=dt.date.today(), format="DD MMM YYYY", required=True),
        "Quantity": st.column_config.NumberColumn("Quantity (optional)", min_value=0),
    })


def clean(frame) -> list[dict]:
    out = []
    for x in frame.to_dict("records"):
        if not isinstance(x["Symbol"], str) or not x["Symbol"].strip() or pd.isna(x["Buy price"]) or pd.isna(x["Buy date"]):
            continue
        qty = x["Quantity"] if pd.notna(x["Quantity"]) and x["Quantity"] > 0 else None
        out.append({"symbol": x["Symbol"].strip().upper(), "buy_price": float(x["Buy price"]),
                    "buy_date": pd.Timestamp(x["Buy date"]).date(), "qty": qty})
    return out[:40]


if st.button("Show performance", type="primary"):
    st.session_state["tr_request"] = clean(edited)

if "tr_request" in st.session_state:
    request = st.session_state["tr_request"]
    if not request:
        st.warning("Fill in the symbol, buy price and buy date for at least one stock.")
    else:
        with st.spinner("Fetching prices…"):
            res = portfolio.track(request, ui.nifty(), history_fn=ui.history)
        if res["errors"]:
            st.warning("Not found on NSE or BSE: " + ", ".join(res["errors"]))
        if res["rows"]:
            m = st.columns(4)
            m[0].metric("Value now", f"₹{res['value']:,.0f}", delta=f"{res['day']:+.2f}% today")
            m[1].metric("Your return", f"{res['gain']:+.1f}%", help=f"On ₹{res['invested']:,.0f} invested")
            m[2].metric("Nifty 50, same dates", ui.fmt(res["nifty_gain"], "{:+.1f}%"),
                        help="What the same money would have done in the Nifty 50, bought on the same dates")
            diff = None if res["nifty_gain"] is None else res["gain"] - res["nifty_gain"]
            m[3].metric("Versus Nifty", ui.fmt(diff, "{:+.1f} pts"))
            df = pd.DataFrame([{"Symbol": x["symbol"], "Buy date": x["buy_date"], "Buy price": x["buy_price"],
                                "Price now": x["price"], "Today": x["day"], "Since you bought": x["gain"],
                                "Nifty, same period": x["nifty"], "Versus Nifty": x["vs_nifty"]} for x in res["rows"]])
            pct = st.column_config.NumberColumn(format="%+.1f%%")
            st.dataframe(df, hide_index=True, width="stretch", column_config={
                "Buy date": st.column_config.DateColumn(format="DD MMM YYYY"),
                "Buy price": st.column_config.NumberColumn(format="₹%.2f"),
                "Price now": st.column_config.NumberColumn(format="₹%.2f"),
                "Today": st.column_config.NumberColumn(format="%+.2f%%"), "Since you bought": pct,
                "Nifty, same period": pct, "Versus Nifty": st.column_config.NumberColumn(format="%+.1f pts")})
            st.caption("Dividends are not included. If a stock was split or issued a bonus after you bought it, "
                       "enter the buy price adjusted for that.")

# ------------------------------------------------------------------ email subscription

st.divider()
st.markdown("#### Get this by email every weekday")
if not settings.email_ready():
    st.info("Email delivery has not been switched on for this site yet.")
    st.stop()

import mailer  # noqa: E402
import store  # noqa: E402

email = st.text_input("Your email address", placeholder="name@example.com", key="tr_email").strip().lower()
pending = st.session_state.get("tr_pending")

if st.button("Send me a confirmation code"):
    holdings = clean(edited)
    sends = st.session_state.get("tr_sends", 0)
    if "@" not in email or "." not in email.split("@")[-1]:
        st.error("Enter a valid email address.")
    elif not holdings:
        st.error("Fill in at least one stock above first.")
    elif sends >= 3:
        st.error("Too many codes requested. Reload the page and try again later.")
    else:
        code = f"{secrets.randbelow(900000) + 100000}"
        try:
            mailer.send(email, "Your confirmation code for Indian Stock Checkup",
                        f"<p>Your confirmation code is <b style='font-size:20px'>{code}</b>.</p>"
                        "<p>Enter it on the Daily Email page to start receiving your daily stock update. "
                        "If you did not ask for this, ignore this email and nothing will be sent.</p>",
                        f"Your confirmation code is {code}")
            st.session_state["tr_pending"] = {"email": email, "code": code, "holdings": holdings}
            st.session_state["tr_sends"] = sends + 1
            pending = st.session_state["tr_pending"]
        except Exception:
            st.error("The confirmation email could not be sent. Check the address and try again.")

if pending:
    st.success(f"A 6-digit code was sent to {pending['email']}. Enter it below.")
    typed = st.text_input("Confirmation code", max_chars=6, key="tr_code")
    if st.button("Confirm and subscribe", type="primary"):
        if typed.strip() != pending["code"]:
            st.error("That code does not match.")
        else:
            try:
                store.upsert(pending["email"], {
                    "token": secrets.token_urlsafe(24), "created": dt.date.today().isoformat(),
                    "holdings": [{**h, "buy_date": h["buy_date"].isoformat()} for h in pending["holdings"]]})
                del st.session_state["tr_pending"]
                st.success("Subscribed. Your first email arrives on the next weekday around 12 noon India time. "
                           "To change your list, subscribe again with the same address; the new list replaces the old one.")
            except Exception:
                st.error("Your subscription could not be saved right now. Please try again in a minute.")

st.caption("Your email address and stock list are stored encrypted and used only to send this daily update. "
           "Every email has a link to stop them.")
