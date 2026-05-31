# Canonical modern RDD recipe (R) — local polynomial RD with robust bias-corrected
# inference (Calonico, Cattaneo, Titiunik), MSE-optimal bandwidth via rdrobust,
# plus the Cattaneo-Jansson-Ma manipulation density test via rddensity.
# `df` is preloaded by the parity harness. Columns: y (outcome), x (running var), z (covariate).
suppressMessages({
  library(rdrobust)
  library(rddensity)
})

cutoff <- 0

rd <- rdrobust(y = df$y, x = df$x, c = cutoff)            # triangular kernel, p=1, mserd bandwidth
# coef rows: Conventional, Bias-Corrected, Robust
cat(sprintf("RD_EST:%f\n", rd$coef["Conventional", 1]))  # point estimate (kernel/bw-driven, language-invariant)
cat(sprintf("SE_ROBUST:%f\n", rd$se["Robust", 1]))        # robust bias-corrected SE
cat(sprintf("CI_LO:%f\n", rd$ci["Robust", 1]))
cat(sprintf("CI_HI:%f\n", rd$ci["Robust", 2]))
cat(sprintf("BW:%f\n", rd$bws["h", 1]))                   # MSE-optimal bandwidth (left = right here)

# Manipulation / density continuity test at the cutoff (CJM 2020)
den <- rddensity(X = df$x, c = cutoff)
cat(sprintf("DENSITY_T:%f\n", den$test$t_jk))             # jackknife t-statistic for the density jump
