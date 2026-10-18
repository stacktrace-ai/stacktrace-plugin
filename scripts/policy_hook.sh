#!/bin/sh
# CLI usage errors exit 2, which Claude treats as an explicit block.
# Forward native verdicts only after a successful adapter run.
if ! command -v stacktrace >/dev/null 2>&1 && [ -x "${HOME:-}/.local/bin/stacktrace" ]; then
  PATH="$HOME/.local/bin:$PATH"
  export PATH
fi
output=$(stacktrace remote policy hooks "$@" 2>/dev/null) || exit 0
if [ -n "$output" ]; then
  printf '%s\n' "$output"
fi
