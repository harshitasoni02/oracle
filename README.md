# Shizuha Predict — Gold & Silver Price Forecaster

Standalone price predictor for gold and silver with India-focused INR pricing,
TradingView-style charts, and multi-timeframe technical analysis predictions.

## Quick Start

```bash
cd predict
docker compose up --build
```

Then open:
- **Frontend**: http://localhost:5173
- **Backend API**: http://localhost:8000/api/

On first run it may take ~2–3 minutes for Celery to fetch data from Yahoo Finance.
You can trigger a manual refresh from the UI or via:

```bash
curl -X POST http://localhost:8000/api/refresh/
```

## Features

### Price Data
- Real-time gold (GC=F) and silver (SI=F) COMEX futures prices
- USD/INR live exchange rate
- INR prices: per gram, per 10g (gold), per kg (silver)
- 24h high/low and % change

### Charts (TradingView lightweight-charts)
- Candlestick OHLCV chart
- Toggle overlays: SMA 20/50/200, EMA 12/26, Bollinger Bands
- Volume bars
- Timeframes: 1D (15m bars), 1W (1h bars), 1M/3M/6M (daily), 1Y (weekly)

### Sub-charts (Recharts)
- RSI (14) with overbought/oversold zones
- MACD (12, 26, 9) with histogram
- Stochastic %K (14) with signal zones

### Technical Analysis Signals
15 indicators computed natively (pure pandas/numpy):
- **Trend**: SMA 20/50/200, EMA 12/26/50, SMA alignment
- **Momentum**: RSI (14), MACD, Stochastic (14,3), CCI (20), Williams %R (14)
- **Volatility**: Bollinger Bands (20,2), ATR (14)
- **Volume**: OBV

Composite signal score (−1.0 to +1.0) → Strong Buy / Buy / Neutral / Sell / Strong Sell

### Predictions
- **Short-term** (1D, 1W, 2W): Technical signal composite × ATR-based expected move
- **Long-term** (1M, 3M, 6M, 1Y): Linear regression on log-prices + India seasonal bias
- Each prediction shows: direction, price range, confidence %, rationale

### India Seasonality
Long-term predictions incorporate gold/silver demand seasonality:
- Q3 (festival season): +1% gold bias
- Q4 (wedding season + Dhanteras): +1.5% gold bias

## Architecture

```
predict/
├── backend/                # Django + Celery
│   ├── predictmanager/     # Django project
│   └── predictor/          # App: models, views, services
│       └── services/
│           ├── data_fetcher.py   # yfinance OHLCV + USD/INR
│           ├── indicators.py     # All TA indicators (pure pandas)
│           └── prediction.py     # Short + long term engine
└── frontend/               # React + Vite
    └── src/
        ├── pages/PredictorPage.jsx
        └── components/
            ├── PriceChart.jsx         # lightweight-charts candlestick
            ├── IndicatorSubChart.jsx  # RSI/MACD/Stoch (recharts)
            ├── SignalTable.jsx        # Composite gauge + table
            ├── PredictionCards.jsx    # Timeframe prediction cards
            ├── CurrentPriceCard.jsx   # USD + INR price display
            └── MetalTimeframeBar.jsx  # Metal/TF selector
```

## Celery Schedule

| Task | Frequency |
|------|-----------|
| Refresh current prices | Every 5 min |
| Refresh 15m/1h intraday bars | Every 15 min |
| Refresh 1d/1wk historical bars | Every 1 hour |
| Recompute all indicators | Every 15 min |
| Generate all predictions | Every 30 min |

## API Endpoints

```
GET  /api/price/{gold|silver}/                   Current price snapshot
GET  /api/historical/{metal}/?timeframe=1m        OHLCV bars
GET  /api/indicators/{metal}/?timeframe=1d        Indicator values + signals
GET  /api/predictions/{metal}/                    All timeframe predictions
POST /api/refresh/                                Trigger full data refresh
GET  /api/health/                                 Health check
```

## Disclaimer

Predictions are based on technical analysis only. Not financial advice.
Gold and silver prices are affected by geopolitical events, central bank policy,
inflation expectations, and other factors not captured here.
