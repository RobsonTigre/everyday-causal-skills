# Exercises (DGP-generation) reference recipe (Python). `df` is preloaded by
# run_parity.py from evals/parity/fixtures/exercises_parity.csv — but here `df`
# holds the DGP SPECIFICATION (one row of parameters), not a dataset.
#
# The exercises skill generates practice data from a known DGP. The parity
# contract is: (1) the declared true effect (TRUE_ATT) is deterministic and must
# match R exactly; (2) given the same DGP spec, the language-native RNG draws its
# own data and the canonical naive estimator (the 2x2 DiD means-of-means)
# recovers the SAME effect within Monte-Carlo sampling error (RECOVERED_ATT).
#
# Mirrors DGP-03 (Classic 2x2 DiD, true ATT = 5.0) in references/dgp-library.md.
import numpy as np

s = df.iloc[0]
seed = int(s["seed"])
n_stores, n_months = int(s["n_stores"]), int(s["n_months"])
treat_month = int(s["treat_month"])
true_att = float(s["true_att"])

# --- Generate the exercise dataset from the DGP spec (DGP-03 structural form) ---
np.random.seed(seed)
store_id = np.repeat(np.arange(1, n_stores + 1), n_months)
month = np.tile(np.arange(1, n_months + 1), n_stores)
treated = (store_id <= n_stores // 2).astype(int)
post = (month >= treat_month).astype(int)
store_fe = np.repeat(np.random.normal(0, float(s["store_fe_sd"]), n_stores), n_months)
time_trend = float(s["time_trend"]) * month
revenue = (
    float(s["base"]) + store_fe + time_trend + true_att * treated * post
    + np.random.normal(0, float(s["noise_sd"]), n_stores * n_months)
)
gen = __import__("pandas").DataFrame(
    {"treated": treated, "post": post, "revenue": revenue})

# --- Recover the effect with the canonical 2x2 DiD estimator (means-of-means) ---
m = gen.groupby(["treated", "post"])["revenue"].mean()
recovered = (m[(1, 1)] - m[(1, 0)]) - (m[(0, 1)] - m[(0, 0)])

# Declared ground truth (deterministic — must match R exactly).
print(f"TRUE_ATT:{true_att:.6f}")
# Recovered effect (stochastic — RNG differs across languages; agree within MC error).
print(f"RECOVERED_ATT:{recovered:.6f}")
