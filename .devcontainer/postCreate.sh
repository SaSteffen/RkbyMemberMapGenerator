#!/usr/bin/env bash
# Runs once after the dev container is created: installs uv, Python deps,
# git hooks, and pnpm (via Corepack; Node itself comes from the devcontainer
# Feature in devcontainer.json).
set -euo pipefail

WORKSPACE_DIR="${1:-$PWD}"
cd "$WORKSPACE_DIR"

curl -LsSf https://astral.sh/uv/install.sh | sh
export PATH="$HOME/.local/bin:$PATH"

uv sync
uv run pre-commit install --install-hooks

corepack enable
corepack prepare pnpm@latest --activate

# Load .env into every interactive terminal. `docker exec` sessions (which is
# how VS Code opens integrated terminals) don't reliably inherit env vars set
# via `docker run --env-file`, so source the file directly on shell startup
# instead.
BASHRC="$HOME/.bashrc"
if ! grep -q '# rkby: load .env' "$BASHRC" 2>/dev/null; then
  cat >>"$BASHRC" <<EOF

# rkby: load .env
if [ -f "$WORKSPACE_DIR/.env" ]; then
  set -a
  source "$WORKSPACE_DIR/.env"
  set +a
fi
EOF
fi
unset NODE_OPTIONS