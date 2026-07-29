# EVAL_EXECUTABLE
import numpy as np
import pandas as pd


rng = np.random.default_rng(606)
n = 4000
true_late = 2000.0

encouragement = rng.binomial(1, 0.5, n)
motivation = rng.normal(0, 1, n)
training = (
    0.25 + 0.07 * encouragement + 0.18 * motivation + rng.normal(0, 0.2, n) > 0.5
).astype(int)
earnings = (
    32000
    + true_late * training
    + 3500 * motivation
    + rng.normal(0, 5000, n)
)

df = pd.DataFrame(
    {
        "person_id": np.arange(1, n + 1),
        "encouragement": encouragement,
        "training": training,
        "earnings": np.round(earnings, 2),
    }
)
df.to_csv("data.csv", index=False)
print(f"ESTIMATE:{true_late}")
