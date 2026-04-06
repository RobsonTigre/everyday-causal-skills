# everyday-causal-skills

Causal inference plugin for AI agents. Helps users choose a method, check assumptions, write the analysis in R or Python, and stress-test the results.

## Workflow

The plugin works in six stages. Start from any step. Stages marked (optional) can be skipped.

1. **Plan** → `/causal-planner` identifies the causal question and recommends a method
2. **Structure** (optional) → `/causal-dag` maps causal relationships and identifies adjustment sets
3. **Implement** → Method-specific skill (`/causal-did`, `/causal-iv`, `/causal-rdd`, `/causal-sc`, `/causal-matching`, `/causal-timeseries`, `/causal-experiments`, `/causal-hte`) checks assumptions and writes the analysis
4. **Audit** → `/causal-auditor` stress-tests the completed analysis against threats to validity
5. **Report** → `/causal-report` compiles artifacts into a structured report
6. **Practice** → `/causal-exercises` generates exercises with known ground truth

## How skills connect

- `/causal-planner` is the recommended entry point. It recommends which method skill to use next.
- `/causal-dag` sits between the planner and method skills. It helps decide what to control for before estimation begins. The auditor can refer back to it.
- Each method skill follows five internal stages: setup, assumptions, implementation, robustness, interpretation.
- When assumptions fail, method skills suggest alternatives (e.g., if parallel trends fail in DiD, suggest synthetic control).
- `/causal-hte` follows any average treatment effect method. It estimates who benefits most and supports policy learning.
- `/causal-auditor` should run AFTER an analysis is complete, not before.
- `/causal-report` is the terminal skill. It reads all artifacts (plan, DAG, implementation, audit) and compiles them into a report.

## Guardrails

- **Verification gate**: No result interpretation until actual code output has been seen — not just the code itself.
- **Severity flags**: Fatal problems block progress. Serious ones are flagged as caveats. Rationalization shortcuts are called out.
- **Anti-rationalization**: If results look too clean or convenient, the skill will push back.

## Available skills

| Skill | When to use |
|-------|------------|
| `causal-planner` | User has a causal question but doesn't know which method to use |
| `causal-dag` | DAG construction, adjustment sets, confounders, backdoor paths, bad controls |
| `causal-experiments` | Design or analyze RCTs and A/B tests |
| `causal-did` | Difference-in-differences, staggered adoption, TWFE, event studies |
| `causal-iv` | Instrumental variables, 2SLS, weak instrument diagnostics |
| `causal-rdd` | Sharp and fuzzy regression discontinuity |
| `causal-sc` | Synthetic control with donor weighting and placebo tests |
| `causal-matching` | Propensity score matching, IPW, doubly-robust estimators |
| `causal-timeseries` | Interrupted time series and CausalImpact |
| `causal-hte` | Heterogeneous treatment effects, CATE, Causal Forest, policy learning |
| `causal-auditor` | Stress-test a completed analysis |
| `causal-report` | Compile analysis into a structured report (business, academic, hybrid) |
| `causal-exercises` | Practice with simulated data |
