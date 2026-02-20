from fastapi import FastAPI, WebSocket, Request
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path
import random
import asyncio

from strategy_engine import save_signal, get_signals
from risk import calculate_position_size
from backtester import backtest
from ai_model import ai_score

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Webhook
@app.post("/webhook")
async def webhook(request: Request):
    data = await request.body()
    signal_text = data.decode()

    parts = signal_text.split("|")
    action = parts[0]
    symbol = parts[1]
    price = float(parts[2])

    signal_data = {
        "action": action,
        "symbol": symbol,
        "price": price
    }

    save_signal(signal_data)

    return {"status": "stored"}

# Signal history
@app.get("/signals")
def signals():
    return get_signals()

# Risk calculator
@app.get("/risk")
def risk(capital: float, risk_percent: float, entry: float, stoploss: float):
    qty = calculate_position_size(capital, risk_percent, entry, stoploss)
    return {"recommended_quantity": qty}

# Backtest
@app.get("/backtest")
def run_backtest():
    return backtest()

# AI Score
@app.get("/ai-score")
def ai():
    return {"probability_percent": ai_score()}

# Demo WebSocket
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    while True:
        await websocket.send_json({"price": random.randint(40000, 45000)})
        await asyncio.sleep(2)

# Static files
BASE_DIR = Path(__file__).resolve().parent.parent
FRONTEND_DIR = BASE_DIR / "frontend"
app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")
