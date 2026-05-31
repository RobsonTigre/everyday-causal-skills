# DAG parity reference recipe (Python). `df` is preloaded by the runner.
# Canonical stack: networkx for graph identification (d-separation, descendants);
# statsmodels OLS for the front-door estimand. Mirrors reference/dag.R.
import networkx as nx
import statsmodels.api as sm

# Front-door / backdoor SCM matching the fixture:
#   X -> D, X -> Y ; U -> D, U -> Y (U unobserved) ; D -> M -> Y (full mediator).
G = nx.DiGraph()
G.add_edges_from([("X", "D"), ("X", "Y"),
                  ("U", "D"), ("U", "Y"),
                  ("D", "M"), ("M", "Y")])
assert nx.is_directed_acyclic_graph(G)

# Structural identification (exercised so capability assertions are real).
# Backdoor blocked by unobserved U: conditioning on observed {X} alone does NOT
# d-separate D and Y in the mutilated graph -> no valid observed backdoor set.
G_mut = G.copy()
G_mut.remove_edges_from(list(G.out_edges("D")))
x_blocks = nx.d_separated(G_mut, {"D"}, {"Y"}, {"X"})
print(f"Observed backdoor set {{X}} blocks D-Y? {x_blocks}")

# Front-door estimand via two OLS stages (the numeric parity target).
stage1 = sm.OLS(df["M"], sm.add_constant(df["D"])).fit()
gamma = stage1.params["D"]                      # D -> M
stage2 = sm.OLS(df["Y"], sm.add_constant(df[["M", "D"]])).fit()
alpha = stage2.params["M"]                      # M -> Y | D
fd = gamma * alpha                              # total D -> Y via M

print(f"FD_STAGE1:{gamma}")
print(f"FD_STAGE2:{alpha}")
print(f"FRONTDOOR:{fd}")
