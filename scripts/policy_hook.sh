#!/bin/sh
# CLI usage errors exit 2, which Claude treats as an explicit block.
# Forward native verdicts only after a successful adapter run.
if [ -x "${HOME:-}/.local/bin/stacktrace" ] && { [ -z "${VIRTUAL_ENV:-}" ] || [ "$(command -v stacktrace 2>/dev/null || true)" != "$VIRTUAL_ENV/bin/stacktrace" ]; }; then
  PATH="$HOME/.local/bin:$PATH"
  export PATH
fi
output=$(stacktrace remote policy hooks run "${0%/*}/claude_adapter.py" 2>/dev/null) || exit 0
if [ -n "$output" ]; then
  printf '%s\n' "$output"
fi
