# HTE reference recipe (R) — grf causal forest + best linear projection.
# `df` is preloaded by run_parity.py from the shared fixture.
# Fixture is a randomized-treatment design (known propensity 0.5) with linear
# heterogeneity in centered age; compared estimands concentrate across RNGs.
suppressMessages(library(grf))

Y <- df$outcome
W <- df$treatment
X <- as.matrix(df[, c("age", "income", "gender")])

# Center age so the BLP slope targets tau change per year about the sample mean,
# matching the Python LinearDML projection on the same centered features.
Xc <- X
Xc[, "age"] <- Xc[, "age"] - 40

cf <- causal_forest(
  X, Y, W,
  W.hat = rep(0.5, length(Y)),  # known randomized propensity
  num.trees = 4000,
  honesty = TRUE,
  seed = 42
)

# Overall ATE via doubly-robust AIPW scores.
ate <- average_treatment_effect(cf)
cat(sprintf("ATE:%f\n", ate[1]))

# Best linear projection of the CATE onto the (centered) effect modifiers.
blp <- best_linear_projection(cf, Xc)
cat(sprintf("BLP_AGE:%f\n", blp["age", "Estimate"]))

# Heterogeneity sign check: top-minus-bottom CATE-quintile GATE (printed, not gated).
tau <- predict(cf)$predictions
q <- cut(tau, quantile(tau, 0:5 / 5), include.lowest = TRUE, labels = 1:5)
hi <- average_treatment_effect(cf, subset = q == 5)[1]
lo <- average_treatment_effect(cf, subset = q == 1)[1]
cat(sprintf("GATE_HIGH_MINUS_LOW:%f\n", hi - lo))
