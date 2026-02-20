import numpy as np
from sklearn.linear_model import LogisticRegression

def ai_score():
    X = np.array([[30, 1], [70, -1], [50, 1], [80, -1]])
    y = np.array([1, 0, 1, 0])

    model = LogisticRegression()
    model.fit(X, y)

    probability = model.predict_proba([[55, 1]])[0][1]

    return round(probability * 100, 2)
