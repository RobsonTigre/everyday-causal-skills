# HTE reference recipe (Python) — econml CausalForestDML + LinearDML projection.
# `df` is preloaded by run_parity.py from the shared fixture (matches hte.R).
# Randomized-treatment design (known propensity 0.5) with linear heterogeneity in
# centered age; compared estimands (ATE, BLP_AGE) concentrate across RNGs.
import numpy as np
import statsmodels.api as sm
from econml.dml import CausalForestDML, LinearDML
from sklearn.dummy import DummyClassifier
from sklearn.ensemble import GradientBoostingRegressor

Y = df["outcome"].values
T = df["treatment"].values
X = df[["age", "income", "gender"]].values.astype(float)

# Center age so the LinearDML slope targets tau change per year about the sample
# mean, matching the R grf best_linear_projection on the same centered features.
Xc = X.copy()
Xc[:, 0] = Xc[:, 0] - 40.0

# W (confounders / outcome predictors). Treatment is randomized, so propensity is
# the known constant supplied via a prior DummyClassifier (no propensity model).
W = df[["income", "gender"]].values.astype(float)

# Overall ATE via the causal forest (DML/AIPW).
cf = CausalForestDML(
    model_y=GradientBoostingRegressor(n_estimators=200, max_depth=3, random_state=42),
    model_t=DummyClassifier(strategy="prior"),  # known randomized propensity
    discrete_treatment=True,
    n_estimators=4000,
    cv=5,
    random_state=42,
)
cf.fit(Y, T, X=X, W=W)
ate = float(cf.ate(X))
print(f"ATE:{ate:f}")

# Best linear projection of the CATE onto the (centered) effect modifiers, via the
# orthogonal-moment LinearDML coefficients (apples-to-apples with grf's BLP slope).
ld = LinearDML(
    model_y=GradientBoostingRegressor(n_estimators=200, max_depth=3, random_state=42),
    model_t=DummyClassifier(strategy="prior"),
    discrete_treatment=True,
    cv=5,
    random_state=42,
)
ld.fit(Y, T, X=Xc, W=W)
print(f"BLP_AGE:{ld.coef_[0]:f}")

# Heterogeneity sign check: top-minus-bottom CATE-quintile GATE (printed, not gated).
import pandas as pd
cate = cf.effect(X)
q = pd.qcut(cate, 5, labels=[1, 2, 3, 4, 5])
hi = float(cf.ate(X[q == 5]))
lo = float(cf.ate(X[q == 1]))
print(f"GATE_HIGH_MINUS_LOW:{hi - lo:f}")
