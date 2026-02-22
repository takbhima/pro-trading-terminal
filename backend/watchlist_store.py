"""
Persistent watchlist stored as JSON file on disk.
Survives server restarts, browser clears, anything.
File location: watchlist.json in project root.
"""
import json, os

WATCHLIST_FILE = os.path.join(os.path.dirname(__file__), '..', 'watchlist.json')

DEFAULT = [
    {"sym": "^BSESN",       "name": "SENSEX"},
    {"sym": "^NSEBANK",     "name": "Bank Nifty"},
    {"sym": "^NSEI",        "name": "Nifty 50"},
    {"sym": "RELIANCE.NS",  "name": "Reliance"},
    {"sym": "TCS.NS",       "name": "TCS"},
    {"sym": "INFY.NS",      "name": "Infosys"},
    {"sym": "HDFCBANK.NS",  "name": "HDFC Bank"},
    {"sym": "AAPL",         "name": "Apple"},
    {"sym": "MSFT",         "name": "Microsoft"},
    {"sym": "NVDA",         "name": "Nvidia"},
    {"sym": "BTC-USD",      "name": "Bitcoin"},
]

def load() -> list:
    try:
        if os.path.exists(WATCHLIST_FILE):
            with open(WATCHLIST_FILE, 'r') as f:
                return json.load(f)
    except Exception as e:
        print(f"[WL] Load error: {e}")
    # First run — create file with defaults
    save(DEFAULT)
    return DEFAULT

def save(wl: list):
    try:
        with open(WATCHLIST_FILE, 'w') as f:
            json.dump(wl, f, indent=2)
    except Exception as e:
        print(f"[WL] Save error: {e}")

def add(sym: str, name: str) -> dict:
    wl = load()
    sym = sym.upper().strip()
    if any(w['sym'] == sym for w in wl):
        return {"ok": False, "reason": f"{sym} already in watchlist"}
    wl.append({"sym": sym, "name": name or sym})
    save(wl)
    return {"ok": True, "watchlist": wl}

def remove(sym: str) -> dict:
    wl = load()
    sym = sym.upper().strip()
    wl = [w for w in wl if w['sym'] != sym]
    save(wl)
    return {"ok": True, "watchlist": wl}