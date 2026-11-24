"""
Buy or Wait: Bay Area ticket price tracker (web app)

Run locally:   streamlit run app.py
Deploy free:   share.streamlit.io (point it at this repo and app.py)
"""

from pathlib import Path

import pandas as pd
import streamlit as st

from verdict import judge

REAL_DATA = Path("data/prices.csv")
SAMPLE_DATA = Path("data/sample_prices.csv")

st.set_page_config(page_title="Buy or Wait", page_icon="🎟️", layout="wide")


@st.cache_data(ttl=600)
def load():
    if REAL_DATA.exists():
        return pd.read_csv(REAL_DATA), False
    return pd.read_csv(SAMPLE_DATA), True


df, is_sample = load()
df["snapshot_utc"] = pd.to_datetime(df["snapshot_utc"], utc=True)
df["event_datetime_local"] = pd.to_datetime(df["event_datetime_local"], errors="coerce")

st.title("🎟️ Buy or Wait")
st.caption("Bay Area concerts, festivals, Warriors and 49ers games. Know when to buy before you overpay.")

if is_sample:
    st.warning("Showing SAMPLE data so you can see how the app works. Real prices appear once the collector has run.")

# Resale data (SeatGeek) drives the verdicts; Ticketmaster gives face value.
resale = df[df["source"] == "seatgeek"]
face = (
    df[df["source"] == "ticketmaster"]
    .sort_values("snapshot_utc")
    .groupby("title", as_index=False)
    .last()[["title", "lowest_price"]]
    .rename(columns={"lowest_price": "face_value_from"})
)
if resale.empty:
    resale = df  # fall back to whatever source we have

# ---- Filters ----
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

# ---- One card per event ----
COLORS = {"Buy now": "🟢", "Wait": "🟡", "Rising": "🔴", "Hold": "⚪", "Tracking": "🔵"}

summary = []
for event_id, history in upcoming.groupby("event_id"):
    history = history.sort_values("snapshot_utc")
    latest = history.iloc[-1]
    result = judge(history)
    summary.append({**latest.to_dict(), **result, "history": history})

if not summary:
    st.info("No upcoming events match your filters.")
    st.stop()

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

st.divider()
st.caption("Verdicts are based on price trends we've tracked, not a guarantee. Prices don't include every fee.")
