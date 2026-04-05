---
name: causal-exercises
description: Generates practice exercises with simulated data and known ground truth across all causal inference methods. Use when user says "practice", "exercise", "simulate", "learn causal inference", or "test my skills". Not for real data analysis.
metadata:
  author: Robson Tigre
  version: 0.3.2
  compatibility: Requires R (>= 4.0) or Python (>= 3.9). Package dependencies listed in templates.
---

# Causal Exercises

Generate realistic causal inference exercises with simulated data. The true effect is known, so practitioners can verify their work.

## Before You Begin

1. Read `references/lessons.md` — known mistakes. Do not repeat them.
2. Read `references/dgp-library.md` — available data-generating processes.
3. Read `references/method-registry.md` — method details.
- **Explain the why**: When walking through assumptions, recommending methods, or flagging concerns, always explain *why* it matters — not just what to do. Help the user build intuition, not just follow instructions.

## Quality Standards

- Complete every stage. Do not skip assumption checks or robustness tests.
- Quality over speed. A thorough analysis with caveats beats a fast one without.
- When uncertain, say so. Flag limitations rather than presenting weak evidence as strong.
- **Realism over simplicity**: Every scenario must read like a real business problem, not a textbook exercise. Use company names, job titles, and domain-specific language.
- **Always include at least one complication**: Even "Basic" exercises should have one realistic wrinkle (e.g., slightly noisy data, an obvious but important assumption to check). Pure textbook setups teach nothing about real practice.
- **Data first**: Generate and provide the dataset immediately — don't make the student wait. They should be able to start exploring within seconds.
- **Clear deliverable**: Always tell the student exactly what they should produce — "estimate the treatment effect and explain your assumptions" is better than "analyze the data."

## Exercise Flow

### Step 1: Choose Parameters

Ask: "What difficulty level? (Basic / Intermediate / Advanced)"
Ask: "Any particular method to practice, or should I choose?"

Methods available: experiments, DiD, IV, RDD, synthetic control, matching, time series, **DAG reasoning** (variable selection, adjustment sets, bad control detection).
Ask: "R or Python?"

- **Basic**: Clean setup, one method clearly correct, no complications.
- **Intermediate**: Realistic noise, 1-2 complications (staggered rollout, weak instrument, imperfect overlap).
- **Advanced**: Multiple complications, assumption violations baked in that the user must detect and handle.

### Step 2: Generate Scenario

Select a DGP from `references/dgp-library.md` matching the difficulty and method. Present a realistic business narrative. **Do NOT reveal the method, the DGP, or the true effect.**

"**Scenario**: You work as a data analyst at [company]. [Business context narrative]. Your manager wants to know: [causal question]. You have access to the attached dataset."

### Step 3: Create and Save Data

Run the DGP code (using Bash tool) to generate the dataset. Save files:
- `docs/causal-exercises/YYYY-MM-DD-<exercise>/data.csv` — the dataset
- `docs/causal-exercises/YYYY-MM-DD-<exercise>/dgp.[R|py]` — the DGP code (DO NOT show to user yet)
- `docs/causal-exercises/YYYY-MM-DD-<exercise>/solution.md` — true effect and method (DO NOT show yet)

Tell the user: "I've generated the dataset at [path]. Take a look and tell me: What causal method would you use and why?"

### Step 4: Progressive Hints (On Request)

If the user asks for help, provide hints in order:
1. "Think about how the treatment was assigned."
2. "What data structure do you have? Cross-sectional or panel?"
3. "The key identification strategy here involves [hint at mechanism]."
4. "The method I had in mind is [method]."
5. "The key assumption to check is [specific assumption]."

### Step 5: Review and Debrief

After the user presents their analysis (or asks for the answer):
1. Reveal the true DGP and true effect.
2. Compare their estimate to ground truth.
3. Explain what worked and what didn't.
4. If they missed a complication (especially in Advanced): explain what it was and how it affected results.
5. Score: "Your estimate of [X] vs truth of [Y] — [assessment]."

Save debrief to `docs/causal-exercises/YYYY-MM-DD-<exercise>/debrief.md`.

## Common Issues

- **Revealing the DGP too early**: The exercise is ruined if the user sees the true data-generating process before attempting the analysis. Never show DGP code or true effects until the debrief stage.
- **Mismatch between simulated data and method difficulty**: If the exercise is too easy (obvious treatment effect, no violations), it doesn't teach anything. Ensure exercises include realistic complications.

## Integration

**Before this skill**:
- `/causal-planner` -- Optional; user may come directly to practice

**After this skill**:
- `/causal-[method]` -- Apply the practiced method to real data
- `/causal-dag` -- Practice drawing DAGs, identifying adjustment sets, and detecting bad controls

## Self-Correction

If the user identifies a problem with the exercise (e.g., DGP doesn't match the narrative, unrealistic parameters), record the lesson in `references/lessons.md`.
