# Assumption Checklist: Regression Discontinuity Design

Reference: `references/method-registry.md` → Regression Discontinuity Design (RDD)

---

## Continuity at the Cutoff

**Plain language**: If you could magically remove the treatment, the average outcome would change smoothly as you cross the cutoff — no jump. The only reason for a discontinuity in the outcome at the cutoff is the treatment itself, not some other factor that also changes abruptly there.

**Formal statement**: The conditional expectation functions E[Y(0)|X=x] and E[Y(1)|X=x] are continuous at the cutoff x = c, where X is the running variable and Y(0), Y(1) are the potential outcomes. This ensures that the limit of outcomes from the left equals the limit from the right, absent treatment.

**Testable?**: Partially. You cannot directly test continuity of potential outcomes (since we observe only one potential outcome per unit). But you can check whether pre-determined covariates are smooth through the cutoff — if they jump, something other than the treatment changes at c.

**How to test**:

R:
```r
library(rdrobust)

# Covariate smoothness test: run RDD on each pre-determined covariate
# as the "outcome." There should be no discontinuity.
covariates <- c("age", "income", "education")

for (cov in covariates) {
  rd_cov <- rdrobust(y = df[[cov]], x = df$running_var, c = cutoff)
  cat("\n--- Covariate:", cov, "---\n")
  summary(rd_cov)
}

# Visual check: plot each covariate around the cutoff
for (cov in covariates) {
  rdplot(y = df[[cov]], x = df$running_var, c = cutoff,
         title = paste("Smoothness Check:", cov),
         x.label = "Running Variable", y.label = cov)
}
```

Python:
```python
from rdrobust import rdrobust, rdplot

# Covariate smoothness test
covariates = ['age', 'income', 'education']
cutoff = 0  # set your cutoff

for cov in covariates:
    result = rdrobust(df[cov].values, df['running_var'].values, c=cutoff)
    print(f"\n--- Covariate: {cov} ---")
    print(result)

# Visual check
for cov in covariates:
    rdplot(df[cov].values, df['running_var'].values, c=cutoff,
           title=f'Smoothness Check: {cov}',
           x_label='Running Variable', y_label=cov)
```

**What violation looks like**: Pre-determined covariates show a discontinuity at the cutoff. For example, if income jumps at the cutoff for a poverty program, it suggests either manipulation or a confounding policy that also changes at the same threshold. Visual inspection of the covariate plots shows a clear jump or slope change at c.

**Severity if violated**: Fatal. If potential outcomes are discontinuous at the cutoff for reasons other than treatment, the RDD estimate conflates the treatment effect with the pre-existing discontinuity. The entire identifying assumption collapses.

**Mitigation**: (1) Investigate what is causing the covariate discontinuity — is it another policy at the same cutoff? If so, see "No other discontinuities" below. (2) If manipulation is causing the discontinuity, see "No manipulation" below. (3) Use a "donut hole" RDD that excludes observations very close to the cutoff (where manipulation is most likely). (4) If the discontinuity is in a covariate, control for it — but this changes the interpretation and may not fully resolve the bias. (5) Consider choosing a different cutoff or method if the continuity assumption is clearly violated.

---

## No Manipulation of the Running Variable

**Plain language**: People cannot precisely control which side of the cutoff they end up on. If they can — for example, if students know their exact score and can push themselves just over a scholarship threshold — then the units just above and just below are no longer comparable.

**Formal statement**: The density of the running variable f(X) is continuous at the cutoff: lim_{x->c-} f(x) = lim_{x->c+} f(x). A jump in the density at c suggests units are sorting themselves to one side, violating the as-if-random assignment near the cutoff.

**Testable?**: Yes. The McCrary (2008) density test or the improved Cattaneo, Jansson, and Ma (2020) `rddensity` test directly checks for a discontinuity in the density of the running variable at the cutoff.

**How to test**:

R:
```r
library(rddensity)

# Density test for manipulation
density_test <- rddensity(X = df$running_var, c = cutoff)
summary(density_test)

# Visual: plot the density on both sides of the cutoff
plot_density <- rdplotdensity(density_test, df$running_var,
                               title = "McCrary Density Test",
                               xlabel = "Running Variable",
                               ylabel = "Density")

# Also useful: histogram of the running variable
library(ggplot2)
ggplot(df, aes(x = running_var)) +
  geom_histogram(binwidth = 1, fill = "steelblue", color = "white") +
  geom_vline(xintercept = cutoff, color = "red", linetype = "dashed") +
  labs(title = "Distribution of Running Variable",
       x = "Running Variable", y = "Count") +
  theme_minimal()
```

Python:
```python
from rddensity import rddensity, rdplotdensity
import matplotlib.pyplot as plt

# Density test for manipulation
density_test = rddensity(X=df['running_var'].values, c=cutoff)
print(density_test)

# Visual: plot the density on both sides
rdplotdensity(density_test, df['running_var'].values,
              title='McCrary Density Test',
              xlabel='Running Variable', ylabel='Density')

# Histogram
plt.figure(figsize=(10, 6))
plt.hist(df['running_var'], bins=50, color='steelblue', edgecolor='white')
plt.axvline(x=cutoff, color='red', linestyle='--', label='Cutoff')
plt.xlabel('Running Variable')
plt.ylabel('Count')
plt.title('Distribution of Running Variable')
plt.legend()
plt.tight_layout()
plt.show()
```

**What violation looks like**: A visible "bunching" of observations just above (or just below) the cutoff in a histogram. The density test rejects the null of continuity (p < 0.05). More units than expected on the advantageous side of the cutoff.

**Severity if violated**: Fatal. Manipulation means that units just above and below the cutoff are no longer comparable — they differ systematically in their ability and willingness to manipulate. The treatment is no longer as-if randomly assigned near c, and the RDD estimate is biased.

**Mitigation**: (1) "Donut hole" RDD: exclude observations within a small window around the cutoff (e.g., drop units within 1 point of c). This removes the manipulators but reduces sample size and requires the continuity assumption over a larger neighborhood. (2) Argue that manipulation is imprecise — units can influence but not perfectly control the running variable (e.g., test scores have random noise). (3) Use a fuzzy RDD if crossing the cutoff increases but does not determine treatment. (4) If manipulation is clear and precise, RDD is not credible — choose a different method.

---

## No Other Discontinuities at the Cutoff

**Plain language**: Nothing else changes at the same cutoff besides the treatment you're studying. If another program, rule, or policy also kicks in at the same threshold, you can't tell which one is causing the effect you see.

**Formal statement**: The treatment of interest is the ONLY function of the running variable that is discontinuous at c. No other variable W that affects Y has a discontinuity at c: lim_{x->c+} E[W|X=x] = lim_{x->c-} E[W|X=x] for all relevant W.

**Testable?**: Partially. You can check whether observable covariates and other known policy variables are smooth through the cutoff (same as the continuity test). But you may not know about all policies that share the cutoff.

**How to test**:

R:
```r
library(rdrobust)

# Check other variables that might also change at the cutoff
# (e.g., other programs, policies, rules)
other_treatments <- c("other_program", "benefit_level", "regulatory_status")

for (var in other_treatments) {
  rd_other <- rdrobust(y = df[[var]], x = df$running_var, c = cutoff)
  cat("\n--- Variable:", var, "---\n")
  summary(rd_other)
}

# Check predetermined covariates (same as continuity test)
covariates <- c("age", "income", "education")
for (cov in covariates) {
  rd_cov <- rdrobust(y = df[[cov]], x = df$running_var, c = cutoff)
  cat("\n--- Covariate:", cov, "---\n")
  summary(rd_cov)
}
```

Python:
```python
from rdrobust import rdrobust

# Check other treatments/policies at the same cutoff
other_vars = ['other_program', 'benefit_level', 'regulatory_status']

for var in other_vars:
    result = rdrobust(df[var].values, df['running_var'].values, c=cutoff)
    print(f"\n--- Variable: {var} ---")
    print(result)

# Check predetermined covariates
covariates = ['age', 'income', 'education']
for cov in covariates:
    result = rdrobust(df[cov].values, df['running_var'].values, c=cutoff)
    print(f"\n--- Covariate: {cov} ---")
    print(result)
```

**What violation looks like**: Another treatment or policy also shows a discontinuity at the cutoff. For example, if both a scholarship and a mentoring program are assigned based on the same test score threshold, an observed jump in outcomes could be due to either or both programs. The RDD estimate would capture the combined effect, not the effect of the treatment of interest alone.

**Severity if violated**: Serious. If another treatment also changes at the cutoff, the RDD estimate captures the combined effect of all treatments that change at c. The bias equals the sum of the other treatments' effects. This is a failure of isolation, not of internal validity per se — the estimated discontinuity is real, but you can't attribute it to your treatment alone.

**Mitigation**: (1) Identify all programs and policies that share the cutoff, and control for them if possible. (2) Exploit a cutoff that is unique to the treatment of interest. (3) If multiple treatments share the cutoff, use an alternative cutoff (e.g., a different year when only one policy was in effect). (4) Estimate the combined effect and discuss partial identification of the component of interest. (5) Use a different research design entirely (e.g., DiD if you have pre/post data).

---

## Local Identification

**Plain language**: The RDD estimates the treatment effect only for units right at the cutoff — not for everyone. A scholarship program's effect at the 80-point threshold tells you about students scoring around 80, not about students scoring 50 or 95. The result may not generalize to the broader population.

**Formal statement**: The RDD identifies the Average Treatment Effect at the cutoff: tau_RD = E[Y(1) - Y(0) | X = c]. This is a local parameter — it applies to the subpopulation of units with running variable values at or very near c. It is generally not equal to the ATE or ATT for the entire population.

**Testable?**: Not testable per se — this is an inherent property of the RDD design, not an assumption that can be violated. It is an interpretation caveat rather than an identification threat.

**How to test**:

While not a testable assumption, you can explore how the effect varies across bandwidth choices (which implicitly changes the "local" population):

R:
```r
library(rdrobust)

# Main RDD estimate
rd_main <- rdrobust(y = df$outcome, x = df$running_var, c = cutoff)
summary(rd_main)

# Bandwidth sensitivity: how does the estimate change?
bandwidths <- c(rd_main$bws[1, 1] * 0.5,
                rd_main$bws[1, 1] * 0.75,
                rd_main$bws[1, 1],
                rd_main$bws[1, 1] * 1.25,
                rd_main$bws[1, 1] * 1.5)

for (bw in bandwidths) {
  rd_bw <- rdrobust(y = df$outcome, x = df$running_var, c = cutoff, h = bw)
  cat("Bandwidth:", round(bw, 2),
      "| Estimate:", round(rd_bw$coef[1], 4),
      "| CI: [", round(rd_bw$ci[1, 1], 4), ",",
      round(rd_bw$ci[1, 2], 4), "]\n")
}
# If the estimate is stable across bandwidths, the local effect is robust.
# If it changes substantially with wider bandwidths, the effect may
# differ away from the cutoff.
```

Python:
```python
from rdrobust import rdrobust

# Main RDD estimate
rd_main = rdrobust(df['outcome'].values, df['running_var'].values, c=cutoff)
print(rd_main)

# Bandwidth sensitivity
import numpy as np
opt_bw = rd_main.bws.values[0][0]  # optimal bandwidth
bandwidths = [opt_bw * m for m in [0.5, 0.75, 1.0, 1.25, 1.5]]

for bw in bandwidths:
    rd_bw = rdrobust(df['outcome'].values, df['running_var'].values,
                     c=cutoff, h=bw)
    print(f"Bandwidth: {bw:.2f} | "
          f"Estimate: {rd_bw.coef.values[0][0]:.4f} | "
          f"CI: [{rd_bw.ci.values[0][0]:.4f}, {rd_bw.ci.values[0][1]:.4f}]")
```

**What violation looks like**: Not a "violation" per se. The concern manifests when decision-makers want to apply the RDD finding to units far from the cutoff. For example, extrapolating the effect of a remedial program at the 50th percentile cutoff to students at the 20th percentile is not supported by the RDD design.

**Severity if violated**: Minor. This is an external validity / generalizability concern, not an internal validity issue. The estimate at the cutoff is still valid — it just may not apply elsewhere.

**Mitigation**: (1) Be transparent that the RDD effect is local and state who it applies to (e.g., "This effect applies to students scoring near the threshold of 80 points"). (2) If the policy question is about effects away from the cutoff, RDD is the wrong tool — consider DiD, IV, or matching. (3) If multiple cutoffs exist (e.g., different regions with different thresholds), estimate effects at each and compare to assess how the effect varies. (4) Extrapolation methods exist (e.g., Angrist & Rokkanen 2015), but require strong additional assumptions.
