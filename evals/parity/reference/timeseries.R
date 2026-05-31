# Single-series interrupted time series (segmented regression) -- R reference.
# `df` is preloaded by the parity runner from the shared fixture.
# Mirrors the Python recipe: same segmented-regression design and Newey-West
# (HAC) SEs (lag = 4, no prewhitening) so the estimands compare like-for-like.
suppressMessages(library(sandwich))

model <- lm(outcome ~ time + post + time_since, data = df)
V <- NeweyWest(model, lag = 4, prewhite = FALSE)  # Newey-West HAC standard errors
se <- sqrt(diag(V))

cat(sprintf("LEVEL:%f\n", coef(model)["post"]))        # immediate level shift
cat(sprintf("TREND:%f\n", coef(model)["time_since"]))   # change in slope after intervention
cat(sprintf("SE_LEVEL:%f\n", se["post"]))               # HAC SE of the level shift
