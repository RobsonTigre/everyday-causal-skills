# IV reference recipe (Python). `df` is preloaded by run_parity.py.
# Canonical modern Python path: linearmodels.IV2SLS for 2SLS estimation.
# The classic first-stage partial F is taken from statsmodels' homoskedastic
# f_test so it matches fixest's Wald F exactly (linearmodels' own
# first_stage.diagnostics uses a different df adjustment -- see spec/baseline).
from linearmodels.iv import IV2SLS
import statsmodels.formula.api as smf

# 2SLS: outcome ~ 1 + exogenous control + [endogenous ~ instrument]
m = IV2SLS.from_formula(
    "outcome ~ 1 + control + [endogenous ~ instrument]", data=df
).fit(cov_type="unadjusted")

# Point estimate of the endogenous regressor (the LATE / causal coefficient).
print(f"ATE:{m.params['endogenous']:.6f}")

# Homoskedastic (classic) first-stage partial F of the instrument: Wald F of the
# instrument coefficient in the full first-stage OLS. Matches fixest's Wald F.
fs = smf.ols("endogenous ~ instrument + control", data=df).fit()
f_stat = float(fs.f_test("instrument = 0").fvalue)
print(f"FIRST_STAGE_F:{f_stat:.6f}")

# Reduced-form coefficient of the instrument on the outcome (always-valid).
rf = smf.ols("outcome ~ instrument + control", data=df).fit()
print(f"REDUCED_FORM:{rf.params['instrument']:.6f}")
