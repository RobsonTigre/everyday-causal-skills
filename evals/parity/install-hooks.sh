#!/usr/bin/env bash
# Installs a pre-push hook that runs the R<->Python parity gate on changed methods.
set -euo pipefail
ROOT="$(git rev-parse --show-toplevel)"
HOOK="$ROOT/.git/hooks/pre-push"
cat > "$HOOK" <<'EOF'
#!/usr/bin/env bash
# Auto-installed by evals/parity/install-hooks.sh — blocks push on NEW R<->Python disparities.
ROOT="$(git rev-parse --show-toplevel)"

# Pick a Python that has the parity deps (PyYAML) AND the recipe packages (scpi_pkg, etc.).
# system python3 usually has neither, so detect a real environment first.
PY="${EVAL_PYTHON:-}"
[ -z "$PY" ] && [ -x "$ROOT/.venv/bin/python" ]            && PY="$ROOT/.venv/bin/python"
[ -z "$PY" ] && [ -n "${VIRTUAL_ENV:-}" ] && [ -x "$VIRTUAL_ENV/bin/python" ] && PY="$VIRTUAL_ENV/bin/python"
[ -z "$PY" ] && [ -x "$HOME/.venv/bin/python" ]            && PY="$HOME/.venv/bin/python"
[ -z "$PY" ] && PY="python3"

echo "[parity] checking changed methods (python: $PY)..."
EVAL_PYTHON="$PY" "$PY" "$ROOT/evals/parity/run_parity.py" --changed --repo-root "$ROOT" || {
  echo "[parity] BLOCKED: new R<->Python disparity. Fix or add to baseline.yaml before pushing."
  exit 1
}
EOF
chmod +x "$HOOK"
echo "Installed pre-push hook at $HOOK"
