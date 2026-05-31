# Matching/weighting parity reference (R). `df` is preloaded by the runner.
# Estimators are dependency-light (base glm + lm) so they run identically to the
# Python recipe: MLE logistic propensity score, Hajek IPW (ATE/ATT), and AIPW (ATE).
covs <- c("x1", "x2", "x3")
fml <- as.formula(paste("treatment ~", paste(covs, collapse = " + ")))

# Propensity score via MLE logistic regression (matches statsmodels Logit).
ps_mod <- glm(fml, data = df, family = binomial)
ps <- as.numeric(predict(ps_mod, type = "response"))

y <- df$outcome
t <- df$treatment

# --- Hajek (self-normalized) IPW, ATE ---
w1 <- t / ps
w0 <- (1 - t) / (1 - ps)
mu1_ipw <- sum(w1 * y) / sum(w1)
mu0_ipw <- sum(w0 * y) / sum(w0)
ipw_ate <- mu1_ipw - mu0_ipw

# --- Hajek IPW, ATT (treated get weight 1; controls reweighted by ps/(1-ps)) ---
wt_att <- ps / (1 - ps)
mu1_att <- mean(y[t == 1])
mu0_att <- sum(wt_att[t == 0] * y[t == 0]) / sum(wt_att[t == 0])
ipw_att <- mu1_att - mu0_att

# --- AIPW (doubly robust), ATE ---
out_fml <- as.formula(paste("outcome ~", paste(covs, collapse = " + ")))
m1 <- lm(out_fml, data = df[t == 1, ])
m0 <- lm(out_fml, data = df[t == 0, ])
mu1_hat <- as.numeric(predict(m1, newdata = df))
mu0_hat <- as.numeric(predict(m0, newdata = df))

aipw_1 <- mu1_hat + t * (y - mu1_hat) / ps
aipw_0 <- mu0_hat + (1 - t) * (y - mu0_hat) / (1 - ps)
aipw_ate <- mean(aipw_1 - aipw_0)

cat(sprintf("IPW_ATE:%f\n", ipw_ate))
cat(sprintf("IPW_ATT:%f\n", ipw_att))
cat(sprintf("AIPW_ATE:%f\n", aipw_ate))
