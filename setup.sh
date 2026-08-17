#!/usr/bin/env bash
# One-time (and safe-to-re-run) dev environment setup: installs/verifies uv
# (Python), nvm-managed Node.js pinned via .nvmrc, and pnpm via Corepack —
# then runs `uv sync` and installs the git hooks. macOS/Linux only.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$REPO_ROOT"

# Bump when updating: https://github.com/nvm-sh/nvm/releases
NVM_INSTALL_VERSION="v0.40.6"

echo "==> Python toolchain (uv)"
if ! command -v uv >/dev/null 2>&1; then
  echo "Installing uv..."
  curl -LsSf https://astral.sh/uv/install.sh | sh
  if [ -f "$HOME/.local/bin/env" ]; then
    # shellcheck disable=SC1091
    source "$HOME/.local/bin/env"
  fi
fi
if ! command -v uv >/dev/null 2>&1; then
  echo "error: uv installed but not on PATH; open a new shell and re-run this script" >&2
  exit 1
fi
uv sync

echo "==> Node.js toolchain (nvm + corepack/pnpm)"
export NVM_DIR="${NVM_DIR:-$HOME/.nvm}"
if [ ! -s "$NVM_DIR/nvm.sh" ]; then
  echo "Installing nvm ${NVM_INSTALL_VERSION}..."
  curl -o- "https://raw.githubusercontent.com/nvm-sh/nvm/${NVM_INSTALL_VERSION}/install.sh" | bash
fi
# shellcheck disable=SC1091
. "$NVM_DIR/nvm.sh"

nvm install # reads the version pinned in .nvmrc
nvm use

if ! command -v corepack >/dev/null 2>&1; then
  npm install -g corepack
fi
corepack enable
corepack prepare pnpm@latest --activate

echo "==> One-time: git hooks (lint/format + commit-msg checks)"
uv run pre-commit install --install-hooks

cat <<EOF

Done. Toolchain versions:
  uv:    $(uv --version)
  node:  $(node --version) (pinned via .nvmrc)
  npm:   $(npm --version)
  pnpm:  $(pnpm --version)

Next steps, e.g.:
  uv run scripts/scrape_applicants.py
  uv run scripts/generate_member_maps.py
EOF
