# Assumption Checklist: Directed Acyclic Graphs

Reference: `references/method-registry.md` → Directed Acyclic Graphs

---

## Acyclicity

**Plain language**: The causal graph cannot have directed cycles — no variable can cause itself through a chain of arrows. If A causes B and B causes C, then C cannot cause A in the same time period. Feedback loops require unrolling over time (e.g., A_t → B_{t+1} → A_{t+2}).

**Formal statement**: The graph G = (V, E) is a directed acyclic graph, meaning there is no sequence of directed edges v_1 → v_2 → ... → v_k → v_1 for any set of vertices. Equivalently, there exists a topological ordering of V such that every directed edge points from an earlier to a later node.

**Testable?**: Partially. Cycles can sometimes be detected by checking the logical ordering of variables: if X precedes Y in time, then Y → X violates temporality. However, simultaneous causation (both directions operate instantaneously) cannot be tested from data alone — it requires domain knowledge.

**How to test**:

R:
```r
library(dagitty)

# Define your DAG
dag <- dagitty('dag {
  D [exposure]
  Y [outcome]
  X -> D
  X -> Y
  D -> Y
}')

# dagitty enforces acyclicity at parse time.
# If you accidentally introduce a cycle, it will error.
# Test explicitly:
is_dag <- isAcyclic(dag)
cat("Is the graph acyclic?", is_dag, "\n")

# If you suspect feedback, add time subscripts:
# D_t -> M_{t+1} -> D_{t+2} is acyclic
# D -> M -> D is NOT
```

Python:
```python
import networkx as nx

# Define the graph
G = nx.DiGraph()
G.add_edges_from([("X", "D"), ("X", "Y"), ("D", "Y")])

# Check for cycles
is_dag = nx.is_directed_acyclic_graph(G)
print(f"Is the graph acyclic? {is_dag}")

# If cycles exist, list them
if not is_dag:
    cycles = list(nx.simple_cycles(G))
    print(f"Cycles found: {cycles}")
    print("Fix: unroll feedback loops over time (e.g., D_t -> M_t1 -> D_t2)")
```

**What violation looks like**: The graph software refuses to parse the graph (dagitty), or `nx.is_directed_acyclic_graph()` returns False. Substantively, you'll notice that the causal story requires circular reasoning: "A causes B which causes A."

**Severity if violated**: Fatal. All DAG-based identification theory — d-separation, backdoor criterion, adjustment sets — assumes acyclicity. If the graph has cycles, none of these tools produce valid results. The entire identification strategy breaks down.

**Mitigation**: (1) Unroll feedback loops over time: replace A → B → A with A_t → B_{t+1} → A_{t+2}. This makes the graph acyclic while preserving the causal story. (2) Use simultaneous equation models (SEMs) or dynamic structural models if feedback is instantaneous. (3) If the feedback is the core feature of the problem, DAGs are the wrong framework — consider dynamic causal models or agent-based models instead.

---

## Causal Sufficiency

**Plain language**: Every common cause of any two variables in the graph is itself represented in the graph — either as an observed variable or explicitly marked as unobserved. If education and income are both driven by "family wealth" and you leave family wealth out entirely, your DAG is wrong because it hides a confounding path.

**Formal statement**: For every pair of variables (V_i, V_j) in the graph G, every common cause C such that C → ... → V_i and C → ... → V_j is included in V(G). Unobserved common causes must be explicitly represented as latent (U) nodes with bidirected edges (V_i <-> V_j in dagitty notation).

**Testable?**: No. You cannot test whether you've included all common causes, because by definition the ones you missed are the ones you don't know about. However, testable implications (conditional independencies) can provide indirect evidence: if an implied independence fails, the DAG may be missing a common cause.

**How to test**:

While causal sufficiency is untestable, you can look for indirect evidence of missing common causes:

R:
```r
library(dagitty)

# Define DAG — mark unobserved variables explicitly
dag <- dagitty('dag {
  D [exposure]
  Y [outcome]
  U [unobserved]
  X -> D
  X -> Y
  D -> Y
  U -> D
  U -> Y
}')

# List testable implications — if any fail in data,
# a missing common cause is one possible explanation
impliedConditionalIndependencies(dag)

# Run local tests against your data
# Failures suggest the DAG is missing edges or nodes
tests <- localTests(dag, data = df, type = "cis.pillai")
print(tests)

# Focus on tests with small p-values (rejections)
failed <- tests[tests$p.value < 0.05, ]
cat("Failed implications (possible missing common causes):\n")
print(failed)
```

Python:
```python
import networkx as nx
from itertools import combinations

# Check d-separation implications against data
# If two variables are d-separated in the graph but correlated
# in data, a common cause may be missing

# List all pairs that should be independent (no path)
G = nx.DiGraph()
G.add_edges_from([("X", "D"), ("X", "Y"), ("D", "Y")])

# Check unconditional d-separation: pairs the DAG says are marginally independent
# Two nodes with no directed path can still be d-connected via a common cause,
# so we must use d-separation, not path reachability.
for v1, v2 in combinations(G.nodes(), 2):
    if nx.d_separated(G, {v1}, {v2}, set()):
        print(f"{v1} and {v2} should be marginally independent — check in data")
        # If they're correlated in data, you may be missing a common cause
```

**What violation looks like**: Testable implications of the DAG are rejected by data. Variables that the DAG says should be independent are actually correlated. Residuals from regressions implied by the DAG show unexplained patterns.

**Severity if violated**: Serious. Missing a common cause means a confounding path is open but invisible in the graph. The adjustment sets computed from the graph will be incomplete, leading to omitted variable bias. If the missing common cause is strongly related to both treatment and outcome, the bias can be large.

**Mitigation**: (1) Brainstorm aggressively: for every variable pair, ask "what could cause both of these?" Include domain experts. (2) Represent uncertain common causes as latent nodes (U) with bidirected edges. This tells dagitty/DoWhy that unobserved confounding exists, and the software will correctly report that no backdoor adjustment is available. (3) Run sensitivity analysis (e.g., E-value, Rosenbaum bounds) to assess how strong an unobserved confounder would need to be to overturn the result. (4) If key confounders are missing, consider IV or panel methods instead of cross-sectional adjustment.

---

## Causal Markov Condition

**Plain language**: Once you know a variable's direct causes (its parents in the DAG), knowing anything else about its non-descendants gives you no additional information about it. In other words, each variable's behavior is fully determined by its direct causes plus noise — distant ancestors or unrelated variables add nothing once the direct causes are accounted for.

**Formal statement**: For every variable V_i in the DAG G, V_i is conditionally independent of all its non-descendants given its parents: V_i ⊥ NonDesc(V_i) | Parents(V_i). Together with faithfulness, this axiom allows us to read conditional independencies directly from the graph using d-separation.

**Testable?**: Not directly. The CMC is an axiom relating the probability distribution to the graph structure. However, its implications (conditional independencies) ARE testable via the faithfulness assumption. If a testable implication fails, either the CMC or the graph structure is wrong.

**How to test**:

The CMC itself is untestable, but you can test its consequences:

R:
```r
library(dagitty)

# The CMC + faithfulness together imply specific conditional independencies.
# localTests checks these against data.
dag <- dagitty('dag {
  D [exposure]
  Y [outcome]
  X -> D
  X -> Y
  D -> Y
}')

# These tests check consequences of the CMC:
# each implied independence comes from the Markov condition applied to the graph
tests <- localTests(dag, data = df, type = "cis.pillai")
print(tests)
```

Python:
```python
import networkx as nx

# The CMC implies: each node is independent of its non-descendants given its parents.
# Verify this structurally by checking d-separation for each node:
G = nx.DiGraph()
G.add_edges_from([("X", "D"), ("X", "Y"), ("D", "Y")])

for node in G.nodes():
    parents = set(G.predecessors(node))
    descendants = nx.descendants(G, node) | {node}
    non_descendants = set(G.nodes()) - descendants

    for nd in non_descendants:
        if nd not in parents:
            # CMC implies: node ⊥ nd | parents
            is_sep = nx.d_separated(G, {node}, {nd}, parents)
            print(f"CMC check: {node} ⊥ {nd} | {parents} → d-separated: {is_sep}")
```

**What violation looks like**: A variable shows systematic dependence on a non-descendant even after conditioning on all its parents. This suggests either: (1) the graph is missing an edge (a direct cause was omitted), (2) the Markov condition genuinely fails (rare — implies the causal model is fundamentally wrong), or (3) statistical artifact from finite samples.

**Severity if violated**: Serious. The CMC is the foundation for reading conditional independencies from the graph. If it fails, d-separation cannot be trusted, and adjustment sets derived from the graph may not block the paths they're supposed to. In practice, CMC violations almost always indicate a misspecified graph rather than a true violation of the axiom.

**Mitigation**: (1) Re-examine the graph for missing edges — the most common explanation. (2) Check for latent variables that could explain the residual dependence. (3) Consider measurement error: noisy proxies for parent variables can create apparent CMC violations. (4) If the domain genuinely involves quantum effects or other non-classical mechanisms, the CMC may not hold — but this is exceedingly rare in social science and business applications.

---

## No Measurement Error on Conditioning Variables

**Plain language**: The variables you condition on (your adjustment set) must be measured accurately. If you adjust for "income" but your income variable is noisy (self-reported, rounded, or proxied by zip code), the adjustment is incomplete. You close the backdoor path partially, not fully, leaving residual confounding.

**Formal statement**: For each variable X_j in the adjustment set S, the observed value X_j^{obs} = X_j (the true value). If instead X_j^{obs} = X_j + epsilon_j where epsilon_j is measurement error independent of D and Y, conditioning on X_j^{obs} does not fully block the backdoor path through X_j. The residual confounding is proportional to the reliability ratio Var(X_j) / Var(X_j^{obs}).

**Testable?**: Partially. If you have repeated measures or alternative measures of the same variable, you can estimate reliability. Test-retest correlation provides a lower bound on measurement quality.

**How to test**:

R:
```r
# Check measurement reliability using repeated measures
# If you have two measures of the same variable (e.g., two income reports)

# Test-retest reliability
reliability <- cor(df$X_measure1, df$X_measure2, use = "complete.obs")
cat("Test-retest correlation:", reliability, "\n")

# Rule of thumb:
# > 0.90 = excellent (measurement error unlikely to matter much)
# 0.70-0.90 = acceptable (some residual confounding possible)
# < 0.70 = poor (substantial residual confounding likely)

# If reliability is low, estimate the bias correction factor
# True effect ≈ Observed effect / reliability
cat("Attenuation factor:", reliability, "\n")
cat("If observed effect is X, true confounding is roughly X /",
    round(reliability, 3), "\n")

# With multiple indicators: use factor analysis or SEM
# to extract a latent variable with less measurement error
# library(lavaan)
# model <- 'X_true =~ X_measure1 + X_measure2 + X_measure3'
# fit <- sem(model, data = df)
```

Python:
```python
import numpy as np
from scipy.stats import pearsonr

# Check measurement reliability using repeated measures
# X_measure1 and X_measure2 are two measures of the same variable

reliability, p_value = pearsonr(df["X_measure1"], df["X_measure2"])
print(f"Test-retest correlation: {reliability:.3f} (p = {p_value:.4f})")

# Interpretation:
# > 0.90 = excellent (measurement error unlikely to matter much)
# 0.70-0.90 = acceptable (some residual confounding possible)
# < 0.70 = poor (substantial residual confounding likely)

if reliability < 0.70:
    print("WARNING: Low reliability. Residual confounding is likely.")
    print(f"Attenuation factor: {reliability:.3f}")
    print("Consider using multiple indicators or finding a better measure.")
elif reliability < 0.90:
    print("CAUTION: Moderate reliability. Some residual confounding possible.")
else:
    print("OK: High reliability. Measurement error unlikely to drive results.")
```

**What violation looks like**: Reliability estimates below 0.70 for key conditioning variables. Large discrepancies between repeated measures of the same variable. The adjustment set "should" close a backdoor path, but the estimated treatment effect changes substantially when using different proxies for the same confounder.

**Severity if violated**: Serious. Measurement error in conditioning variables produces residual confounding even when the DAG is correct and the adjustment set is valid. The bias is toward the unadjusted (confounded) estimate. For binary confounders, misclassification can severely attenuate the adjustment. This is one of the most underappreciated threats in applied causal inference.

**Mitigation**: (1) Use multiple measures and extract a latent factor (reduces error). (2) Use instrumental variables for the confounder itself (errors-in-variables regression). (3) Report sensitivity: "If my confounder is measured with reliability R, the true effect is approximately [adjusted estimate] / R." (4) Use administrative data or validated instruments instead of self-reports where possible. (5) Consider regression calibration if you have a validation subsample with precise measures.

---

## Positivity

**Plain language**: For every combination of values of your conditioning variables (adjustment set), you need both treated and untreated units. If you adjust for age and income, then in every age-income cell, there must be people who got the treatment and people who didn't. If all high-income people are treated and no high-income people are untreated, you have no comparison group for that stratum.

**Formal statement**: For all values x in the support of the adjustment set X: 0 < P(D = 1 | X = x) < 1. Equivalently, the propensity score e(x) = P(D = 1 | X = x) must be strictly between 0 and 1 for all x in the population.

**Testable?**: Yes. Check propensity score distributions and look for regions of non-overlap between treated and untreated groups.

**How to test**:

R:
```r
library(ggplot2)

# Estimate propensity score (probability of treatment given covariates)
ps_model <- glm(D ~ X1 + X2 + X3, data = df, family = binomial)
df$pscore <- predict(ps_model, type = "response")

# Check for extreme propensity scores
cat("Propensity score summary:\n")
print(summary(df$pscore))
cat("\nProportion with pscore < 0.01:", mean(df$pscore < 0.01), "\n")
cat("Proportion with pscore > 0.99:", mean(df$pscore > 0.99), "\n")

# Overlap plot — the key diagnostic
ggplot(df, aes(x = pscore, fill = factor(D))) +
  geom_density(alpha = 0.5) +
  labs(title = "Propensity Score Overlap",
       x = "Propensity Score", fill = "Treatment") +
  theme_minimal()

# If there's poor overlap, check which covariate combinations
# lack common support
# Trim to common support region
trimmed <- df[df$pscore > 0.05 & df$pscore < 0.95, ]
cat("\nObservations retained after trimming:", nrow(trimmed),
    "of", nrow(df), "\n")
```

Python:
```python
import numpy as np
import matplotlib.pyplot as plt
from sklearn.linear_model import LogisticRegression

# Estimate propensity score
X_covariates = df[["X1", "X2", "X3"]].values
ps_model = LogisticRegression(max_iter=1000).fit(X_covariates, df["D"])
df["pscore"] = ps_model.predict_proba(X_covariates)[:, 1]

# Summary statistics
print("Propensity score summary:")
print(df["pscore"].describe())
print(f"\nProportion with pscore < 0.01: {(df['pscore'] < 0.01).mean():.3f}")
print(f"Proportion with pscore > 0.99: {(df['pscore'] > 0.99).mean():.3f}")

# Overlap plot — the key diagnostic
fig, ax = plt.subplots(figsize=(8, 5))
ax.hist(df.loc[df["D"] == 1, "pscore"], bins=50, alpha=0.5,
        density=True, label="Treated", color="steelblue")
ax.hist(df.loc[df["D"] == 0, "pscore"], bins=50, alpha=0.5,
        density=True, label="Untreated", color="salmon")
ax.set_xlabel("Propensity Score")
ax.set_ylabel("Density")
ax.set_title("Propensity Score Overlap")
ax.legend()
plt.tight_layout()
plt.show()

# Report overlap quality
n_before = len(df)
trimmed = df[(df["pscore"] > 0.05) & (df["pscore"] < 0.95)]
n_after = len(trimmed)
print(f"\nObservations retained after trimming: {n_after} of {n_before}")
```

**What violation looks like**: Propensity score distributions for treated and untreated groups that barely overlap. Large regions where one group has no observations. Extreme propensity scores (near 0 or 1) concentrated in one group. After trimming to common support, you lose a substantial fraction of the sample.

**Severity if violated**: Serious. Positivity is an estimation requirement, not an identification requirement — the DAG and adjustment set may be correct even when positivity is practically violated. Without positivity, estimators extrapolate into regions with no data, producing model-dependent results.

**Mitigation**: (1) Trim the sample to the region of common support and acknowledge the estimand changes (you're estimating the effect for the overlap population, not the full population). (2) Use weight truncation or stabilized weights in IPW. (3) Consider a different adjustment set that creates better overlap. (4) If positivity fails badly, the treatment is essentially deterministic given covariates — backdoor adjustment won't work, and you need a different identification strategy (IV, RDD, DiD).

---

## Stable Unit Treatment Value Assumption (SUTVA)

**Plain language**: Each unit's outcome depends only on its own treatment status, not on what treatment other units receive. There is also only one version of the treatment — no hidden variations. If you're studying the effect of a marketing email, SUTVA means my response to the email doesn't depend on whether my neighbor also got it, and every recipient got the same email.

**Formal statement**: For all units i: Y_i(d_1, ..., d_N) = Y_i(d_i). The potential outcome for unit i depends only on i's own treatment assignment d_i, not on the treatment assignments of other units. Additionally, if d_i = d_j, then the treatment received by i is identical to that received by j (no hidden versions).

**Testable?**: Partially. Interference (spillover) can sometimes be detected by checking whether outcomes of untreated units correlate with the treatment density in their neighborhood. Hidden treatment versions can be detected by examining treatment implementation details.

**How to test**:

R:
```r
# Check for interference/spillover:
# If untreated units near many treated units have different outcomes
# than untreated units near few treated units, SUTVA may be violated.

# Example: compute treatment density in each unit's neighborhood
# df$treat_neighbors = number of treated units in same group/region
summary(lm(Y ~ D + treat_neighbors, data = df[df$D == 0, ]))
# If treat_neighbors is significant among untreated, spillover exists
```

Python:
```python
import statsmodels.api as sm

# Check for interference/spillover among untreated units:
# If outcome of untreated units depends on how many neighbors are treated,
# SUTVA is violated (spillover exists).
untreated = df[df["D"] == 0].copy()
X = sm.add_constant(untreated["treat_neighbors"])
model = sm.OLS(untreated["Y"], X).fit()
print(model.summary())
# If treat_neighbors coefficient is significant, spillover exists
```

**What violation looks like**: Untreated units near many treated units show different outcomes than isolated untreated units. Treatment effect estimates change dramatically when you vary the definition of the control group. Different implementations of "the same" treatment produce different effect sizes.

**Severity if violated**: Serious. Interference means the standard potential outcomes framework breaks down — there isn't a single "untreated potential outcome" for each unit, because it depends on others' treatment. Hidden treatment versions mean the treatment effect is a mixture across versions, making interpretation ambiguous. Both violations make the causal estimand ill-defined.

**Mitigation**: (1) For interference: use clustered designs where treatment is assigned at the group level, or model spillover explicitly. (2) For hidden treatment versions: standardize treatment implementation, or estimate version-specific effects. (3) Conduct sensitivity analysis: how large would spillover need to be to overturn the result? (4) If interference is the core feature (e.g., social networks), use interference-aware methods (exposure mapping, partial interference models).

---

## Consistency

**Plain language**: The outcome you observe for a treated unit is the same outcome that unit would have had if we had intervened to set their treatment. In other words, there's no gap between "naturally receiving treatment" and "being assigned treatment" — the mechanism of treatment delivery doesn't matter, only the treatment itself.

**Formal statement**: If D_i = d, then Y_i^{obs} = Y_i(d). The observed outcome equals the potential outcome under the observed treatment value. This links the observed data to the counterfactual framework.

**Testable?**: No. Consistency is a definitional bridge between observed and potential outcomes. It fails when the treatment is poorly defined (e.g., "exercise" can mean many different things) or when the assignment mechanism itself affects the outcome.

**How to test**:

Consistency is untestable from data alone. Instead, verify it through study design:

R:
```r
# Consistency check is conceptual, not statistical.
# Ask these questions about your treatment:
# 1. Is the treatment well-defined? (one specific intervention, not a vague concept)
# 2. Would the outcome be the same regardless of HOW the unit came to be treated?
# 3. Are there meaningful treatment versions you're collapsing together?

# If treatment is "took the drug", consistency holds if:
# - The drug is standardized (same formulation, dose)
# - Self-selection into treatment doesn't change the drug's mechanism
# If treatment is "exercised regularly", consistency is questionable:
# - Exercise type, duration, intensity all vary
# - People who choose to exercise may exercise differently than if assigned
```

Python:
```python
# Consistency is verified through design review, not code.
# Check: does the treatment variable have a clear, manipulable definition?

# Red flags for consistency violations:
# - Treatment is an attribute (race, gender) rather than an action
# - Treatment has many versions (different exercise types lumped together)
# - Assignment mechanism might change the treatment itself

# If treatment has versions, check if effect varies across them:
# df.groupby(["D", "treatment_version"])["Y"].mean()
# Large variation across versions suggests consistency is shaky
```

**What violation looks like**: The treatment effect varies dramatically depending on how treatment was assigned (randomized vs. self-selected), even after controlling for confounders. The treatment concept is too vague to define a single intervention (e.g., "being educated" vs. "completing a specific degree program").

**Severity if violated**: Serious. Without consistency, the connection between observed data and potential outcomes breaks. The "causal effect" becomes ambiguous because Y(d) isn't well-defined. Results may be internally valid for one version of treatment but not generalizable.

**Mitigation**: (1) Define treatment precisely and manipulably. (2) If treatment has versions, estimate version-specific effects or acknowledge the estimand is an average across versions. (3) Avoid treatments that are attributes rather than actions (the "race" vs. "perception of race" distinction). (4) Check whether assignment mechanism affects outcomes independently of treatment.

---

## Faithfulness

**Plain language**: Every statistical independence in the data corresponds to a separation in the DAG structure. There are no "accidental" cancellations where two causal paths happen to exactly offset each other, making variables appear independent when they're actually causally connected. If the DAG says X and Y are connected by an open path, then X and Y should be statistically dependent.

**Formal statement**: The joint distribution P over variables V is faithful to the DAG G if every conditional independence in P is entailed by the d-separation criterion applied to G. Equivalently, there are no exact cancellations: if two paths from X to Y carry effects of opposite signs but equal magnitude, P would still show marginal independence, violating faithfulness even though G has an open path from X to Y.

**Testable?**: No. Faithfulness is an assumption about the relationship between the true distribution and the graph structure. You cannot distinguish "independent because d-separated" from "independent because of exact cancellation" in finite data. However, near-violations (approximate cancellations) may appear as very weak associations where the DAG predicts strong ones.

**How to test**:

While faithfulness is untestable, you can look for suggestive evidence of near-violations:

R:
```r
library(dagitty)

# List what the DAG says should be DEPENDENT
# (i.e., connected by open paths)
# Then check if those associations are suspiciously weak in the data

# Get the testable implications (independencies)
dag <- dagitty('dag {
  D [exposure]
  Y [outcome]
  X -> D
  X -> Y
  D -> Y
}')

# Any non-implied association should show up in the data
# If D and Y show near-zero correlation despite an open path,
# faithfulness may be violated (or the path is very weak)

# Check pairwise correlations for variables the DAG says are connected
cor_matrix <- cor(df[, c("D", "Y", "X")], use = "complete.obs")
cat("Correlation matrix (look for near-zero values on connected pairs):\n")
print(round(cor_matrix, 3))
```

Python:
```python
import pandas as pd

# Check pairwise correlations for variables the DAG says are connected
# Near-zero correlations where the DAG predicts dependence
# are suggestive of faithfulness violations (path cancellation)

cor_matrix = df[["D", "Y", "X"]].corr()
print("Correlation matrix (look for near-zero values on connected pairs):")
print(cor_matrix.round(3))

# If D -> Y exists in the DAG but cor(D, Y) is near zero,
# either: (1) the effect is truly tiny, (2) paths cancel
# (faithfulness violation), or (3) the DAG is wrong.
# Domain knowledge is needed to adjudicate.
```

**What violation looks like**: Variables that the DAG says are connected by open causal paths show near-zero associations in data. A treatment has two paths to the outcome (one positive, one negative through a mediator) that happen to almost perfectly cancel. This is rare in practice but can occur in specific structural configurations.

**Severity if violated**: Serious. If faithfulness is violated, the testable implications of the DAG become unreliable as a diagnostic tool. You might fail to detect open paths, leading to incorrect conclusions about which paths are active. More importantly, algorithms that learn DAG structure from data (e.g., PC algorithm, FCI) assume faithfulness — they will produce incorrect graphs if it's violated.

**Mitigation**: (1) Faithfulness violations from exact cancellation are considered rare in practice (they require precise parameter tuning). (2) If you suspect near-cancellation, decompose the total effect into direct and indirect components to see if they have opposite signs. (3) Use theory and domain knowledge rather than relying solely on statistical tests to validate the DAG. (4) Be cautious with causal discovery algorithms — they are more sensitive to faithfulness violations than manual DAG construction.

---

## Correct Edge Direction

**Plain language**: Every arrow in the DAG points in the right direction. If you draw X → Y, then X genuinely causes Y, not the reverse. Getting an arrow backwards is as bad as omitting a confounder — it can make a valid adjustment set invalid or hide a bias.

**Formal statement**: For every directed edge V_i → V_j in the graph G, V_i is a direct cause of V_j relative to the variables in V(G). No edge should be reversed: if the true causal structure has V_j → V_i, then G is misspecified. Misspecified edge directions change the d-separation structure, potentially altering which adjustment sets are valid.

**Testable?**: Partially. Temporal ordering provides a strong test: causes must precede effects. Some edges can be tested using instrumental variable logic (Mendelian randomization) or natural experiments. But in cross-sectional observational data with simultaneous variables, direction is often untestable.

**How to test**:

R:
```r
# The strongest test is temporal: causes precede effects.
# Check whether your causal ordering is consistent with timing.

# For each edge X -> Y in your DAG, verify:
# 1. Is X measured before Y? (strongest evidence)
# 2. Can you intervene on X and observe Y change? (experimental)
# 3. Does theory/domain knowledge support X -> Y over Y -> X?

# dagitty can check if the graph is consistent with
# a given temporal ordering
library(dagitty)

dag <- dagitty('dag {
  D [exposure]
  Y [outcome]
  X -> D
  X -> Y
  D -> Y
}')

# Test: if we know X is measured at time 1, D at time 2, Y at time 3
# then X -> D and D -> Y are consistent with temporal ordering
# but Y -> X would NOT be

# Check testable implications — if any fail, edge direction may be wrong
tests <- localTests(dag, data = df, type = "cis.pillai")
cat("Implied independence tests:\n")
print(tests)

# Failed tests suggest EITHER a missing edge OR a wrong direction
# Domain knowledge is needed to distinguish these
```

Python:
```python
import networkx as nx

# Verify temporal consistency of edge directions
# For each edge, check if cause precedes effect in time

G = nx.DiGraph()
G.add_edges_from([("X", "D"), ("X", "Y"), ("D", "Y")])

# Define temporal ordering (earlier = lower number)
time_order = {"X": 1, "D": 2, "Y": 3}

print("Edge direction consistency with temporal ordering:")
for u, v in G.edges():
    t_u = time_order.get(u, None)
    t_v = time_order.get(v, None)
    if t_u is not None and t_v is not None:
        consistent = t_u < t_v
        status = "OK" if consistent else "VIOLATION"
        print(f"  {u} -> {v}: time({u})={t_u}, time({v})={t_v} [{status}]")
    else:
        print(f"  {u} -> {v}: temporal ordering unknown — needs domain knowledge")
```

**What violation looks like**: Testable implications of the DAG are rejected, but no confounders appear to be missing. The estimated causal effect is implausibly large, has the wrong sign, or is highly sensitive to minor specification changes — all of which can result from a reversed edge that makes the "adjustment set" invalid. In extreme cases, a reversed edge turns a confounder into a collider (or vice versa), completely changing the identification strategy.

**Severity if violated**: Fatal. A reversed edge changes the d-separation structure of the graph. A variable that is a confounder under the correct direction becomes a collider (or vice versa) under the wrong direction. This means adjustment sets computed from the graph may open spurious paths instead of closing them. The estimated causal effect can be biased in either direction, including sign reversal.

**Mitigation**: (1) Use temporal ordering as the primary guide: if X is measured before Y, prefer X → Y. (2) For simultaneous variables, rely on domain theory and the mechanism: "does X plausibly cause Y, or is it the other direction?" (3) Run the analysis under both directions as a sensitivity check: if the conclusion changes when you flip a debatable arrow, the result is fragile. (4) Use partial identification or bounds that are valid under both directions. (5) If direction is genuinely ambiguous and consequential, flag it as a key limitation and consider natural experiments that could disambiguate.
