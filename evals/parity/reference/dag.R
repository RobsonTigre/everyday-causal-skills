# DAG parity reference recipe (R). `df` is preloaded by the runner.
# Canonical stack: dagitty for graph identification (adjustment sets,
# d-separation, testable implications); base lm for the front-door estimand.
suppressMessages(library(dagitty))

# Front-door / backdoor SCM matching the fixture:
#   X -> D, X -> Y ; U -> D, U -> Y (U unobserved) ; D -> M -> Y (full mediator).
g <- dagitty('dag {
  D [exposure]
  Y [outcome]
  U [unobserved]
  X -> D
  X -> Y
  U -> D
  U -> Y
  D -> M
  M -> Y
}')
stopifnot(isAcyclic(g))

# Structural identification (exercised so capability assertions are real).
# With U unobserved, no backdoor set exists; dagitty returns an empty result.
bd <- adjustmentSets(g, exposure = "D", outcome = "Y", type = "minimal")
cat("Backdoor minimal adjustment sets (D->Y):\n"); print(bd)

# Front-door identification: M fully mediates D -> Y.
ii <- impliedConditionalIndependencies(g)
cat("Number of implied conditional independencies:", length(ii), "\n")

# Front-door estimand via two OLS stages (the numeric parity target).
stage1 <- lm(M ~ D, data = df)
gamma  <- unname(coef(stage1)["D"])          # D -> M
stage2 <- lm(Y ~ M + D, data = df)
alpha  <- unname(coef(stage2)["M"])          # M -> Y | D
fd     <- gamma * alpha                        # total D -> Y via M

cat(sprintf("FD_STAGE1:%f\n", gamma))
cat(sprintf("FD_STAGE2:%f\n", alpha))
cat(sprintf("FRONTDOOR:%f\n", fd))
