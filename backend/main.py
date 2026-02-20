
from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
import requests
import asyncio
import random

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def root():
    return {"status": "Trading Terminal Backend Running"}

@app.get("/option-chain/{symbol}")
def get_option_chain(symbol: str):
    url = f"https://www.nseindia.com/api/option-chain-equities?symbol={symbol}"
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Accept": "application/json"
    }
    session = requests.Session()
    session.get("https://www.nseindia.com", headers=headers)
    response = session.get(url, headers=headers)
    return response.json()

@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    price = 500
    while True:
        price += random.uniform(-1,1)
        await ws.send_json({"price": round(price,2)})
        await asyncio.sleep(1)

from fastapi.staticfiles import StaticFiles

app.mount("/", StaticFiles(directory="frontend", html=True), name="frontend")
