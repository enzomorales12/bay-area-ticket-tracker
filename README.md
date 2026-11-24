# Bay Area Ticket Price Tracker

Tracks resale and face-value ticket prices for Bay Area events (Warriors, 49ers, concerts and festivals) twice a day, building a price history that answers one question: **when is the best time to buy?**

## How it works

1. `collector.py` pulls current prices from SeatGeek (resale) and Ticketmaster (face value) for events within 45 miles over the next 90 days.
2. Each run adds one row per event to `data/prices.csv`, including `days_until_event`, so you can see how prices change as the event gets closer.
3. GitHub Actions runs it automatically at about 8 AM and 6 PM Pacific, even when your laptop is off.

> **Data source status (Nov 2026):** SeatGeek's public API returns event details but leaves the price fields empty for new developer keys, so resale prices need another source. Ticketmaster face-value prices still work. See the project notes for the options being considered.

## Setup

1. **Get API keys (free)**
   - SeatGeek: sign up at the SeatGeek developer platform and create an app to get a **client ID**.
   - Ticketmaster: register at developer.ticketmaster.com to get an **API key** (Consumer Key).
2. **Create a GitHub repo** and upload these files, keeping the `.github/workflows` folder.
3. **Add your keys as secrets:** repo **Settings → Secrets and variables → Actions → New repository secret**
   - `SEATGEEK_CLIENT_ID`
   - `TICKETMASTER_API_KEY`
4. **Test it:** **Actions** tab → **Collect ticket prices** → **Run workflow**. After it finishes, `data/prices.csv` should appear in the repo.

## The Buy or Wait app

`app.py` is a Streamlit web app that shows each upcoming event with its price history and a verdict:

- 🟢 **Buy now**: at or near the lowest price tracked
- 🟡 **Wait**: price is dropping, often with more tickets being listed
- 🔴 **Rising**: price is climbing, so buy soon if you're going
- ⚪ **Hold**: steady price, so set an alert and wait
- 🔵 **Tracking**: not enough history yet

The rules live in `verdict.py` and are meant to be tuned as real data comes in. Until `data/prices.csv` exists, the app shows clearly labeled sample data (`data/sample_prices.csv`, made by `make_sample_data.py`).

The **When to buy** tab compares each event's price at different points before the show (60+ days out, 30–59, 14–29, 7–13, 3–6, 1–2, day of) against that event's own average. That makes it possible to test whether presale or day-of really is the cheapest time to buy.

**Deploy it free:** share.streamlit.io → New app → pick this repo → main file `app.py`.

## Price alerts

`alerts.py` runs after each collection and emails friends when an event they're watching drops to their target price. It's **off by default** and only prints what it would send until you turn it on:

1. Put the watchlist in a secret named `WATCHLIST_CSV` (same columns as `watchlist.csv`). Don't put real emails in `watchlist.csv`, because this repo is public.
2. Add secrets `ALERT_EMAIL_FROM` (a Gmail address) and `ALERT_EMAIL_PASSWORD` (a Gmail app password).
3. Add a repo **variable** `ALERTS_ENABLED` = `true`.

Each friend gets at most one alert per event per day. The sent log stores a one-way code instead of email addresses.

## Tests

```bash
pip install pytest
python -m pytest -q
```

## Run it on your own computer (optional)

```bash
pip install -r requirements.txt
export SEATGEEK_CLIENT_ID=your_id
export TICKETMASTER_API_KEY=your_key
python collector.py
streamlit run app.py
```

## Changing what it tracks

All settings are at the top of `collector.py`: search area, how many days ahead, and which categories.
