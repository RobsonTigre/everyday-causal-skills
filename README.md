🇺🇸  **English** | [🇧🇷  Português (BR)](README.pt-BR.md)

# everyday-causal-skills

<p align="center">
  <img src="repo-cover.png" alt="everyday-causal-skills" width="60%" />
</p>

> Use it to think through causal problems, plan your analysis, and implement it — conceptually or in R and Python.

A [Claude Code](https://docs.anthropic.com/en/docs/claude-code) plugin for causal inference. Describe a problem in plain language and it walks you through choosing a method, checking assumptions, writing the analysis in R or Python, and stress-testing the results. Built for practitioners who want a structured workflow and learners building intuition alongside [the book](https://www.everydaycausal.com/).

## Quick start

1. `/causal-planner` — Describe your problem in plain language. The plugin identifies the causal question and recommends a method.
2. `/causal-did` (or whichever method fits) — Walk through assumptions, generate analysis code, and run robustness checks.
3. `/causal-auditor` — Stress-test the finished analysis against threats to validity.

## What it looks like

In one example: a retail company rolled out a loyalty program in 12 stores and wants to know if repeat purchases increased. You type `/causal-planner`, answer a few questions about treatment, outcome, and data structure, and it recommends difference-in-differences.

You run `/causal-did`. The plugin walks you through five stages: confirming the setup, testing parallel pre-trends, generating estimation code in R or Python, running placebo and robustness checks, and summarizing the result with caveats. If pre-trends diverge, it flags the problem and suggests alternatives before you move on.

## Skills

| Skill | Purpose |
|---|---|
| `/causal-planner` | Describe a causal question in plain language and get a method recommendation with an analysis plan |
| `/causal-experiments` | Design and analyze RCTs and A/B tests — power analysis, randomization checks, balance diagnostics |
| `/causal-did` | Difference-in-differences with support for staggered adoption, TWFE, and event studies |
| `/causal-iv` | Instrumental variables estimation with 2SLS, weak instrument diagnostics, and exclusion checks |
| `/causal-rdd` | Sharp and fuzzy regression discontinuity with bandwidth selection and manipulation tests |
| `/causal-sc` | Synthetic control with donor weighting, pre-fit diagnostics, and placebo tests |
| `/causal-matching` | Propensity score matching, IPW, and doubly-robust estimators with balance diagnostics |
| `/causal-timeseries` | Interrupted time series and CausalImpact with pre-period validation |
| `/causal-auditor` | Stress-test any completed analysis against five categories of threats to validity |
| `/causal-exercises` | Practice on simulated data with known ground truth and get feedback on your approach |

## How it works

Every method skill follows five stages: setup, assumptions, implementation, robustness, and interpretation.

Built-in guardrails at every stage:

- **Verification gate** — The plugin won't interpret results until it has seen actual output from your code, not just the code itself
- **Severity flags** — Fatal problems (like violated assumptions) block progress; serious ones get flagged as caveats; rationalization shortcuts are called out
- **Method integration** — Each skill knows what comes before it, what comes after, and what to suggest when assumptions fail

## Installation

Run these three commands in the Claude Code prompt:

```bash
# 1. Register the marketplace
/plugin marketplace add RobsonTigre/everyday-causal-skills

# 2. Install the plugin (format: plugin@marketplace)
/plugin install everyday-causal-skills@everyday-causal-skills

# 3. Activate
/reload-plugins
```

Verify with `/causal-planner` — if it asks about your causal problem, you're set.

To update:

```bash
/plugin marketplace update everyday-causal-skills
/reload-plugins
```

To auto-update on startup: `/plugin` → **Marketplaces** tab → toggle **auto-update**.

## Resources

This plugin helps you think through causal problems step by step, but it does not replace your judgment. AI can make mistakes, especially when interpreting context-specific assumptions. For the reasoning behind each method, consult the book.

- [Everyday Causal Inference: How to Estimate, Test, and Explain Impacts with R and Python](https://www.everydaycausal.com/) — [Robson Tigre](https://www.robsontigre.com/)

Recommended companion plugins:

- [superpowers](https://github.com/obra/superpowers) — Helps the AI think before acting, so it plans and reasons through problems instead of jumping straight into code or answers
- [claude-mem](https://github.com/thedotmack/claude-mem) — Captures relevant information across sessions and brings it back when needed, giving the AI a working memory

## Roadmap

- [ ] **`/causal-dag`** — DAG construction, critique, and identification-strategy reasoning
- [ ] **`/causal-ml`** — Causal forests, X-learner, DML, heterogeneous treatment effects
- [ ] **`/causal-sensitivity`** — E-values, Rosenbaum bounds, omitted variable bias (Cinelli & Hazlett)
- [ ] **`/causal-mediation`** — Direct/indirect effects, natural and controlled mediation
- [ ] **`/causal-discovery`** — Learn causal structure from data (PC, FCI, score-based)
- [ ] **`/causal-trivia`** — Concept drills and causal inference trivia
- [ ] **`/causal-news`** — Summaries of recent causal inference papers
- [ ] **`/causal-report`** — Publication-ready reports with tables, figures, and method summaries
- [ ] **Ground skills in seminal papers** — Link each skill to its foundational papers with key results and assumptions
- [ ] **Token optimization** — Compress SKILL.md files to reduce token cost without losing precision
