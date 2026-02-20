def calculate_probability(df):
    last = df.iloc[-1]
    score = 50

    if last["rsi"] > 60:
        score += 10
    if last["ema20"] > last["ema50"]:
        score += 20

    return min(score, 95)
