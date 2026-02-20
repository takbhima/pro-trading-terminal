from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
import asyncio

from backend.data_fetcher import get_data
from backend.indicators import apply_indicators
from backend.strategy import generate_signal
from backend.ai_score import calculate_probability
from backend.risk import calculate_position_size
from backend.backtest import backtest

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

symbols = ["^NSEBANK", "^NSEI"]

signal_history = []

@app.get("/")
def root():
    return {"status": "running"}

@app.get("/signals")
def get_signals():
    return signal_history

@app.get("/risk")
def risk(capital: float, risk_percent: float, entry: float, stoploss: float):
    qty = calculate_position_size(capital, risk_percent, entry, stoploss)
    return {"quantity": qty}

@app.get("/backtest/{symbol}")
def run_backtest(symbol: str):
    df = get_data(symbol, "5m")
    df = apply_indicators(df)
    return backtest(df)

@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    while True:
        for symbol in symbols:
            df_5m = apply_indicators(get_data(symbol, "5m"))
            df_15m = apply_indicators(get_data(symbol, "15m"))

            signal = generate_signal(df_5m, df_15m)

            if signal:
                probability = calculate_probability(df_5m)

                data = {
                    "symbol": symbol,
                    "signal": signal,
                    "price": float(df_5m["Close"].iloc[-1]),
                    "probability": probability
                }

                signal_history.append(data)
                await ws.send_json(data)

        await asyncio.sleep(60)
