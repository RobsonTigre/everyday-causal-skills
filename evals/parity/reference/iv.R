# IV reference recipe (R). `df` is preloaded by run_parity.py.
# Canonical modern R path: fixest::feols with the `| endogenous ~ instrument`
# 2SLS syntax. Prints key estimands as KEY:<value> for the parity runner.
suppressMessages(library(fixest))

# 2SLS: outcome ~ exogenous control | endogenous ~ instrument
m <- feols(outcome ~ control | endogenous ~ instrument, data = df, vcov = "iid")

# Point estimate of the endogenous regressor (the LATE / causal coefficient).
cat(sprintf("ATE:%f\n", coef(m)[["fit_endogenous"]]))

# Homoskedastic (classic) first-stage partial F of the instrument: Wald test of
# the instrument coefficient in the full first-stage regression. This is the
# same statistic statsmodels' f_test returns, so R and Python match exactly.
fs <- feols(endogenous ~ instrument + control, data = df, vcov = "iid")
fstat <- wald(fs, "instrument", print = FALSE)$stat
cat(sprintf("FIRST_STAGE_F:%f\n", fstat))

# Reduced-form coefficient of the instrument on the outcome (always-valid).
rf <- feols(outcome ~ instrument + control, data = df, vcov = "iid")
cat(sprintf("REDUCED_FORM:%f\n", coef(rf)[["instrument"]]))
