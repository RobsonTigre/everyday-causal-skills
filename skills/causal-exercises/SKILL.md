---
name: causal-exercises
description: Generates practice exercises with simulated data and known ground truth across all causal inference methods. Use when user says "practice", "exercise", "simulate", "learn causal inference", or "test my skills". Not for real data analysis.
metadata:
  author: Robson Tigre
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
- **Canonical runnable block**: When showing a DGP or solution program, put the
  exact line `# EVAL_EXECUTABLE` as the first nonblank program line inside
  exactly one correct-language code fence. Do not indent it or add other text
  on that line. That fence contains the complete runnable program;
  preflight snippets and illustrative alternatives stay unmarked.

## Exercise Flow

### Step 1: Choose Parameters

Ask: "What difficulty level? (Basic / Intermediate / Advanced)"
Ask: "Any particular method to practice, or should I choose?"

Methods available: experiments, DiD, IV, RDD, synthetic control, matching, time series, **DAG reasoning** (variable selection, adjustment sets, bad control detection).
Ask: "R or Python?"

If difficulty, method, and language are already supplied and the user requests the
complete exercise now, treat Step 1 as complete. Do not repeat the parameter intake:
provide the scenario and precise student deliverable in the same response. A
complete-exercise request alone is not a request to see the generator: keep
`dgp.[R|py]`, the solution, and the true effect hidden until the debrief. Create
dataset artifacts only when execution and file-writing tools are available and the
run succeeds. Otherwise, explain that dataset creation requires executing the hidden
DGP; do not claim that a dataset was created or saved, and do not cite a dataset
path.
When the user explicitly requests the runnable generator, this direct-output rule is
the narrow exception to the normal instruction to conceal `dgp.[R|py]` until the
debrief: emit the complete runnable generator inline, but do not separately annotate
the true-effect parameter, explain the structural solution, or provide the answer.
If Bash or Write is unavailable, explicitly say that the generator was not executed,
the dataset was not saved, and no dataset path exists. Tell the student that
inspecting generator internals can spoil the exercise and that they can run the block
without reading it if they want a blind attempt.

**Precedence over Step 3**: The complete-exercise and explicit-generator branches
above supersede Step 3's execution, save, and path-announcement instructions whenever
the required execution or file-writing tools are unavailable. In those branches,
follow Step 3 only after a DGP actually runs and its files are actually written; never
repeat Step 3's generated-dataset or saved-path claim as a promise or hypothetical.

- **Basic**: Clean setup, one method clearly correct, no complications.
- **Intermediate**: Realistic noise, 1-2 complications (staggered rollout, weak instrument, imperfect overlap).
- **Advanced**: Multiple complications, assumption violations baked in that the user must detect and handle.

**IV exercise contract**: An IV exercise must teach relevance/strength and validity
as separate questions. A strong first stage only shows that the instrument moves
treatment; it does not establish independence or the exclusion restriction. Design
the scenario and DGP so the student must reason about both:

- vary instrument strength across a labeled scenario, parameter, or comparison and
  require a first-stage coefficient, robust F statistic, and weak-instrument
  diagnosis;
- include a scenario-specific validity challenge, such as a plausible direct path
  from the encouragement to the outcome, and ask the student to defend independence,
  exclusion, and monotonicity rather than declaring the instrument valid from its F
  statistic;
- define the compliers in the scenario and teach **LATE** as the average treatment
  effect for those compliers. For example, an encouragement design identifies the
  effect among people who take treatment when encouraged but not otherwise, not the
  ATE for everyone; and
- make the requested deliverable trace a path from data to first-stage diagnostics,
  reduced form and 2SLS, assumption assessment, and a scenario-specific LATE
  interpretation.

Keep the challenge discoverable from the narrative and observed variables. Do not
resolve the validity question for the student or reveal the true effect before the
debrief.

### Step 2: Generate Scenario

Select a DGP from `references/dgp-library.md` matching the difficulty and method. Present a realistic business narrative. **Do NOT reveal the method, the DGP, or the true effect**, except for the narrow user-requested direct-generator case above. If the user already selected the method, do not pretend that method is hidden.

"**Scenario**: You work as a data analyst at [company]. [Business context narrative]. Your manager wants to know: [causal question]. You have access to the attached dataset."

### Step 3: Create and Save Data

Run the DGP code (using Bash tool) to generate the dataset. If it needs a package the user may not have, follow `references/preflight.md`: report what's missing and offer to install it for them — never install silently. Save files:
- `docs/causal-exercises/YYYY-MM-DD-<exercise>/data.csv` — the dataset
- `docs/causal-exercises/YYYY-MM-DD-<exercise>/dgp.[R|py]` — the DGP code (do not show until debrief unless the direct-generator exception applies)
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

1. **Reveal** the true DGP and true effect.
2. **Compare**: "Your estimate of [X] vs the true effect of [Y]."
3. **Explain the gap** — connect the error to a specific cause:
   - If method was correct but estimate is off: "The gap of [Z] is [sampling variability / a finite-sample artifact]. With more data, this would shrink. Your approach was sound."
   - If method was correct but assumption was violated: "Your estimate missed because [assumption] was violated in this data. Here's how: [specific mechanism from the DGP]. The diagnostic that would have caught it is [test/plot] — it would have shown [what to look for]."
   - If method was wrong: "This scenario called for [correct method] because [reason]. The method you chose assumes [assumption], which doesn't hold here because [explanation from DGP]."
4. **Connect to practice**: "In real data, you wouldn't know the true effect. The way to protect yourself is [specific diagnostic or robustness check that would have flagged the issue]."
5. **Score**: "Your estimate of [X] vs truth of [Y] — [assessment]."

Save debrief to `docs/causal-exercises/YYYY-MM-DD-<exercise>/debrief.md`.

## Common Issues

- **Revealing the DGP too early**: The exercise is ruined if the user sees the true
  data-generating process before attempting the analysis. Never show DGP code or
  true effects until the debrief stage unless the user explicitly requested the
  runnable generator under the narrow direct-output exception; even then, withhold
  the separate solution and true-effect annotation.
- **Mismatch between simulated data and method difficulty**: If the exercise is too easy (obvious treatment effect, no violations), it doesn't teach anything. Ensure exercises include realistic complications.
- **Conflating a strong instrument with a valid one**: A large first-stage F
  statistic supports relevance, not independence or exclusion. Grade these as
  separate parts of an IV exercise.

## Integration

**Before this skill**:
- `/causal-planner` -- Optional; user may come directly to practice

**After this skill**:
- `/causal-[method]` -- Apply the practiced method to real data
- `/causal-dag` -- Practice drawing DAGs, identifying adjustment sets, and detecting bad controls

## Self-Correction

If the user identifies a problem with the exercise (e.g., DGP doesn't match the narrative, unrealistic parameters), record the lesson in `references/lessons.md`.
