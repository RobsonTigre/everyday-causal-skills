# Directed Acyclic Graph — Python Template

## Prerequisites

```python
# Install (if needed)
# pip install networkx matplotlib statsmodels pandas numpy

# Import
import networkx as nx
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import statsmodels.api as sm
```

## Define the DAG

```python
# Define the causal graph as a directed acyclic graph
G = nx.DiGraph()
G.add_edges_from([
    ("X", "D"),  # X causes D
    ("X", "Y"),  # X causes Y
    ("D", "Y"),  # D causes Y (causal effect of interest)
])

# Mark treatment and outcome
treatment = "D"
outcome = "Y"

# Verify the graph is acyclic
assert nx.is_directed_acyclic_graph(G), "Graph contains cycles!"
print("DAG is valid (acyclic).")
```

## Visualize the DAG

```python
pos = nx.spring_layout(G, seed=42)
plt.figure(figsize=(8, 6))
nx.draw(G, pos, with_labels=True, node_color="lightblue",
        node_size=2000, font_size=14, font_weight="bold",
        arrowsize=20, arrows=True)
plt.title("Causal DAG")
plt.tight_layout()
plt.show()
```

## Compute Adjustment Sets

```python
# Find valid adjustment sets using d-separation
# A set S is a valid adjustment set if it blocks all backdoor paths
# without blocking causal paths

from itertools import combinations

nodes = set(G.nodes()) - {treatment, outcome}

valid_sets = []
for size in range(len(nodes) + 1):
    for subset in combinations(nodes, size):
        s = set(subset)
        # Check: no descendant of treatment in S
        descendants_of_d = nx.descendants(G, treatment)
        if s & descendants_of_d:
            continue
        # Check: S blocks all backdoor paths (d-separates D and Y in mutilated graph)
        # Remove outgoing edges from D to test backdoor blocking
        G_mutilated = G.copy()
        G_mutilated.remove_edges_from(list(G.out_edges(treatment)))
        if nx.d_separated(G_mutilated, {treatment}, {outcome}, s):
            valid_sets.append(s)

# Find minimal sets (no proper subset is also valid)
minimal_sets = []
for s in valid_sets:
    if not any(other < s for other in valid_sets if other != s):
        minimal_sets.append(s)

print("Minimal sufficient adjustment sets:")
for s in minimal_sets:
    print(f"  {s if s else '{} (empty set — no adjustment needed)'}")
```

## List Testable Implications

```python
# List testable conditional independence implications
# (limited to conditioning sets of size <= 2 to avoid combinatorial explosion)

from itertools import combinations

nodes = list(G.nodes())
max_cond_size = min(2, len(nodes) - 2)

print("Testable implications (conditioning sets up to size 2):")

implications = []
for x, y in combinations(nodes, 2):
    other = [n for n in nodes if n not in (x, y)]
    for size in range(max_cond_size + 1):
        for z_set in combinations(other, size):
            z = set(z_set)
            if nx.d_separated(G, {x}, {y}, z):
                z_str = ", ".join(sorted(z)) if z else "{}"
                implications.append((x, y, z))
                print(f"  {x} ⊥ {y} | {{{z_str}}}")

if not implications:
    print("  No testable implications (fully connected graph).")
```

## With Data (Optional)

The sections below require a dataframe `df` with columns matching the DAG nodes.

### Identify with DoWhy

```python
# If you have a dataframe `df` with columns matching the DAG nodes:
#
# pip install dowhy
#
# from dowhy import CausalModel
#
# model = CausalModel(data=df, treatment="D", outcome="Y",
#                     graph='digraph { X -> D; X -> Y; D -> Y; }')
# identified = model.identify_effect()
# print("Backdoor variables:", identified.get_backdoor_variables())
```

### Test Implications Against Data

```python
# Test each implied conditional independence using partial correlations.
# A partial correlation near zero supports the DAG; a large one rejects it.

def partial_correlation(df, x, y, z_list):
    """
    Compute partial correlation of x and y given z_list
    using OLS residualization.
    """
    if not z_list:
        return df[x].corr(df[y])

    # Residualize x on z
    Z = sm.add_constant(df[list(z_list)])
    resid_x = sm.OLS(df[x], Z).fit().resid

    # Residualize y on z
    resid_y = sm.OLS(df[y], Z).fit().resid

    return resid_x.corr(resid_y)

print("Testing implied independencies against data:\n")
print(f"{'Independence':<30} {'Partial Corr':>12} {'Verdict':>10}")
print("-" * 55)

for x, y, z_set in implications:
    # Only test if all variables are observed (skip U)
    all_vars = {x, y} | z_set
    if any(v not in df.columns for v in all_vars):
        continue

    pcor = partial_correlation(df, x, y, list(z_set))
    verdict = "OK" if abs(pcor) < 0.10 else "FAIL"

    z_str = f" | {z_set}" if z_set else ""
    label = f"{x} _||_ {y}{z_str}"
    print(f"  {label:<28} {pcor:>10.3f}   {verdict:>6}")

    if verdict == "FAIL":
        print(f"    ^ DAG predicts independence but partial corr = {pcor:.3f}")
        print(f"      Possible causes: missing edge, wrong direction, or faithfulness violation")
```

### Front-Door Estimation

```python
# Use this ONLY when:
# 1. No valid backdoor adjustment set exists (unobserved confounder U -> D, U -> Y)
# 2. A full mediator M exists: D -> M -> Y
# 3. No unobserved confounder of M and Y
# 4. No direct effect of D on Y (all effect flows through M)

# Step 1: Regress M on D (effect of treatment on mediator)
stage1 = sm.OLS(df["M"], sm.add_constant(df["D"])).fit()
gamma = stage1.params["D"]
print(f"Stage 1 (D -> M): gamma = {gamma:.4f} (SE = {stage1.bse['D']:.4f})")

# Step 2: Regress Y on M, controlling for D
# Controlling for D blocks the back-door path D -> M when estimating M -> Y
X_stage2 = sm.add_constant(df[["M", "D"]])
stage2 = sm.OLS(df["Y"], X_stage2).fit()
alpha = stage2.params["M"]
print(f"Stage 2 (M -> Y | D): alpha = {alpha:.4f} (SE = {stage2.bse['M']:.4f})")

# Front-door estimate: total causal effect = gamma * alpha
fd_estimate = gamma * alpha
print(f"\nFront-door estimate (D -> Y via M): {fd_estimate:.4f}")

# Bootstrap standard error for the product
n_boot = 1000
boot_estimates = []
for _ in range(n_boot):
    boot_idx = np.random.choice(len(df), size=len(df), replace=True)
    boot_df = df.iloc[boot_idx]
    b1 = sm.OLS(boot_df["M"], sm.add_constant(boot_df["D"])).fit()
    b2 = sm.OLS(boot_df["Y"], sm.add_constant(boot_df[["M", "D"]])).fit()
    boot_estimates.append(b1.params["D"] * b2.params["M"])

boot_se = np.std(boot_estimates)
boot_ci = np.percentile(boot_estimates, [2.5, 97.5])
print(f"Bootstrap SE: {boot_se:.4f}")
print(f"95% CI: [{boot_ci[0]:.4f}, {boot_ci[1]:.4f}]")
```
