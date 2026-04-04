🇺🇸  **English** | [🇧🇷  Português (BR)](README.pt-BR.md)

# everyday-causal-skills

<p align="center">
  <img src="repo-cover.png" alt="everyday-causal-skills" width="60%" />
</p>

> Use it to think through causal problems, plan your analysis, and implement it: conceptually or in R and Python.

A causal inference plugin for AI agents. Describe a problem in plain language and it helps you choose a method, check assumptions, write the analysis in R or Python, and stress-test the results. Made for practitioners who want a structured workflow and learners building intuition alongside [the book](https://www.everydaycausal.com/).

**Works with:** Claude Code · Gemini CLI · GitHub Copilot CLI · Codex CLI · Cursor

**Who this is for:** Anyone who needs to measure whether something actually worked, such as Marketing and growth teams; Product managers and BI analysts; Data scientists; Revenue and operations teams; Policy researchers; Students and self-taught practitioners.

## What you get from this plugin

The plugin works in five steps, from refining the question you want to answer, to writing the report. You are free to pick and start from any step you like.

```
Describe your problem
→ Get a method recommendation
→ Check assumptions and structure the analysis
→ Stress-test the results
→ Write the executive report
```

**Example:**

1. Say a retail company rolled out a loyalty program in 12 stores and wants to know if repeat purchases actually increased. You run `/causal-planner`, answer a few questions about treatment, outcome, and data structure.
2. The plugin recommends you to use difference-in-differences as the tool to measure the impact of the program.
3. Then `/causal-did` picks it up: it checks whether pre-trends hold, writes the estimation code in R or Python, and runs placebo and robustness checks. If something breaks along the way, it tells you before you waste time on code that won't hold up.
4. Once you have results, `/causal-auditor` pokes holes in the analysis so you don't have to wait for a reviewer to do it.

## Skills

| Skill | Purpose |
|---|---|
| `/causal-planner` | Describe a causal question in plain language and get a method recommendation with an analysis plan |
| `/causal-experiments` | Design and analyze RCTs and A/B tests (power analysis, randomization checks, balance diagnostics) |
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

- **Verification gate.** The plugin won't interpret results until it has seen actual output from your code, not just the code itself.
- **Severity flags.** Fatal problems (like violated assumptions) block progress; serious ones get flagged as caveats; rationalization shortcuts are called out.
- **Method integration.** Each skill knows what comes before it, what comes after, and what to suggest when assumptions fail.

## Installation

Pick your platform of choice below and click to expand the instructions.

<details>
<summary><h3>Claude Code</h3></summary>

Run these commands in the Claude Code prompt:

```bash
# 1. Register the marketplace
/plugin marketplace add RobsonTigre/everyday-causal-skills

# 2. Install the plugin (format: plugin@marketplace)
/plugin install everyday-causal-skills@everyday-causal-skills

# 3. Activate
/reload-plugins
```

To update:

```bash
/plugin marketplace update everyday-causal-skills
/reload-plugins
```

To auto-update on startup: `/plugin` → **Marketplaces** tab → toggle **auto-update**.

</details>

<details>
<summary><h3>Gemini CLI</h3></summary>

```bash
gemini extensions install https://github.com/RobsonTigre/everyday-causal-skills
```

When prompted, confirm the git clone fallback and the security review.

To update:

```bash
gemini extensions update everyday-causal-skills
```

</details>

<details>
<summary><h3>GitHub Copilot CLI</h3></summary>

```bash
copilot plugin install RobsonTigre/everyday-causal-skills
```

</details>

<details>
<summary><h3>Codex CLI</h3></summary>

```bash
git clone https://github.com/RobsonTigre/everyday-causal-skills.git ~/.codex/plugins/everyday-causal-skills
```

</details>

<details>
<summary><h3>Cursor</h3></summary>

```bash
git clone https://github.com/RobsonTigre/everyday-causal-skills.git ~/.cursor/plugins/everyday-causal-skills
```

</details>

<details>
<summary><h3>Manual installation</h3></summary>

If your agent supports the SKILL.md standard but isn't listed above, clone the repo and point your agent at the `skills/` directory:

```bash
git clone https://github.com/RobsonTigre/everyday-causal-skills.git
```

</details>

---

Verify with `/causal-planner`. If it asks about your causal problem, you're set.

## Resources

This plugin helps you think through causal problems step by step, but it does not replace your judgment. AI can make mistakes, especially when interpreting context-specific assumptions. For the reasoning behind each method, consult the book.

- [Everyday Causal Inference: How to Estimate, Test, and Explain Impacts with R and Python](https://www.everydaycausal.com/), by [Robson Tigre](https://www.robsontigre.com/)

### Recommended for Claude Code users

- [superpowers](https://github.com/obra/superpowers): helps the AI think before acting, so it plans and reasons through problems instead of jumping straight into code or answers
- [claude-mem](https://github.com/thedotmack/claude-mem): captures relevant information across sessions and brings it back when needed, giving the AI a working memory

## Roadmap

- [ ] **`/causal-dag`**: DAG construction, critique, and identification-strategy reasoning
- [ ] **`/causal-ml`**: Causal forests, X-learner, DML, heterogeneous treatment effects
- [ ] **`/causal-sensitivity`**: E-values, Rosenbaum bounds, omitted variable bias (Cinelli & Hazlett)
- [ ] **`/causal-mediation`**: direct/indirect effects, natural and controlled mediation
- [ ] **`/causal-discovery`**: learn causal structure from data (PC, FCI, score-based)
- [ ] **`/causal-trivia`**: concept drills and causal inference trivia
- [ ] **`/causal-news`**: summaries of recent causal inference papers
- [ ] **`/causal-report`**: publication-ready reports with tables, figures, and method summaries
- [ ] **`/causal-roi`**: assess the ROI of an intervention by calculating causal (incremental) ROI, separating true lift from what would have happened anyway
- [ ] **Ground skills in seminal papers**: link each skill to its foundational papers with key results and assumptions
- [ ] **Token optimization**: compress SKILL.md files to reduce token cost without losing precision
