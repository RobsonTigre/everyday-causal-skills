# ROI Translation — Python Template

Turns an estimated causal effect into financial value through one canonical
pipeline (see `references/roi-framework.md`): normalization → estimand scaling
→ projection waterfall → ROI with uncertainty → breakeven → verdict. Every
published number comes from executing this script — never from mental math.

## Prerequisites

> Missing packages? See `references/preflight.md`: the snippet below only *detects* what's
> missing — then the agent offers to install it for you. Nothing is installed without your okay.

```python
# --- Preflight: detect missing packages (does NOT install) ---
import importlib.util

required = {"numpy": "numpy", "pandas": "pandas"}  # import-name -> pip-name (they match unless noted)
missing = [pip for mod, pip in required.items() if importlib.util.find_spec(mod) is None]
if missing:
    print("Missing Python packages:", ", ".join(missing))
    print("Install with: pip install " + " ".join(missing))
else:
    print("All required Python packages are installed.")

import numpy as np
import pandas as pd
```

## Named Inputs

The ONLY block that changes per analysis. Every financial parameter is
(a) sourced from artifacts/finance/product data, (b) a labeled scenario range
approved by the user, or (c) unknown — in which case the verdict is withheld.
Never silently adopt the book's illustrative values.

```python
# --- Named inputs (adapt values; keep names and structure) --------------------
# Currency: symbol used verbatim, never converted. Mixed currencies are FATAL.
currency = "R$"

# Causal estimate (from artifacts or interview)
effect_raw = 3.90     # per-unit effect in the study's outcome construct (example: revenue/user/month)
ci_lo_raw  = 2.9167   # interval bounds around effect_raw, same construct
ci_hi_raw  = 4.8833
ci_level   = 0.95     # recorded from the upstream analysis; never assumed or relabeled
estimand   = "ATE"    # ATE / ITT / LATE / ATT / cumulative / CATE — see scaling below

# Normalization (framework section 2): reduce to incremental PROFIT per
# identified unit per base period. Here: a revenue effect times a margin.
# Probability-POINT effects: delta_p * value_per_event (never times baseline).
# Relative lifts: baseline * relative_lift * value_per_event.
# Logit/probit coefficients: require an AME first — never exp(beta)-1.
margin = 0.60         # share of each revenue unit surviving variable costs (1.0 if already profit)

# Estimand scaling (framework section 4): who does the effect apply to?
# LATE -> complier share (product adoption is NOT the complier share).
# CATE -> segment weight. ITT/ATE -> 1.0 (ITT: take-up is already embedded;
# a second adoption adjustment double-counts).
scaling_factor = 1.0

# Population & pipeline
horizon    = 12                                        # projection periods (same period as the effect)
n_eligible = np.full(horizon, 5e6)                     # ELIGIBLE units per period (pre-rollout, pre-survival)
                                                       # If you only have an ACTIVE/surviving path, put it
                                                       # here and set survival = 1 (never apply survival twice).
rollout    = np.minimum(1.0, 0.25 * np.arange(1, horizon + 1))  # deployment ramp in [0,1]; for ITT: deployment only
persistence = 0.90    # lambda: effect persistence per period, in (0,1] — growth (>1) is rejected
survival    = 0.97    # unit survival per period, in [0,1]
discount    = 0.01    # discount rate r per period (from finance; 0 only if the user says so)
transport   = 0.95    # representativeness of study pop for rollout pop, in [0,1] (0 is valid)
net_incrementality = 0.97  # survives cannibalization / SUTVA at scale, in [0,1] (0 is valid)

# Investment (cost taxonomy, framework section 3 — each cost in exactly one place)
one_time  = 4e6                       # fixed build cost at t = 0
recurring = np.full(horizon, 1e5)     # per-period maintenance/licence costs

# Decision policy (framework section 6)
hurdle           = 0.0   # minimum acceptable ROI; a CONFIRMED 0 = breakeven is valid
hurdle_confirmed = True  # False -> "clears breakeven by X" language only, no ship/kill verdict
margin_buffer    = 2.0   # comfortable = CI lower bound >= buffer x hurdle line (process choice)
```

## Input Validation

```python
# --- Validate before any arithmetic: bad inputs are blocking errors, not warnings ---
def require(ok, msg):
    if not ok:
        raise ValueError(msg)

require(ci_lo_raw <= effect_raw <= ci_hi_raw,
        "FATAL input error: interval must satisfy ci_lo <= effect <= ci_hi")
require(0 < persistence <= 1,
        "persistence (lambda) must be in (0,1]; growing effects (>1) are not supported in v1")
require(0 <= survival <= 1, "survival must be in [0,1]")
require(discount >= 0, "discount rate must be >= 0")
require(bool(np.all((rollout >= 0) & (rollout <= 1))), "rollout must be in [0,1] each period")
require(0 <= transport <= 1, "transport factor must be in [0,1]")
require(0 <= net_incrementality <= 1, "net incrementality factor must be in [0,1]")
require(0 <= scaling_factor <= 1, "scaling factor must be in [0,1]")
require(len(n_eligible) == horizon and len(rollout) == horizon and len(recurring) == horizon,
        "n_eligible, rollout, recurring must each have `horizon` entries (same time base)")
require(margin >= 0, "margin must be >= 0")
```

## Normalization & Estimand Scaling

```python
# Normalization gate: reduce the causal result to incremental profit per
# identified unit per base period (Delta-Profit_0). WHY: money math is only
# meaningful once the effect is on a profit-per-unit-per-period basis.
delta_profit0 = effect_raw * margin
ci_lo_n = ci_lo_raw * margin   # margin >= 0, so the plug-in transformation is monotone
ci_hi_n = ci_hi_raw * margin

# Estimand scaling enters the population size once (and only once): for a LATE,
# the value accrues to compliers, so the monetizable population is N x share.
```

## Pipeline: Waterfall, ROI, Breakeven

```python
# Per-period pipeline weights. WHY each factor exists:
#   persistence**t : effects fade (novelty wears off, competitors adapt)
#   survival**t    : units churn off the platform
#   1/(1+r)**t     : money later is worth less than money now
t_idx = np.arange(horizon)
unit_weight = persistence**t_idx * survival**t_idx / (1 + discount)**t_idx

# EFFECTIVE_PERIODS: a decayed, discounted count of full-strength periods.
# Reduces to the book's sum(lambda**t) when survival = 1 and r = 0.
effective_periods = float(unit_weight.sum())
pv_per_unit = delta_profit0 * effective_periods  # label as delta-CLV ONLY when the unit is a customer

# Projection waterfall: start naive, discount one factor at a time so every
# deduction is visible (nothing hides inside a single multiplier).
w0_naive     = delta_profit0 * float((n_eligible * scaling_factor).sum())              # naive projection
w1_decay     = delta_profit0 * float((n_eligible * scaling_factor * unit_weight).sum())  # + persistence/survival/discount
w2_rollout   = delta_profit0 * float((n_eligible * scaling_factor * rollout * unit_weight).sum())  # + adoption ramp
w3_transport = w2_rollout * transport                                                   # + representativeness
w4_netincr   = w3_transport * net_incrementality                                        # + cannibalization / SUTVA

# Pipeline multiplier M: everything except the effect itself. The SAME M feeds
# ROI, the CI bounds, and breakeven — one pipeline, no parallel formulas.
M = float((n_eligible * scaling_factor * rollout * unit_weight).sum()) * transport * net_incrementality
pv_incremental_profit = delta_profit0 * M   # equals w4_netincr by construction

pv_investment = one_time + float((recurring / (1 + discount)**t_idx).sum())
require(pv_investment > 0,
        "investment is zero: ROI and breakeven are undefined — report PV_INCREMENTAL_PROFIT only")
require(M > 0, "pipeline multiplier M is zero: no monetizable exposure — breakeven undefined")

net_profit = pv_incremental_profit - pv_investment
roi    = net_profit / pv_investment
roi_lo = (ci_lo_n * M - pv_investment) / pv_investment  # plug-in: valid because the
roi_hi = (ci_hi_n * M - pv_investment) / pv_investment  # calculation is monotone in the effect

# Breakeven from the SAME pipeline: the Delta-Profit_0 that makes ROI exactly 0.
breakeven_effect = pv_investment / M
hurdle_line = (1 + hurdle) * pv_investment / M  # nonzero hurdle shifts the decision line
```

## Verdict (Decision Matrix)

```python
# Margin of safety, not interval width, drives the call (framework section 6):
#   CI lower bound >= buffer x line  -> Ship (comfortable)
#   lower bound in [line, buffer x line) -> Ship, staged (thin)
#   CI straddles the line            -> Size the bet (never plain "ship")
#   upper bound below the line       -> Kill (write the kill memo)
if ci_hi_n < hurdle_line:
    verdict_code = -1
elif ci_lo_n >= margin_buffer * hurdle_line:
    verdict_code = 2
elif ci_lo_n >= hurdle_line:
    verdict_code = 1
else:
    verdict_code = 0
verdict_label = {-1: "KILL", 0: "SIZE THE BET", 1: "SHIP (STAGED)", 2: "SHIP"}[verdict_code]
if not hurdle_confirmed:
    # No confirmed business hurdle: report the breakeven comparison, withhold ship/kill.
    verdict_label = (f"no confirmed hurdle - effect clears breakeven by "
                     f"{ci_lo_n / breakeven_effect:.1f}x at the CI lower bound")
```

## Sensitivity (multi-period forecasts only)

```python
# Stress the two forecast assumptions (persistence and discount rate).
# WHY: with a multi-period forecast, lambda compounds — small errors grow large.
# Skipping this table on a multi-period forecast is a SERIOUS violation.
if horizon > 1:
    print("\nSensitivity: ROI under alternative persistence / discount assumptions")
    lams = sorted({min(1.0, max(0.05, v)) for v in
                   (persistence - 0.1, persistence, persistence + 0.1)})
    for lam in lams:
        for r2 in sorted({0.0, discount, 2 * discount}):
            w2 = lam**t_idx * survival**t_idx / (1 + r2)**t_idx
            M2 = float((n_eligible * scaling_factor * rollout * w2).sum()) * transport * net_incrementality
            inv2 = one_time + float((recurring / (1 + r2)**t_idx).sum())
            print(f"  lambda={lam:.2f} r={r2:.3f} -> ROI {(delta_profit0 * M2 - inv2) / inv2:.2f}")
```

## One-Pager Block & Machine-Readable Results

```python
# Human-readable one-pager block (waterfall shown factor by factor).
fmt = lambda x: f"{x:,.0f}"
print("\n=== ROI one-pager ===============================================")
print(f"Effect (normalized): {currency}{delta_profit0:.4f} per unit per period "
      f"({100 * ci_level:.0f}% CI [{ci_lo_n:.4f}, {ci_hi_n:.4f}])")
print(f"Projection waterfall ({currency}):")
print(f"  naive projection                 {fmt(w0_naive)}")
print(f"  + persistence/survival/discount  {fmt(w1_decay)}")
print(f"  + adoption ramp (rollout)        {fmt(w2_rollout)}")
print(f"  + transport (representativeness) {fmt(w3_transport)}")
print(f"  + net incrementality (cannibalization/SUTVA) {fmt(w4_netincr)}")
print(f"Investment (PV): {currency}{fmt(pv_investment)} | Net profit: {currency}{fmt(net_profit)}")
print(f"ROI: {roi:.2f}  [{roi_lo:.2f}, {roi_hi:.2f} at the effect's {100 * ci_level:.0f}% CI]")
print(f"Breakeven effect (same pipeline): {currency}{breakeven_effect:.4f} per unit per period")
print(f"Verdict: {verdict_label}")

# Machine-readable KEY: value lines (parity contract — keep names and format).
print(f"EFFECTIVE_PERIODS:{effective_periods:.10f}")
print(f"PV_INCREMENTAL_PROFIT_PER_UNIT:{pv_per_unit:.10f}")
print(f"PV_INCREMENTAL_PROFIT:{pv_incremental_profit:.10f}")
print(f"NET_PROFIT:{net_profit:.10f}")
print(f"ROI:{roi:.10f}")
print(f"ROI_LO:{roi_lo:.10f}")
print(f"ROI_HI:{roi_hi:.10f}")
print(f"BREAKEVEN_EFFECT:{breakeven_effect:.10f}")
print(f"VERDICT_CODE:{verdict_code}")

# roi-results.csv: the inter-skill data contract consumed by /causal-report
# (framework section 10). Withheld/undefined results keep an empty value —
# never a fabricated number.
results = pd.DataFrame({
    "metric": ["EFFECTIVE_PERIODS", "PV_INCREMENTAL_PROFIT_PER_UNIT",
               "PV_INCREMENTAL_PROFIT", "NET_PROFIT", "ROI", "ROI", "ROI",
               "BREAKEVEN_EFFECT", "VERDICT_CODE"],
    "scenario": "base",
    "value": [effective_periods, pv_per_unit, pv_incremental_profit, net_profit,
              roi, roi_lo, roi_hi, breakeven_effect, verdict_code],
    "currency": ["", currency, currency, currency, "", "", "", currency, ""],
    "unit": ["periods", "per unit", "total", "total", "ratio", "ratio", "ratio",
             "per unit per period", "code"],
    "interval_level": ["", "", "", "", "", ci_level, ci_level, "", ""],
    "status": ["point", "point", "point", "point", "point", "lo", "hi", "point", "point"],
    "notes": "",
})
results.to_csv("roi-results.csv", index=False)
print("\nWrote roi-results.csv")
```
