# Assumption Checklist: Instrumental Variables

Reference: `references/method-registry.md` → Instrumental Variables (IV)

---

## Relevance (Strong First Stage)

**Plain language**: The instrument must actually affect the treatment. If the instrument has little or no influence on whether someone receives the treatment, it's useless — like trying to push a boulder with a feather. A weak instrument leads to unreliable, noisy estimates.

**Formal statement**: Cov(Z, D) != 0, where Z is the instrument and D is the treatment. In practice, the first-stage F-statistic should be large: F > 10 by the Stock-Yogo rule, and ideally F > 100 for reliable inference. With a single endogenous regressor and one instrument, the effective F-statistic equals the standard first-stage F-statistic.

**Testable?**: Yes. This is the one IV assumption that is directly testable.

**How to test**:

R:
```r
library(fixest)

# IV estimation with fixest
iv_model <- feols(outcome ~ exogenous_controls | endogenous_treatment ~ instrument,
                  data = df, cluster = ~cluster_var)

# First-stage F-statistic
fitstat(iv_model, "ivf")
# Rule of thumb: F > 10 (Stock & Yogo 2005)
# Better: F > 100 (Lee et al. 2022 recommend much higher thresholds)

# Full first-stage results
summary(iv_model, stage = 1)

# Alternative: manual first stage
first_stage <- feols(endogenous_treatment ~ instrument + exogenous_controls,
                     data = df, cluster = ~cluster_var)
summary(first_stage)
cat("First-stage F:", fitstat(first_stage, "f")$f$stat, "\n")
```

Python:
```python
from linearmodels.iv import IV2SLS

# IV estimation
iv_model = IV2SLS.from_formula(
    'outcome ~ 1 + exogenous_controls + [endogenous_treatment ~ instrument]',
    data=df)
iv_res = iv_model.fit(cov_type='clustered', clusters=df['cluster_var'])

# First-stage diagnostics
print(iv_res.first_stage)
print(f"First-stage F-statistic: {iv_res.first_stage.diagnostics.iloc[0]['f.stat']:.2f}")

# Manual first stage
import statsmodels.formula.api as smf
first_stage = smf.ols('endogenous_treatment ~ instrument + exogenous_controls',
                       data=df).fit()
print(first_stage.summary())
print(f"F-statistic: {first_stage.fvalue:.2f}")
```

**What violation looks like**: First-stage F-statistic below 10. Instrument coefficient in the first stage is small and/or insignificant. The IV second-stage confidence interval is extremely wide (a hallmark of weak instruments). In severe cases, the IV estimate is farther from the OLS estimate than theory would predict (weak instrument bias pushes IV toward OLS).

**Severity if violated**: Fatal if F < 10. With a weak instrument: (1) the IV estimate is biased toward the OLS estimate, defeating the purpose of IV, (2) standard confidence intervals have terrible coverage (actual rejection rates far exceed nominal levels), and (3) inference is unreliable. Even with F between 10 and 20, bias can be 10-20% of the OLS bias.

**Mitigation**: (1) Find a stronger instrument. (2) If you have multiple weak instruments, use the Limited Information Maximum Likelihood (LIML) estimator instead of 2SLS — it is less biased under weak instruments. In `fixest`: use `method = "liml"`. (3) Use Anderson-Rubin confidence sets, which are robust to weak instruments. (4) Report the reduced-form effect of the instrument on the outcome (this is always valid, just rescaled). (5) If the instrument is genuinely weak, IV is not viable — choose a different identification strategy.

---

## Exclusion Restriction

**Plain language**: The instrument affects the outcome ONLY through its effect on the treatment — not through any other channel. If the instrument has a direct effect on the outcome (bypassing the treatment), the IV estimate is biased.

**Formal statement**: Cov(Z, epsilon) = 0, where epsilon is the structural error in the outcome equation. Equivalently, Z affects Y only through D: Z -> D -> Y, with no direct path Z -> Y and no unblocked backdoor paths Z <- U -> Y.

**Testable?**: No. The exclusion restriction is fundamentally untestable with a single instrument. It must be argued on substantive grounds. With multiple instruments, overidentification tests (Sargan/Hansen) can detect violations, but only if at least one instrument is valid.

**How to test**:

Formal testing is not possible with a single instrument. The best you can do is:

R:
```r
# With multiple instruments: overidentification test (Sargan/Hansen)
library(fixest)

iv_overid <- feols(outcome ~ exogenous_controls |
                     endogenous_treatment ~ instrument1 + instrument2,
                   data = df)
fitstat(iv_overid, "sargan")
# H0: all instruments are valid
# Rejection suggests at least one instrument violates exclusion
# BUT: non-rejection does not prove validity

# Reduced form: check if the instrument has a "reasonable" effect
# on the outcome (should be proportional to first stage * treatment effect)
reduced_form <- feols(outcome ~ instrument + exogenous_controls,
                      data = df, cluster = ~cluster_var)
summary(reduced_form)
```

Python:
```python
from linearmodels.iv import IV2SLS

# With multiple instruments: overidentification test
iv_overid = IV2SLS.from_formula(
    'outcome ~ 1 + exogenous_controls + [endogenous_treatment ~ instrument1 + instrument2]',
    data=df)
iv_overid_res = iv_overid.fit(cov_type='robust')
print(iv_overid_res.wooldridge_overid)
# p < 0.05 suggests at least one instrument is invalid

# Reduced form as a sanity check
import statsmodels.formula.api as smf
rf = smf.ols('outcome ~ instrument + exogenous_controls', data=df).fit()
print(rf.summary())
```

**What violation looks like**: There is no single statistical signature. Violations are detected through substantive reasoning, not data. Red flags include: (1) the instrument plausibly affects the outcome through channels other than the treatment, (2) the IV estimate is implausibly large or the wrong sign, (3) with multiple instruments, the overidentification test rejects. Example: using distance to college as an instrument for education on earnings — distance might also proxy for urban/rural differences that directly affect earnings.

**Severity if violated**: Fatal. If the exclusion restriction is violated, the IV estimate is inconsistent — it converges to a wrong value even with infinite data. There is no statistical fix; the instrument is simply invalid.

**Mitigation**: None — choose a different instrument or a different method. (1) Argue the exclusion restriction carefully by listing all possible channels from Z to Y and explaining why only the D channel is operative. (2) Use a different instrument. (3) Conduct sensitivity analysis: Conley, Hansen, and Rossi (2012) propose methods to bound the IV estimate when the exclusion restriction is "approximately" satisfied (Z has a small direct effect on Y). In R: `ivmodel::AR.test()` for Anderson-Rubin bounds. (4) If no valid instrument exists, IV is not the right method — consider DiD, RDD, or matching if applicable.

---

## Independence / Exogeneity

**Plain language**: The instrument is "as good as randomly assigned" — it's not correlated with the unobserved factors that affect the outcome. People didn't choose their instrument value based on their expected outcomes.

**Formal statement**: Z is independent of potential outcomes: Z ⊥ (Y(0), Y(1), D(0), D(1)), or the weaker conditional version: Z ⊥ (Y(0), Y(1), D(0), D(1)) | X, where X is a set of observed covariates. This means the instrument is uncorrelated with unobserved determinants of the outcome, possibly after conditioning on covariates.

**Testable?**: Partially. You can check whether the instrument is balanced on observables (like checking balance in an RCT), but you cannot rule out correlation with unobservables.

**How to test**:

R:
```r
library(cobalt)
library(fixest)

# Balance test: is the instrument "as good as random" with respect
# to observed covariates?
bal <- bal.tab(instrument ~ X1 + X2 + X3, data = df,
               binary = "std", continuous = "std",
               thresholds = c(m = 0.1))
print(bal)
love.plot(bal, threshold = 0.1)

# Regression-based balance test
balance_tests <- lapply(c("X1", "X2", "X3"), function(x) {
  feols(as.formula(paste(x, "~ instrument")), data = df)
})
modelsummary::modelsummary(balance_tests, stars = TRUE)
```

Python:
```python
import pandas as pd
from scipy.stats import ttest_ind, pearsonr

# Balance test: check if instrument is correlated with observables
covariates = ['X1', 'X2', 'X3']

balance = []
for cov in covariates:
    high_z = df.loc[df['instrument'] > df['instrument'].median(), cov]
    low_z = df.loc[df['instrument'] <= df['instrument'].median(), cov]
    stat, pval = ttest_ind(high_z, low_z)
    corr, corr_p = pearsonr(df['instrument'], df[cov])
    balance.append({
        'covariate': cov,
        'corr_with_instrument': corr,
        'corr_p_value': corr_p,
        't_stat': stat,
        'p_value': pval
    })

print(pd.DataFrame(balance))
# Covariates should NOT be significantly correlated with the instrument
```

**What violation looks like**: The instrument is correlated with observable confounders (a red flag that suggests correlation with unobservables too). The instrument was chosen or influenced by the units themselves based on their expected outcomes. The IV estimate changes substantially when you add different control variables (suggesting the instrument is not independent conditional on different conditioning sets).

**Severity if violated**: Fatal. If the instrument is correlated with unobserved determinants of the outcome, the IV estimate is inconsistent. The whole point of IV is to exploit exogenous variation; if the instrument is endogenous, you've gained nothing over OLS.

**Mitigation**: (1) Condition on covariates X that make the independence assumption more plausible (conditional instrument exogeneity). (2) Find a more clearly exogenous instrument (natural experiments, lotteries, regulatory quirks). (3) Provide a detailed narrative for why the instrument is plausibly exogenous. (4) Conduct sensitivity analysis on the degree of instrument endogeneity needed to overturn the result.

---

## Monotonicity

**Plain language**: The instrument pushes everyone in the same direction. There are no "defiers" — people who do the opposite of what the instrument encourages. If the instrument increases the probability of treatment for some, it should not decrease it for others.

**Formal statement**: D_i(1) >= D_i(0) for all i (or D_i(1) <= D_i(0) for all i), where D_i(z) is unit i's treatment status when the instrument takes value z. This rules out "defiers" — units for whom a higher instrument value decreases treatment take-up.

**Testable?**: No, in general. Monotonicity involves individual-level responses to the instrument that we cannot observe (we see each unit under only one value of Z). In some special cases with multi-valued instruments or stratified data, partial tests exist.

**How to test**:

While not formally testable, you can check for suggestive evidence:

R:
```r
# Check first-stage effect across subgroups
# Monotonicity implies the first stage should be non-negative
# (or non-positive) for ALL subgroups
library(fixest)

# Split by key covariate and check first stage in each group
subgroups <- unique(df$subgroup_var)
for (g in subgroups) {
  sub_df <- df[df$subgroup_var == g, ]
  fs <- feols(endogenous_treatment ~ instrument, data = sub_df)
  cat("Subgroup:", g,
      "| First-stage coef:", round(coef(fs)["instrument"], 4),
      "| p-value:", round(pvalue(fs)["instrument"], 4), "\n")
}
# Red flag: if the first-stage coefficient flips sign across subgroups
```

Python:
```python
import statsmodels.formula.api as smf

# Check first-stage sign across subgroups
for group_val in df['subgroup_var'].unique():
    sub_df = df[df['subgroup_var'] == group_val]
    fs = smf.ols('endogenous_treatment ~ instrument', data=sub_df).fit()
    print(f"Subgroup {group_val}: "
          f"first-stage coef = {fs.params['instrument']:.4f}, "
          f"p = {fs.pvalues['instrument']:.4f}")

# Red flag: first-stage coefficient changes sign across subgroups
```

**What violation looks like**: The first-stage relationship between the instrument and treatment flips sign across subgroups. For example, if draft lottery eligibility increases military service for most people but decreases it for those with alternative service obligations (defiers). In the data, you might see a zero or negative first stage in some subgroups.

**Severity if violated**: Serious. Monotonicity is required for the LATE (Local Average Treatment Effect) interpretation — that IV estimates the effect for compliers. If defiers exist, the IV estimate is a weighted average of complier and defier effects, with defier effects getting negative weights. This makes the estimand uninterpretable. However, if the proportion of defiers is small, the bias may be minor.

**Mitigation**: (1) Argue that defiers are implausible in your context (e.g., a draft lottery cannot decrease military service for anyone). (2) If defiers plausibly exist in a subgroup, restrict the sample to the subgroup where monotonicity holds. (3) Use partial identification bounds that allow for some defiers (e.g., Balke & Pearl 1997 bounds). (4) Accept the point estimate but note that the LATE interpretation is weakened.
