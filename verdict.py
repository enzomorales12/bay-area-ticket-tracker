"""
Buy-or-wait rules
-----------------
Turns an event's price history into a simple verdict a friend can act on.

The rules are deliberately simple and easy to explain. Tune them as real
data comes in (for example, if day-of prices turn out to drop more than
expected for non-sellout shows).
"""

import pandas as pd

MIN_SNAPSHOTS = 3        # need at least this many price checks before judging
NEAR_LOW = 1.05          # within 5% of the lowest price seen = "good price"
TREND_WINDOW = 4         # how many recent snapshots to judge the trend on
TREND_THRESHOLD = 0.03   # 3% move counts as rising / dropping


def judge(history: pd.DataFrame) -> dict:
    """
    history: rows for ONE event from one source, sorted oldest -> newest,
    with columns lowest_price, listing_count, days_until_event.
    Returns {"verdict": ..., "reason": ...}.
    """
    prices = history["lowest_price"].dropna()
    if len(prices) < MIN_SNAPSHOTS:
        return {"verdict": "Tracking", "reason": "Not enough price history yet. Check back in a day or two."}

    current = prices.iloc[-1]
    lowest_seen = prices.min()
    recent = prices.tail(TREND_WINDOW)
    change = (recent.iloc[-1] - recent.iloc[0]) / recent.iloc[0] if recent.iloc[0] else 0

    listings = history["listing_count"].dropna()
    supply_up = len(listings) >= 2 and listings.iloc[-1] > listings.iloc[0]

    days_left = history["days_until_event"].dropna()
    days_left = int(days_left.iloc[-1]) if len(days_left) else None

    still_falling = prices.iloc[-1] < prices.iloc[-2]  # a drop that has flattened out isn't a reason to wait
    if change <= -TREND_THRESHOLD and still_falling and (days_left is None or days_left > 1):
        reason = f"Down {abs(change):.0%} over the last few checks"
        if supply_up:
            reason += " and more tickets are being listed"
        return {"verdict": "Wait", "reason": reason + ". The price may keep falling."}

    if current <= lowest_seen * NEAR_LOW:
        return {"verdict": "Buy now", "reason": f"${current:,.0f} is at or near the lowest price we've seen (${lowest_seen:,.0f})."}

    if change >= TREND_THRESHOLD:
        return {"verdict": "Rising", "reason": f"Up {change:.0%} over the last few checks. Buy soon if you're going."}

    return {"verdict": "Hold", "reason": f"Price is steady, about {current / lowest_seen - 1:.0%} above the lowest we've seen. Set an alert and wait."}
