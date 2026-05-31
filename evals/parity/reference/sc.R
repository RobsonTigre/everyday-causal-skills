# Synthetic-control parity reference (R).
# Canonical classic R SC: Synth (Abadie, Diamond, Hainmueller) — simplex-constrained
# weights (>= 0, sum to 1). `df` is preloaded by the parity runner from
# fixtures/sc_parity.csv.
#
# Prints, for cross-language comparison:
#   ATT       : mean post-treatment gap (actual treated - synthetic)
#   RMSPE_PRE : pre-treatment root mean squared prediction error (fit quality)
#   W_DONOR1  : synthetic-control weight on donor_1
suppressMessages(library(Synth))

TREAT_TIME <- 13
TREATED <- "treated"

# Synth needs a numeric unit id and a unit-name column.
df$unit <- as.character(df$unit)
units <- sort(unique(df$unit))
df$unit_num <- match(df$unit, units)
treated_num <- match(TREATED, units)
donor_nums <- setdiff(seq_along(units), treated_num)

time_min <- min(df$time)
pre_times <- time_min:(TREAT_TIME - 1)
post_times <- TREAT_TIME:max(df$time)

# Match on every pre-treatment outcome (the full pre-period path), mirroring the
# Python recipe's reliance on the pre-treatment outcome trajectory.
special_preds <- lapply(pre_times, function(tt) list("outcome", tt, "mean"))

dp <- dataprep(
  foo = as.data.frame(df),
  predictors = NULL,
  dependent = "outcome",
  unit.variable = "unit_num",
  time.variable = "time",
  special.predictors = special_preds,
  treatment.identifier = treated_num,
  controls.identifier = donor_nums,
  time.predictors.prior = pre_times,
  time.optimize.ssr = pre_times,
  unit.names.variable = "unit",
  time.plot = time_min:max(df$time)
)

# Default Synth: simplex-constrained weights via nested V-optimization.
so <- synth(dp, verbose = FALSE, optimxmethod = "BFGS")

w <- as.numeric(so$solution.w)
names(w) <- units[donor_nums]
w_donor1 <- unname(w["donor_1"])

synthetic <- as.numeric(dp$Y0plot %*% so$solution.w)
actual <- as.numeric(dp$Y1plot)
times <- as.integer(rownames(dp$Y1plot))

gap <- actual - synthetic
pre_mask <- times < TREAT_TIME
post_mask <- times >= TREAT_TIME

att <- mean(gap[post_mask])
rmspe_pre <- sqrt(mean(gap[pre_mask]^2))

cat(sprintf("ATT:%f\n", att))
cat(sprintf("RMSPE_PRE:%f\n", rmspe_pre))
cat(sprintf("W_DONOR1:%f\n", w_donor1))
