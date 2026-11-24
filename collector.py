"""
Ticket Price Collector
----------------------
Saves a snapshot of ticket prices for upcoming Bay Area events
(Warriors, 49ers, concerts, festivals) to data/prices.csv.

Run it once a day (GitHub Actions does this automatically) and the CSV
slowly becomes a price history you can analyze: how prices move as the
event gets closer.

Sources:
  - SeatGeek   -> resale prices (lowest, median, average, highest, # of listings)
  - Ticketmaster -> face-value price range (what the original ticket cost)

API keys are read from environment variables so they never live in the code:
  SEATGEEK_CLIENT_ID
  TICKETMASTER_API_KEY   (optional)
"""

import csv
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

# ---------------------------------------------------------------------------
# Settings you can change
# ---------------------------------------------------------------------------

# Center of the search area (roughly between San Francisco and San Jose)
LAT, LON = 37.55, -122.15
RADIUS_MILES = 45

# Only look this many days ahead
DAYS_AHEAD = 90

# SeatGeek categories to track
SEATGEEK_TYPES = ["nba", "nfl", "concert", "music_festival"]

# Ticketmaster categories to track
TICKETMASTER_CLASSES = ["Music", "Sports"]

OUTPUT_FILE = Path("data/prices.csv")

COLUMNS = [
    "snapshot_utc",       # when this price was collected
    "source",             # seatgeek or ticketmaster
    "event_id",
    "title",
    "category",
    "event_datetime_local",
    "days_until_event",   # the key column for "when should I buy?"
    "venue",
    "city",
    "performer",
    "lowest_price",
    "median_price",
    "average_price",
    "highest_price",
    "listing_count",
    "popularity",
    "url",
]

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

NOW = datetime.now(timezone.utc)


def days_until(local_datetime_text):
    """How many days from now until the event (rounded down)."""
    if not local_datetime_text:
        return ""
    try:
        event_time = datetime.fromisoformat(local_datetime_text[:19])
    except ValueError:
        return ""
    # Bay Area is UTC-8 / UTC-7; using -8 is close enough for whole days.
    now_local = (NOW - timedelta(hours=8)).replace(tzinfo=None)
    return (event_time - now_local).days


# ---------------------------------------------------------------------------
# SeatGeek (resale prices)
# ---------------------------------------------------------------------------


def fetch_seatgeek(client_id):
    rows = []
    end_date = (NOW + timedelta(days=DAYS_AHEAD)).strftime("%Y-%m-%d")

    for event_type in SEATGEEK_TYPES:
        page = 1
        while True:
            response = requests.get(
                "https://api.seatgeek.com/2/events",
                params={
                    "client_id": client_id,
                    "lat": LAT,
                    "lon": LON,
                    "range": f"{RADIUS_MILES}mi",
                    "taxonomies.name": event_type,
                    "datetime_utc.lte": end_date,
                    "per_page": 100,
                    "page": page,
                },
                timeout=30,
            )
            response.raise_for_status()
            data = response.json()
            events = data.get("events", [])

            for e in events:
                stats = e.get("stats") or {}
                venue = e.get("venue") or {}
                performers = e.get("performers") or [{}]
                rows.append({
                    "snapshot_utc": NOW.isoformat(timespec="minutes"),
                    "source": "seatgeek",
                    "event_id": e.get("id"),
                    "title": e.get("title"),
                    "category": event_type,
                    "event_datetime_local": e.get("datetime_local"),
                    "days_until_event": days_until(e.get("datetime_local")),
                    "venue": venue.get("name"),
                    "city": venue.get("city"),
                    "performer": performers[0].get("name"),
                    "lowest_price": stats.get("lowest_price"),
                    "median_price": stats.get("median_price"),
                    "average_price": stats.get("average_price"),
                    "highest_price": stats.get("highest_price"),
                    "listing_count": stats.get("listing_count"),
                    "popularity": e.get("score"),
                    "url": e.get("url"),
                })

            total = (data.get("meta") or {}).get("total", 0)
            if page * 100 >= total or not events:
                break
            page += 1

    return rows


# ---------------------------------------------------------------------------
# Ticketmaster (face-value price range)
# ---------------------------------------------------------------------------


def fetch_ticketmaster(api_key):
    rows = []
    end_time = (NOW + timedelta(days=DAYS_AHEAD)).strftime("%Y-%m-%dT%H:%M:%SZ")

    for classification in TICKETMASTER_CLASSES:
        page = 0
        while True:
            response = requests.get(
                "https://app.ticketmaster.com/discovery/v2/events.json",
                params={
                    "apikey": api_key,
                    "latlong": f"{LAT},{LON}",
                    "radius": RADIUS_MILES,
                    "unit": "miles",
                    "classificationName": classification,
                    "endDateTime": end_time,
                    "size": 200,
                    "page": page,
                },
                timeout=30,
            )
            response.raise_for_status()
            data = response.json()
            events = (data.get("_embedded") or {}).get("events", [])

            for e in events:
                price = (e.get("priceRanges") or [{}])[0]
                venue = ((e.get("_embedded") or {}).get("venues") or [{}])[0]
                start = (e.get("dates") or {}).get("start") or {}
                local_dt = ""
                if start.get("localDate"):
                    local_dt = f"{start['localDate']}T{start.get('localTime', '00:00:00')}"
                rows.append({
                    "snapshot_utc": NOW.isoformat(timespec="minutes"),
                    "source": "ticketmaster",
                    "event_id": e.get("id"),
                    "title": e.get("name"),
                    "category": classification.lower(),
                    "event_datetime_local": local_dt,
                    "days_until_event": days_until(local_dt),
                    "venue": venue.get("name"),
                    "city": (venue.get("city") or {}).get("name"),
                    "performer": "",
                    "lowest_price": price.get("min"),
                    "median_price": "",
                    "average_price": "",
                    "highest_price": price.get("max"),
                    "listing_count": "",
                    "popularity": "",
                    "url": e.get("url"),
                })

            page_info = data.get("page") or {}
            # Ticketmaster stops paging after 1,000 results
            if page + 1 >= page_info.get("totalPages", 0) or (page + 1) * 200 >= 1000:
                break
            page += 1

    return rows


# ---------------------------------------------------------------------------
# Save
# ---------------------------------------------------------------------------


def save(rows):
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    is_new_file = not OUTPUT_FILE.exists()
    with OUTPUT_FILE.open("a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNS)
        if is_new_file:
            writer.writeheader()
        writer.writerows(rows)


def main():
    all_rows = []

    seatgeek_id = os.environ.get("SEATGEEK_CLIENT_ID")
    if seatgeek_id:
        sg_rows = fetch_seatgeek(seatgeek_id)
        print(f"SeatGeek: {len(sg_rows)} events")
        all_rows += sg_rows
    else:
        print("SeatGeek skipped (no SEATGEEK_CLIENT_ID set)")

    tm_key = os.environ.get("TICKETMASTER_API_KEY")
    if tm_key:
        tm_rows = fetch_ticketmaster(tm_key)
        print(f"Ticketmaster: {len(tm_rows)} events")
        all_rows += tm_rows
    else:
        print("Ticketmaster skipped (no TICKETMASTER_API_KEY set)")

    if not all_rows:
        raise SystemExit("No data collected. Check that your API keys are set.")

    # Keep one row per event per run, in case an event shows up in two categories
    unique = {}
    for row in all_rows:
        unique.setdefault((row["source"], row["event_id"]), row)
    all_rows = list(unique.values())

    save(all_rows)
    print(f"Saved {len(all_rows)} rows to {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
