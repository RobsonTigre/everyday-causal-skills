# Canonical modern RDD recipe (Python) — local polynomial RD with robust bias-corrected
# inference (Calonico, Cattaneo, Titiunik) via the rdrobust port, MSE-optimal bandwidth,
# plus the Cattaneo-Jansson-Ma manipulation density test via rddensity.
# `df` is preloaded by the parity harness. Columns: y (outcome), x (running var), z (covariate).
from rdrobust import rdrobust
from rddensity import rddensity

cutoff = 0

rd = rdrobust(y=df["y"], x=df["x"], c=cutoff)             # triangular kernel, p=1, mserd bandwidth
# coef rows (0,1,2): Conventional, Bias-Corrected, Robust
print(f"RD_EST:{rd.coef.iloc[0, 0]}")                     # point estimate (kernel/bw-driven, language-invariant)
print(f"SE_ROBUST:{rd.se.iloc[2, 0]}")                    # robust bias-corrected SE
print(f"CI_LO:{rd.ci.iloc[2, 0]}")
print(f"CI_HI:{rd.ci.iloc[2, 1]}")
print(f"BW:{rd.bws.iloc[0, 0]}")                          # MSE-optimal bandwidth (left = right here)

# Manipulation / density continuity test at the cutoff (CJM 2020)
den = rddensity(X=df["x"].values, c=cutoff)
print(f"DENSITY_T:{den.test.t_jk}")                       # jackknife t-statistic for the density jump
