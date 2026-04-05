# everyday-causal-skills

Causal inference plugin for AI agents. Helps users choose a method, check assumptions, write the analysis in R or Python, and stress-test the results.

## Workflow

The plugin works in five stages. Start from any step.

1. **Plan** → `/causal-planner` identifies the causal question and recommends a method
2. **Implement** → Method-specific skill (`/causal-did`, `/causal-iv`, `/causal-rdd`, `/causal-sc`, `/causal-matching`, `/causal-timeseries`, `/causal-experiments`) checks assumptions and writes the analysis
3. **Audit** → `/causal-auditor` stress-tests the completed analysis against threats to validity
4. **Practice** → `/causal-exercises` generates exercises with known ground truth

## How skills connect

- `/causal-planner` is the recommended entry point. It recommends which method skill to use next.
- Each method skill follows five internal stages: setup, assumptions, implementation, robustness, interpretation.
- When assumptions fail, method skills suggest alternatives (e.g., if parallel trends fail in DiD, suggest synthetic control).
- `/causal-auditor` should run AFTER an analysis is complete, not before.

## Guardrails

- **Verification gate**: No result interpretation until actual code output has been seen — not just the code itself.
- **Severity flags**: Fatal problems block progress. Serious ones are flagged as caveats. Rationalization shortcuts are called out.
- **Anti-rationalization**: If results look too clean or convenient, the skill will push back.

## Available skills

| Skill | When to use |
|-------|------------|
| `causal-planner` | User has a causal question but doesn't know which method to use |
| `causal-experiments` | Design or analyze RCTs and A/B tests |
| `causal-did` | Difference-in-differences, staggered adoption, TWFE, event studies |
| `causal-iv` | Instrumental variables, 2SLS, weak instrument diagnostics |
| `causal-rdd` | Sharp and fuzzy regression discontinuity |
| `causal-sc` | Synthetic control with donor weighting and placebo tests |
| `causal-matching` | Propensity score matching, IPW, doubly-robust estimators |
| `causal-timeseries` | Interrupted time series and CausalImpact |
| `causal-auditor` | Stress-test a completed analysis |
| `causal-exercises` | Practice with simulated data |
