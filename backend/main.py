
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
from fastapi.responses import FileResponse
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Serve static frontend folder
app.mount("/static", StaticFiles(directory=os.path.join(BASE_DIR, "frontend")), name="static")

# Serve index.html at root
@app.get("/")
def serve_index():
    return FileResponse(os.path.join(BASE_DIR, "frontend", "index.html"))
