import yfinance as yf
import pandas as pd

def backtest(symbol="^NSEI", interval="5m", period="5d"):
    df = yf.download(symbol, interval=interval, period=period)
    df["EMA9"] = df["Close"].ewm(span=9).mean()
    df["EMA21"] = df["Close"].ewm(span=21).mean()

    df["Signal"] = 0
    df.loc[df["EMA9"] > df["EMA21"], "Signal"] = 1
    df.loc[df["EMA9"] < df["EMA21"], "Signal"] = -1

    returns = df["Close"].pct_change()
    strategy_returns = returns * df["Signal"].shift(1)

    total_return = strategy_returns.sum()

    return {
        "total_return_percent": round(total_return * 100, 2),
        "trades": int((df["Signal"].diff() != 0).sum())
    }
