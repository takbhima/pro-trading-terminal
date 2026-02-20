from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import asyncio, os

from backend.data_fetcher import get_data
from backend.indicators   import apply_indicators
from backend.strategy     import generate_signal
from backend.ai_score     import calculate_probability
from backend.risk         import calculate_position_size
from backend.backtest     import backtest

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

SYMBOLS = ["^NSEBANK", "^NSEI"]
signal_history = []

# ── API routes ──────────────────────────────────────────────────────────────

@app.get("/api/status")
def status():
    return {"status": "running", "signals": len(signal_history)}

@app.get("/api/signals")
def get_signals():
    return signal_history

@app.get("/api/risk")
def risk(capital: float, risk_percent: float, entry: float, stoploss: float):
    qty = calculate_position_size(capital, risk_percent, entry, stoploss)
    return {"quantity": qty}

@app.get("/api/backtest/{symbol}")
def run_backtest(symbol: str):
    try:
        df = apply_indicators(get_data(symbol, "15m", "30d"))
        return backtest(df)
    except Exception as e:
        return {"error": str(e)}

# ── WebSocket ───────────────────────────────────────────────────────────────

@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    try:
        while True:
            for symbol in SYMBOLS:
                try:
                    df_5m  = apply_indicators(get_data(symbol, "5m"))
                    df_15m = apply_indicators(get_data(symbol, "15m"))
                    signal = generate_signal(df_5m, df_15m)
                    if signal:
                        probability = calculate_probability(df_5m)
                        data = {
                            "symbol"     : symbol,
                            "type"       : signal["type"],
                            "signal"     : signal["type"],
                            "price"      : signal["price"],
                            "sl"         : signal["sl"],
                            "tp"         : signal["tp"],
                            "atr"        : signal["atr"],
                            "rsi"        : signal["rsi"],
                            "probability": probability,
                        }
                        signal_history.insert(0, data)
                        if len(signal_history) > 200:
                            signal_history.pop()
                        await ws.send_json(data)
                except Exception as e:
                    print(f"[ERROR] {symbol}: {e}")
            await asyncio.sleep(60)
    except WebSocketDisconnect:
        print("[WS] Client disconnected")

# ── Serve frontend ──────────────────────────────────────────────────────────

frontend_dir = os.path.join(os.path.dirname(__file__), "frontend")
app.mount("/static", StaticFiles(directory=frontend_dir), name="static")

@app.get("/")
def serve_index():
    return FileResponse(os.path.join(frontend_dir, "index.html"))

@app.get("/{full_path:path}")
def catch_all(full_path: str):
    return FileResponse(os.path.join(frontend_dir, "index.html"))
