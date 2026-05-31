# Exercises (DGP-generation) reference recipe (R). `df` is preloaded by
# run_parity.py from evals/parity/fixtures/exercises_parity.csv — but here `df`
# holds the DGP SPECIFICATION (one row of parameters), not a dataset.
#
# The exercises skill generates practice data from a known DGP. The parity
# contract is: (1) the declared true effect (TRUE_ATT) is deterministic and must
# match Python exactly; (2) given the same DGP spec, the language-native RNG
# draws its own data and the canonical naive estimator (the 2x2 DiD
# means-of-means) recovers the SAME effect within Monte-Carlo sampling error
# (RECOVERED_ATT).
#
# Mirrors DGP-03 (Classic 2x2 DiD, true ATT = 5.0) in references/dgp-library.md.
s <- df[1, ]
seed <- as.integer(s$seed)
n_stores <- as.integer(s$n_stores)
n_months <- as.integer(s$n_months)
treat_month <- as.integer(s$treat_month)
true_att <- as.numeric(s$true_att)

# --- Generate the exercise dataset from the DGP spec (DGP-03 structural form) ---
set.seed(seed)
store_id <- rep(1:n_stores, each = n_months)
month <- rep(1:n_months, times = n_stores)
treated <- as.integer(store_id <= n_stores %/% 2)
post <- as.integer(month >= treat_month)
store_fe <- rep(rnorm(n_stores, 0, as.numeric(s$store_fe_sd)), each = n_months)
time_trend <- as.numeric(s$time_trend) * month
revenue <- as.numeric(s$base) + store_fe + time_trend +
  true_att * treated * post +
  rnorm(n_stores * n_months, 0, as.numeric(s$noise_sd))
gen <- data.frame(treated = treated, post = post, revenue = revenue)

# --- Recover the effect with the canonical 2x2 DiD estimator (means-of-means) ---
agg <- aggregate(revenue ~ treated + post, gen, mean)
cell <- function(tr, po) agg$revenue[agg$treated == tr & agg$post == po]
recovered <- (cell(1, 1) - cell(1, 0)) - (cell(0, 1) - cell(0, 0))

# Declared ground truth (deterministic — must match Python exactly).
cat(sprintf("TRUE_ATT:%f\n", true_att))
# Recovered effect (stochastic — RNG differs across languages; agree within MC error).
cat(sprintf("RECOVERED_ATT:%f\n", recovered))
