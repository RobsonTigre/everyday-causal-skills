# Analysis Plan — Loyalty Program Impact on Repeat Purchases

**Date**: 2026-03-15
**Business objective**: Evaluation. The loyalty program was already rolled out to
12 stores; leadership wants to know whether it caused an increase in repeat
purchases before deciding whether to expand it to the remaining 38 stores.

## Design

- **Treatment**: Enrollment in the new loyalty program.
- **Outcome**: Repeat purchase rate (share of customers with a second purchase
  within 90 days).
- **Units**: 50 retail stores total — 12 treated, 38 untreated (comparison group).
- **Panel**: 24 months of store-month data. The program launched in month 7 for
  all 12 treated stores simultaneously (no staggering) — 6 months pre-period,
  18 months post-period.
- **Recommended method**: Difference-in-differences (two-way fixed effects),
  store and month fixed effects, standard errors clustered by store.

## Key assumption to verify

Parallel trends: treated and control stores must show similar repeat-purchase
trends in the 6 months before launch. Hand off to `/causal-dag` to confirm no
other store-level intervention coincided with the loyalty program launch, then
to `/causal-did` for estimation.

## Next steps

1. `/causal-dag` — confirm the adjustment set (store-level confounders).
2. `/causal-did` — estimate the treatment effect.
3. `/causal-auditor` — stress-test the result.
