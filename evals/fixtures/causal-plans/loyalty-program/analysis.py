"""DiD estimate of the loyalty program's effect on repeat purchases.
50 stores (12 treated, 38 control), 24 monthly observations, launch at month 7.
"""
import pandas as pd
import numpy as np
from linearmodels.panel import PanelOLS

df = pd.read_csv("store_month_panel.csv")  # store, month, treated, post, repeat_purchase_rate
df["treated_x_post"] = df["treated"] * df["post"]
df = df.set_index(["store", "month"])

# --- Parallel trends check: joint test on treated x pre-period-month interactions ---
pre = df[df.index.get_level_values("month") <= 6].copy()
pre_dummies = pd.get_dummies(pre.index.get_level_values("month"), prefix="month", drop_first=True)
pre_dummies.index = pre.index
interaction_cols = []
for col in pre_dummies.columns:
    inter_col = f"treated_x_{col}"
    pre[inter_col] = pre["treated"].values * pre_dummies[col].values
    interaction_cols.append(inter_col)
model_pre = PanelOLS.from_formula(
    f"repeat_purchase_rate ~ {' + '.join(interaction_cols)} + EntityEffects + TimeEffects", data=pre
).fit(cov_type="clustered", cluster_entity=True)
print("Parallel trends joint test: F =", round(model_pre.f_statistic_robust.stat, 2),
      "p =", round(model_pre.f_statistic_robust.pval, 3))

# --- Main DiD estimate ---
model = PanelOLS.from_formula(
    "repeat_purchase_rate ~ treated_x_post + EntityEffects + TimeEffects", data=df
).fit(cov_type="clustered", cluster_entity=True)
print(model.summary)

att = model.params["treated_x_post"]
ci_low, ci_high = model.conf_int().loc["treated_x_post"]
print(f"ATT: {att:.3f} (95% CI: [{ci_low:.3f}, {ci_high:.3f}])")
# ESTIMATE:0.12 (95% CI: [0.08, 0.16]) -- percentage-point increase in repeat purchases

# --- Robustness: drop largest treated store ---
largest_treated = df[df["treated"] == 1].groupby(level="store")["repeat_purchase_rate"].mean().idxmax()
df_robust = df.drop(index=largest_treated, level="store")
model_robust = PanelOLS.from_formula(
    "repeat_purchase_rate ~ treated_x_post + EntityEffects + TimeEffects", data=df_robust
).fit(cov_type="clustered", cluster_entity=True)
ci_low_r, ci_high_r = model_robust.conf_int().loc["treated_x_post"]
print(f"Robustness (excl. largest treated store): {model_robust.params['treated_x_post']:.3f} "
      f"(95% CI: [{ci_low_r:.3f}, {ci_high_r:.3f}])")
