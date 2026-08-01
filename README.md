# Macro Intelligence AI

Institutional-grade macro intelligence for Gold (XAU/USD) and Nasdaq (NQ) —
Treasury yields, interest-rate expectations, macro news, DXY, ICT price
action, and an AI decision layer, on a free-tier infrastructure stack.

## Status — every module implemented

| # | Module | What it does |
|---|---|---|
| 1 | Treasury Intelligence Engine | 3M-30Y par yields + 10Y-2Y / 10Y-3M spreads from FRED |
| 2 | Interest Rate Intelligence Engine | Fed funds rate, SOFR, and a 2Y-yield-derived rate-expectation signal |
| 3 | Economic News Intelligence Engine | Currents API headlines (keyword sentiment) + FRED release calendar |
| 4 | DXY Forecast Engine | FRED broad dollar index + a disclosed OLS trend forecast |
| 5 | ICT Analysis Engine | Swings, fair value gaps, liquidity sweeps, structure shifts, order blocks |
| 6 | AI Decision Engine | Transparent rules-based synthesis of every module above |
| 7 | Historical Learning Engine | Grades past AI decisions against what price actually did |
| 8 | Dashboard | Live summary of every module |
| 9 | User Authentication | Supabase email/password (browser client + SSR session refresh) |
| 10 | Settings | Risk tolerance, watchlist, theme — direct-to-Supabase, RLS-scoped |
| 11 | Notifications | In-app only (see "Honest limits" below) — no email/SMS/push |
| 12 | Performance Analytics | Win rate, average PnL, max drawdown |
| — | **Top-Down Analysis** *(added)* | Big Picture / Intermediate / Short-Term framework — see below |

Nothing here is a mock — every module hits a real free API or reads real
rows a scheduled job put in Supabase. Where a method is intentionally
simple (the DXY forecast, the AI Decision Engine's scoring, the news
sentiment tagging), the code and this README say so directly rather than
implying more sophistication than is actually there.

## Top-Down Analysis

The classic three-perspective framework, added as its own module
(`/top-down`) on top of the 12 above — narrowing from macro to execution:

**Big picture**
1. Macro market analysis — inflationary / disinflationary / deflationary,
   from FRED's CPI (CPIAUCSL) year-over-year trend
2. Interest rate analysis — higher / lower / unexpected-change / steady,
   extending the Rates engine's 2Y-vs-funds-rate read with a check for a
   discrete recent Fed move that contradicts what was priced in beforehand
3. Inter-market analysis — a free broad commodity index (IMF's Global
   Price Index of All Commodities via FRED, `PALLFNFINDEXM` — the same
   kind of official free proxy DXY already uses) plus USDX (reusing the
   DXY engine's own trend read)
4. Seasonal influences — monthly average return and win rate computed
   directly from our own stored price history, not a lookup table

**Intermediate**
1. Top-down analysis — monthly, weekly, and daily structural bias, by
   resampling our stored daily bars and rerunning the exact same
   swing/market-structure-shift detectors the ICT engine uses on daily
   bars — one method, three lenses
2. COT data — CFTC's Commitment of Traders report (Legacy Futures Only),
   pulled from their public Socrata API. No key needed.
3. Market sentiment — combines News engine headline sentiment with COT
   net-speculator positioning into one read

**Short-term**
1. Correlation analysis — 60-day return correlation across Gold, Nasdaq
   (QQQ), USDX, and the 10Y Treasury yield
2. Time and price theory — previous day/week/month high-low levels (the
   real "price" component) plus a day-of-week return tendency (the
   honest "time" component our daily-bar data supports — true ICT
   kill-zone timing needs intraday bars, a paid tier; see the ICT engine's
   own scope note)
3. IPDA — the Interbank Price Delivery Algorithm concept, operationalized
   as rolling 20/40/60-day high-low ranges with today's close classified
   against each one

No new API keys needed for any of this — it's built entirely on FRED
(already have a key), the CFTC's free public API, and our own stored
data. One infrastructure change came with it: ICT and Historical Learning
used to call Twelve Data live on every refresh; both now read from a
shared `market_prices` table (populated by `POST /api/market-data/refresh`)
so Twelve Data only gets hit once per cycle instead of twice-plus.

## Honest limits — read this before you rely on any of it

- **Notifications are in-app only.** They're rows in a `notifications`
  table you see when you open `/notifications`. There is no email, SMS,
  or push delivery wired up — adding one (e.g. Resend's free tier for
  email) is a clean follow-on, not part of this build.
- **NQ is proxied with QQQ.** Real Nasdaq-100 futures data is a paid feed
  on every provider with a free tier we found. QQQ (the Nasdaq-100 ETF)
  moves with the same underlying index and is what the ICT and
  Historical Learning engines actually analyze for "NQ."
- **The DXY forecast is a disclosed linear trend extrapolation** (OLS fit
  + confidence band from the residual spread), not a proprietary model.
  It's the honest baseline any real forecasting effort gets compared
  against.
- **The AI Decision Engine is a rules-based weighted score, not an LLM
  call or a trained model.** Every weight is a constant in
  `ai_decision_service.py` you can read and change. An optional
  LLM-generated rationale is sketched (commented out) at the bottom of
  that file — it needs your own paid Anthropic API key, so it's opt-in.
- **News sentiment is a keyword heuristic**, not NLP. It counts hits from
  a small positive/negative macro lexicon.
- **ICT timeframe is daily bars.** Intraday (1H/4H) ICT setups are more
  true to how the methodology is usually traded, but polling that
  frequently needs a paid market-data tier — daily is what fits inside
  Twelve Data's free 800-requests/day budget alongside everything else.
- **The "CRB index" is FRED's Global Price Index of All Commodities**,
  an IMF-sourced broad commodity proxy — not a license to the actual
  Refinitiv/CoreCommodity CRB Index, which isn't free.
- **COT data matches contracts by a `LIKE` pattern** on the CFTC's market
  name field (e.g. `%GOLD%COMMODITY EXCHANGE%`), not an exact string, since
  the exact naming can vary by report vintage — check `cot_positioning.market_name`
  after your first refresh to confirm it matched the contract you expect.
- **Seasonality and correlation confidence scale with however much price
  history Twelve Data actually returns** on the first `market-data/refresh`
  call — more years sampled means a more meaningful monthly average, and
  `years_sampled` in the API response says exactly how many you have.
- This is decision-support software, not financial advice — see the
  footer disclaimer that appears on every page.

## Stack

Next.js 16 (App Router) + TypeScript + Tailwind + TradingView Lightweight
Charts · FastAPI · Supabase (Postgres, Auth, Realtime) · Render (backend
hosting, free) · Vercel (frontend hosting, free) · GitHub Actions (CI +
scheduled refresh).

**Free-tier realities worth knowing:**
- Render's free web service sleeps after 15 minutes idle (30-60s cold
  start). The scheduled-refresh GitHub Action pings it hourly, which
  doubles as the data refresh.
- Supabase free projects pause after 7 days with no API requests — same
  hourly ping prevents that.
- Vercel's Hobby plan is personal/non-commercial use only per its Terms
  of Service — fine here, Pro ($20/mo) only if this gets monetized.
- Render's free Postgres is *not* used — Supabase is the only database.

## Local development

**Prerequisites:** Python 3.12+, Node 22+, and four free accounts/keys:
[Supabase](https://supabase.com),
[FRED](https://fred.stlouisfed.org/docs/api/api_key.html),
[Twelve Data](https://twelvedata.com),
[Currents API](https://currentsapi.services).

**1. Supabase** — create a project, then run all four files in
`supabase/migrations/` **in order** (0001, 0002, 0003, 0004) in the SQL
editor. Copy the Project URL, `anon` key, and `service_role` key from
Project Settings → API.

**2. Backend**
```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # fill in every key from the Prerequisites section
uvicorn app.main:app --reload
```
Seed every table once, in dependency order (the scheduler does this
automatically afterward, but the tables start empty):
```bash
TOKEN="<value of REFRESH_TOKEN in your .env>"
for m in treasury rates dxy news market-data ict top-down ai-decision history performance notifications; do
  curl -X POST "http://localhost:8000/api/$m/refresh" -H "X-Refresh-Token: $TOKEN"
done
```
Run the test suite: `pytest -v` (uses respx to mock every external API —
no real keys or network access needed for tests to pass).

**3. Frontend**
```bash
cd frontend
npm install
cp .env.example .env.local   # Supabase URL + anon key + backend URL
npm run dev
```
Open http://localhost:3000. Sign up for an account (top-level `/signup`)
to see Settings and Notifications — everything else is public-read.

## Deploying

- **Backend → Render:** New → Web Service → connect this repo → Render
  auto-detects `backend/render.yaml`. Set every env var from
  `backend/.env.example` in the Render dashboard.
- **Frontend → Vercel:** Import this repo → root directory `frontend` →
  set the three env vars from `frontend/.env.example`.
- **GitHub Actions:** add repo secrets `BACKEND_URL` (your Render URL) and
  `REFRESH_TOKEN` (must match the backend's env var) so
  `scheduled-refresh.yml` can run the full refresh chain hourly.
- After the first deploy, run the same seed loop from step 2 above once
  against your live `BACKEND_URL` — the hourly schedule takes it from
  there.

## Where to go from here

The obvious next layer, roughly in order of effort: real push/email
notification delivery, intraday ICT timeframes (needs a paid data tier),
an LLM-generated AI Decision rationale (needs `ANTHROPIC_API_KEY`, sketch
already in `ai_decision_service.py`), and OAuth login alongside
email/password. None of these are required for the app to work end to
end today.
