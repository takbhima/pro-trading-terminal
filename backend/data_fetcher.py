import yfinance as yf
import pandas as pd

def get_data(symbol: str, interval: str = "5m", period: str = "5d") -> pd.DataFrame:
    df = yf.download(symbol, period=period, interval=interval,
                     progress=False, auto_adjust=True)
    if df is None or df.empty:
        raise ValueError(f"No data returned for {symbol}")
    df.dropna(inplace=True)
    return df
