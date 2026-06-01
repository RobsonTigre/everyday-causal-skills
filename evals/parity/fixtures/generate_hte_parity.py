"""Generate the deterministic HTE parity fixture.

Design goals (so grf's AIPW and econml's DML agree despite different RNGs):
  * Randomized treatment with KNOWN propensity 0.5 -> removes confounding/propensity
    estimation noise; both forests target the same well-identified ATE.
  * Strong LINEAR heterogeneity in a single dominant modifier (`age`) -> the robust
    summary estimands we compare (overall ATE, and the best-linear-projection slope
    on the centered modifier) concentrate as n grows and are RNG-stable.
  * Modest noise + large n (8000) so the ATE/BLP-slope standard errors are small
    relative to the parity tolerance.

True CATE:  tau(x) = 4 + 0.20 * (age - 40)
  => true ATE at the sample mean age (~40) is ~4.0
  => true BLP slope of tau on (age - 40) is 0.20

Columns: worker_id, age, income, gender, treatment, outcome
(matches the column contract used by templates/{r,python}/hte.md)
"""
import numpy as np
import pandas as pd

SEED = 20260530
N = 8000
AGE_MEAN = 40.0
TAU_INTERCEPT = 4.0      # CATE at age == AGE_MEAN
TAU_AGE_SLOPE = 0.20     # CATE change per year of age (centered)
NOISE_SD = 3.0
PROPENSITY = 0.5         # randomized assignment, known propensity

OUT = "/Users/robsontigre/Desktop/everyday-causal-skills/evals/parity/fixtures/hte_parity.csv"


def main():
    rng = np.random.default_rng(SEED)

    age = rng.normal(AGE_MEAN, 10.0, N).round(2)
    income = rng.normal(50000, 15000, N).round(2)
    gender = rng.integers(0, 2, N)

    # Randomized treatment: known propensity, no confounding.
    treatment = rng.binomial(1, PROPENSITY, N)

    # Baseline outcome depends on covariates (these are confounders/predictors of Y
    # but NOT of treatment, since treatment is randomized).
    baseline = (
        50.0
        + 0.10 * (age - AGE_MEAN)
        + 0.0001 * (income - 50000)
        + 1.5 * gender
    )

    # Heterogeneous treatment effect: linear in centered age (dominant modifier).
    tau = TAU_INTERCEPT + TAU_AGE_SLOPE * (age - AGE_MEAN)

    noise = rng.normal(0, NOISE_SD, N)
    outcome = (baseline + treatment * tau + noise).round(4)

    df = pd.DataFrame({
        "worker_id": np.arange(1, N + 1),
        "age": age,
        "income": income,
        "gender": gender,
        "treatment": treatment,
        "outcome": outcome,
    })
    df.to_csv(OUT, index=False)

    # Report the ground-truth summaries the parity recipes target.
    print(f"wrote {OUT}  shape={df.shape}")
    print(f"true ATE (E[tau]) = {tau.mean():.4f}")
    print(f"true BLP age slope = {TAU_AGE_SLOPE:.4f}")
    print(f"treated fraction = {treatment.mean():.4f}")


if __name__ == "__main__":
    main()
