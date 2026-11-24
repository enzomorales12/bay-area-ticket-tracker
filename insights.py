"""
"When to buy" analysis
----------------------
Answers: on average, how does an event's resale price at each point
before the event compare with that event's typical price?

Each event's prices are divided by that event's own average, so a $40
indie show and a $300 Warriors game can be compared on the same scale.
100% = the event's average price. Below 100% = cheaper than usual.
"""

import pandas as pd

BUCKETS = [
    (60, 10_000, "60+ days"),
    (30, 59, "30–59 days"),
    (14, 29, "14–29 days"),
    (7, 13, "7–13 days"),
    (3, 6, "3–6 days"),
    (1, 2, "1–2 days"),
    (0, 0, "Day of"),
]
ORDER = [label for _, _, label in BUCKETS]


def bucket(days) -> str | None:
    if pd.isna(days):
        return None
    for low, high, label in BUCKETS:
        if low <= days <= high:
            return label
    return None


def price_by_timing(prices: pd.DataFrame, min_snapshots: int = 3) -> pd.DataFrame:
    """
    Returns one row per (category, timing bucket) with:
      pct_of_avg  average price as a % of each event's own average
      events      how many different events fed that number
    """
    df = prices.copy()
    df["lowest_price"] = pd.to_numeric(df["lowest_price"], errors="coerce")
    df["days_until_event"] = pd.to_numeric(df["days_until_event"], errors="coerce")
    df = df.dropna(subset=["lowest_price", "days_until_event"])
    df = df[df["days_until_event"] >= 0]

    counts = df.groupby("event_id")["lowest_price"].transform("count")
    df = df[counts >= min_snapshots]
    if df.empty:
        return pd.DataFrame(columns=["category", "timing", "pct_of_avg", "events"])

    df["relative"] = df["lowest_price"] / df.groupby("event_id")["lowest_price"].transform("mean")
    df["timing"] = df["days_until_event"].apply(bucket)

    # Average within each event first, so events with more snapshots don't dominate
    per_event = df.groupby(["category", "timing", "event_id"], as_index=False)["relative"].mean()
    out = per_event.groupby(["category", "timing"], as_index=False).agg(
        pct_of_avg=("relative", "mean"), events=("event_id", "nunique")
    )
    out["pct_of_avg"] = (out["pct_of_avg"] * 100).round(1)
    out["timing"] = pd.Categorical(out["timing"], categories=ORDER, ordered=True)
    return out.sort_values(["category", "timing"])


def best_time(table: pd.DataFrame, min_events: int = 3) -> pd.DataFrame:
    """Cheapest timing bucket per category, only where enough events back it up."""
    solid = table[table["events"] >= min_events]
    if solid.empty:
        return solid
    idx = solid.groupby("category")["pct_of_avg"].idxmin()
    return solid.loc[idx, ["category", "timing", "pct_of_avg", "events"]]
