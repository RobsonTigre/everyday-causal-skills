# Directed Acyclic Graph — Python Template

## Prerequisites

```python
# Install (if needed)
# pip install dowhy networkx matplotlib statsmodels pandas numpy

# Import
import dowhy
from dowhy import CausalModel
import networkx as nx
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import statsmodels.api as sm
```

## Define the DAG

```python
# Define the DAG using DoWhy's GML graph format
# D = treatment, Y = outcome
# X = observed confounder, M = mediator, U = unobserved confounder
gml_graph = """
graph [
  directed 1
  node [ id "D" label "D" ]
  node [ id "Y" label "Y" ]
  node [ id "X" label "X" ]
  node [ id "M" label "M" ]
  node [ id "U" label "U" ]
  edge [ source "X" target "D" ]
  edge [ source "X" target "Y" ]
  edge [ source "D" target "Y" ]
  edge [ source "D" target "M" ]
  edge [ source "M" target "Y" ]
  edge [ source "U" target "D" ]
  edge [ source "U" target "Y" ]
]
"""

model = CausalModel(
    data=df,
    treatment="D",
    outcome="Y",
    graph=gml_graph
)

# Verify acyclicity
G = nx.parse_gml(gml_graph)
assert nx.is_directed_acyclic_graph(G), "Graph contains cycles!"
print("DAG is valid (acyclic).")
```

## Visualize the DAG

```python
# --- DoWhy built-in visualization ---
model.view_model()

# --- Manual networkx plot for more control ---
fig, ax = plt.subplots(figsize=(8, 6))

# Define node positions (adjust to match your graph layout)
pos = {
    "D": (0, 1),
    "Y": (2, 1),
    "X": (1, 2),
    "M": (1, 1),
    "U": (1, 0),
}

# Color nodes by role
node_colors = []
for node in G.nodes():
    if node == "D":
        node_colors.append("steelblue")    # treatment
    elif node == "Y":
        node_colors.append("salmon")        # outcome
    elif node == "U":
        node_colors.append("lightgray")     # unobserved
    else:
        node_colors.append("lightgreen")    # observed covariates

nx.draw(
    G, pos, ax=ax,
    with_labels=True,
    node_color=node_colors,
    node_size=2000,
    font_size=12,
    font_weight="bold",
    arrows=True,
    arrowsize=20,
    edge_color="gray",
    width=2
)
ax.set_title("Causal DAG", fontsize=14)
plt.tight_layout()
plt.show()
```

## Identify Adjustment Sets

```python
# --- DoWhy identification ---
# Uses the backdoor criterion to find valid adjustment sets
identified_estimand = model.identify_effect(proceed_when_unidentifiable=True)
print(identified_estimand)

# --- Extract backdoor variables ---
# These are the variables DoWhy recommends conditioning on
backdoor_vars = identified_estimand.get_backdoor_variables()
print(f"\nBackdoor adjustment variables: {backdoor_vars}")

# --- Check specific variables ---
# Classify each variable by its role in the graph
for node in G.nodes():
    if node in ("D", "Y"):
        continue
    is_ancestor_D = nx.has_path(G, node, "D")
    is_ancestor_Y = nx.has_path(G, node, "Y")
    is_descendant_D = nx.has_path(G, "D", node)
    role = []
    if is_ancestor_D and is_ancestor_Y:
        role.append("common cause (potential confounder)")
    if is_descendant_D:
        role.append("descendant of D (potential mediator/collider)")
    if is_ancestor_D and not is_ancestor_Y and not is_descendant_D:
        role.append("treatment-only cause (potential instrument)")
    if not role:
        role.append("no direct role in D-Y relationship")
    print(f"  {node}: {', '.join(role)}")
```

## List Testable Implications

```python
# The DAG implies conditional independencies (d-separation statements).
# If a test fails, the DAG may be missing an edge or have a wrong direction.

from itertools import combinations

def check_d_separation(G, x, y, z_set):
    """Check if x and y are d-separated given z_set in DAG G."""
    return nx.d_separated(G, {x}, {y}, z_set)

# Enumerate testable implications for all variable triples
nodes = list(G.nodes())
print("Testable implications (d-separation statements):\n")

implications = []
for x, y in combinations(nodes, 2):
    # Check unconditional independence
    if check_d_separation(G, x, y, set()):
        implications.append((x, y, set()))
        print(f"  {x} _||_ {y}")

    # Check conditional independence given each other variable
    other_nodes = [n for n in nodes if n not in (x, y)]
    for size in range(1, len(other_nodes) + 1):
        for z_set in combinations(other_nodes, size):
            z = set(z_set)
            if check_d_separation(G, x, y, z):
                implications.append((x, y, z))
                print(f"  {x} _||_ {y} | {z}")

if not implications:
    print("  No testable implications (fully connected graph).")
```

## Test Implications Against Data

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

## Front-Door Estimation

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
