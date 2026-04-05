# DGP Library: Data-Generating Processes for Causal Inference Exercises

Single source of truth for all data-generating processes used in eval exercises, skill demonstrations, and self-study. Each DGP produces a dataset with a known true causal effect that the student must recover using the correct method.

**Convention**: Every DGP is fully self-contained. Both R and Python code are provided, use fixed seeds for reproducibility, and write a CSV file that a student can load independently.

---

## DGP-01: Clean A/B Test (Basic, Experiments)

**Narrative**: An e-commerce company runs a straightforward A/B test on its checkout page. 10,000 users are randomly assigned 50/50 to see either the original page (control) or a redesigned page (treatment). The outcome is whether they complete a purchase (binary conversion).

**True ATE**: 0.03 (3 percentage-point increase in conversion)

**Difficulty**: Basic

**Target method**: Randomized Experiment / A/B Test

**Complications**: None. Clean randomization, no attrition, full compliance.

**R code**:
```r
set.seed(42)
n <- 10000
treatment <- rbinom(n, 1, 0.5)
# Base conversion rate 10%, treatment adds 3pp
p_convert <- 0.10 + 0.03 * treatment
conversion <- rbinom(n, 1, p_convert)
df <- data.frame(
  user_id     = 1:n,
  treatment   = treatment,
  conversion  = conversion
)
write.csv(df, "data.csv", row.names = FALSE)
```

**Python code**:
```python
import numpy as np
import pandas as pd

np.random.seed(42)
n = 10000
treatment = np.random.binomial(1, 0.5, n)
p_convert = 0.10 + 0.03 * treatment
conversion = np.random.binomial(1, p_convert)
df = pd.DataFrame({
    "user_id": np.arange(1, n + 1),
    "treatment": treatment,
    "conversion": conversion,
})
df.to_csv("data.csv", index=False)
```

---

## DGP-02: A/B Test with Differential Attrition (Intermediate, Experiments)

**Narrative**: A mobile app runs an A/B test on a new onboarding flow for 5,000 users. The new flow is more demanding, so 15% of treatment users drop out before the outcome is measured, while only 5% of control users drop out. Dropouts tend to be lower-engagement users who would have had worse outcomes. The true ATE among all randomized users is 0.05, but the naive estimate among completers is biased upward by approximately 0.02.

**True ATE**: 0.05 (among all randomized users, intention-to-treat)

**Difficulty**: Intermediate

**Target method**: Randomized Experiment with attrition correction

**Complications**: Differential attrition correlated with treatment and potential outcomes. Naive analysis on completers is biased. Student must detect attrition imbalance and apply bounds or Lee bounds.

**R code**:
```r
set.seed(101)
n <- 5000
treatment <- rbinom(n, 1, 0.5)

# Latent user engagement (higher = more engaged)
engagement <- rnorm(n, 0, 1)

# Outcome: score from 0-100, engagement and treatment both help
potential_outcome <- 50 + 10 * engagement + 5 * treatment + rnorm(n, 0, 10)

# Attrition: more likely in treatment, especially for low-engagement users
p_attrit <- ifelse(treatment == 1,
  plogis(-1.5 - 0.8 * engagement),  # ~15% base for treatment
  plogis(-2.9 - 0.3 * engagement)   # ~5% base for control
)
attrit <- rbinom(n, 1, p_attrit)

# Observed outcome: NA if attrited
observed_outcome <- ifelse(attrit == 1, NA, potential_outcome)

df <- data.frame(
  user_id          = 1:n,
  treatment        = treatment,
  engagement_score = round(engagement, 3),
  outcome          = round(observed_outcome, 2),
  attrited         = attrit
)
write.csv(df, "data.csv", row.names = FALSE)
```

**Python code**:
```python
import numpy as np
import pandas as pd

np.random.seed(101)
n = 5000
treatment = np.random.binomial(1, 0.5, n)

engagement = np.random.normal(0, 1, n)

potential_outcome = 50 + 10 * engagement + 5 * treatment + np.random.normal(0, 10, n)

def logistic(x):
    return 1 / (1 + np.exp(-x))

p_attrit = np.where(
    treatment == 1,
    logistic(-1.5 - 0.8 * engagement),
    logistic(-2.9 - 0.3 * engagement),
)
attrit = np.random.binomial(1, p_attrit)

observed_outcome = np.where(attrit == 1, np.nan, potential_outcome)

df = pd.DataFrame({
    "user_id": np.arange(1, n + 1),
    "treatment": treatment,
    "engagement_score": np.round(engagement, 3),
    "outcome": np.round(observed_outcome, 2),
    "attrited": attrit,
})
df.to_csv("data.csv", index=False)
```

---

## DGP-03: Classic 2x2 DiD (Basic, DiD)

**Narrative**: A retail chain tests a new store layout in 50 of its 100 stores starting in month 13 (out of 24 months). Before the layout change, treated and control stores follow parallel revenue trends. The layout change produces a sustained lift of 5.0 thousand dollars per month in the treated stores.

**True ATT**: 5.0 (thousands of dollars per month)

**Difficulty**: Basic

**Target method**: Difference-in-Differences (classic 2x2)

**Complications**: None. Clean parallel trends, balanced panel, no anticipation.

**R code**:
```r
set.seed(303)
n_stores <- 100
n_months <- 24
treat_month <- 13

store_id <- rep(1:n_stores, each = n_months)
month    <- rep(1:n_months, times = n_stores)

# First 50 stores are treated
treated <- as.integer(store_id <= 50)
post    <- as.integer(month >= treat_month)

# Store-level fixed effect
store_fe <- rep(rnorm(n_stores, 0, 3), each = n_months)

# Common time trend (linear + small noise)
time_trend <- 0.2 * month

# True ATT = 5.0
revenue <- 50 + store_fe + time_trend + 5.0 * treated * post + rnorm(n_stores * n_months, 0, 2)

df <- data.frame(
  store_id = store_id,
  month    = month,
  treated  = treated,
  post     = post,
  revenue  = round(revenue, 2)
)
write.csv(df, "data.csv", row.names = FALSE)
```

**Python code**:
```python
import numpy as np
import pandas as pd

np.random.seed(303)
n_stores = 100
n_months = 24
treat_month = 13

store_id = np.repeat(np.arange(1, n_stores + 1), n_months)
month = np.tile(np.arange(1, n_months + 1), n_stores)

treated = (store_id <= 50).astype(int)
post = (month >= treat_month).astype(int)

store_fe = np.repeat(np.random.normal(0, 3, n_stores), n_months)
time_trend = 0.2 * month

revenue = (
    50 + store_fe + time_trend + 5.0 * treated * post
    + np.random.normal(0, 2, n_stores * n_months)
)

df = pd.DataFrame({
    "store_id": store_id,
    "month": month,
    "treated": treated,
    "post": post,
    "revenue": np.round(revenue, 2),
})
df.to_csv("data.csv", index=False)
```

---

## DGP-04: Staggered Policy Rollout (Intermediate, DiD)

**Narrative**: A restaurant chain with 200 locations rolls out a new ordering kiosk in four waves: 50 stores at month 7, 50 at month 13, 50 at month 19, and 50 never treated (pure control). The chain observes monthly order counts over 24 months. The true ATT differs by cohort: early adopters (month 7) gain 200 orders/month, mid adopters (month 13) gain 150, and late adopters (month 19) gain 100. Naive TWFE is biased because it uses early-treated units as implicit controls for later-treated units, contaminating the estimate.

**True ATT**: 200 (cohort 1), 150 (cohort 2), 100 (cohort 3)

**Difficulty**: Intermediate

**Target method**: Staggered DiD (Callaway-Sant'Anna or Sun-Abraham)

**Complications**: Heterogeneous treatment effects across cohorts. Naive TWFE produces a biased weighted average that can even have the wrong sign for some dynamic effects. Student must use a heterogeneity-robust estimator.

**R code**:
```r
set.seed(404)
n_stores <- 200
n_months <- 24

# Assign cohorts: 50 each to treatment months 7, 13, 19, and never-treated (0)
cohort_month <- rep(c(7, 13, 19, 0), each = 50)

store_id <- rep(1:n_stores, each = n_months)
month    <- rep(1:n_months, times = n_stores)
g        <- rep(cohort_month, each = n_months)  # cohort indicator

# Store and time fixed effects
store_fe <- rep(rnorm(n_stores, 0, 20), each = n_months)
time_fe  <- rep(rnorm(n_months, 0, 5), times = n_stores)

# Treatment effect: varies by cohort, grows slightly over time since treatment
treat_effect <- ifelse(g == 0 | month < g, 0,
  ifelse(g == 7,  200 + 2 * (month - g),
  ifelse(g == 13, 150 + 1.5 * (month - g),
                  100 + 1 * (month - g))))

orders <- 800 + store_fe + time_fe + treat_effect + rnorm(n_stores * n_months, 0, 30)

df <- data.frame(
  store_id     = store_id,
  month        = month,
  cohort_month = g,
  orders       = round(orders)
)
write.csv(df, "data.csv", row.names = FALSE)
```

**Python code**:
```python
import numpy as np
import pandas as pd

np.random.seed(404)
n_stores = 200
n_months = 24

cohort_month = np.repeat([7, 13, 19, 0], 50)

store_id = np.repeat(np.arange(1, n_stores + 1), n_months)
month = np.tile(np.arange(1, n_months + 1), n_stores)
g = np.repeat(cohort_month, n_months)

store_fe = np.repeat(np.random.normal(0, 20, n_stores), n_months)
time_fe = np.tile(np.random.normal(0, 5, n_months), n_stores)

treat_effect = np.where(
    (g == 0) | (month < g), 0,
    np.where(g == 7, 200 + 2 * (month - g),
    np.where(g == 13, 150 + 1.5 * (month - g),
             100 + 1 * (month - g)))
)

orders = (
    800 + store_fe + time_fe + treat_effect
    + np.random.normal(0, 30, n_stores * n_months)
)

df = pd.DataFrame({
    "store_id": store_id,
    "month": month,
    "cohort_month": g,
    "orders": np.round(orders).astype(int),
})
df.to_csv("data.csv", index=False)
```

---

## DGP-05: Strong Instrument (Basic, IV)

**Narrative**: A health insurer sends encouragement letters to randomly selected members urging them to enroll in a wellness program. The letter (instrument) strongly predicts enrollment (treatment), but enrollment is voluntary so it is endogenous. The outcome is annual medical spending. Among compliers (those who enroll because of the letter), the program reduces spending by $10,000. The first-stage F-statistic exceeds 50.

**True LATE**: -10.0 (thousands of dollars reduction in spending among compliers)

**Difficulty**: Basic

**Target method**: Instrumental Variables (2SLS)

**Complications**: None. Strong instrument, exclusion restriction holds, monotonicity satisfied.

**R code**:
```r
set.seed(505)
n <- 3000

# Instrument: randomly assigned encouragement letter
Z <- rbinom(n, 1, 0.5)

# Unobserved health motivation (confounder)
U <- rnorm(n, 0, 1)

# Treatment: enrollment in wellness program
# Letter strongly predicts enrollment (F > 50)
p_enroll <- plogis(-1.0 + 1.5 * Z + 1.0 * U)
D <- rbinom(n, 1, p_enroll)

# Outcome: medical spending (thousands)
# U directly affects spending (healthier people spend less)
# D reduces spending by 10 for compliers
Y <- 50 - 10 * D - 8 * U + rnorm(n, 0, 10)

df <- data.frame(
  id         = 1:n,
  encouraged = Z,
  enrolled   = D,
  spending   = round(Y, 2)
)
write.csv(df, "data.csv", row.names = FALSE)
```

**Python code**:
```python
import numpy as np
import pandas as pd

np.random.seed(505)
n = 3000

Z = np.random.binomial(1, 0.5, n)
U = np.random.normal(0, 1, n)

def logistic(x):
    return 1 / (1 + np.exp(-x))

p_enroll = logistic(-1.0 + 1.5 * Z + 1.0 * U)
D = np.random.binomial(1, p_enroll)

Y = 50 - 10 * D - 8 * U + np.random.normal(0, 10, n)

df = pd.DataFrame({
    "id": np.arange(1, n + 1),
    "encouraged": Z,
    "enrolled": D,
    "spending": np.round(Y, 2),
})
df.to_csv("data.csv", index=False)
```

---

## DGP-06: Weak Instrument (Intermediate, IV)

**Narrative**: Same health insurer setting, but now the encouragement letter is a generic email that barely moves enrollment. The first-stage F-statistic is around 5, well below the conventional threshold of 10. The true LATE is still -$10,000, but 2SLS estimates are wildly imprecise and biased toward the OLS estimate. Student must diagnose instrument weakness and consider alternatives (LIML, Anderson-Rubin confidence sets).

**True LATE**: -10.0 (thousands of dollars, but poorly identified)

**Difficulty**: Intermediate

**Target method**: Instrumental Variables (with weak-instrument diagnostics)

**Complications**: Weak first stage (F ~ 5). 2SLS is biased toward OLS. Confidence intervals are unreliable without weak-instrument-robust inference.

**R code**:
```r
set.seed(606)
n <- 3000

Z <- rbinom(n, 1, 0.5)
U <- rnorm(n, 0, 1)

# Weak instrument: small coefficient on Z
p_enroll <- plogis(-1.0 + 0.3 * Z + 1.0 * U)
D <- rbinom(n, 1, p_enroll)

Y <- 50 - 10 * D - 8 * U + rnorm(n, 0, 10)

df <- data.frame(
  id         = 1:n,
  encouraged = Z,
  enrolled   = D,
  spending   = round(Y, 2)
)
write.csv(df, "data.csv", row.names = FALSE)
```

**Python code**:
```python
import numpy as np
import pandas as pd

np.random.seed(606)
n = 3000

Z = np.random.binomial(1, 0.5, n)
U = np.random.normal(0, 1, n)

def logistic(x):
    return 1 / (1 + np.exp(-x))

p_enroll = logistic(-1.0 + 0.3 * Z + 1.0 * U)
D = np.random.binomial(1, p_enroll)

Y = 50 - 10 * D - 8 * U + np.random.normal(0, 10, n)

df = pd.DataFrame({
    "id": np.arange(1, n + 1),
    "encouraged": Z,
    "enrolled": D,
    "spending": np.round(Y, 2),
})
df.to_csv("data.csv", index=False)
```

---

## DGP-07: Sharp RDD (Basic, RDD)

**Narrative**: A university offers a merit scholarship to any student whose GPA is at or above 3.5. The scholarship is automatically awarded (perfect compliance at the cutoff). The outcome is first-year earnings after graduation (in thousands). The true effect of the scholarship on earnings at the cutoff is $3,000. The running variable (GPA) has a smooth density with no manipulation.

**True effect**: 3.0 (thousands of dollars at the cutoff)

**Difficulty**: Basic

**Target method**: Sharp Regression Discontinuity Design

**Complications**: None. Sharp assignment, smooth density, clean relationship.

**R code**:
```r
set.seed(707)
n <- 2000

# Running variable: GPA centered around 3.5 (range roughly 2.0-4.0)
gpa <- runif(n, 2.0, 4.0)

# Treatment: deterministic at cutoff
scholarship <- as.integer(gpa >= 3.5)

# Outcome: earnings in thousands
# Smooth function of GPA + treatment jump at cutoff
earnings <- 30 + 5 * (gpa - 3.5) + 2 * (gpa - 3.5)^2 +
            3.0 * scholarship + rnorm(n, 0, 3)

df <- data.frame(
  student_id  = 1:n,
  gpa         = round(gpa, 3),
  scholarship = scholarship,
  earnings    = round(earnings, 2)
)
write.csv(df, "data.csv", row.names = FALSE)
```

**Python code**:
```python
import numpy as np
import pandas as pd

np.random.seed(707)
n = 2000

gpa = np.random.uniform(2.0, 4.0, n)
scholarship = (gpa >= 3.5).astype(int)

earnings = (
    30 + 5 * (gpa - 3.5) + 2 * (gpa - 3.5) ** 2
    + 3.0 * scholarship + np.random.normal(0, 3, n)
)

df = pd.DataFrame({
    "student_id": np.arange(1, n + 1),
    "gpa": np.round(gpa, 3),
    "scholarship": scholarship,
    "earnings": np.round(earnings, 2),
})
df.to_csv("data.csv", index=False)
```

---

## DGP-08: Fuzzy RDD (Intermediate, RDD)

**Narrative**: A similar scholarship program, but now eligibility at the GPA 3.5 cutoff does not guarantee receipt. About 80% of students above the cutoff actually receive the scholarship (some decline or fail other criteria), and about 10% below the cutoff receive it through an appeals process. The true effect of actually receiving the scholarship on earnings is $4,000 among compliers at the cutoff.

**True effect**: 4.0 (thousands of dollars, LATE at the cutoff)

**Difficulty**: Intermediate

**Target method**: Fuzzy Regression Discontinuity Design

**Complications**: Imperfect compliance at the cutoff. Student must use a fuzzy RD (local IV) approach rather than comparing means.

**R code**:
```r
set.seed(808)
n <- 3000

gpa <- runif(n, 2.0, 4.0)
above_cutoff <- as.integer(gpa >= 3.5)

# Fuzzy treatment: 80% take-up above, 10% take-up below
p_scholarship <- ifelse(above_cutoff == 1, 0.80, 0.10)
scholarship <- rbinom(n, 1, p_scholarship)

# Unobserved ability correlated with scholarship take-up
ability <- 0.5 * (scholarship - mean(p_scholarship)) + rnorm(n, 0, 0.5)

# Outcome: earnings in thousands
earnings <- 30 + 5 * (gpa - 3.5) + 1.5 * (gpa - 3.5)^2 +
            4.0 * scholarship + 3 * ability + rnorm(n, 0, 3)

df <- data.frame(
  student_id  = 1:n,
  gpa         = round(gpa, 3),
  eligible    = above_cutoff,
  scholarship = scholarship,
  earnings    = round(earnings, 2)
)
write.csv(df, "data.csv", row.names = FALSE)
```

**Python code**:
```python
import numpy as np
import pandas as pd

np.random.seed(808)
n = 3000

gpa = np.random.uniform(2.0, 4.0, n)
above_cutoff = (gpa >= 3.5).astype(int)

p_scholarship = np.where(above_cutoff == 1, 0.80, 0.10)
scholarship = np.random.binomial(1, p_scholarship)

ability = 0.5 * (scholarship - p_scholarship.mean()) + np.random.normal(0, 0.5, n)

earnings = (
    30 + 5 * (gpa - 3.5) + 1.5 * (gpa - 3.5) ** 2
    + 4.0 * scholarship + 3 * ability + np.random.normal(0, 3, n)
)

df = pd.DataFrame({
    "student_id": np.arange(1, n + 1),
    "gpa": np.round(gpa, 3),
    "eligible": above_cutoff,
    "scholarship": scholarship,
    "earnings": np.round(earnings, 2),
})
df.to_csv("data.csv", index=False)
```

---

## DGP-09: Single Treated Unit (Basic, Synthetic Control)

**Narrative**: A U.S. state enacts a public health regulation at time period 21 (out of 40). There are 30 unaffected donor states. The outcome is monthly hospital admissions per 100,000 population. Before the policy, the treated state's admissions trajectory can be well-approximated by a weighted combination of donor states. The true effect is a reduction of 500 admissions per 100,000.

**True effect**: -500 (admissions per 100,000 per month, post-treatment)

**Difficulty**: Basic

**Target method**: Synthetic Control Method

**Complications**: None. Good pre-treatment fit is achievable; donor pool is adequate.

**R code**:
```r
set.seed(909)
n_donors <- 30
n_periods <- 40
treat_period <- 21

# Common factors driving admissions
factor1 <- cumsum(rnorm(n_periods, 0, 5))
factor2 <- sin(2 * pi * (1:n_periods) / 12) * 20

# Donor states: different loadings on common factors
donor_loadings1 <- runif(n_donors, 0.5, 1.5)
donor_loadings2 <- runif(n_donors, 0.5, 1.5)

# Treated state: its own loadings (recoverable from donors)
treated_loading1 <- 1.0
treated_loading2 <- 0.8

# Build panel
state_id <- rep(0:n_donors, each = n_periods)  # 0 = treated
period   <- rep(1:n_periods, times = n_donors + 1)

admissions <- numeric(length(state_id))
for (i in seq_along(state_id)) {
  t <- period[i]
  s <- state_id[i]
  if (s == 0) {
    # Treated state
    base <- 5000 + treated_loading1 * factor1[t] + treated_loading2 * factor2[t]
    effect <- ifelse(t >= treat_period, -500, 0)
    admissions[i] <- base + effect + rnorm(1, 0, 15)
  } else {
    # Donor state
    base <- 5000 + donor_loadings1[s] * factor1[t] + donor_loadings2[s] * factor2[t]
    admissions[i] <- base + rnorm(1, 0, 15)
  }
}

df <- data.frame(
  state_id   = state_id,
  period     = period,
  treated    = as.integer(state_id == 0),
  admissions = round(admissions, 1)
)
write.csv(df, "data.csv", row.names = FALSE)
```

**Python code**:
```python
import numpy as np
import pandas as pd

np.random.seed(909)
n_donors = 30
n_periods = 40
treat_period = 21

factor1 = np.cumsum(np.random.normal(0, 5, n_periods))
factor2 = np.sin(2 * np.pi * np.arange(1, n_periods + 1) / 12) * 20

donor_loadings1 = np.random.uniform(0.5, 1.5, n_donors)
donor_loadings2 = np.random.uniform(0.5, 1.5, n_donors)

treated_loading1 = 1.0
treated_loading2 = 0.8

rows = []
for s in range(n_donors + 1):
    for t in range(1, n_periods + 1):
        if s == 0:
            base = 5000 + treated_loading1 * factor1[t - 1] + treated_loading2 * factor2[t - 1]
            effect = -500 if t >= treat_period else 0
            admissions = base + effect + np.random.normal(0, 15)
        else:
            base = (
                5000
                + donor_loadings1[s - 1] * factor1[t - 1]
                + donor_loadings2[s - 1] * factor2[t - 1]
            )
            admissions = base + np.random.normal(0, 15)
        rows.append({"state_id": s, "period": t, "treated": int(s == 0),
                      "admissions": round(admissions, 1)})

df = pd.DataFrame(rows)
df.to_csv("data.csv", index=False)
```

---

## DGP-10: Synthetic Control with Poor Donor Pool (Intermediate, SC)

**Narrative**: A small island economy enacts a tourism tax. The available donor pool consists of 20 mainland economies that are structurally different: different GDP levels, different industry compositions, different population dynamics. The true effect of the tax is a reduction of 500 tourism arrivals per month, but because the donors are dissimilar, the synthetic control cannot achieve good pre-treatment fit. The student must diagnose the poor fit and interpret results cautiously.

**True effect**: -500 (tourism arrivals per month)

**Difficulty**: Intermediate

**Target method**: Synthetic Control Method (with fit diagnostics)

**Complications**: Donor units are dissimilar to the treated unit. Pre-treatment RMSPE is high. Student must check placebo tests and recognize the fragility of the estimate.

**R code**:
```r
set.seed(1010)
n_donors <- 20
n_periods <- 40
treat_period <- 21

# Treated unit has a unique seasonal pattern (island tourism)
island_season <- 200 * sin(2 * pi * (1:n_periods) / 12 + 1.0)
island_trend  <- 3 * (1:n_periods)

# Donors have a different seasonal phase and different level
donor_season_phase <- runif(n_donors, -pi, 0)  # different phase from island
donor_level <- runif(n_donors, 2000, 6000)      # very different base levels
donor_trend <- runif(n_donors, 0.5, 2.0)

state_id <- rep(0:n_donors, each = n_periods)
period   <- rep(1:n_periods, times = n_donors + 1)

arrivals <- numeric(length(state_id))
for (i in seq_along(state_id)) {
  t <- period[i]
  s <- state_id[i]
  if (s == 0) {
    base <- 8000 + island_trend[t] + island_season[t]
    effect <- ifelse(t >= treat_period, -500, 0)
    arrivals[i] <- base + effect + rnorm(1, 0, 50)
  } else {
    base <- donor_level[s] + donor_trend[s] * t +
            100 * sin(2 * pi * t / 12 + donor_season_phase[s])
    arrivals[i] <- base + rnorm(1, 0, 50)
  }
}

df <- data.frame(
  unit_id  = state_id,
  period   = period,
  treated  = as.integer(state_id == 0),
  arrivals = round(arrivals)
)
write.csv(df, "data.csv", row.names = FALSE)
```

**Python code**:
```python
import numpy as np
import pandas as pd

np.random.seed(1010)
n_donors = 20
n_periods = 40
treat_period = 21

periods = np.arange(1, n_periods + 1)
island_season = 200 * np.sin(2 * np.pi * periods / 12 + 1.0)
island_trend = 3 * periods

donor_season_phase = np.random.uniform(-np.pi, 0, n_donors)
donor_level = np.random.uniform(2000, 6000, n_donors)
donor_trend = np.random.uniform(0.5, 2.0, n_donors)

rows = []
for s in range(n_donors + 1):
    for t in range(1, n_periods + 1):
        if s == 0:
            base = 8000 + island_trend[t - 1] + island_season[t - 1]
            effect = -500 if t >= treat_period else 0
            val = base + effect + np.random.normal(0, 50)
        else:
            base = (
                donor_level[s - 1]
                + donor_trend[s - 1] * t
                + 100 * np.sin(2 * np.pi * t / 12 + donor_season_phase[s - 1])
            )
            val = base + np.random.normal(0, 50)
        rows.append({"unit_id": s, "period": t, "treated": int(s == 0),
                      "arrivals": round(val)})

df = pd.DataFrame(rows)
df.to_csv("data.csv", index=False)
```

---

## DGP-11: Good Overlap (Basic, Matching)

**Narrative**: A job training program is offered to unemployed workers. Participation is voluntary but predicted by three observed confounders: age, years of education, and previous earnings. Overlap between treated and control groups is good (propensity scores range 0.15 to 0.85 in both groups). The true ATE is a $2,000 increase in post-program earnings.

**True ATE**: 2.0 (thousands of dollars)

**Difficulty**: Basic

**Target method**: Matching / Propensity Score Methods

**Complications**: None. Good overlap, all confounders observed, no unmeasured confounding.

**R code**:
```r
set.seed(1111)
n <- 2000

age       <- rnorm(n, 35, 8)
education <- rnorm(n, 12, 2)
prev_earn <- rnorm(n, 25, 8)

# Treatment assignment: depends on confounders (moderate selection)
p_treat <- plogis(-2 + 0.03 * age + 0.15 * education + 0.04 * prev_earn)
treatment <- rbinom(n, 1, p_treat)

# Outcome: post-program earnings (thousands)
# True ATE = 2.0
post_earn <- 20 + 0.3 * age + 1.5 * education + 0.5 * prev_earn +
             2.0 * treatment + rnorm(n, 0, 5)

df <- data.frame(
  id         = 1:n,
  age        = round(age, 1),
  education  = round(education, 1),
  prev_earn  = round(prev_earn, 2),
  treatment  = treatment,
  post_earn  = round(post_earn, 2)
)
write.csv(df, "data.csv", row.names = FALSE)
```

**Python code**:
```python
import numpy as np
import pandas as pd

np.random.seed(1111)
n = 2000

age = np.random.normal(35, 8, n)
education = np.random.normal(12, 2, n)
prev_earn = np.random.normal(25, 8, n)

def logistic(x):
    return 1 / (1 + np.exp(-x))

p_treat = logistic(-2 + 0.03 * age + 0.15 * education + 0.04 * prev_earn)
treatment = np.random.binomial(1, p_treat)

post_earn = (
    20 + 0.3 * age + 1.5 * education + 0.5 * prev_earn
    + 2.0 * treatment + np.random.normal(0, 5, n)
)

df = pd.DataFrame({
    "id": np.arange(1, n + 1),
    "age": np.round(age, 1),
    "education": np.round(education, 1),
    "prev_earn": np.round(prev_earn, 2),
    "treatment": treatment,
    "post_earn": np.round(post_earn, 2),
})
df.to_csv("data.csv", index=False)
```

---

## DGP-12: Poor Overlap (Intermediate, Matching)

**Narrative**: Same job training program, but now participation is very strongly predicted by confounders. Highly educated, higher-earning workers almost always participate; low-education, low-earning workers almost never do. The propensity score distribution has very thin overlap (treated scores cluster 0.7-0.95, control scores cluster 0.05-0.3). The true ATE is still $2,000, but naive PSM without trimming or attention to the overlap region produces biased estimates because it extrapolates to regions where no comparable units exist.

**True ATE**: 2.0 (thousands of dollars)

**Difficulty**: Intermediate

**Target method**: Matching with trimming / overlap diagnostics

**Complications**: Severe positivity violation. Most treated units have no comparable controls. Student must diagnose overlap problems, trim the sample, and may need to redefine the estimand (ATT instead of ATE) or use augmented estimators.

**R code**:
```r
set.seed(1212)
n <- 2000

age       <- rnorm(n, 35, 8)
education <- rnorm(n, 12, 2)
prev_earn <- rnorm(n, 25, 8)

# Strong selection: sharp separation
p_treat <- plogis(-8 + 0.05 * age + 0.5 * education + 0.15 * prev_earn)
treatment <- rbinom(n, 1, p_treat)

# Outcome: True ATE = 2.0
post_earn <- 20 + 0.3 * age + 1.5 * education + 0.5 * prev_earn +
             2.0 * treatment + rnorm(n, 0, 5)

df <- data.frame(
  id         = 1:n,
  age        = round(age, 1),
  education  = round(education, 1),
  prev_earn  = round(prev_earn, 2),
  treatment  = treatment,
  post_earn  = round(post_earn, 2)
)
write.csv(df, "data.csv", row.names = FALSE)
```

**Python code**:
```python
import numpy as np
import pandas as pd

np.random.seed(1212)
n = 2000

age = np.random.normal(35, 8, n)
education = np.random.normal(12, 2, n)
prev_earn = np.random.normal(25, 8, n)

def logistic(x):
    return 1 / (1 + np.exp(-x))

p_treat = logistic(-8 + 0.05 * age + 0.5 * education + 0.15 * prev_earn)
treatment = np.random.binomial(1, p_treat)

post_earn = (
    20 + 0.3 * age + 1.5 * education + 0.5 * prev_earn
    + 2.0 * treatment + np.random.normal(0, 5, n)
)

df = pd.DataFrame({
    "id": np.arange(1, n + 1),
    "age": np.round(age, 1),
    "education": np.round(education, 1),
    "prev_earn": np.round(prev_earn, 2),
    "treatment": treatment,
    "post_earn": np.round(post_earn, 2),
})
df.to_csv("data.csv", index=False)
```

---

## DGP-13: Clean Interrupted Time Series (Basic, ITS)

**Narrative**: A city implements a new traffic safety policy at month 101 (out of 200 months). The outcome is monthly traffic fatalities. Before the policy, fatalities follow a stable linear trend. The policy produces an immediate, permanent level shift. The true per-period effect is -10 fatalities/month, yielding a cumulative effect of 1,000 fewer fatalities over the 100 post-treatment months. There is no seasonality or other confounding time-varying factors.

**True effect**: -10 per month (cumulative -1000 over 100 post-months)

**Difficulty**: Basic

**Target method**: Interrupted Time Series (segmented regression)

**Complications**: None. Clean level shift, linear pre-trend, no seasonality.

**R code**:
```r
set.seed(1313)
n_periods <- 200
treat_period <- 101

month <- 1:n_periods
post  <- as.integer(month >= treat_period)
time_since_treatment <- ifelse(post == 1, month - treat_period, 0)

# Pre-trend: slight decline in fatalities (improving safety over time)
trend <- -0.05 * month

# True effect: level shift of -10 fatalities
fatalities <- 100 + trend - 10 * post + rnorm(n_periods, 0, 3)

df <- data.frame(
  month      = month,
  post       = post,
  fatalities = round(fatalities, 1)
)
write.csv(df, "data.csv", row.names = FALSE)
```

**Python code**:
```python
import numpy as np
import pandas as pd

np.random.seed(1313)
n_periods = 200
treat_period = 101

month = np.arange(1, n_periods + 1)
post = (month >= treat_period).astype(int)

trend = -0.05 * month

fatalities = 100 + trend - 10 * post + np.random.normal(0, 3, n_periods)

df = pd.DataFrame({
    "month": month,
    "post": post,
    "fatalities": np.round(fatalities, 1),
})
df.to_csv("data.csv", index=False)
```

---

## DGP-14: ITS with Seasonality (Intermediate, ITS)

**Narrative**: A hospital implements a hand-hygiene intervention at week 105 (out of 156 weeks, i.e., 3 years of weekly data). The outcome is weekly hospital-acquired infections. There is strong seasonality (infections peak in winter). The true intervention effect is a reduction of 50 infections per week, but because the intervention happens to start in autumn, a naive before/after comparison confounds the treatment effect with the seasonal decline into winter. Student must model the seasonal component to isolate the true effect.

**True effect**: -50 infections per week

**Difficulty**: Intermediate

**Target method**: Interrupted Time Series with seasonal adjustment

**Complications**: Strong 52-week seasonal cycle. The intervention timing partially coincides with a seasonal trough, inflating the naive ITS estimate. Student must include Fourier terms or seasonal dummies.

**R code**:
```r
set.seed(1414)
n_weeks <- 156
treat_week <- 105

week <- 1:n_weeks
post <- as.integer(week >= treat_week)

# Seasonality: peak in winter (weeks ~1-10 and ~49-52 each year)
season <- 30 * sin(2 * pi * week / 52) + 15 * cos(2 * pi * week / 52)

# Slight downward pre-trend
trend <- -0.1 * week

# True effect: -50 infections per week
infections <- 300 + trend + season - 50 * post + rnorm(n_weeks, 0, 10)

df <- data.frame(
  week       = week,
  post       = post,
  infections = round(pmax(infections, 0), 1)
)
write.csv(df, "data.csv", row.names = FALSE)
```

**Python code**:
```python
import numpy as np
import pandas as pd

np.random.seed(1414)
n_weeks = 156
treat_week = 105

week = np.arange(1, n_weeks + 1)
post = (week >= treat_week).astype(int)

season = 30 * np.sin(2 * np.pi * week / 52) + 15 * np.cos(2 * np.pi * week / 52)
trend = -0.1 * week

infections = 300 + trend + season - 50 * post + np.random.normal(0, 10, n_weeks)
infections = np.maximum(infections, 0)

df = pd.DataFrame({
    "week": week,
    "post": post,
    "infections": np.round(infections, 1),
})
df.to_csv("data.csv", index=False)
```

---

## DGP-15: DiD with Non-Parallel Trends (Advanced, DiD)

**Narrative**: A state raises its minimum wage while a neighboring state does not. Both states are observed over 24 months, with the policy taking effect at month 13. However, the treated state was already on a steeper upward trajectory in wages before the policy -- its economy was growing faster for structural reasons unrelated to the minimum wage change. The true ATT is 5.0, but a naive DiD estimate is biased upward because the pre-trends are not parallel. The student must detect the violation and understand that DiD is not credible here without adjustment.

**True ATT**: 5.0 (but DiD gives approximately 8.0 due to diverging pre-trends)

**Difficulty**: Advanced

**Target method**: DiD (violation detection)

**Complications**: Pre-treatment trends diverge. A pre-trends test or event study will reveal the problem. Student must recognize that the parallel trends assumption fails and consider alternative approaches (e.g., conditioning on pre-trend, or switching to synthetic control).

**R code**:
```r
set.seed(1515)
n_units <- 200   # 100 per state
n_months <- 24
treat_month <- 13

unit_id <- rep(1:n_units, each = n_months)
month   <- rep(1:n_months, times = n_units)
treated <- as.integer(unit_id <= 100)
post    <- as.integer(month >= treat_month)

# Unit fixed effects
unit_fe <- rep(rnorm(n_units, 0, 2), each = n_months)

# Diverging trends: treated state grows faster even pre-treatment
trend_control <- 0.2 * month
trend_treated <- 0.5 * month   # steeper slope

trend <- ifelse(treated == 1, trend_treated, trend_control)

# True treatment effect is 5.0, but DiD will also capture the
# extra pre-trend slope (0.3 * 12 months of divergence post = ~3.6 extra)
true_effect <- 5.0 * treated * post

wage <- 25 + unit_fe + trend + true_effect + rnorm(n_units * n_months, 0, 1.5)

df <- data.frame(
  unit_id = unit_id,
  month   = month,
  treated = treated,
  post    = post,
  wage    = round(wage, 2)
)
write.csv(df, "data.csv", row.names = FALSE)
```

**Python code**:
```python
import numpy as np
import pandas as pd

np.random.seed(1515)
n_units = 200
n_months = 24
treat_month = 13

unit_id = np.repeat(np.arange(1, n_units + 1), n_months)
month = np.tile(np.arange(1, n_months + 1), n_units)
treated = (unit_id <= 100).astype(int)
post = (month >= treat_month).astype(int)

unit_fe = np.repeat(np.random.normal(0, 2, n_units), n_months)

trend_control = 0.2 * month
trend_treated = 0.5 * month
trend = np.where(treated == 1, trend_treated, trend_control)

true_effect = 5.0 * treated * post

wage = 25 + unit_fe + trend + true_effect + np.random.normal(0, 1.5, n_units * n_months)

df = pd.DataFrame({
    "unit_id": unit_id,
    "month": month,
    "treated": treated,
    "post": post,
    "wage": np.round(wage, 2),
})
df.to_csv("data.csv", index=False)
```

---

## DGP-16: RDD with Manipulation (Advanced, RDD)

**Narrative**: A government subsidy program awards grants to firms scoring at or above 70 on a review score. However, some firms near the cutoff lobby reviewers to nudge their scores just above 70. This creates bunching (excess density) just above the cutoff. The true effect of the subsidy on firm revenue is $3 million, but because manipulating firms differ systematically from non-manipulators, estimates near the cutoff are biased. The student must detect the manipulation via a McCrary/density test and understand its implications.

**True effect**: 3.0 (millions of dollars, but biased by sorting)

**Difficulty**: Advanced

**Target method**: RDD (violation detection)

**Complications**: Running variable manipulation at the cutoff. McCrary density test rejects smoothness. Student must detect the bunching and understand that the local randomization assumption fails.

**R code**:
```r
set.seed(1616)
n <- 3000

# Latent score (what the score would be without manipulation)
latent_score <- runif(n, 50, 90)

# Firm "connectedness" (ability to manipulate)
connected <- rbinom(n, 1, 0.3)

# Manipulation: connected firms near the cutoff get bumped above it
manipulation <- ifelse(connected == 1 & latent_score >= 65 & latent_score < 70,
                       runif(n, 1, 5), 0)
observed_score <- latent_score + manipulation

# Treatment: based on observed (manipulated) score
subsidy <- as.integer(observed_score >= 70)

# Outcome: revenue in millions
# Connected firms are also higher-ability, creating bias
revenue <- 10 + 0.2 * (observed_score - 70) + 0.05 * (observed_score - 70)^2 +
           3.0 * subsidy + 2.0 * connected + rnorm(n, 0, 2)

df <- data.frame(
  firm_id  = 1:n,
  score    = round(observed_score, 2),
  subsidy  = subsidy,
  revenue  = round(revenue, 2)
)
write.csv(df, "data.csv", row.names = FALSE)
```

**Python code**:
```python
import numpy as np
import pandas as pd

np.random.seed(1616)
n = 3000

latent_score = np.random.uniform(50, 90, n)
connected = np.random.binomial(1, 0.3, n)

manipulation = np.where(
    (connected == 1) & (latent_score >= 65) & (latent_score < 70),
    np.random.uniform(1, 5, n),
    0,
)
observed_score = latent_score + manipulation

subsidy = (observed_score >= 70).astype(int)

revenue = (
    10 + 0.2 * (observed_score - 70) + 0.05 * (observed_score - 70) ** 2
    + 3.0 * subsidy + 2.0 * connected + np.random.normal(0, 2, n)
)

df = pd.DataFrame({
    "firm_id": np.arange(1, n + 1),
    "score": np.round(observed_score, 2),
    "subsidy": subsidy,
    "revenue": np.round(revenue, 2),
})
df.to_csv("data.csv", index=False)
```

---

## DGP-17: Matching with Unobserved Confounder (Advanced, Matching)

**Narrative**: A company evaluates whether attending a leadership workshop improves employee performance ratings. Three confounders are observed: tenure, prior performance, and department. However, there is a fourth unobserved confounder: intrinsic motivation. Highly motivated employees are both more likely to attend the workshop and to receive higher performance ratings regardless. The true ATE of the workshop is 2.0 points, but matching on the three observed confounders yields an estimate of approximately 4.0 because of omitted variable bias from motivation.

**True ATE**: 2.0 (performance rating points)

**Difficulty**: Advanced

**Target method**: Matching (violation detection and sensitivity analysis)

**Complications**: Unobserved confounder (motivation) that affects both treatment and outcome. Matching on observed covariates does not eliminate the bias. Student must recognize the possibility of OVB and conduct a sensitivity analysis (e.g., Rosenbaum bounds, E-value).

**R code**:
```r
set.seed(1717)
n <- 2000

tenure      <- rnorm(n, 5, 2)
prior_perf  <- rnorm(n, 70, 10)
department  <- sample(1:5, n, replace = TRUE)

# Unobserved confounder: motivation (not in the dataset)
motivation  <- rnorm(n, 0, 1)

# Treatment: workshop attendance
p_attend <- plogis(-3 + 0.1 * tenure + 0.02 * prior_perf +
                   0.8 * motivation)
workshop <- rbinom(n, 1, p_attend)

# Outcome: performance rating (0-100)
# True effect of workshop = 2.0
# Motivation directly boosts performance by ~4 points per SD
performance <- 70 + 1.0 * tenure + 0.3 * prior_perf +
               4.0 * motivation + 2.0 * workshop +
               rnorm(n, 0, 5)

# Note: motivation is NOT included in the output dataset
df <- data.frame(
  id          = 1:n,
  tenure      = round(tenure, 1),
  prior_perf  = round(prior_perf, 1),
  department  = department,
  workshop    = workshop,
  performance = round(performance, 1)
)
write.csv(df, "data.csv", row.names = FALSE)
```

**Python code**:
```python
import numpy as np
import pandas as pd

np.random.seed(1717)
n = 2000

tenure = np.random.normal(5, 2, n)
prior_perf = np.random.normal(70, 10, n)
department = np.random.choice(range(1, 6), n)

# Unobserved confounder
motivation = np.random.normal(0, 1, n)

def logistic(x):
    return 1 / (1 + np.exp(-x))

p_attend = logistic(-3 + 0.1 * tenure + 0.02 * prior_perf + 0.8 * motivation)
workshop = np.random.binomial(1, p_attend)

performance = (
    70 + 1.0 * tenure + 0.3 * prior_perf
    + 4.0 * motivation + 2.0 * workshop
    + np.random.normal(0, 5, n)
)

# motivation is NOT included in the output
df = pd.DataFrame({
    "id": np.arange(1, n + 1),
    "tenure": np.round(tenure, 1),
    "prior_perf": np.round(prior_perf, 1),
    "department": department,
    "workshop": workshop,
    "performance": np.round(performance, 1),
})
df.to_csv("data.csv", index=False)
```

---

## DGP-18: IV with Exclusion Restriction Violation (Advanced, IV)

**Narrative**: Researchers study the effect of exercise on mental health using distance to the nearest gym as an instrument. The idea is that living closer to a gym encourages exercise but should not directly affect mental health. However, proximity to a gym is also correlated with neighborhood walkability and green space, which directly improve mental health independent of exercise. The true LATE of exercise is a 10-point improvement in mental health score, but because the instrument has a direct effect on the outcome (violating the exclusion restriction), the IV estimate is approximately 15.

**True LATE**: 10.0 (mental health score points)

**Difficulty**: Advanced

**Target method**: IV (violation detection)

**Complications**: The instrument (gym distance) violates the exclusion restriction by having a direct effect on the outcome through neighborhood quality. The IV estimate is biased upward. Student must recognize the plausibility concern and discuss why the exclusion restriction might fail.

**R code**:
```r
set.seed(1818)
n <- 3000

# Instrument: distance to nearest gym (km, lower = closer)
# Reversed so "encouraged" = close to gym
gym_distance <- runif(n, 0.5, 15)
Z <- -gym_distance  # higher Z = closer to gym (encouragement)

# Unobserved confounder: stress levels
stress <- rnorm(n, 0, 1)

# Treatment: hours of exercise per week
# Closer gym -> more exercise, but stress also reduces exercise
exercise <- pmax(0, 3 + 0.3 * Z - 1.5 * stress + rnorm(n, 0, 2))

# Outcome: mental health score (0-100, higher = better)
# True effect of exercise = +10 per unit (on standardized scale)
# EXCLUSION VIOLATION: gym proximity (Z) directly improves mental health
# through neighborhood walkability/green space (direct effect = +3 per unit of Z)
mental_health <- 50 + 10 * (exercise / sd(exercise)) +
                 3 * (Z / sd(Z)) -  # <-- exclusion violation
                 8 * stress + rnorm(n, 0, 5)

df <- data.frame(
  id            = 1:n,
  gym_distance  = round(gym_distance, 2),
  exercise      = round(exercise, 2),
  mental_health = round(mental_health, 2)
)
write.csv(df, "data.csv", row.names = FALSE)
```

**Python code**:
```python
import numpy as np
import pandas as pd

np.random.seed(1818)
n = 3000

gym_distance = np.random.uniform(0.5, 15, n)
Z = -gym_distance

stress = np.random.normal(0, 1, n)

exercise = np.maximum(0, 3 + 0.3 * Z - 1.5 * stress + np.random.normal(0, 2, n))

mental_health = (
    50
    + 10 * (exercise / exercise.std())
    + 3 * (Z / Z.std())   # exclusion violation
    - 8 * stress
    + np.random.normal(0, 5, n)
)

df = pd.DataFrame({
    "id": np.arange(1, n + 1),
    "gym_distance": np.round(gym_distance, 2),
    "exercise": np.round(exercise, 2),
    "mental_health": np.round(mental_health, 2),
})
df.to_csv("data.csv", index=False)
```

---

## DGP-DAG-01: Collider Bias (Bad Control Trap) (Intermediate, DAG)

**Narrative**: A company wants to know if gender (D) affects wages (Y). They have data on occupation (O) and ability (A). The true effect of gender on wages is -1.0 (discrimination). Ability is unobserved but affects both occupation and wages. Occupation is a collider: caused by both gender and ability.

**True ATE**: -1.0

**Difficulty**: Intermediate

**Target method**: DAG reasoning — student must identify that controlling for occupation alone reverses the sign.

**Complications**: Controlling for O alone yields ~+0.6 (wrong sign!). Must control for both O and A, or neither (ITT).

**R code**:
```r
set.seed(42)
n <- 10000
female     <- rbinom(n, 1, 0.5)
ability    <- rnorm(n, 0, 1)
occupation <- 1 + 2 * ability + (-2) * female + rnorm(n, 0, 1)
wage       <- 1 + (-1) * female + 3 * ability + 0.5 * occupation + rnorm(n, 0, 1)
df <- data.frame(
  id = 1:n, female = female, ability = ability,
  occupation = round(occupation, 2), wage = round(wage, 2)
)
write.csv(df, "dag_collider.csv", row.names = FALSE)
```

**Python code**:
```python
import numpy as np
import pandas as pd

np.random.seed(42)
n = 10000
female     = np.random.binomial(1, 0.5, n)
ability    = np.random.normal(0, 1, n)
occupation = 1 + 2 * ability + (-2) * female + np.random.normal(0, 1, n)
wage       = 1 + (-1) * female + 3 * ability + 0.5 * occupation + np.random.normal(0, 1, n)
df = pd.DataFrame({
    "id": np.arange(1, n + 1), "female": female, "ability": ability,
    "occupation": np.round(occupation, 2), "wage": np.round(wage, 2),
})
df.to_csv("dag_collider.csv", index=False)
```

---

## DGP-DAG-02: M-Bias (Pre-Treatment Collider) (Advanced, DAG)

**Narrative**: A researcher studies whether a job training program (D) improves earnings (Y). Variable Z is observed and is a pre-treatment collider: caused by U1 (unobserved motivation, which also causes D) and U2 (unobserved neighborhood quality, which also causes Y). U1 and U2 are independent. Conditioning on Z opens a spurious path.

**True ATE**: 2.0

**Difficulty**: Advanced

**Target method**: DAG reasoning — student must recognize Z as an M-bias collider and NOT control for it.

**Complications**: Naive OLS controlling for Z gives a biased estimate (~2.3). Omitting Z gives the correct estimate (~2.0).

**R code**:
```r
set.seed(42)
n <- 10000
U1 <- rnorm(n)
U2 <- rnorm(n)
Z  <- 0.8 * U1 + 0.8 * U2 + rnorm(n)
D  <- rbinom(n, 1, plogis(0.5 * U1))
Y  <- 2.0 * D + 1.5 * U2 + rnorm(n)
df <- data.frame(id = 1:n, D = D, Y = round(Y, 2), Z = round(Z, 2))
write.csv(df, "dag_mbias.csv", row.names = FALSE)
```

**Python code**:
```python
import numpy as np
import pandas as pd
from scipy.special import expit

np.random.seed(42)
n = 10000
U1 = np.random.normal(0, 1, n)
U2 = np.random.normal(0, 1, n)
Z  = 0.8 * U1 + 0.8 * U2 + np.random.normal(0, 1, n)
D  = np.random.binomial(1, expit(0.5 * U1))
Y  = 2.0 * D + 1.5 * U2 + np.random.normal(0, 1, n)
df = pd.DataFrame({
    "id": np.arange(1, n + 1), "D": D,
    "Y": np.round(Y, 2), "Z": np.round(Z, 2),
})
df.to_csv("dag_mbias.csv", index=False)
```

---

## DGP-DAG-03: Front-Door Criterion (Advanced, DAG)

**Narrative**: A company wants to know if ad exposure (D) increases purchases (Y). An unobserved factor (U, brand affinity) causes both ad exposure and purchases. However, ad exposure works entirely through a measurable mediator: website visits (M). The front-door criterion applies: D → M → Y, with U → D and U → Y.

**True ATE**: 1.5 (= effect of D on M × effect of M on Y = 0.6 × 2.5)

**Difficulty**: Advanced

**Target method**: DAG reasoning + front-door estimation — student must recognize backdoor is blocked by unobserved U, but front-door through M is available.

**Complications**: Naive regression of Y on D gives biased estimate (~2.8). Front-door two-step gives ~1.5.

**R code**:
```r
set.seed(42)
n <- 10000
U <- rnorm(n)
D <- rbinom(n, 1, plogis(1.0 * U))
M <- 0.6 * D + rnorm(n, 0, 0.5)
Y <- 2.5 * M + 2.0 * U + rnorm(n, 0, 0.5)
df <- data.frame(id = 1:n, D = D, M = round(M, 2), Y = round(Y, 2))
write.csv(df, "dag_frontdoor.csv", row.names = FALSE)
```

**Python code**:
```python
import numpy as np
import pandas as pd
from scipy.special import expit

np.random.seed(42)
n = 10000
U = np.random.normal(0, 1, n)
D = np.random.binomial(1, expit(1.0 * U))
M = 0.6 * D + np.random.normal(0, 0.5, n)
Y = 2.5 * M + 2.0 * U + np.random.normal(0, 0.5, n)
df = pd.DataFrame({
    "id": np.arange(1, n + 1), "D": D,
    "M": np.round(M, 2), "Y": np.round(Y, 2),
})
df.to_csv("dag_frontdoor.csv", index=False)
```

---

## Quick Reference Index

| DGP | Title | Difficulty | Method | True Effect | Key Feature |
|-----|-------|-----------|--------|-------------|-------------|
| 01 | Clean A/B Test | Basic | Experiment | ATE = 0.03 | Clean randomization |
| 02 | A/B Test with Attrition | Intermediate | Experiment | ATE = 0.05 | Differential attrition |
| 03 | Classic 2x2 DiD | Basic | DiD | ATT = 5.0 | Clean parallel trends |
| 04 | Staggered Policy Rollout | Intermediate | DiD | ATT = 200/150/100 | Heterogeneous cohort effects |
| 05 | Strong Instrument | Basic | IV | LATE = -10.0 | F > 50 |
| 06 | Weak Instrument | Intermediate | IV | LATE = -10.0 | F ~ 5, imprecise |
| 07 | Sharp RDD | Basic | RDD | Effect = 3.0 | Perfect compliance |
| 08 | Fuzzy RDD | Intermediate | RDD | LATE = 4.0 | 80% compliance |
| 09 | Single Treated Unit | Basic | SC | Effect = -500 | Good donor fit |
| 10 | SC with Poor Donor Pool | Intermediate | SC | Effect = -500 | Dissimilar donors |
| 11 | Good Overlap | Basic | Matching | ATE = 2.0 | Wide propensity support |
| 12 | Poor Overlap | Intermediate | Matching | ATE = 2.0 | Thin overlap region |
| 13 | Clean ITS | Basic | ITS | Effect = -10/month | No seasonality |
| 14 | ITS with Seasonality | Intermediate | ITS | Effect = -50/week | 52-week seasonal cycle |
| 15 | DiD with Non-Parallel Trends | Advanced | DiD | ATT = 5.0 (biased ~8.0) | Pre-trend divergence |
| 16 | RDD with Manipulation | Advanced | RDD | Effect = 3.0 (biased) | Bunching at cutoff |
| 17 | Matching with Unobserved Confounder | Advanced | Matching | ATE = 2.0 (biased ~4.0) | OVB from hidden variable |
| 18 | IV with Exclusion Violation | Advanced | IV | LATE = 10.0 (biased ~15.0) | Direct instrument effect |
| DAG-01 | Collider Bias (Bad Control Trap) | Intermediate | DAG | ATE = -1.0 | Collider conditioning reverses sign |
| DAG-02 | M-Bias (Pre-Treatment Collider) | Advanced | DAG | ATE = 2.0 | Conditioning on Z opens spurious path |
| DAG-03 | Front-Door Criterion | Advanced | DAG | ATE = 1.5 | Front-door identification via mediator |
