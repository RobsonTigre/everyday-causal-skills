# Matching/weighting parity reference (Python). `df` is preloaded by the runner.
# Mirrors reference/matching.R exactly: MLE logistic propensity score (statsmodels
# Logit, matching R glm), Hajek IPW (ATE/ATT), and AIPW (ATE). Dependency-light on
# purpose so the two languages compute the same estimands.
import numpy as np
import statsmodels.api as sm

covs = ["x1", "x2", "x3"]

# Propensity score via MLE logistic regression (matches R glm).
X_ps = sm.add_constant(df[covs])
ps_mod = sm.Logit(df["treatment"], X_ps).fit(disp=0)
ps = ps_mod.predict(X_ps).to_numpy()

y = df["outcome"].to_numpy()
t = df["treatment"].to_numpy()

# --- Hajek (self-normalized) IPW, ATE ---
w1 = t / ps
w0 = (1 - t) / (1 - ps)
mu1_ipw = np.sum(w1 * y) / np.sum(w1)
mu0_ipw = np.sum(w0 * y) / np.sum(w0)
ipw_ate = mu1_ipw - mu0_ipw

# --- Hajek IPW, ATT (treated weight 1; controls reweighted by ps/(1-ps)) ---
wt_att = ps / (1 - ps)
mu1_att = y[t == 1].mean()
mu0_att = np.sum(wt_att[t == 0] * y[t == 0]) / np.sum(wt_att[t == 0])
ipw_att = mu1_att - mu0_att

# --- AIPW (doubly robust), ATE ---
X_out = sm.add_constant(df[covs])
m1 = sm.OLS(y[t == 1], X_out.to_numpy()[t == 1]).fit()
m0 = sm.OLS(y[t == 0], X_out.to_numpy()[t == 0]).fit()
mu1_hat = m1.predict(X_out.to_numpy())
mu0_hat = m0.predict(X_out.to_numpy())

aipw_1 = mu1_hat + t * (y - mu1_hat) / ps
aipw_0 = mu0_hat + (1 - t) * (y - mu0_hat) / (1 - ps)
aipw_ate = np.mean(aipw_1 - aipw_0)

print(f"IPW_ATE:{ipw_ate}")
print(f"IPW_ATT:{ipw_att}")
print(f"AIPW_ATE:{aipw_ate}")
