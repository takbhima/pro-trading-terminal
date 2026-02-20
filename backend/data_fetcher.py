import yfinance as yf

def get_data(symbol, interval="5m"):
    ticker = yf.Ticker(symbol)
    df = ticker.history(period="5d", interval=interval)
    df.dropna(inplace=True)
    return df
