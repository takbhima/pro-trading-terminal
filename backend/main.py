from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import asyncio
import random
from pathlib import Path

app = FastAPI()

# -----------------------------
# CORS
# -----------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -----------------------------
# API ROUTE
# -----------------------------
@app.get("/api/status")
async def status():
    return {"status": "Backend Running"}

# -----------------------------
# WEBSOCKET ROUTE (BEFORE STATIC)
# -----------------------------
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    print("WebSocket connected")

    try:
        while True:
            await websocket.send_json({
                "price": round(random.uniform(30000, 40000), 2)
            })
            await asyncio.sleep(2)

    except WebSocketDisconnect:
        print("WebSocket disconnected")


# -----------------------------
# STATIC FILES (MUST BE LAST)
# -----------------------------
BASE_DIR = Path(__file__).resolve().parent.parent
FRONTEND_DIR = BASE_DIR / "frontend"

app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")
