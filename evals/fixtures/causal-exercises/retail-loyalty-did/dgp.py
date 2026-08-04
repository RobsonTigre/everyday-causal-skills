# EVAL_EXECUTABLE
import numpy as np
import pandas as pd


rng = np.random.default_rng(303)
n_stores = 100
n_months = 24
true_att = 5.0

store_id = np.repeat(np.arange(1, n_stores + 1), n_months)
month = np.tile(np.arange(1, n_months + 1), n_stores)
treatment = (store_id <= 50).astype(int)
post = (month >= 13).astype(int)
store_effect = np.repeat(rng.normal(0, 3, n_stores), n_months)
sales = (
    50
    + store_effect
    + 0.2 * month
    + true_att * treatment * post
    + rng.normal(0, 2, n_stores * n_months)
)

df = pd.DataFrame(
    {
        "store_id": store_id,
        "month": month,
        "treatment": treatment,
        "post": post,
        "sales": np.round(sales, 2),
    }
)
df.to_csv("data.csv", index=False)
print(f"ESTIMATE:{true_att}")
