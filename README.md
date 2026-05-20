# Shizuha Oracle

Gold and Silver price forecaster with India-focused INR pricing, TradingView-style
charts, multi-timeframe technical analysis, news sentiment, and short / long-term
predictions. Runs as a fully self-contained Docker Compose stack.

![Stack](https://img.shields.io/badge/stack-Django%20%2B%20Celery%20%2B%20React-blue)
![Python](https://img.shields.io/badge/python-3.11-blue)
![Node](https://img.shields.io/badge/node-20-green)

---

## Table of Contents

- [Features](#features)
- [Quick Start](#quick-start)
- [Architecture](#architecture)
- [Tech Stack](#tech-stack)
- [Configuration](#configuration)
- [API Reference](#api-reference)
- [WebSocket](#websocket)
- [Celery Schedule](#celery-schedule)
- [Project Structure](#project-structure)
- [Development](#development)
- [Deployment Modes](#deployment-modes)
- [Disclaimer](#disclaimer)

---

## Features

**Live prices**
- Spot gold (XAU/USD) and silver (XAG/USD) via GoldAPI, with yfinance fallback
- USD/INR live exchange rate
- MCX-equivalent INR prices including import duty, AIDC, GST
- Per gram, per 10g (gold), per kg (silver) breakdowns
- 24h high/low, % change

**Charts**
- TradingView lightweight-charts candlestick with SMA 20/50/200, EMA 12/26, Bollinger Bands, volume
- Timeframes: 1m, 5m, 15m, 1h, 1D, 1W
- Recharts sub-charts for RSI (14), MACD (12/26/9), Stochastic %K

**Technical analysis**
- 15 indicators computed in pure pandas/numpy (no TA-Lib dependency)
- Composite signal score (-1.0 to +1.0) -> Strong Buy / Buy / Neutral / Sell / Strong Sell
- Dow Jones correlation panel as a risk-on / safe-haven proxy

**Predictions**
- **Short-term** (Tomorrow, Next Week, 2 Weeks): composite signal x ATR-based expected move
- **Long-term** (1M, 3M, 6M, 1Y): log-price linear regression + India seasonal bias
  (Q3 festival +1%, Q4 wedding/Dhanteras +1.5% on gold)
- Each card shows direction, price range, confidence, and a rationale list

**News & sentiment**
- Aggregates from Google News RSS + Economic Times commodities feed
- FinBERT (Hugging Face) classifies each article (Bullish / Neutral / Bearish)
- 24h / 7d / 30d sentiment scores with momentum
- Article category breakdown (GEO, FED, INDIA, RBI, INFL, ETF)

**Real-time**
- WebSocket broadcasts updated spot prices every ~3 seconds
- Frontend "LIVE" badge reflects WS connection state with auto-reconnect

**Two deployment modes**
- **Standalone / detached** (default): no auth, runs on its own
- **Federated**: gated behind a Shizuha ID JWT — see [Deployment Modes](#deployment-modes)

---

## Quick Start

```bash
git clone https://github.com/shizuha-labs/oracle.git
cd oracle
docker compose up --build
```

Then open:
- **Frontend**: <http://localhost:5173>
- **Backend API**: <http://localhost:8000/api/>

The first build takes a few minutes (PyTorch CPU wheel + the FinBERT model download).
After that, give Celery ~30-60 seconds to fetch initial data, or trigger an immediate
refresh:

```bash
curl -X POST http://localhost:8000/api/refresh/
```

To stop:

```bash
docker compose down            # keep data
docker compose down -v         # wipe SQLite + HF model cache
```

---

## Architecture

```
                     +---------------------+
                     |   React + Vite      |
                     |   (port 5173)       |
                     |   - TradingView     |
                     |   - Recharts        |
                     |   - WS auto-reconn  |
                     +----------+----------+
                                |
                       HTTP /api  +  WebSocket /ws
                                |
                     +----------+----------+
                     |   Django + DRF      |
                     |   (port 8000)       |
                     |   - REST endpoints  |
                     |   - Channels (ASGI) |
                     +----+-----+-----+----+
                          |     |     |
        +-----------------+     |     +-----------------+
        |                       |                       |
+-------+-------+      +--------+--------+      +-------+-------+
| celery-worker |      |   live_streamer |      |  celery-beat  |
|               |      | (every 3s push) |      |   (cron)      |
| refresh_prices|      | GoldAPI -> WS   |      |               |
| historical    |      |                 |      |               |
| indicators    |      +--------+--------+      +-------+-------+
| predictions   |               |                       |
| sentiment     |               |                       |
+-------+-------+               |                       |
        |                       |                       |
        +-----------+-----------+-----------+-----------+
                    |                       |
            +-------+-------+       +-------+-------+
            |  SQLite       |       |  Redis        |
            |  (./db/)      |       |  (broker +    |
            |               |       |   channels)   |
            +---------------+       +---------------+
                    |
            yfinance / GoldAPI / TwelveData / Google News
                       (external sources)
```

All four processes (`django`, `celery-worker`, `celery-beat`, `streamer`) run inside
the `backend` container under `supervisord`. Redis backs both Celery and Django
Channels. SQLite is good enough for a single-node deployment; swap to Postgres in
`settings.py` if you need concurrent-writer scale.

---

## Tech Stack

| Layer | Tech |
|---|---|
| Backend | Django 4, Django REST Framework, Django Channels (Daphne ASGI) |
| Async | Celery (worker + beat), Redis broker |
| Realtime | WebSocket via Channels, channel layer over Redis |
| DB | SQLite (default), Postgres-ready |
| Data sources | yfinance, GoldAPI, Twelve Data (optional), Google News RSS |
| ML | Hugging Face Transformers + FinBERT, PyTorch CPU |
| Frontend | React 18, Vite 5, Tailwind, React Query, axios |
| Charts | lightweight-charts (TradingView), Recharts |
| Process supervision | supervisord |

---

## Configuration

All configuration is via environment variables. Defaults are set for standalone
detached mode in `docker-compose.yaml`.

| Variable | Default | Description |
|---|---|---|
| `ORACLE_DETACHED` | `1` (standalone) | When `1`, API is open with no auth. When `0`, requires a Shizuha ID JWT. |
| `JWT_SECRET_KEY` | `oracle-dev-insecure-key` | HS256 signing key. Override in production. |
| `REDIS_URL` | `redis://redis:6379/0` | Broker + channel layer. |
| `DEBUG` | `1` | Django debug mode. Set `0` for production. |
| `TWELVEDATA_API_KEY` | _(empty)_ | Optional. Enables Twelve Data for fine-grained intraday bars. yfinance fallback if unset. |
| `HF_HOME` | `/app/hf_cache` | Hugging Face model cache (persisted in a Docker volume). |
| `VITE_API_BASE` | `/api` | Frontend axios base URL. |
| `VITE_BASE_PATH` | `/` | Vite base path for the SPA. |
| `VITE_DETACHED` | `1` (standalone) | When `1`, frontend skips Shizuha ID login redirects. |
| `VITE_API_URL` | `http://backend:8000` | Vite dev-server proxy target (used inside Docker). |

---

## API Reference

All endpoints return JSON. In detached mode, no auth header is required.

```
GET  /api/health/                              Health check
GET  /api/price/{gold|silver}/                 Current spot price + INR conversions
GET  /api/historical/{metal}/?timeframe={tf}   OHLCV bars  (tf: 1m, 5m, 15m, 1h, 1d, 1w)
GET  /api/indicators/{metal}/?timeframe={tf}   Indicator values + per-indicator signals
GET  /api/predictions/{metal}/                 All seven timeframe predictions
GET  /api/sentiment/{metal}/                   News sentiment + recent articles
POST /api/refresh/                             Trigger an immediate full refresh
```

Examples:

```bash
curl http://localhost:8000/api/price/gold/
curl 'http://localhost:8000/api/historical/silver/?timeframe=1h'
curl http://localhost:8000/api/predictions/gold/
curl -X POST http://localhost:8000/api/refresh/
```

---

## WebSocket

```
ws://localhost:8000/ws/prices/
```

Messages received from the server:

```jsonc
// every ~3s
{
  "type": "price_update",
  "timestamp": "2026-05-20T06:06:19Z",
  "metals": {
    "gold":   { "price_usd": 4473.7, "price_per_10g_inr": 139309.16, "source": "spot" },
    "silver": { "price_usd": 74.39,  "price_per_kg_inr": 231953.0,    "source": "spot" }
  }
}

// when refresh_sentiment finishes
{ "type": "sentiment_update", "metal": "gold", ... }
```

Messages the client can send:

```jsonc
{ "type": "ping" }   // server replies { "type": "pong" }
```

---

## Celery Schedule

| Task | Interval | Purpose |
|---|---|---|
| `refresh_prices` | 5 min | Current spot + USD/INR snapshot |
| `refresh_minute_bars` | 5 min | 1m and 5m OHLCV bars |
| `refresh_intraday_bars` | 15 min | 15m and 1h OHLCV bars |
| `refresh_historical_bars` | hourly (HH:05) | Daily and weekly OHLCV bars |
| `compute_all_indicators` | 15 min | All 15 indicators across all timeframes |
| `generate_all_predictions` | 30 min | Short-term + long-term predictions |
| `refresh_sentiment` | 3 hours | News fetch + FinBERT classification |

`refresh_all` chains all of the above and is what `POST /api/refresh/` triggers.

---

## Project Structure

```
oracle/
├── README.md
├── docker-compose.yaml             # standalone / detached deployment
├── backend/
│   ├── Dockerfile
│   ├── docker-entrypoint.sh        # runs makemigrations + migrate
│   ├── supervisord.conf            # supervises django + celery + streamer
│   ├── requirements.txt
│   ├── manage.py
│   ├── oraclemanager/              # Django project
│   │   ├── settings.py
│   │   ├── celery.py               # beat schedule
│   │   ├── asgi.py                 # HTTP + WebSocket routing
│   │   └── urls.py
│   └── oracle/                     # Django app
│       ├── models.py               # PriceSnapshot, PriceBar, IndicatorSnapshot, Prediction, SentimentSnapshot
│       ├── views.py                # DRF APIViews
│       ├── consumers.py            # PriceConsumer (WS)
│       ├── routing.py
│       ├── tasks.py                # Celery tasks
│       ├── serializers.py
│       ├── authentication.py       # Federated JWT (only used when ORACLE_DETACHED=0)
│       ├── middleware.py           # Service-access gate (skipped in detached mode)
│       ├── permissions.py
│       ├── management/commands/
│       │   └── run_streamer.py     # The live broadcaster
│       └── services/
│           ├── data_fetcher.py     # yfinance / GoldAPI
│           ├── twelvedata_fetcher.py
│           ├── live_streamer.py    # 3s spot loop + per-minute bar saves
│           ├── indicators.py       # 15 TA indicators in pandas
│           ├── prediction.py       # short + long-term engine
│           ├── news_fetcher.py     # Google News + Economic Times RSS
│           └── sentiment.py        # FinBERT classification
└── frontend/
    ├── Dockerfile
    ├── package.json
    ├── vite.config.js              # /api and /ws proxy to backend
    ├── tailwind.config.js
    └── src/
        ├── main.jsx
        ├── App.jsx                 # ProtectedRoute (no-op in detached mode)
        ├── pages/OraclePage.jsx
        ├── components/
        │   ├── PriceChart.jsx          # lightweight-charts candlestick
        │   ├── IndicatorSubChart.jsx   # RSI / MACD / Stoch
        │   ├── SignalTable.jsx
        │   ├── PredictionCards.jsx
        │   ├── CurrentPriceCard.jsx
        │   ├── MetalTimeframeBar.jsx
        │   └── SentimentCard.jsx
        ├── contexts/AuthContext.jsx
        ├── hooks/useLivePrices.js      # WebSocket hook with auto-reconnect
        └── services/api.js             # axios client
```

---

## Development

**Backend changes** auto-reload via Django runserver + supervisord.

**Frontend changes** auto-reload via Vite HMR.

Tail logs from the backend container:

```bash
docker compose exec backend tail -f /var/log/django/django.log
docker compose exec backend tail -f /var/log/django/celery-worker-error.log
docker compose exec backend tail -f /var/log/django/streamer-error.log
```

Open a Django shell:

```bash
docker compose exec backend python manage.py shell
```

Inspect supervisord:

```bash
docker compose exec backend supervisorctl status
docker compose exec backend supervisorctl restart streamer
```

Sanity-check the WebSocket from inside the container:

```bash
docker compose exec backend python -c "
import asyncio, websockets, json
async def t():
    async with websockets.connect('ws://localhost:8000/ws/prices/') as ws:
        await ws.send(json.dumps({'type':'ping'}))
        print(await ws.recv())
asyncio.run(t())"
```

---

## Deployment Modes

### Standalone / detached (default)

`docker-compose.yaml` sets `ORACLE_DETACHED=1` and `VITE_DETACHED=1`. No auth, runs
on its own bridge network with its own Redis. This is what you get from a fresh
`docker compose up`.

### Federated (Shizuha ID JWT)

Set `ORACLE_DETACHED=0` (and remove `VITE_DETACHED=1`), point `SHIZUHA_ID_API_URL`
at your Shizuha ID instance, and provide a real `JWT_SECRET_KEY` that matches the
ID issuer. The API will then enforce:

- a valid Bearer JWT from Shizuha ID
- the `oracle` service claim in the token's `enabled_services` (unless the user
  is `is_staff` / `is_superuser`)

The middleware that gates this lives in `oracle/middleware.py`; the DRF auth class
in `oracle/authentication.py`.

### Production notes

- Replace `JWT_SECRET_KEY` with a real secret.
- Set `DEBUG=0`.
- Consider swapping SQLite for Postgres (see `DATABASES` in `settings.py`) — the
  streamer + Celery historical refresh can occasionally collide on SQLite locks.
- Set `HF_TOKEN` if you want faster Hugging Face downloads / higher rate limits.
- Set `TWELVEDATA_API_KEY` if you want better intraday bar coverage.

---

## Disclaimer

Predictions are based on technical analysis, log-regression, and news sentiment.
They are **not financial advice**. Gold and silver prices are driven by
geopolitical events, central bank policy, real yields, currency moves, and many
other factors not captured by this model. Use at your own risk.
