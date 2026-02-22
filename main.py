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
from backend.trade_manager   import TradeManager

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True,
                   allow_methods=["*"], allow_headers=["*"])

trade_manager    = TradeManager()
signal_history   = []
_last_signal_key: dict = {}
_last_price:      dict = {}
_bar_state:       dict = {}
_ws_clients: list = []

_INTERVAL_MINUTES = {
    '1m':1,'2m':2,'5m':5,'15m':15,'30m':30,
    '60m':60,'1h':60,'1d':1440,'1wk':10080
}

def _floor_bar(unix_ts: int, interval_min: int) -> int:
    return (unix_ts // (interval_min * 60)) * (interval_min * 60)

_IST  = pytz.timezone('Asia/Kolkata')
_EST  = pytz.timezone('America/New_York')
_UTC  = pytz.utc

_MARKET_HOURS = {
    'NSE':    (_IST, ( 9, 15), (15, 30)),
    'NYSE':   (_EST, ( 9, 30), (16,  0)),
    'NASDAQ': (_EST, ( 9, 30), (16,  0)),
    'LSE':    (pytz.timezone('Europe/London'), (8, 0), (16, 30)),
}
_CRYPTO_SYMS = {'BTC-USD','ETH-USD','BNB-USD','SOL-USD','XRP-USD',
                'DOGE-USD','GC=F','SI=F','CL=F','NG=F'}

def get_open_markets():
    now = datetime.now(timezone.utc)
    out = []
    for name, (tz, (oh, om), (ch, cm)) in _MARKET_HOURS.items():
        local = now.astimezone(tz)
        if local.weekday() >= 5: continue
        o = local.replace(hour=oh, minute=om, second=0, microsecond=0)
        c = local.replace(hour=ch, minute=cm, second=0, microsecond=0)
        if o <= local <= c:
            out.append(name)
    return out

def is_symbol_tradeable(sym: str, open_markets: list) -> bool:
    if sym in _CRYPTO_SYMS: return True
    if sym.endswith('=F'):  return True
    is_nse = sym.endswith('.NS') or sym.endswith('.BO') or sym in ('^NSEI','^NSEBANK','^BSESN')
    is_us  = not is_nse and '.' not in sym.replace('-','') and not sym.startswith('^')
    if is_nse and 'NSE' in open_markets: return True
    if is_us  and 'NYSE' in open_markets: return True
    if open_markets: return True
    return False

def ts_format(idx, intraday: bool = False):
    try:
        dt = pd.Timestamp(idx)
        if intraday:
            if dt.tzinfo is not None:
                dt = dt.tz_convert('UTC').tz_localize(None)
            return int(dt.timestamp())
        else:
            if dt.tzinfo is not None:
                dt = dt.tz_convert('UTC').tz_localize(None)
            return dt.strftime('%Y-%m-%d')
    except Exception:
        return str(idx)[:10]


# ── API ───────────────────────────────────────────────────────────────────────
@app.get("/api/test")
def api_test():
    return {"status": "ok", "open_markets": get_open_markets(),
            "server_tz": "UTC", "display_tz": "Asia/Kolkata"}

@app.get("/api/status")
def api_status():
    return {"open_markets": get_open_markets(), "signals": len(signal_history),
            "active_trades": len(trade_manager.get_all_active())}

@app.get("/api/strategies")
def api_strategies():
    return list_strategies()

@app.get("/api/watchlist")
def api_get_watchlist():
    return wl_load()

@app.post("/api/watchlist")
def api_add_watchlist(sym: str, name: str = ""):
    return wl_add(sym, name)

@app.delete("/api/watchlist/{sym}")
def api_del_watchlist(sym: str):
    return wl_remove(sym)


# ── Trade endpoints ───────────────────────────────────────────────────────────
@app.get("/api/trade/{symbol}")
def api_get_trade(symbol: str):
    t = trade_manager.get_active(symbol)
    return JSONResponse({"trade": t})

@app.delete("/api/trade/{symbol}")
def api_close_trade(symbol: str, price: float = 0):
    if not price:
        try:
            import yfinance as yf
            info  = yf.Ticker(symbol).fast_info
            price = float(getattr(info,'last_price',None) or
                          getattr(info,'regular_market_price',None) or 0)
        except Exception:
            pass
    t = trade_manager.get_active(symbol)
    if not t:
        return JSONResponse({"error": "No active trade for this symbol"}, status_code=404)
    if not price:
        price = t['entry_price']
    ev = trade_manager.force_close(symbol, price, 'Manual Close')
    return JSONResponse({"exit": ev})

@app.get("/api/trade/{symbol}/history")
def api_trade_history(symbol: str):
    return JSONResponse({"history": trade_manager.get_history(symbol)})

@app.get("/api/trades/active")
def api_all_active():
    return JSONResponse({"trades": trade_manager.get_all_active()})


# ── Chart data ────────────────────────────────────────────────────────────────
@app.get("/api/chartdata")
def api_chartdata(symbol: str, interval: str = "1d", strategy: str = "pro_mtf"):
    try:
        period_map = {"1m":"7d","2m":"7d","5m":"60d","15m":"60d","30m":"60d",
                      "1h":"730d","60m":"730d","1d":"2y","1wk":"10y"}
        period   = period_map.get(interval, "2y")
        intraday = interval not in ("1d", "1wk")

        df = get_data(symbol, interval, period)
        if df is None or df.empty:
            return JSONResponse({"error": f"No data for {symbol}",
                                 "candles":[], "ema9":[], "ema21":[], "ema200":[],
                                 "signals":[], "latest_signal": None, "active_trade": None})

        def ts(idx): return ts_format(idx, intraday)

        df = df.copy()
        df['_e9']  = _ema(df['Close'], 9)
        df['_e21'] = _ema(df['Close'], 21)
        df['_e200']= _ema(df['Close'], 200)
        df.dropna(subset=['Open','High','Low','Close'], inplace=True)

        candles = [{"time": ts(i), "open":round(float(r.Open),4),
                    "high":round(float(r.High),4), "low":round(float(r.Low),4),
                    "close":round(float(r.Close),4)} for i, r in df.iterrows()]

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
            # Open trade if none active for this symbol
            if trade_manager.get_active(symbol) is None:
                trade_manager.open_trade(latest, symbol, strategy, interval)

        active_trade = trade_manager.get_active(symbol)

        return JSONResponse({
            "candles": candles, "ema9": ema9, "ema21": ema21, "ema200": ema200,
            "signals": chart_signals, "latest_signal": latest,
            "total_signals": len(chart_signals),
            "active_trade": active_trade,
        })
    except Exception as e:
        import traceback; traceback.print_exc()
        return JSONResponse({"error": str(e), "candles":[], "ema9":[], "ema21":[],
                             "ema200":[], "signals":[], "latest_signal": None,
                             "active_trade": None})


# ── News ──────────────────────────────────────────────────────────────────────
@app.get("/api/news")
def api_news(symbols: str = ""):
    try:
        sym_list = [s.strip() for s in symbols.split(',') if s.strip()] if symbols \
                   else [w['sym'] for w in wl_load()[:8]]
        return JSONResponse({"news": fetch_news(sym_list), "count": len(fetch_news(sym_list))})
    except Exception as e:
        return JSONResponse({"news": [], "error": str(e)})

@app.get("/api/predict")
def api_predict(symbol: str, interval: str = "1d"):
    try:
        period_map = {"5m":"60d","15m":"60d","1h":"730d","1d":"2y","1wk":"10y"}
        df   = get_data(symbol, interval, period_map.get(interval, "2y"))
        if df is None or df.empty:
            return JSONResponse({"error": f"No data for {symbol}"})
        news = fetch_news([symbol], max_per_symbol=10)
        return JSONResponse(generate_prediction(df, news, symbol, interval))
    except Exception as e:
        import traceback; traceback.print_exc()
        return JSONResponse({"error": str(e)})


# ── WebSocket ─────────────────────────────────────────────────────────────────
@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket):
    await ws.accept()
    _ws_clients.append(ws)

    open_markets     = get_open_markets()
    current_symbol   = {"sym": None}
    current_interval = {"iv": "5m"}
    tick_count       = 0

    await ws.send_json({
        "type": "status", "open_markets": open_markets, "any_open": bool(open_markets),
        "message": f"Open: {', '.join(open_markets)}" if open_markets
                   else "Markets closed — crypto & futures still live",
    })

    async def recv_msgs():
        while True:
            try:
                msg = await asyncio.wait_for(ws.receive_json(), timeout=0.1)
                if isinstance(msg, dict) and msg.get("type") == "subscribe":
                    current_symbol["sym"] = msg.get("symbol", "").strip()
                    current_interval["iv"] = msg.get("interval", "5m")
                    _bar_state.pop(f"{current_symbol['sym']}_{current_interval['iv']}", None)
            except asyncio.TimeoutError:
                pass
            except Exception:
                break

    recv_task = asyncio.create_task(recv_msgs())

    try:
        while True:
            tick_count  += 1
            open_markets = get_open_markets()
            sym          = current_symbol["sym"]

            # ── Price tick every 5 s ──────────────────────────────────────────
            if sym:
                tradeable = is_symbol_tradeable(sym, open_markets)
                if tradeable:
                    try:
                        import yfinance as yf
                        from datetime import timezone as _tz

                        info  = yf.Ticker(sym).fast_info
                        price = float(getattr(info, 'last_price', None) or
                                      getattr(info, 'regular_market_price', None) or 0)

                        if price > 0:
                            prev_close = float(getattr(info, 'previous_close', price) or price)
                            chg  = round(price - prev_close, 4)
                            pct  = round((chg / prev_close * 100) if prev_close else 0, 2)
                            _last_price[sym] = price

                            now_unix  = int(datetime.now(_tz.utc).timestamp())
                            iv_key    = current_interval.get("iv", "5m")
                            iv_min    = _INTERVAL_MINUTES.get(iv_key, 5)
                            bar_time  = _floor_bar(now_unix, iv_min)
                            state_key = f"{sym}_{iv_key}"
                            prev_state= _bar_state.get(state_key)

                            if prev_state is None or prev_state["time"] != bar_time:
                                open_p = prev_state["close"] if prev_state else price
                                _bar_state[state_key] = {"time":bar_time,"open":open_p,
                                                         "high":price,"low":price,"close":price}
                            else:
                                _bar_state[state_key]["high"]  = max(_bar_state[state_key]["high"],  price)
                                _bar_state[state_key]["low"]   = min(_bar_state[state_key]["low"],   price)
                                _bar_state[state_key]["close"] = price

                            bar = _bar_state[state_key]

                            # ── Check exit conditions ─────────────────────────
                            exit_event = trade_manager.check_exits(price, sym)
                            if exit_event:
                                await ws.send_json(exit_event)
                                print(f"[TRADE EXIT] {sym} {exit_event['exit_reason']} "
                                      f"pnl={exit_event['pnl']} ({exit_event['pnl_pct']}%)")

                            # ── Live PnL for active trade ─────────────────────
                            active_trade = trade_manager.get_active(sym)
                            live_pnl = None
                            if active_trade:
                                side  = active_trade['side']
                                entry = active_trade['entry_price']
                                live_pnl = round(price - entry if side=='BUY' else entry - price, 4)

                            await ws.send_json({
                                "type"        : "tick",
                                "symbol"      : sym,
                                "price"       : round(price, 4),
                                "change"      : chg,
                                "change_pct"  : pct,
                                "open_markets": open_markets,
                                "bar"         : {"time":bar["time"],
                                                 "open":round(bar["open"],4),
                                                 "high":round(bar["high"],4),
                                                 "low":round(bar["low"],4),
                                                 "close":round(bar["close"],4)},
                                "active_trade": active_trade,
                                "live_pnl"    : live_pnl,
                            })
                    except Exception as e:
                        print(f"[WS tick] {sym}: {e}")
                else:
                    if tick_count % 12 == 0:
                        await ws.send_json({"type":"status","open_markets":open_markets,
                                            "any_open":bool(open_markets),
                                            "message":"Market closed for this symbol"})

            # ── Signal scan every 60 s ────────────────────────────────────────
            if tick_count % 12 == 0:
                wl = wl_load()
                for item in wl[:10]:
                    s = item['sym']
                    if not is_symbol_tradeable(s, open_markets): continue
                    try:
                        df   = get_data(s, "5m", "2d")
                        sigs = STRATEGIES['pro_mtf']['fn'](df, lambda idx: ts_format(idx, True))
                        if sigs:
                            last    = sigs[-1]
                            sig_key = f"{s}_{last['time']}"
                            if _last_signal_key.get(s) != sig_key:
                                _last_signal_key[s] = sig_key
                                try:
                                    t = estimate_target_time(df, float(last['price']),
                                                             float(last['tp']), '5m')
                                    last['target_time']     = t['label']
                                    last['target_datetime'] = t['datetime']
                                    last['target_bars']     = t['bars']
                                except Exception:
                                    pass
                                payload = {**last, "symbol": s, "type": "signal"}
                                signal_history.insert(0, payload)
                                if len(signal_history) > 200: signal_history.pop()
                                if trade_manager.get_active(s) is None:
                                    trade_manager.open_trade(last, s, 'pro_mtf', '5m')
                                await ws.send_json(payload)
                    except Exception as e:
                        print(f"[WS scan] {s}: {e}")

            # ── Status + EOD sweep every 5 min ────────────────────────────────
            if tick_count % 60 == 0:
                open_markets = get_open_markets()
                await ws.send_json({"type":"status","open_markets":open_markets,
                                    "any_open":bool(open_markets),
                                    "message":f"Open: {', '.join(open_markets)}" if open_markets
                                              else "Markets closed — crypto & futures still live"})
                eod_events = trade_manager.eod_sweep()
                for ev in eod_events:
                    await ws.send_json(ev)
                    print(f"[EOD EXIT] {ev['symbol']} pnl={ev['pnl']}")

            await asyncio.sleep(5)

    except WebSocketDisconnect:
        pass
    except Exception as e:
        print(f"[WS] fatal: {e}")
    finally:
        recv_task.cancel()
        if ws in _ws_clients:
            _ws_clients.remove(ws)


# ── Static (MUST BE LAST) ─────────────────────────────────────────────────────
_frontend = os.path.join(os.path.dirname(__file__), "frontend")

@app.get("/")
def serve_index():
    return FileResponse(os.path.join(_frontend, "index.html"))

@app.get("/{full_path:path}")
def catch_all(full_path: str):
    if full_path.startswith("api/"): return JSONResponse({"error":"Not found"}, status_code=404)
    return FileResponse(os.path.join(_frontend, "index.html"))