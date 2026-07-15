# ROI translation pipeline -- R reference.
# `df` is preloaded by the parity runner from the shared fixture (one row per
# period; scalar inputs are constant columns read from the first row).
# Mirrors templates/r/roi.md and the Python recipe term for term: validation ->
# normalization -> estimand scaling -> pipeline multiplier M -> ROI (point +
# plug-in bounds) -> breakeven from the SAME pipeline -> verdict code.

require_ok <- function(ok, msg) if (!ok) stop(msg, call. = FALSE)

horizon    <- nrow(df)
t_idx      <- 0:(horizon - 1)
n_eligible <- as.numeric(df$n_eligible)
rollout    <- as.numeric(df$rollout)
recurring  <- as.numeric(df$recurring)

effect_raw <- df$effect_raw[1]; ci_lo_raw <- df$ci_lo_raw[1]; ci_hi_raw <- df$ci_hi_raw[1]
margin     <- df$margin[1];     scaling_factor <- df$scaling_factor[1]
persistence <- df$persistence[1]; survival <- df$survival[1]; discount <- df$discount[1]
transport  <- df$transport[1];  net_incrementality <- df$net_incrementality[1]
one_time   <- df$one_time[1];   hurdle <- df$hurdle[1]; margin_buffer <- df$margin_buffer[1]

# Validation: bad inputs are blocking errors, not warnings.
require_ok(ci_lo_raw <= effect_raw && effect_raw <= ci_hi_raw,
           "interval must satisfy ci_lo <= effect <= ci_hi")
require_ok(persistence > 0 && persistence <= 1, "persistence must be in (0,1]")
require_ok(survival >= 0 && survival <= 1, "survival must be in [0,1]")
require_ok(discount >= 0, "discount rate must be >= 0")
require_ok(all(rollout >= 0 & rollout <= 1), "rollout must be in [0,1]")
require_ok(transport >= 0 && transport <= 1, "transport must be in [0,1]")
require_ok(net_incrementality >= 0 && net_incrementality <= 1,
           "net incrementality must be in [0,1]")
require_ok(scaling_factor >= 0 && scaling_factor <= 1, "scaling factor must be in [0,1]")
require_ok(margin >= 0, "margin must be >= 0")

# Normalization: reduce to incremental profit per unit per period.
delta_profit0 <- effect_raw * margin
ci_lo_n <- ci_lo_raw * margin
ci_hi_n <- ci_hi_raw * margin

# Pipeline multiplier M (estimand scaling enters exactly once).
unit_weight <- persistence^t_idx * survival^t_idx / (1 + discount)^t_idx
effective_periods <- sum(unit_weight)
M <- sum(n_eligible * scaling_factor * rollout * unit_weight) * transport * net_incrementality

pv_per_unit <- delta_profit0 * effective_periods
pv <- delta_profit0 * M
pv_investment <- one_time + sum(recurring / (1 + discount)^t_idx)
require_ok(pv_investment > 0, "investment must be positive: ROI and breakeven undefined at zero")
require_ok(M > 0, "pipeline multiplier M is zero: no monetizable exposure")

net_profit <- pv - pv_investment
roi    <- net_profit / pv_investment
roi_lo <- (ci_lo_n * M - pv_investment) / pv_investment
roi_hi <- (ci_hi_n * M - pv_investment) / pv_investment
breakeven_effect <- pv_investment / M

# Verdict code from the hurdle-adjusted line and the margin buffer:
# 2 ship / 1 ship-staged / 0 size-the-bet / -1 kill.
line <- (1 + hurdle) * pv_investment / M
verdict_code <- if (ci_hi_n < line) {
  -1L
} else if (ci_lo_n >= margin_buffer * line) {
  2L
} else if (ci_lo_n >= line) {
  1L
} else {
  0L
}

cat(sprintf("EFFECTIVE_PERIODS:%.10f\n", effective_periods))
cat(sprintf("PV_INCREMENTAL_PROFIT_PER_UNIT:%.10f\n", pv_per_unit))
cat(sprintf("PV_INCREMENTAL_PROFIT:%.10f\n", pv))
cat(sprintf("NET_PROFIT:%.10f\n", net_profit))
cat(sprintf("ROI:%.10f\n", roi))
cat(sprintf("ROI_LO:%.10f\n", roi_lo))
cat(sprintf("ROI_HI:%.10f\n", roi_hi))
cat(sprintf("BREAKEVEN_EFFECT:%.10f\n", breakeven_effect))
cat(sprintf("VERDICT_CODE:%d\n", verdict_code))
