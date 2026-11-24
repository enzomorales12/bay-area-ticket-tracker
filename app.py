"""
Buy or Wait: Bay Area ticket price tracker (web app)

Run locally:   streamlit run app.py
Deploy free:   share.streamlit.io (point it at this repo and app.py)
"""

from pathlib import Path

import pandas as pd
import streamlit as st

from insights import best_time, price_by_timing
from verdict import judge

REAL_DATA = Path("data/prices.csv")
SAMPLE_DATA = Path("data/sample_prices.csv")

st.set_page_config(page_title="Buy or Wait", page_icon="🎟️", layout="wide")


MANUAL_DATA = Path("data/manual_prices.csv")


@st.cache_data(ttl=600)
def load():
    real = [pd.read_csv(p) for p in (REAL_DATA, MANUAL_DATA) if p.exists()]
    real = [d for d in real if not d.empty]
    if real:
        return pd.concat(real, ignore_index=True), False
    return pd.read_csv(SAMPLE_DATA), True


df, is_sample = load()
df["snapshot_utc"] = pd.to_datetime(df["snapshot_utc"], utc=True)
df["event_datetime_local"] = pd.to_datetime(df["event_datetime_local"], errors="coerce")

st.title("🎟️ Buy or Wait")
st.caption("Bay Area concerts, festivals, Warriors and 49ers games. Know when to buy before you overpay.")

if is_sample:
    st.warning("Showing SAMPLE data so you can see how the app works. Real prices appear once the collector has run.")

# Resale data (SeatGeek or hand-logged) drives the verdicts; Ticketmaster gives face value.
RESALE_SOURCES = ["seatgeek", "manual"]
resale = df[df["source"].isin(RESALE_SOURCES) & df["lowest_price"].notna()]
face = (
    df[df["source"] == "ticketmaster"]
    .sort_values("snapshot_utc")
    .groupby("title", as_index=False)
    .last()[["title", "lowest_price"]]
    .rename(columns={"lowest_price": "face_value_from"})
)
if resale.empty:
    resale = df  # fall back to whatever source we have

events_tab, insights_tab = st.tabs(["🎫 Events", "📈 When to buy"])

# =====================================================================
# Events tab: one card per upcoming event with a verdict
# =====================================================================
COLORS = {"Buy now": "🟢", "Wait": "🟡", "Rising": "🔴", "Hold": "⚪", "Tracking": "🔵"}

with events_tab:
    col1, col2 = st.columns([1, 2])
    categories = sorted(resale["category"].dropna().unique())
    picked = col1.multiselect("Category", categories, default=categories)
    search = col2.text_input("Search an artist, team or venue")

    events = resale[resale["category"].isin(picked)]
    if search:
        s = search.lower()
        events = events[
            events["title"].str.lower().str.contains(s, na=False)
            | events["venue"].str.lower().str.contains(s, na=False)
        ]

    upcoming = events[events["event_datetime_local"] >= pd.Timestamp.now() - pd.Timedelta(hours=6)]

    summary = []
    for event_id, history in upcoming.groupby("event_id"):
        history = history.sort_values("snapshot_utc")
        latest = history.iloc[-1]
        summary.append({**latest.to_dict(), **judge(history), "history": history})

    if not summary:
        st.info("No upcoming events match your filters.")
    else:
        summary.sort(key=lambda e: e["event_datetime_local"])
        st.write(f"**{len(summary)} upcoming events**")

        for e in summary:
            icon = COLORS.get(e["verdict"], "⚪")
            date = e["event_datetime_local"].strftime("%a %b %d, %-I:%M %p")
            price = f"${e['lowest_price']:,.0f}" if pd.notna(e["lowest_price"]) else "n/a"
            with st.expander(f"{icon} **{e['verdict']}** · {e['title']} · {date} · from {price}"):
                left, right = st.columns([2, 1])
                chart = e["history"].set_index("snapshot_utc")[["lowest_price", "median_price"]].dropna(how="all")
                left.line_chart(chart, y_label="Price ($)")
                right.markdown(f"**{e['reason']}**")
                right.markdown(f"📍 {e['venue']}, {e['city']}")
                if pd.notna(e.get("days_until_event")):
                    right.markdown(f"⏳ {int(e['days_until_event'])} days away")
                if pd.notna(e.get("listing_count")):
                    right.markdown(f"🎫 {int(e['listing_count']):,} tickets listed")
                fv = face.loc[face["title"] == e["title"], "face_value_from"]
                if len(fv) and pd.notna(fv.iloc[0]):
                    right.markdown(f"🏷️ Face value from ${fv.iloc[0]:,.0f}")
                if isinstance(e.get("url"), str) and e["url"].startswith("http"):
                    right.link_button("View tickets", e["url"])

# =====================================================================
# Insights tab: how prices move as events get closer
# =====================================================================
with insights_tab:
    st.subheader("When is the cheapest time to buy?")
    st.write(
        "Each bar shows how an event's lowest resale price compares with that event's own average "
        "at different points before the show. **Below 100% means cheaper than usual.** "
        "Prices are normalized per event, so cheap and expensive events count equally."
    )

    table = price_by_timing(resale)
    if table.empty:
        st.info("Not enough price history yet. This fills in after a few days of collection.")
    else:
        cats = sorted(table["category"].unique())
        cat = st.selectbox("Category", cats)
        view = table[table["category"] == cat].set_index("timing")
        st.bar_chart(view["pct_of_avg"], y_label="% of the event's average price", x_label="Time before event")

        best = best_time(table)
        if not best.empty:
            st.markdown("**Cheapest time to buy so far**")
            for _, row in best.iterrows():
                diff = row["pct_of_avg"] - 100
                vs = f"{abs(diff):.0f}% {'below' if diff < 0 else 'above'} average"
                when = "Day of the event" if row["timing"] == "Day of" else f"{row['timing']} before"
                st.markdown(f"- **{row['category']}**: {when}, about {vs} (based on {row['events']} events)")
        st.caption(
            "Only events with at least 3 price checks are included, and a 'cheapest time' is shown only "
            "when at least 3 events support it. Expect these numbers to shift as more data comes in."
        )

st.divider()
st.caption("Verdicts are based on price trends we've tracked, not a guarantee. Prices don't include every fee.")
