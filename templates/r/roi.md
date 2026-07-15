# ROI Translation — R Template

Turns an estimated causal effect into financial value through one canonical
pipeline (see `references/roi-framework.md`): normalization → estimand scaling
→ projection waterfall → ROI with uncertainty → breakeven → verdict. Every
published number comes from executing this script — never from mental math.

## Prerequisites

> Base R only — no packages to install. (Nothing to preflight.)

```r
# --- Preflight: base R only, nothing to detect or install ---
cat("All required R packages are installed (base R only).\n")
```

## Named Inputs

The ONLY block that changes per analysis. Every financial parameter is
(a) sourced from artifacts/finance/product data, (b) a labeled scenario range
approved by the user, or (c) unknown — in which case the verdict is withheld.
Never silently adopt the book's illustrative values.

```r
# --- Named inputs (adapt values; keep names and structure) --------------------
# Currency: symbol used verbatim, never converted. Mixed currencies are FATAL.
currency <- "R$"

# Causal estimate (from artifacts or interview)
effect_raw <- 3.90     # per-unit effect in the study's outcome construct (example: revenue/user/month)
ci_lo_raw  <- 2.9167   # interval bounds around effect_raw, same construct
ci_hi_raw  <- 4.8833
ci_level   <- 0.95     # recorded from the upstream analysis; never assumed or relabeled
estimand   <- "ATE"    # ATE / ITT / LATE / ATT / cumulative / CATE — see scaling below

# Normalization (framework section 2): reduce to incremental PROFIT per
# identified unit per base period. Here: a revenue effect times a margin.
# Probability-POINT effects: delta_p * value_per_event (never times baseline).
# Relative lifts: baseline * relative_lift * value_per_event.
# Logit/probit coefficients: require an AME first — never exp(beta)-1.
margin <- 0.60         # share of each revenue unit surviving variable costs (1.0 if already profit)

# Estimand scaling (framework section 4): who does the effect apply to?
# LATE -> complier share (product adoption is NOT the complier share).
# CATE -> segment weight. ITT/ATE -> 1.0 (ITT: take-up is already embedded;
# a second adoption adjustment double-counts).
scaling_factor <- 1.0

# Population & pipeline
horizon    <- 12                          # projection periods (same period as the effect)
n_eligible <- rep(5e6, horizon)           # ELIGIBLE units per period (pre-rollout, pre-survival)
                                          # If you only have an ACTIVE/surviving path, put it here
                                          # and set survival <- 1 (never apply survival twice).
rollout    <- pmin(1, 0.25 * (1:horizon)) # deployment ramp in [0,1]; for ITT: deployment only
persistence <- 0.90    # lambda: effect persistence per period, in (0,1] — growth (>1) is rejected
survival    <- 0.97    # unit survival per period, in [0,1]
discount    <- 0.01    # discount rate r per period (from finance; 0 only if the user says so)
transport   <- 0.95    # representativeness of study pop for rollout pop, in [0,1] (0 is valid)
net_incrementality <- 0.97  # survives cannibalization / SUTVA at scale, in [0,1] (0 is valid)

# Investment (cost taxonomy, framework section 3 — each cost in exactly one place)
one_time  <- 4e6                # fixed build cost at t = 0
recurring <- rep(1e5, horizon)  # per-period maintenance/licence costs

# Decision policy (framework section 6)
hurdle           <- 0.0   # minimum acceptable ROI; a CONFIRMED 0 = breakeven is valid
hurdle_confirmed <- TRUE  # FALSE -> "clears breakeven by X" language only, no ship/kill verdict
margin_buffer    <- 2.0   # comfortable = CI lower bound >= buffer x hurdle line (process choice)
```

## Input Validation

```r
# --- Validate before any arithmetic: bad inputs are blocking errors, not warnings ---
stopifnot_msg <- function(ok, msg) if (!ok) stop(msg, call. = FALSE)

stopifnot_msg(ci_lo_raw <= effect_raw && effect_raw <= ci_hi_raw,
              "FATAL input error: interval must satisfy ci_lo <= effect <= ci_hi")
stopifnot_msg(persistence > 0 && persistence <= 1,
              "persistence (lambda) must be in (0,1]; growing effects (>1) are not supported in v1")
stopifnot_msg(survival >= 0 && survival <= 1, "survival must be in [0,1]")
stopifnot_msg(discount >= 0, "discount rate must be >= 0")
stopifnot_msg(all(rollout >= 0 & rollout <= 1), "rollout must be in [0,1] each period")
stopifnot_msg(transport >= 0 && transport <= 1, "transport factor must be in [0,1]")
stopifnot_msg(net_incrementality >= 0 && net_incrementality <= 1,
              "net incrementality factor must be in [0,1]")
stopifnot_msg(scaling_factor >= 0 && scaling_factor <= 1, "scaling factor must be in [0,1]")
stopifnot_msg(length(n_eligible) == horizon && length(rollout) == horizon &&
              length(recurring) == horizon,
              "n_eligible, rollout, recurring must each have `horizon` entries (same time base)")
stopifnot_msg(margin >= 0, "margin must be >= 0")
```

## Normalization & Estimand Scaling

```r
# Normalization gate: reduce the causal result to incremental profit per
# identified unit per base period (Delta-Profit_0). WHY: money math is only
# meaningful once the effect is on a profit-per-unit-per-period basis.
delta_profit0 <- effect_raw * margin
ci_lo_n <- ci_lo_raw * margin   # margin >= 0, so the plug-in transformation is monotone
ci_hi_n <- ci_hi_raw * margin

# Estimand scaling enters the population size once (and only once): for a LATE,
# the value accrues to compliers, so the monetizable population is N x share.
```

## Pipeline: Waterfall, ROI, Breakeven

```r
# Per-period pipeline weights. WHY each factor exists:
#   persistence^t : effects fade (novelty wears off, competitors adapt)
#   survival^t    : units churn off the platform
#   1/(1+r)^t     : money later is worth less than money now
t_idx <- 0:(horizon - 1)
unit_weight <- persistence^t_idx * survival^t_idx / (1 + discount)^t_idx

# EFFECTIVE_PERIODS: a decayed, discounted count of full-strength periods.
# Reduces to the book's sum(lambda^t) when survival = 1 and r = 0.
effective_periods <- sum(unit_weight)
pv_per_unit <- delta_profit0 * effective_periods  # label as delta-CLV ONLY when the unit is a customer

# Projection waterfall: start naive, discount one factor at a time so every
# deduction is visible (nothing hides inside a single multiplier).
w0_naive     <- delta_profit0 * sum(n_eligible * scaling_factor)          # naive projection
w1_decay     <- delta_profit0 * sum(n_eligible * scaling_factor * unit_weight)  # + persistence/survival/discount
w2_rollout   <- delta_profit0 * sum(n_eligible * scaling_factor * rollout * unit_weight)  # + adoption ramp
w3_transport <- w2_rollout * transport                                     # + representativeness
w4_netincr   <- w3_transport * net_incrementality                          # + cannibalization / SUTVA

# Pipeline multiplier M: everything except the effect itself. The SAME M feeds
# ROI, the CI bounds, and breakeven — one pipeline, no parallel formulas.
M <- sum(n_eligible * scaling_factor * rollout * unit_weight) * transport * net_incrementality
pv_incremental_profit <- delta_profit0 * M   # equals w4_netincr by construction

pv_investment <- one_time + sum(recurring / (1 + discount)^t_idx)
stopifnot_msg(pv_investment > 0,
              "investment is zero: ROI and breakeven are undefined — report PV_INCREMENTAL_PROFIT only")
stopifnot_msg(M > 0,
              "pipeline multiplier M is zero: no monetizable exposure — breakeven undefined")

net_profit <- pv_incremental_profit - pv_investment
roi    <- net_profit / pv_investment
roi_lo <- (ci_lo_n * M - pv_investment) / pv_investment  # plug-in: valid because the
roi_hi <- (ci_hi_n * M - pv_investment) / pv_investment  # calculation is monotone in the effect

# Breakeven from the SAME pipeline: the Delta-Profit_0 that makes ROI exactly 0.
breakeven_effect <- pv_investment / M
hurdle_line <- (1 + hurdle) * pv_investment / M  # nonzero hurdle shifts the decision line
```

## Verdict (Decision Matrix)

```r
# Margin of safety, not interval width, drives the call (framework section 6):
#   CI lower bound >= buffer x line  -> Ship (comfortable)
#   lower bound in [line, buffer x line) -> Ship, staged (thin)
#   CI straddles the line            -> Size the bet (never plain "ship")
#   upper bound below the line       -> Kill (write the kill memo)
verdict_code <- if (ci_hi_n < hurdle_line) {
  -1L
} else if (ci_lo_n >= margin_buffer * hurdle_line) {
  2L
} else if (ci_lo_n >= hurdle_line) {
  1L
} else {
  0L
}
verdict_label <- c(`-1` = "KILL", `0` = "SIZE THE BET", `1` = "SHIP (STAGED)",
                   `2` = "SHIP")[as.character(verdict_code)]
if (!hurdle_confirmed) {
  # No confirmed business hurdle: report the breakeven comparison, withhold ship/kill.
  verdict_label <- sprintf("no confirmed hurdle - effect clears breakeven by %.1fx at the CI lower bound",
                           ci_lo_n / breakeven_effect)
}
```

## Sensitivity (multi-period forecasts only)

```r
# Stress the two forecast assumptions (persistence and discount rate).
# WHY: with a multi-period forecast, lambda compounds — small errors grow large.
# Skipping this table on a multi-period forecast is a SERIOUS violation.
if (horizon > 1) {
  cat("\nSensitivity: ROI under alternative persistence / discount assumptions\n")
  for (lam in unique(pmin(1, pmax(0.05, c(persistence - 0.1, persistence, persistence + 0.1))))) {
    for (r2 in unique(c(0, discount, 2 * discount))) {
      w2 <- lam^t_idx * survival^t_idx / (1 + r2)^t_idx
      M2 <- sum(n_eligible * scaling_factor * rollout * w2) * transport * net_incrementality
      inv2 <- one_time + sum(recurring / (1 + r2)^t_idx)
      cat(sprintf("  lambda=%.2f r=%.3f -> ROI %.2f\n",
                  lam, r2, (delta_profit0 * M2 - inv2) / inv2))
    }
  }
}
```

## One-Pager Block & Machine-Readable Results

```r
# Human-readable one-pager block (waterfall shown factor by factor).
fmt <- function(x) format(round(x), big.mark = ",", scientific = FALSE)
cat("\n=== ROI one-pager ===============================================\n")
cat(sprintf("Effect (normalized): %s%.4f per unit per period (%.0f%% CI [%.4f, %.4f])\n",
            currency, delta_profit0, 100 * ci_level, ci_lo_n, ci_hi_n))
cat(sprintf("Projection waterfall (%s):\n", currency))
cat(sprintf("  naive projection                 %s\n", fmt(w0_naive)))
cat(sprintf("  + persistence/survival/discount  %s\n", fmt(w1_decay)))
cat(sprintf("  + adoption ramp (rollout)        %s\n", fmt(w2_rollout)))
cat(sprintf("  + transport (representativeness) %s\n", fmt(w3_transport)))
cat(sprintf("  + net incrementality (cannibalization/SUTVA) %s\n", fmt(w4_netincr)))
cat(sprintf("Investment (PV): %s%s | Net profit: %s%s\n",
            currency, fmt(pv_investment), currency, fmt(net_profit)))
cat(sprintf("ROI: %.2f  [%.2f, %.2f at the effect's %.0f%% CI]\n",
            roi, roi_lo, roi_hi, 100 * ci_level))
cat(sprintf("Breakeven effect (same pipeline): %s%.4f per unit per period\n",
            currency, breakeven_effect))
cat(sprintf("Verdict: %s\n", verdict_label))

# Machine-readable KEY: value lines (parity contract — keep names and format).
cat(sprintf("EFFECTIVE_PERIODS:%.10f\n", effective_periods))
cat(sprintf("PV_INCREMENTAL_PROFIT_PER_UNIT:%.10f\n", pv_per_unit))
cat(sprintf("PV_INCREMENTAL_PROFIT:%.10f\n", pv_incremental_profit))
cat(sprintf("NET_PROFIT:%.10f\n", net_profit))
cat(sprintf("ROI:%.10f\n", roi))
cat(sprintf("ROI_LO:%.10f\n", roi_lo))
cat(sprintf("ROI_HI:%.10f\n", roi_hi))
cat(sprintf("BREAKEVEN_EFFECT:%.10f\n", breakeven_effect))
cat(sprintf("VERDICT_CODE:%d\n", verdict_code))

# roi-results.csv: the inter-skill data contract consumed by /causal-report
# (framework section 10). Withheld/undefined results keep an empty value —
# never a fabricated number.
results <- data.frame(
  metric = c("EFFECTIVE_PERIODS", "PV_INCREMENTAL_PROFIT_PER_UNIT",
             "PV_INCREMENTAL_PROFIT", "NET_PROFIT", "ROI", "ROI", "ROI",
             "BREAKEVEN_EFFECT", "VERDICT_CODE"),
  scenario = "base",
  value = c(effective_periods, pv_per_unit, pv_incremental_profit, net_profit,
            roi, roi_lo, roi_hi, breakeven_effect, verdict_code),
  currency = c("", currency, currency, currency, "", "", "", currency, ""),
  unit = c("periods", "per unit", "total", "total", "ratio", "ratio", "ratio",
           "per unit per period", "code"),
  interval_level = c("", "", "", "", "", ci_level, ci_level, "", ""),
  status = c("point", "point", "point", "point", "point", "lo", "hi", "point", "point"),
  notes = ""
)
write.csv(results, "roi-results.csv", row.names = FALSE)
cat("\nWrote roi-results.csv\n")
```
