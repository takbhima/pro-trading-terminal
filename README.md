# 🚀 Pro Trading Terminal — Base Version 1.0

A professional full-stack trading terminal built with FastAPI + Lightweight Charts.

---

## Features

### 📊 Chart
- Candlestick chart with EMA 9 / 21 / 200 overlays
- All intraday times shown in **IST (Asia/Kolkata)**
- Live candle updates every **5 seconds** via WebSocket (no refresh needed)
- BUY/SELL signal arrows directly on chart

### ⚡ 6 Trading Strategies
| Strategy | Signals/Day | Best For | Style |
|---|---|---|---|
| Pro MTF | 1–3 | 1D, 1W | Swing |
| VWAP + EMA | 4–6 | 5m, 15m | Intraday |
| RSI Reversal | 3–6 | 5m, 15m | Mean Reversion |
| Bollinger Breakout | 4–6 | 5m, 15m | Breakout |
| MACD Crossover | 4–6 | 15m, 1H | Trend |
| ST Scalper | 6–12 | 5m | Scalping |

### 📋 Watchlist
- Persistent across server restarts (JSON file storage)
- Live signal badges (▲ BUY / ▼ SELL) per symbol
- Add/remove symbols with modal

### 📰 News Tab
- 10+ breaking news articles from watchlist stocks
- Auto-categorized: Earnings, Policy, Geopolitical, M&A, IPO, Analyst, Risk...
- Sentiment scoring: Bullish / Bearish / Neutral

### 🤖 Predict Tab
- Combined Technical + News sentiment score
- Direction: BULLISH / BEARISH / NEUTRAL with confidence %
- Price targets (TP1, TP2, SL) based on ATR

### ⏱ Target Time
- Every signal shows estimated time to reach target
- Computed from ATR velocity × distance to target

### 🔴 Real-Time Ticks
- WebSocket sends live OHLC every 5 seconds
- Chart candle updates live (Open stays fixed, H/L/C update)
- New candle auto-appended at bar boundary
- Crypto (BTC-USD, ETH-USD) and Futures (GC=F, CL=F) work 24/7

### 🌍 Multi-Market Support
- NSE (9:15–15:30 IST)
- NYSE / NASDAQ (9:30–16:00 EST)
- LSE (8:00–16:30 GMT)
- Crypto & Futures: 24/7

---

## Setup

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Upgrade yfinance (required for news)
pip install --upgrade yfinance

# 3. Run
uvicorn main:app --host 0.0.0.0 --port 8000 --reload

# 4. Open browser
http://localhost:8000
```

---

## File Structure

```
├── main.py                    # FastAPI server, WebSocket, all API routes
├── requirements.txt
├── watchlist.json             # Auto-created, persists watchlist
├── README.md
├── backend/
│   ├── data_fetcher.py        # yfinance data with retry logic
│   ├── indicators.py          # EMA, RSI, ATR, Supertrend, crossover/under
│   ├── strategies.py          # 6 strategy implementations + registry
│   ├── news_fetcher.py        # Multi-source news (yfinance + RSS fallback)
│   ├── predictor.py           # Technical + news sentiment prediction engine
│   ├── watchlist_store.py     # JSON file persistence for watchlist
│   ├── risk.py                # Position size calculator
│   └── ai_score.py            # Signal probability scoring
└── frontend/
    └── index.html             # Single-file UI (Lightweight Charts v4)
```

---

## Supported Symbols (examples)

| Type | Symbols |
|---|---|
| Indian Indices | `^NSEI`, `^NSEBANK`, `^BSESN` |
| NSE Stocks | `RELIANCE.NS`, `HDFCBANK.NS`, `TCS.NS`, `CANBK.NS` |
| US Stocks | `AAPL`, `MSFT`, `NVDA`, `TSLA` |
| Crypto (24/7) | `BTC-USD`, `ETH-USD`, `SOL-USD` |
| Commodities | `GC=F` (Gold), `CL=F` (Crude Oil), `SI=F` (Silver) |
| Currency | `EURUSD=X`, `USDINR=X` |

---

## Key Architecture Decisions

1. **Timezone**: Backend sends UTC unix timestamps. Frontend JS adds `getTimezoneOffset() * -60` before passing to Lightweight Charts. This shows correct local time for any browser timezone.

2. **Live Candles**: WebSocket tracks bar state (O/H/L/C) per symbol per interval. `candleSeries.update()` called every 5s — LWC handles same-bar updates and new-bar creation automatically.

3. **News**: Multi-source fallback chain → yfinance `get_news()` → Yahoo RSS → Moneycontrol RSS → Reuters RSS. Always returns 10+ articles.

4. **Signals**: Each strategy function receives `ts_fn` directly, eliminating timestamp matching bugs. BUY always has TP > Price > SL; SELL always has TP < Price < SL.

---

## Version History

| Version | Date | Notes |
|---|---|---|
| 1.0 | Feb 2026 | Base version — all features stable |

---

*For educational purposes only. Not financial advice.*