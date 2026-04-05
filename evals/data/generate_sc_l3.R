set.seed(2031)

n_units <- 10   # 1 treated + 9 donors
n_periods <- 30 # 20 pre + 10 post
treatment_time <- 21
true_effect <- 5.0

# Common factor
common_factor <- cumsum(rnorm(n_periods, 0.5, 1))

# Unit-specific loadings and intercepts
unit_data <- data.frame()
for (u in 1:n_units) {
  intercept <- rnorm(1, 50, 10)
  loading <- runif(1, 0.5, 1.5)
  noise <- rnorm(n_periods, 0, 2)

  outcome <- intercept + loading * common_factor + noise

  # Add treatment effect to unit 1
  if (u == 1) {
    outcome[treatment_time:n_periods] <- outcome[treatment_time:n_periods] + true_effect
  }

  unit_data <- rbind(unit_data, data.frame(
    unit = u,
    time = 1:n_periods,
    outcome = round(outcome, 2),
    treated = as.integer(u == 1),
    post = as.integer((1:n_periods) >= treatment_time)
  ))
}

write.csv(unit_data, "evals/data/sc_basic_l3.csv", row.names = FALSE)
cat("Generated SC L3 dataset: 10 units x 30 periods, true effect =", true_effect, "\n")
