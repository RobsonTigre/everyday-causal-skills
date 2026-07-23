# Audit — Loyalty Program DiD

**Overall verdict: YELLOW** — no fatal findings, 2 serious findings. The
estimate is usable but should be reported with the caveats below.

## Findings

### SERIOUS: Short pre-period limits the parallel-trends test's power

Only 6 months of pre-treatment data are available. The joint pre-trend test
does not reject equal pre-treatment trends, but with only 6 pre-periods the
test has limited power to detect a slow-moving divergence between treated
and control stores. Recommend treating the parallel-trends finding as
supportive rather than dispositive, and revisiting with a longer pre-period
if the program is re-evaluated later.

### SERIOUS: Small number of treated clusters

With only 12 treated stores (of 50 total), cluster-robust standard errors
can be unreliable in finite samples (the standard asymptotic justification
assumes many clusters). Recommend a wild cluster bootstrap as a robustness
check before treating the reported 95% CI as final.

## Not flagged

- **SUTVA**: No evidence of spillover between treated and control stores
  (they are not co-located or served by shared staff).
- **Manipulation of treatment assignment**: Store selection for the pilot
  was based on pre-determined size/region criteria recorded before launch,
  not on anticipated outcomes.
- **Unobserved confounding (store manager quality)**: Noted in `dag.md` as a
  residual threat. Not elevated to a finding because it would need to be
  correlated with the *timing* of the loyalty launch specifically, not just
  with store performance generally, to bias a DiD estimate — no evidence of
  that here, but it cannot be ruled out with the available data.
