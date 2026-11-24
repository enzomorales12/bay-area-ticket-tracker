"""
Import the hand-logged prices
-----------------------------
Reads the "Price Log" and "Events" tabs of the Ticket Price Log Google Sheet
and rewrites data/manual_prices.csv in the same columns as data/prices.csv,
so the app treats hand-logged prices like any other resale price.

Set two secrets (GitHub repo Settings -> Secrets and variables -> Actions):
  PRICE_LOG_CSV_URL   CSV link for the "Price Log" tab
  EVENTS_CSV_URL      CSV link for the "Events" tab

Get each link in Google Sheets with File -> Share -> Publish to web ->
pick the tab -> "Comma-separated values (.csv)" -> Publish, then copy the URL.
"""

import os
from datetime import datetime, timezone
from io import StringIO
from pathlib import Path

import pandas as pd
import requests

from collector import COLUMNS

OUTPUT = Path("data/manual_prices.csv")

CATEGORY = {"NBA": "nba", "NFL": "nfl", "NHL": "nhl", "MLB": "mlb", "Concert": "concert", "Festival": "music_festival"}


def fetch_csv(url: str) -> pd.DataFrame:
    response = requests.get(url, timeout=30)
    response.raise_for_status()
    return pd.read_csv(StringIO(response.text), dtype={"Event ID": str})


def to_price_rows(log: pd.DataFrame, events: pd.DataFrame) -> pd.DataFrame:
    # Only the columns typed by hand; the rest comes from the Events tab
    log = log[["Logged on", "Event", "Lowest price ($)", "Site"]].dropna(subset=["Logged on", "Event", "Lowest price ($)"]).copy()
    if log.empty:
        return pd.DataFrame(columns=COLUMNS)

    events = events.rename(columns={"Event": "title", "Event ID": "event_id"})
    log = log.merge(events, left_on="Event", right_on="title", how="left")

    logged = pd.to_datetime(log["Logged on"], errors="coerce")
    event_date = pd.to_datetime(log["Event date"], errors="coerce")
    start = log["Start time"].where(log["Start time"].astype(str).str.contains(":"), "12:00 PM")
    event_dt = pd.to_datetime(log["Event date"].astype(str) + " " + start.astype(str).str.strip(),
                              format="%Y-%m-%d %I:%M %p", errors="coerce")

    price = pd.to_numeric(log["Lowest price ($)"].astype(str).str.replace(r"[$,]", "", regex=True), errors="coerce")

    out = pd.DataFrame({
        # Logged once a day; 20:00 UTC is noon Pacific, so the date stays the same in both
        "snapshot_utc": logged.dt.strftime("%Y-%m-%dT20:00+00:00"),
        "source": "manual",
        "event_id": log["event_id"],
        "title": log["title"],
        "category": log["Category"].map(CATEGORY).fillna(log["Category"].str.lower()),
        "event_datetime_local": event_dt.dt.strftime("%Y-%m-%dT%H:%M:%S"),
        "days_until_event": (event_date - logged).dt.days,
        "venue": log["Venue"],
        "city": log["City"],
        "performer": "",
        "lowest_price": price,
        "median_price": "",
        "average_price": "",
        "highest_price": "",
        "listing_count": "",
        "popularity": "",
        "url": log["SeatGeek link"],
    })
    out = out.dropna(subset=["event_id", "lowest_price", "snapshot_utc"])
    # If the same event was logged twice in a day, keep the lower price
    out = out.sort_values("lowest_price").drop_duplicates(["event_id", "snapshot_utc"]).sort_values("snapshot_utc")
    return out[COLUMNS]


def main():
    log_url = os.environ.get("PRICE_LOG_CSV_URL")
    events_url = os.environ.get("EVENTS_CSV_URL")
    if not (log_url and events_url):
        print("Price log import skipped (PRICE_LOG_CSV_URL / EVENTS_CSV_URL not set)")
        return

    rows = to_price_rows(fetch_csv(log_url), fetch_csv(events_url))
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    rows.to_csv(OUTPUT, index=False)
    print(f"Imported {len(rows)} logged prices for {rows['event_id'].nunique()} events "
          f"({datetime.now(timezone.utc):%Y-%m-%d %H:%M} UTC)")


if __name__ == "__main__":
    main()
