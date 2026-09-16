#!/usr/bin/env bash

set -euo pipefail

REPO_ROOT="$(git rev-parse --show-toplevel)"
cd "$REPO_ROOT"

HOOKS_DIR="scripts/git-hooks"
HOOK_FILE="$HOOKS_DIR/pre-push"

if [ ! -f "$HOOK_FILE" ]; then
  echo "expected $HOOK_FILE not found" >&2
  exit 1
fi

chmod +x "$HOOK_FILE"
git config core.hooksPath "$HOOKS_DIR"
echo "core.hooksPath set to $HOOKS_DIR for this repository"
