import json
import os
from datetime import datetime

SIGNAL_FILE = "backend/signals.json"

def save_signal(signal_data):
    if not os.path.exists(SIGNAL_FILE):
        with open(SIGNAL_FILE, "w") as f:
            json.dump([], f)

    with open(SIGNAL_FILE, "r") as f:
        signals = json.load(f)

    signal_data["timestamp"] = datetime.utcnow().isoformat()
    signals.append(signal_data)

    with open(SIGNAL_FILE, "w") as f:
        json.dump(signals, f, indent=2)

def get_signals():
    if not os.path.exists(SIGNAL_FILE):
        return []
    with open(SIGNAL_FILE, "r") as f:
        return json.load(f)
