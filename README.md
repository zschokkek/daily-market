# Kalshi Wordle — Guess the Daily Market

Daily Wordle-style game where you guess the **Kalshi market of the day**.

- **Pool each day:** all **Sports markets expiring today** + **any LIVE market** (in-play).
- **Columns (per spec):** `name of market` · `category` · `number of strikes` · `expiration date` · `volume`
- **Feedback:** 🟩 green = exact, 🟨 yellow = close, ⬜ gray = miss — with ▲/▼ arrows for numeric/date direction.

Built as a single static page (`index.html`) + a Python snapshot builder that talks to the same API behind Kalshi's **Market Atlas**.

## Play

```bash
cd kalshi-wordle
python3 -m http.server 8000
# http://localhost:8000
```

Or just open `index.html` directly.

## How the daily pool is built (Market Atlas)

Same source the Kalshi landing pages use:

```
GET https://api.elections.kalshi.com/trade-api/v2/events?status=open&with_nested_markets=true&limit=200
→ paginate with cursor
→ for each event.market:
    exp    = market.expected_expiration_time || market.expiration_time
    isSports = event.category == "Sports"           // Market Atlas top-level category
    isToday  = exp.slice(0,10) == todayISO
    isLive   = close_time < now < expiration_time   // any live market
    include  = (isSports && isToday) || isLive

Columns:
  name      → event.title + " — " + market.yes_sub_title
  category  → event.category + " · " + event.subcategory (e.g. Sports · MLB)
  strikes   → event.markets.length   (outcomes in that event)
  expiration→ market.expected_expiration_time (YYYY-MM-DD)
  volume    → market.volume (total $)
```

When the API is unreachable (CORS / offline) the page falls back to `pool.json` — a snapshot in the same shape — so the game stays playable. The page also tries a live `fetch` to `https://api.elections.kalshi.com/trade-api/v2/markets?status=open` on load and will show a `LIVE` badge when that succeeds.

## Refresh the snapshot

```bash
python3 fetch_markets.py   # rewrites pool.json + market_atlas.json for today
```

`fetch_markets.py` scans `…/events?status=open&with_nested_markets=true`, applies the filter above, deduplicates by ticker, and writes `pool.json`. Schedule it daily (cron / GitHub Action) for a true daily wordle.

## Daily target

Deterministic so everyone gets the same puzzle:

```js
idx = hash(todayISO + "kalshi-v1") % pool.length
target = pool[idx]
```

Stored in `localStorage` per date. Debug: `?reset=1` clears today's state, `?debug=1` adds a "new target" button.

## Files

- `index.html` — the game (no build step, Tailwind CDN)
- `pool.json` — fallback pool (snapshot from 2026-08-07; 22 markets)
- `fetch_markets.py` — rebuild pool.json from live Market Atlas / Trade API
- `market_atlas.json` — written by fetch_markets.py (pool metadata)
- `markets_raw.json` — raw `…/markets` dump from last fetch (for debugging)

