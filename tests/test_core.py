"""Run with:  python -m pytest -q"""

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from alerts import find_alerts, matches, person_id  # noqa: E402
from insights import best_time, bucket, price_by_timing  # noqa: E402
from verdict import judge  # noqa: E402


def history(prices, listings=None, days=10):
    n = len(prices)
    return pd.DataFrame({
        "lowest_price": prices,
        "listing_count": listings or [100] * n,
        "days_until_event": list(range(days + n - 1, days - 1, -1)),
    })


# ---- verdict.py ----------------------------------------------------------

def test_not_enough_data_is_tracking():
    assert judge(history([100, 98]))["verdict"] == "Tracking"


def test_falling_price_says_wait():
    assert judge(history([100, 95, 90, 85], listings=[100, 120, 140, 160]))["verdict"] == "Wait"


def test_at_lowest_price_says_buy():
    assert judge(history([120, 110, 100, 100, 100]))["verdict"] == "Buy now"


def test_rising_price_says_rising():
    assert judge(history([80, 90, 100, 110]))["verdict"] == "Rising"


def test_day_of_drop_does_not_say_wait():
    # One day out there's no time left to wait
    result = judge(history([100, 95, 90, 85], days=0))
    assert result["verdict"] != "Wait"


# ---- insights.py ---------------------------------------------------------

def test_buckets():
    assert bucket(0) == "Day of"
    assert bucket(2) == "1–2 days"
    assert bucket(45) == "30–59 days"
    assert bucket(None) is None


def test_price_by_timing_normalizes_per_event():
    rows = []
    for ev, base in [("a", 50), ("b", 500), ("c", 100)]:
        for d, mult in [(20, 1.2), (5, 1.0), (0, 0.8)]:
            rows.append({"event_id": ev, "category": "concert", "days_until_event": d, "lowest_price": base * mult})
    table = price_by_timing(pd.DataFrame(rows))
    day_of = table[table["timing"] == "Day of"]["pct_of_avg"].iloc[0]
    assert day_of == 80.0  # cheap and expensive events count equally
    assert best_time(table).iloc[0]["timing"] == "Day of"


# ---- alerts.py -----------------------------------------------------------

def test_title_matching_needs_every_word():
    assert matches("NBA Cup: Sacramento Kings at Golden State Warriors", "warriors kings")
    assert not matches("Lakers at Golden State Warriors", "warriors kings")


def test_alert_fires_once_per_day():
    prices = pd.DataFrame([{
        "source": "seatgeek", "event_id": 1, "title": "Kings at Warriors", "venue": "Chase Center",
        "event_datetime_local": "2026-12-01T19:00:00", "days_until_event": 5,
        "lowest_price": 55, "url": "https://example.com", "snapshot_utc": "2026-11-24T16:00",
    }])
    watch = pd.DataFrame([{"name": "Sam", "email": "sam@example.com", "event_search": "warriors kings",
                           "target_price": 60, "active": "yes"}])
    first = find_alerts(prices, watch, set())
    assert len(first) == 1
    assert find_alerts(prices, watch, {first[0]["key"]}) == []
    assert "@" not in first[0]["key"][0]  # the log never stores the raw email
    assert first[0]["key"][0] == person_id("SAM@example.com ")


def test_inactive_watch_is_skipped():
    prices = pd.DataFrame([{"source": "seatgeek", "event_id": 1, "title": "Kings at Warriors",
                            "days_until_event": 5, "lowest_price": 10, "snapshot_utc": "x"}])
    watch = pd.DataFrame([{"name": "Sam", "email": "s@x.com", "event_search": "warriors",
                           "target_price": 60, "active": "no"}])
    assert find_alerts(prices, watch, set()) == []
