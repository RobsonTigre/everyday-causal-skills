# Implementation — Matching Estimate of Structured-Interview Pilot Effect

## Context

A structured-interview scorecard was piloted with a subset of hiring
managers to see whether it changed the interview-to-offer conversion rate.
Managers were not randomly assigned to the pilot — adoption was voluntary,
so this is an observational matching analysis, not an experiment.

## Data

1,400 candidate interviews over 6 months: 380 conducted by a pilot-adopting
manager (treated), 1,020 by a non-adopting manager (control). Covariates:
candidate years of experience, role level, interview panel size, and
manager tenure.

## Method

Propensity score matching (nearest-neighbor, 1:1, caliper 0.1), estimating
the ATT of the structured scorecard on interview-to-offer conversion.

## Balance diagnostics

| Covariate | SMD before | SMD after |
|---|---|---|
| Years of experience | 0.34 | 0.05 |
| Role level | 0.28 | 0.04 |
| Panel size | 0.19 | 0.03 |
| Manager tenure | 0.41 | 0.07 |

All standardized mean differences fall below 0.1 after matching — good
balance achieved on observed covariates.

## Result

**ATT = 9 percentage points (95% CI: [4, 14])** increase in interview-to-offer
conversion rate for candidates interviewed under the structured scorecard,
on a control-group base rate of 22%.

## Caveat

Matching only balances observed covariates. Manager-level factors that
drove *voluntary* adoption of the scorecard (e.g., general interviewing
rigor) are not fully captured by the four covariates above and could still
bias this estimate upward. No sensitivity analysis (e.g., Rosenbaum bounds)
has been run yet.
