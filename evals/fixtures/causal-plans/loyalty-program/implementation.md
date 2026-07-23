# Implementation — DiD Estimate of Loyalty Program Effect

## Stage 1: Data

50 stores (12 treated, 38 control), 24 monthly observations each (1,200
store-months). Program launched in month 7 for all 12 treated stores at once.

## Stage 2: Parallel trends check

Joint F-test on treated × pre-period-month interactions (months 1-6):
the joint test does not reject equal pre-treatment trends. Pre-period is
short (6 months), which limits the power of this test; see `audit.md`.

## Stage 3: Estimation

Two-way fixed effects regression (store and month fixed effects), clustered
standard errors by store:

```
repeat_purchase_rate ~ treated_x_post + store_fe + month_fe
```

**ATT = 12 percentage point increase in repeat purchases (95% CI: [8, 16] pp)**,
averaged over the 18 post-launch months.

## Stage 4: Robustness

- Excluding the largest treated store leaves the estimate materially
  unchanged (11.6 pp, 95% CI: [7.4, 15.8] pp).

## Stage 5: Interpretation

The loyalty program caused a 12 percentage point increase in repeat
purchases among enrolled stores, over a year and a half of post-launch
data. See `dag.md` for the identification argument and `audit.md` for
validity threats.
