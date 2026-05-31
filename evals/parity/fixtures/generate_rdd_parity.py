import numpy as np, pandas as pd
# Deterministic sharp RDD fixture for R<->Python parity.
# Running variable X ~ centered at 0; cutoff c=0; sharp assignment treated = (X>=0).
# Outcome jumps by TAU at the cutoff; smooth quadratic trend on each side.
# Covariate z2 is smooth through the cutoff (for covariate-smoothness diagnostic).
rng = np.random.default_rng(20260531)
N = 2000
TAU = 3.0   # true sharp RD effect at the cutoff
# Running variable: truncated-ish normal on [-1,1], no mass points at exactly 0
x = rng.uniform(-1.0, 1.0, size=N)
treated = (x >= 0).astype(int)
# Smooth conditional mean (continuous in x) + treatment jump + noise
mu = 0.5 + 1.2 * x + 0.8 * x**2 - 0.5 * np.sin(3 * x)
eps = rng.normal(0.0, 0.30, size=N)
y = mu + TAU * treated + eps
# Smooth covariate (no jump at cutoff) for covariate-balance diagnostic
z = 1.0 + 0.7 * x - 0.3 * x**2 + rng.normal(0.0, 0.25, size=N)
df = pd.DataFrame({"y": np.round(y, 6), "x": np.round(x, 6), "z": np.round(z, 6)})
df.to_csv("evals/parity/fixtures/rdd_parity.csv", index=False)
print("wrote", len(df), "rows; TAU=", TAU)
print(df.head())
print("n_below", int((df.x<0).sum()), "n_above", int((df.x>=0).sum()))
