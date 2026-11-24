"""
Creates data/sample_prices.csv: FAKE example data so the app can be
previewed before real prices are collected. Names are generic on purpose.
The app shows a "SAMPLE data" banner whenever it uses this file.
"""

import csv
import random
from datetime import datetime, timedelta, timezone
from pathlib import Path

from collector import COLUMNS

random.seed(7)
now = datetime.now(timezone.utc)

# (title, category, venue, city, start price, daily drift, days away)
EVENTS = [
    ("Sample NBA Game: Home vs Rival", "nba", "Sample Arena", "San Francisco", 140, -0.02, 6),
    ("Sample NBA Game: Home vs Contender", "nba", "Sample Arena", "San Francisco", 190, 0.01, 18),
    ("Sample NBA Game: Home vs Rebuilding Team", "nba", "Sample Arena", "San Francisco", 70, -0.03, 2),
    ("Sample NFL Game: Home vs Division Rival", "nfl", "Sample Stadium", "Santa Clara", 210, 0.015, 12),
    ("Sample NFL Game: Home vs Conference Foe", "nfl", "Sample Stadium", "Santa Clara", 160, -0.01, 5),
    ("Sample NFL Game: Home vs Visiting Team", "nfl", "Sample Stadium", "Santa Clara", 120, -0.02, 1),
    ("Sample Pop Concert", "concert", "Sample Arena", "San Jose", 95, -0.035, 3),
    ("Sample Indie Show", "concert", "Sample Theater", "Oakland", 45, 0.0, 20),
    ("Sample Hip-Hop Concert", "concert", "Sample Arena", "Oakland", 110, -0.015, 9),
    ("Sample Music Festival (Day 1)", "music_festival", "Sample Park", "San Francisco", 180, 0.03, 30),
    ("Sample Music Festival (Day 2)", "music_festival", "Sample Park", "San Francisco", 170, 0.02, 31),
    ("Sample EDM Festival", "music_festival", "Sample Fairgrounds", "San Jose", 130, -0.01, 8),
]

rows = []
for i, (title, cat, venue, city, start, drift, days_away) in enumerate(EVENTS, start=1):
    event_time = (now + timedelta(days=days_away)).replace(hour=3, minute=0, second=0, microsecond=0)
    price, listings = start, random.randint(150, 900)
    for snap in range(30, -1, -1):  # 31 snapshots, one per day
        t = now - timedelta(days=snap)
        price = max(15, price * (1 + drift + random.uniform(-0.02, 0.02)))
        listings = max(10, int(listings * (1 + (-drift) + random.uniform(-0.03, 0.03))))
        rows.append({
            "snapshot_utc": t.isoformat(timespec="minutes"),
            "source": "seatgeek",
            "event_id": f"sample-{i}",
            "title": title,
            "category": cat,
            "event_datetime_local": (event_time - timedelta(hours=8)).strftime("%Y-%m-%dT%H:%M:%S"),
            "days_until_event": days_away + snap,
            "venue": venue,
            "city": city,
            "performer": "",
            "lowest_price": round(price, 2),
            "median_price": round(price * 1.6, 2),
            "average_price": round(price * 1.9, 2),
            "highest_price": round(price * 6, 2),
            "listing_count": listings,
            "popularity": "",
            "url": "",
        })

out = Path("data/sample_prices.csv")
out.parent.mkdir(exist_ok=True)
with out.open("w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=COLUMNS)
    w.writeheader()
    w.writerows(rows)
print(f"Wrote {len(rows)} sample rows to {out}")
