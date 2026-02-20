from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
import asyncio, os, pandas as pd, pytz
from datetime import datetime, timezone, timedelta

from backend.data_fetcher    import get_data
from backend.indicators      import ema as _ema
from backend.strategies      import list_strategies, STRATEGIES
from backend.watchlist_store import load as wl_load, add as wl_add, remove as wl_remove
from backend.news_fetcher    import fetch_news
from backend.predictor       import generate_prediction, estimate_target_time

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True,
                   allow_methods=["*"], allow_headers=["*"])

signal_history = []

# ── Timezone-aware market hours ───────────────────────────────────────────────
_TZ_NSE  = pytz.timezone('Asia/Kolkata')
_TZ_NYSE = pytz.timezone('America/New_York')
_TZ_LSE  = pytz.timezone('Europe/London')

_MARKET_HOURS = {
    'NSE':   (_TZ_NSE,  ( 9, 15), (15, 30)),
    'NYSE':  (_TZ_NYSE, ( 9, 30), (16,  0)),
    'NASDAQ':(_TZ_NYSE, ( 9, 30), (16,  0)),
    'LSE':   (_TZ_LSE,  ( 8,  0), (16, 30)),
}

def get_open_markets() -> list:
    now_utc = datetime.now(timezone.utc)
    open_m  = []
    for name, (tz, (oh, om), (ch, cm)) in _MARKET_HOURS.items():
        local = now_utc.astimezone(tz)
        if local.weekday() >= 5:
            continue
        o = local.replace(hour=oh, minute=om, second=0, microsecond=0)
        c = local.replace(hour=ch, minute=cm, second=0, microsecond=0)
        if o <= local <= c:
            open_m.append(name)
    return open_m

def is_any_market_open() -> bool:
    return len(get_open_markets()) > 0

# ── Timestamp formatting (timezone-safe) ─────────────────────────────────────
def ts_format(idx, intraday=False):
    try:
        dt = pd.Timestamp(idx)
        # Always convert to UTC first to avoid IST/UTC confusion
        if dt.tzinfo is not None:
            dt = dt.tz_convert('UTC').tz_localize(None)
        else:
            # tz-naive: yfinance may return UTC-naive or local-naive
            # For safety, treat as UTC (yfinance actually stores UTC internally)
            pass
        return int(dt.timestamp()) if intraday else dt.strftime("%Y-%m-%d")
    except:
        return str(idx)[:10]

# ─────────────────────────────────────────────────────────────────────────────
#  API — core
# ─────────────────────────────────────────────────────────────────────────────
@app.get("/api/test")
def api_test():
    return {"status": "API working ✓", "open_markets": get_open_markets()}

@app.get("/api/status")
def api_status():
    return {
        "status"      : "running",
        "signals"     : len(signal_history),
        "open_markets": get_open_markets(),
        "any_open"    : is_any_market_open(),
    }

@app.get("/api/strategies")
def api_strategies():
    return list_strategies()

# ─────────────────────────────────────────────────────────────────────────────
#  WATCHLIST (persistent JSON file)
# ─────────────────────────────────────────────────────────────────────────────
@app.get("/api/watchlist")
def api_get_watchlist():
    return wl_load()

@app.post("/api/watchlist")
def api_add_watchlist(sym: str, name: str = ""):
    return wl_add(sym, name)

@app.delete("/api/watchlist/{sym}")
def api_remove_watchlist(sym: str):
    return wl_remove(sym)

# ─────────────────────────────────────────────────────────────────────────────
#  CHART DATA
# ─────────────────────────────────────────────────────────────────────────────
@app.get("/api/chartdata")
def api_chartdata(symbol: str, interval: str = "1d", strategy: str = "pro_mtf"):
    try:
        period_map = {"1m":"7d","2m":"7d","5m":"60d","15m":"60d","30m":"60d",
                      "1h":"730d","60m":"730d","1d":"2y","1wk":"10y"}
        period   = period_map.get(interval, "2y")
        intraday = interval in ("1m","2m","5m","15m","30m","60m","1h","90m")

        df = get_data(symbol, interval, period)
        if df is None or df.empty:
            return JSONResponse({"error": f"No data for {symbol}",
                                 "candles":[],"ema9":[],"ema21":[],"ema200":[],"signals":[],"latest_signal":None})

        def ts(idx): return ts_format(idx, intraday)

        df = df.copy()
        df['_e9']  = _ema(df['Close'], 9)
        df['_e21'] = _ema(df['Close'], 21)
        df['_e200']= _ema(df['Close'], 200)
        df.dropna(subset=['Open','High','Low','Close'], inplace=True)

        candles = [{"time":ts(i),"open":round(float(r.Open),4),"high":round(float(r.High),4),
                    "low":round(float(r.Low),4),"close":round(float(r.Close),4)}
                   for i,r in df.iterrows()]
        ema9   = [{"time":ts(i),"value":round(float(r._e9),4)}   for i,r in df.iterrows() if pd.notna(r._e9)]
        ema21  = [{"time":ts(i),"value":round(float(r._e21),4)}  for i,r in df.iterrows() if pd.notna(r._e21)]
        ema200 = [{"time":ts(i),"value":round(float(r._e200),4)} for i,r in df.iterrows() if pd.notna(r._e200)]

        fn            = STRATEGIES[strategy]['fn']
        chart_signals = fn(df, ts)
        latest        = chart_signals[-1] if chart_signals else None

        if latest:
            t = estimate_target_time(df, float(latest['price']), float(latest['tp']), interval)
            latest['target_time']     = t['label']
            latest['target_datetime'] = t['datetime']
            latest['target_bars']     = t['bars']

        return JSONResponse({
            "candles":candles,"ema9":ema9,"ema21":ema21,"ema200":ema200,
            "signals":chart_signals,"latest_signal":latest,"total_signals":len(chart_signals),
        })
    except Exception as e:
        import traceback; traceback.print_exc()
        return JSONResponse({"error":str(e),"candles":[],"ema9":[],"ema21":[],"ema200":[],"signals":[],"latest_signal":None})

# ─────────────────────────────────────────────────────────────────────────────
#  LIVE PRICE TICK (for real-time updating)
# ─────────────────────────────────────────────────────────────────────────────
@app.get("/api/tick")
def api_tick(symbol: str):
    """Return latest price + change for a symbol. Lightweight, fast."""
    try:
        import yfinance as yf
        t     = yf.Ticker(symbol)
        info  = t.fast_info
        price = float(info.last_price or info.regular_market_price or 0)
        prev  = float(info.previous_close or price)
        chg   = round(price - prev, 4)
        pct   = round((chg / prev * 100) if prev else 0, 2)
        return JSONResponse({
            "symbol": symbol, "price": round(price, 4),
            "change": chg, "change_pct": pct,
            "open_markets": get_open_markets(),
        })
    except Exception as e:
        return JSONResponse({"symbol": symbol, "price": 0, "error": str(e)})

# ─────────────────────────────────────────────────────────────────────────────
#  NEWS
# ─────────────────────────────────────────────────────────────────────────────
@app.get("/api/news")
def api_news(symbols: str = ""):
    try:
        sym_list = [s.strip() for s in symbols.split(',') if s.strip()] if symbols \
                   else [w['sym'] for w in wl_load()[:8]]
        news = fetch_news(sym_list)
        return JSONResponse({"news": news, "count": len(news)})
    except Exception as e:
        return JSONResponse({"news": [], "error": str(e)})

# ─────────────────────────────────────────────────────────────────────────────
#  PREDICTION
# ─────────────────────────────────────────────────────────────────────────────
@app.get("/api/predict")
def api_predict(symbol: str, interval: str = "1d"):
    try:
        period_map = {"5m":"60d","15m":"60d","1h":"730d","1d":"2y","1wk":"10y"}
        df   = get_data(symbol, interval, period_map.get(interval,"2y"))
        if df is None or df.empty:
            return JSONResponse({"error": f"No data for {symbol}"})
        news = fetch_news([symbol], max_per_symbol=10)
        pred = generate_prediction(df, news, symbol, interval)
        return JSONResponse(pred)
    except Exception as e:
        import traceback; traceback.print_exc()
        return JSONResponse({"error": str(e)})

# ─────────────────────────────────────────────────────────────────────────────
#  WEBSOCKET — real-time price ticks + signal alerts
# ─────────────────────────────────────────────────────────────────────────────
# Track last known signal per symbol to avoid re-sending same signal
_last_signal_time: dict = {}
# Track last price per symbol for tick diffing
_last_price: dict = {}

@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    open_markets = get_open_markets()

    # Send initial market status
    await ws.send_json({
        "type"        : "status",
        "open_markets": open_markets,
        "any_open"    : bool(open_markets),
        "message"     : f"Open: {', '.join(open_markets)}" if open_markets else "All markets closed",
    })

    # Which symbol is the client currently viewing (sent by client)
    current_symbol = {"sym": None}

    async def recv_loop():
        """Receive messages from client (e.g. which symbol they're viewing)"""
        try:
            async for msg in ws.iter_json():
                if isinstance(msg, dict):
                    if msg.get("type") == "subscribe":
                        current_symbol["sym"] = msg.get("symbol")
        except Exception:
            pass

    recv_task = asyncio.create_task(recv_loop())

    try:
        tick_counter = 0
        while True:
            tick_counter += 1
            open_markets = get_open_markets()

            # ── Every tick: send price for currently viewed symbol ──────────
            sym = current_symbol["sym"]
            if sym and open_markets:
                try:
                    import yfinance as yf
                    info  = yf.Ticker(sym).fast_info
                    price = float(getattr(info, 'last_price', 0) or
                                  getattr(info, 'regular_market_price', 0) or 0)
                    if price > 0:
                        prev  = _last_price.get(sym, price)
                        chg   = round(price - prev, 4)
                        pct   = round((chg / prev * 100) if prev else 0, 2)
                        _last_price[sym] = price
                        await ws.send_json({
                            "type"        : "tick",
                            "symbol"      : sym,
                            "price"       : round(price, 4),
                            "change"      : chg,
                            "change_pct"  : pct,
                            "open_markets": open_markets,
                        })
                except Exception as e:
                    print(f"[WS tick] {sym}: {e}")

            # ── Every 60s: scan watchlist for new signals ───────────────────
            if tick_counter % 12 == 0:  # every 12 × 5s = 60s
                wl = wl_load()
                symbols_to_scan = [w['sym'] for w in wl[:10]]
                # Only scan stocks in relevant open markets
                # (skip NSE stocks when NSE is closed, etc.)
                for symbol in symbols_to_scan:
                    if not open_markets:
                        break
                    try:
                        is_nse = symbol.endswith('.NS') or symbol.endswith('.BO') or symbol in ('^NSEI','^NSEBANK','^BSESN')
                        is_us  = not is_nse and not symbol.endswith('.L')
                        market_ok = (is_nse and 'NSE' in open_markets) or \
                                    (is_us  and 'NYSE' in open_markets)  or \
                                    (not is_nse and not is_us)
                        if not market_ok:
                            continue

                        df   = get_data(symbol, "5m", "2d")
                        fn   = STRATEGIES['pro_mtf']['fn']
                        sigs = fn(df, lambda idx: ts_format(idx, True))

                        if sigs:
                            last_sig = sigs[-1]
                            sig_key  = f"{symbol}_{last_sig['time']}"
                            if _last_signal_time.get(symbol) != sig_key:
                                _last_signal_time[symbol] = sig_key
                                payload = {**last_sig, "symbol": symbol, "type_msg": "signal"}
                                signal_history.insert(0, payload)
                                if len(signal_history) > 200: signal_history.pop()
                                await ws.send_json({**payload, "type": "signal"})
                    except Exception as e:
                        print(f"[WS scan] {symbol}: {e}")

            # ── Every 300s: send market status update ───────────────────────
            if tick_counter % 60 == 0:
                open_markets = get_open_markets()
                await ws.send_json({
                    "type"        : "status",
                    "open_markets": open_markets,
                    "any_open"    : bool(open_markets),
                    "message"     : f"Open: {', '.join(open_markets)}" if open_markets else "All markets closed",
                })

            await asyncio.sleep(5)  # tick every 5 seconds

    except WebSocketDisconnect:
        recv_task.cancel()
    except Exception as e:
        print(f"[WS] error: {e}")
        recv_task.cancel()

# ─────────────────────────────────────────────────────────────────────────────
#  STATIC + CATCH-ALL (MUST BE LAST)
# ─────────────────────────────────────────────────────────────────────────────
frontend_dir = os.path.join(os.path.dirname(__file__), "frontend")

@app.get("/")
def serve_index():
    return FileResponse(os.path.join(frontend_dir, "index.html"))

@app.get("/{full_path:path}")
def catch_all(full_path: str):
    if full_path.startswith("api/"):
        return JSONResponse({"error": "Not found"}, status_code=404)
    return FileResponse(os.path.join(frontend_dir, "index.html"))