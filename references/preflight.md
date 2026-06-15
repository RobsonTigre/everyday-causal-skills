# Preflight: Missing-Package Handling

Canonical protocol for what to do when a method needs R or Python packages the user
may not have installed. Every method template's **Prerequisites** block follows this,
and every method skill points here at Stage 3 (Implementation).

## The rule

**Detect → report → offer to install → never install without an explicit yes.**

1. **Detect, don't install.** Run the detect-and-report snippet (below). It only checks
   what is missing — it never calls `install.packages()` / `pip install` on its own.
2. **Report.** Tell the user exactly which packages are missing and show the exact
   install command.
3. **Offer.** Ask: *"Want me to install these for you, or will you install them
   yourself?"*
   - **Yes** → run the printed install command, re-run the detect snippet to confirm,
     then proceed.
   - **No** → the user installs manually; wait until the packages are available, then
     proceed.
4. **Never install silently.** Nothing gets installed without an explicit yes — not by
   the template (it can't), and not by the agent (it must ask first).

The detect snippet is *copy-exactly* template code. The offer-and-install step is an
**agent action in the conversation**, not code baked into the template — that keeps the
consent moment with the user and the template non-mutating.

## Required vs optional

- **Required** = packages the template's `library()` / `import` block loads
  unconditionally. The analysis cannot run without them → treat the offer as a hard
  gate: do not proceed until they are installed (by you on consent, or by the user).
- **Optional** = variant- or robustness-only packages (e.g. `did` / `diff-diff` only for
  staggered DiD, `CausalArima`, `tidysynth` when chosen over `Synth`, `dowhy` / `econml`
  for robustness). If missing, note it and proceed without — only offer to install when
  the user actually wants that variant.

## Detect-and-report snippet — R

```r
# --- Preflight: detect missing packages (does NOT install) ---
# Replace the vector with the packages this method's load block needs.
required <- c("fixest", "did", "modelsummary", "tidyverse")
missing  <- required[!vapply(required, requireNamespace, logical(1), quietly = TRUE)]
if (length(missing) > 0) {
  cat("Missing R packages:", paste(missing, collapse = ", "), "\n")
  cat('Install with: install.packages(c(',
      paste0('"', missing, '"', collapse = ", "), "))\n", sep = "")
} else {
  cat("All required R packages are installed.\n")
}
```

For R, package name == install name, so no mapping table is needed.

## Detect-and-report snippet — Python

```python
# --- Preflight: detect missing packages (does NOT install) ---
import importlib.util

# import-name -> pip-name. They match for most packages; a few differ (see below).
required = {
    "pandas": "pandas",
    "numpy": "numpy",
    "matplotlib": "matplotlib",
    "linearmodels": "linearmodels",
    "statsmodels": "statsmodels",
    "diff_diff": "diff-diff",    # import name != pip name
}
missing = [pip for mod, pip in required.items()
           if importlib.util.find_spec(mod) is None]
if missing:
    print("Missing Python packages:", ", ".join(missing))
    print("Install with: pip install " + " ".join(missing))
else:
    print("All required Python packages are installed.")
```

### Import-name ≠ pip-name (Python)

Detection imports by module name; installation uses the pip name. Where they differ:

| import name   | pip name        |
|---------------|-----------------|
| `diff_diff`   | `diff-diff`     |
| `sklearn`     | `scikit-learn`  |
| `scpi_pkg`    | `scpi-pkg`      |

(Most packages — `pandas`, `numpy`, `statsmodels`, `linearmodels`, `dowhy`, `econml`,
`matplotlib`, `seaborn` — use the same name for both.)

## Running the install on consent

Only after the user says yes:

- **R:** `Rscript -e 'install.packages(c("pkg1","pkg2"), repos="https://cloud.r-project.org")'`
  (or run the `install.packages(...)` line inside their R session).
- **Python:** `pip install pkg1 pkg2` (use the *pip* names from the mapping above).

Then re-run the detect snippet to confirm the packages now resolve before proceeding.
