"""
Price alerts
------------
Checks the latest prices against watchlist.csv and emails anyone whose
target price has been reached.

OFF BY DEFAULT. It only sends real emails when the repo variable
ALERTS_ENABLED is set to "true" AND these secrets exist:
  ALERT_EMAIL_FROM       the Gmail address that sends alerts
  ALERT_EMAIL_PASSWORD   a Gmail "app password" (not your normal password)
Otherwise it runs in "dry run" mode and just prints what it would send.

Where the watchlist comes from:
  - the WATCHLIST_CSV secret, if set (use this for real friends' emails,
    since this repo is public), otherwise
  - watchlist.csv in the repo (example row only)

Watchlist columns:
  name          friend's first name (used in the email greeting)
  email         where to send the alert
  event_search  words that appear in the event title, e.g. "Warriors" + "Kings"
  target_price  alert when the lowest price is at or below this
  active        yes / no

Each friend gets at most one alert per event per day (tracked in data/alerts_sent.csv,
which stores a one-way code instead of the email address).
"""

import csv
import hashlib
import os
import smtplib
from datetime import datetime, timezone
from email.message import EmailMessage
from pathlib import Path

from io import StringIO

import pandas as pd

PRICES = Path("data/prices.csv")
WATCHLIST = Path("watchlist.csv")
SENT_LOG = Path("data/alerts_sent.csv")

def person_id(email: str) -> str:
    """Short one-way code for an email, so the public sent-log never shows addresses."""
    return hashlib.sha256(str(email).strip().lower().encode()).hexdigest()[:12]


TODAY = datetime.now(timezone.utc).strftime("%Y-%m-%d")


def latest_prices(prices: pd.DataFrame) -> pd.DataFrame:
    """Most recent resale snapshot for each upcoming event."""
    resale = prices[prices["source"] == "seatgeek"]
    if resale.empty:
        resale = prices
    resale = resale.sort_values("snapshot_utc")
    latest = resale.groupby("event_id", as_index=False).last()
    return latest[pd.to_numeric(latest["days_until_event"], errors="coerce") >= 0]


def matches(title: str, search: str) -> bool:
    """Every word in the search has to appear in the event title."""
    title = str(title).lower()
    return all(word in title for word in str(search).lower().split())


def find_alerts(prices: pd.DataFrame, watchlist: pd.DataFrame, already_sent: set) -> list:
    alerts = []
    latest = latest_prices(prices)
    for _, watch in watchlist.iterrows():
        if str(watch.get("active", "yes")).strip().lower() not in ("yes", "y", "true", "1"):
            continue
        for _, event in latest.iterrows():
            price = pd.to_numeric(event["lowest_price"], errors="coerce")
            if pd.isna(price) or not matches(event["title"], watch["event_search"]):
                continue
            if price <= float(watch["target_price"]):
                key = (person_id(watch["email"]), str(event["event_id"]), TODAY)
                if key not in already_sent:
                    alerts.append({"watch": watch, "event": event, "price": price, "key": key})
    return alerts


def build_email(alert: dict, sender: str) -> EmailMessage:
    w, e, price = alert["watch"], alert["event"], alert["price"]
    msg = EmailMessage()
    msg["From"] = sender
    msg["To"] = w["email"]
    msg["Subject"] = f"🎟️ Price drop: {e['title']} is now ${price:,.0f}"
    msg.set_content(
        f"Hi {w['name']},\n\n"
        f"{e['title']} at {e['venue']} just hit your target.\n"
        f"Lowest price: ${price:,.0f} (your target: ${float(w['target_price']):,.0f})\n"
        f"Event date: {e['event_datetime_local']}\n\n"
        f"Tickets: {e['url']}\n\n"
        "Prices change fast and may not include every fee.\n"
        "Reply STOP and you'll be taken off the list.\n"
    )
    return msg


def load_sent() -> set:
    if not SENT_LOG.exists():
        return set()
    with SENT_LOG.open() as f:
        return {(r["person"], r["event_id"], r["date"]) for r in csv.DictReader(f)}


def log_sent(keys: list):
    new = not SENT_LOG.exists()
    with SENT_LOG.open("a", newline="") as f:
        w = csv.writer(f)
        if new:
            w.writerow(["person", "event_id", "date"])
        w.writerows(keys)


def main():
    if not PRICES.exists():
        print("No prices yet. Nothing to check.")
        return

    prices = pd.read_csv(PRICES)
    secret_list = os.environ.get("WATCHLIST_CSV", "").strip()
    if secret_list:
        watchlist = pd.read_csv(StringIO(secret_list))
    elif WATCHLIST.exists():
        watchlist = pd.read_csv(WATCHLIST)
    else:
        print("No watchlist. Nothing to check.")
        return
    alerts = find_alerts(prices, watchlist, load_sent())
    print(f"{len(alerts)} alert(s) to send")

    enabled = os.environ.get("ALERTS_ENABLED", "").lower() == "true"
    sender = os.environ.get("ALERT_EMAIL_FROM")
    password = os.environ.get("ALERT_EMAIL_PASSWORD")

    if not (enabled and sender and password):
        for a in alerts:
            print(f"[dry run] would email {a['watch']['name']}: {a['event']['title']} at ${a['price']:,.0f}")
        return

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
        smtp.login(sender, password)
        for a in alerts:
            smtp.send_message(build_email(a, sender))
            print(f"Sent to {a['watch']['name']}: {a['event']['title']}")
    log_sent([a["key"] for a in alerts])


if __name__ == "__main__":
    main()
