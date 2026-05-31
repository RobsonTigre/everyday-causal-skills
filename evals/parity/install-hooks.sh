#!/usr/bin/env bash
# Installs a pre-push hook that runs the R<->Python parity gate on changed methods.
set -euo pipefail
ROOT="$(git rev-parse --show-toplevel)"
HOOK="$ROOT/.git/hooks/pre-push"
cat > "$HOOK" <<'EOF'
#!/usr/bin/env bash
# Auto-installed by evals/parity/install-hooks.sh — blocks push on NEW R<->Python disparities.
ROOT="$(git rev-parse --show-toplevel)"
echo "[parity] checking changed methods..."
python3 "$ROOT/evals/parity/run_parity.py" --changed --repo-root "$ROOT" || {
  echo "[parity] BLOCKED: new R<->Python disparity. Fix or add to baseline.yaml before pushing."
  exit 1
}
EOF
chmod +x "$HOOK"
echo "Installed pre-push hook at $HOOK"
