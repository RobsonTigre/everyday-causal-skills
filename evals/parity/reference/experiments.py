# Experiments parity reference recipe (Python). `df` is preloaded by the runner.
# Canonical best-practice estimator: Lin (2013) interacted regression
# adjustment with HC2 robust SEs via statsmodels OLS.
import numpy as np
import statsmodels.formula.api as smf

# 1. Difference in means (unadjusted ATE), HC2 SE.
dim_fit = smf.ols("outcome ~ treatment", data=df).fit(cov_type="HC2")
print(f"ATE:{dim_fit.params['treatment']:.6f}")
print(f"SE:{dim_fit.bse['treatment']:.6f}")

# 2. Lin (2013): center covariates, interact with treatment, HC2 SE.
covariates = ["X1", "X2", "X3"]
d = df.copy()
for c in covariates:
    d[f"{c}_c"] = d[c] - d[c].mean()
dm = [f"{c}_c" for c in covariates]
interactions = " + ".join(f"treatment:{c}" for c in dm)
formula = f"outcome ~ treatment + {' + '.join(dm)} + {interactions}"
lin_fit = smf.ols(formula, data=d).fit(cov_type="HC2")
print(f"ATE_ADJ:{lin_fit.params['treatment']:.6f}")
print(f"SE_ADJ:{lin_fit.bse['treatment']:.6f}")
