# Bay Area Ticket Price Tracker

Tracks resale and face-value ticket prices for Bay Area events (Warriors, 49ers, concerts and festivals) twice a day, building a price history that answers one question: **when is the best time to buy?**

## How it works

1. `collector.py` pulls current prices from SeatGeek (resale) and Ticketmaster (face value) for events within 45 miles over the next 90 days.
2. Each run adds one row per event to `data/prices.csv`, including `days_until_event`, so you can see how prices change as the event gets closer.
3. GitHub Actions runs it automatically at about 8 AM and 6 PM Pacific, even when your laptop is off.

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

**Deploy it free:** share.streamlit.io → New app → pick this repo → main file `app.py`.

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
