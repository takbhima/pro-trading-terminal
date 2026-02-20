def backtest(df):
    wins = 0
    losses = 0

    for i in range(50, len(df)):
        if df["ema20"].iloc[i] > df["ema50"].iloc[i]:
            if df["Close"].iloc[i+1] > df["Close"].iloc[i]:
                wins += 1
            else:
                losses += 1

    total = wins + losses
    accuracy = (wins / total) * 100 if total > 0 else 0

    return {
        "wins": wins,
        "losses": losses,
        "accuracy": round(accuracy, 2)
    }
