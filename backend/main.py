from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import asyncio
import random
import os

app = FastAPI()

# -----------------------------
# CORS (safe for deployment)
# -----------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -----------------------------
# Serve Frontend
# -----------------------------
app.mount("/", StaticFiles(directory="frontend", html=True), name="frontend")

# -----------------------------
# Health Check Route
# -----------------------------
@app.get("/api/status")
async def status():
    return {"status": "Trading Terminal Backend Running"}

# -----------------------------
# WebSocket Endpoint
# -----------------------------
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    print("Client connected")

    try:
        while True:
            # Generate random BTC price (demo)
            price = round(random.uniform(30000, 40000), 2)

            await websocket.send_json({
                "symbol": "BTCUSDT",
                "price": price
            })

            await asyncio.sleep(2)

    except WebSocketDisconnect:
        print("Client disconnected")
