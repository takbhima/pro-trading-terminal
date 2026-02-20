def calculate_probability(df):
    """
    Score 50–95 based on indicator confluence.
    Column names match indicators.py output.
    """
    if df is None or len(df) < 2:
        return 50

    last = df.iloc[-2]  # last closed candle (same as strategy.py)
    score = 50

    # RSI momentum
    if last["rsi"] > 60:
        score += 10
    elif last["rsi"] < 40:
        score += 10  # strong bearish momentum also = confident signal

    # EMA trend alignment (fastEMA = 9, slowEMA = 21)
    if last["fastEMA"] > last["slowEMA"]:
        score += 10
    
    # Price above 200 EMA = strong trend
    if last["Close"] > last["trendEMA"]:
        score += 10

    # Supertrend confirmation
    if last["st_dir"] < 0:   # bullish supertrend
        score += 10
    elif last["st_dir"] > 0: # bearish supertrend
        score += 10

    return min(score, 95)
