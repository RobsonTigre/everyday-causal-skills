# Directed Acyclic Graph — R Template

## Prerequisites
```r
# Install (if needed)
install.packages(c("dagitty", "ggdag", "ggplot2"))

# Load
library(dagitty)
library(ggdag)
library(ggplot2)
```

## Define the DAG
```r
# Define the DAG using dagitty syntax
# D = treatment (exposure), Y = outcome
# X = observed confounder, M = mediator, U = unobserved confounder
dag <- dagitty('dag {
  D [exposure, pos="0,1"]
  Y [outcome, pos="2,1"]
  X [pos="1,0"]
  M [pos="1,1"]
  U [unobserved, pos="1,2"]

  X -> D
  X -> Y
  D -> Y
  D -> M -> Y
  U -> D
  U -> Y
}')

# Verify acyclicity
stopifnot(isAcyclic(dag))
```

## Visualize the DAG
```r
# --- Basic DAG plot ---
ggdag(dag) +
  theme_dag() +
  labs(title = "Causal DAG")

# --- Highlight the adjustment set ---
# Shows which variables to condition on for the backdoor criterion
ggdag_adjustment_set(dag) +
  theme_dag() +
  labs(title = "Adjustment Set (Backdoor Criterion)")

# --- Show all paths from treatment to outcome ---
# Causal (front-door) and non-causal (back-door) paths
ggdag_paths(dag) +
  theme_dag() +
  labs(title = "All Paths from D to Y")

# --- Highlight colliders ---
# Colliders are variables with two parents on a path —
# conditioning on them OPENS a spurious path
ggdag_collider(dag) +
  theme_dag() +
  labs(title = "Colliders in the DAG")
```

## Compute Adjustment Sets
```r
# --- Minimal adjustment sets ---
# Smallest sets of variables that block all back-door paths
# Multiple minimal sets may exist — each is sufficient on its own
min_sets <- adjustmentSets(dag, type = "minimal")
cat("Minimal adjustment sets:\n")
print(min_sets)

# --- Canonical (all valid) adjustment set ---
# The unique maximal set that includes every valid control variable
can_sets <- adjustmentSets(dag, type = "canonical")
cat("\nCanonical adjustment set:\n")
print(can_sets)

# --- Check specific variables ---
# Is a particular variable safe to condition on?
# (Use the 18-pattern taxonomy from SKILL.md Stage 3)
cat("\nParents of D (exposure):", paste(parents(dag, "D"), collapse = ", "), "\n")
cat("Parents of Y (outcome):", paste(parents(dag, "Y"), collapse = ", "), "\n")
cat("Descendants of D:", paste(descendants(dag, "D"), collapse = ", "), "\n")
```

## List Testable Implications
```r
# The DAG implies conditional independencies that you can test in data.
# If a test fails (significant association where independence is predicted),
# the DAG may be wrong — a missing edge or wrong direction.
implications <- impliedConditionalIndependencies(dag)
cat("Testable implications of the DAG:\n")
print(implications)

# Each line reads: "A is independent of B, given {C, D, ...}"
# Test each one against your data to validate the DAG structure.
```

## Test Implications Against Data
```r
# localTests checks every implied conditional independence against data.
# Uses partial correlations (continuous) or conditional independence tests.
# Small p-values = the data REJECTS the independence → DAG may be wrong.

tests <- localTests(dag, data = df, type = "cis.pillai")
cat("Local independence tests:\n")
print(tests)

# Visual summary: points left of the dashed line violate the DAG
# Visual summary: points left of the dashed line violate the DAG
plotLocalTestResults(tests)
title("DAG Validation: Local Independence Tests")
mtext("Points left of 0 violate implied independencies", side = 3, line = 0.3, cex = 0.8)

# Focus on failures
failed <- tests[tests$p.value < 0.05, ]
if (nrow(failed) > 0) {
  cat("\n--- FAILED IMPLICATIONS (p < 0.05) ---\n")
  cat("These suggest the DAG may be missing an edge or have a wrong direction:\n")
  print(failed)
} else {
  cat("\nAll implied independencies are consistent with the data.\n")
}
```

## Front-Door Estimation
```r
# Use this ONLY when:
# 1. No valid backdoor adjustment set exists (unobserved confounder U -> D, U -> Y)
# 2. A full mediator M exists: D -> M -> Y
# 3. No unobserved confounder of M and Y
# 4. No direct effect of D on Y (all effect flows through M)

# Step 1: Regress M on D (effect of treatment on mediator)
stage1 <- lm(M ~ D, data = df)
gamma <- coef(stage1)["D"]
cat("Stage 1 (D -> M):", gamma, "\n")

# Step 2: Regress Y on M, controlling for D
# Controlling for D blocks the back-door path D -> M when estimating M -> Y
stage2 <- lm(Y ~ M + D, data = df)
alpha <- coef(stage2)["M"]
cat("Stage 2 (M -> Y | D):", alpha, "\n")

# Front-door estimate: total causal effect = gamma * alpha
fd_estimate <- gamma * alpha
cat("\nFront-door estimate (D -> Y via M):", fd_estimate, "\n")

# Standard error via delta method (approximate)
library(car)  # for deltaMethod if needed
cat("Note: Use bootstrap for proper standard errors on the product.\n")
```
