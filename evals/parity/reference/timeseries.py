# Single-series interrupted time series (segmented regression) -- Python reference.
# `df` is preloaded by the parity runner from the shared fixture.
# This is the runnable cross-language numerical probe: the Python BSTS port
# (causalimpact) does not import under the project interpreter, so segmented
# regression with Newey-West (HAC) SEs is the shared estimator both languages run.
import statsmodels.formula.api as smf

model = smf.ols("outcome ~ time + post + time_since", data=df).fit(
    cov_type="HAC", cov_kwds={"maxlags": 4})  # Newey-West HAC standard errors

print(f"LEVEL:{model.params['post']}")          # immediate level shift at intervention
print(f"TREND:{model.params['time_since']}")     # change in slope after intervention
print(f"SE_LEVEL:{model.bse['post']}")           # HAC SE of the level shift
