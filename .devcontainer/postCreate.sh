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
