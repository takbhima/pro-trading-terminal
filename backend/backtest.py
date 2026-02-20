def backtest(df):
    """
    Simple backtest: count wins/losses based on EMA crossover signals.
    Uses fastEMA (9) and slowEMA (21) — matches indicators.py column names.
    Checks if price moved in the signal direction on the next candle.
    """
    if df is None or len(df) < 60:
        return {"wins": 0, "losses": 0, "accuracy": 0, "total": 0}

    wins = 0
    losses = 0

    for i in range(50, len(df) - 1):
        fast_now  = df["fastEMA"].iloc[i]
        fast_prev = df["fastEMA"].iloc[i - 1]
        slow_now  = df["slowEMA"].iloc[i]
        slow_prev = df["slowEMA"].iloc[i - 1]

        next_close = df["Close"].iloc[i + 1]
        curr_close = df["Close"].iloc[i]

        # BUY signal: fast crossed above slow
        if fast_prev <= slow_prev and fast_now > slow_now:
            if next_close > curr_close:
                wins += 1
            else:
                losses += 1

        # SELL signal: fast crossed below slow
        elif fast_prev >= slow_prev and fast_now < slow_now:
            if next_close < curr_close:
                wins += 1
            else:
                losses += 1

    total = wins + losses
    accuracy = (wins / total) * 100 if total > 0 else 0

    return {
        "wins"    : wins,
        "losses"  : losses,
        "total"   : total,
        "accuracy": round(accuracy, 2),
    }
