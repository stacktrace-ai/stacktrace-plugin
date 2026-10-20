#!/bin/sh
# CLI usage errors exit 2, which Claude treats as an explicit block.
# Forward native verdicts only after a successful adapter run.
if [ -n "${VIRTUAL_ENV:-}" ] && [ -x "$VIRTUAL_ENV/bin/stacktrace" ]; then
  PATH="$VIRTUAL_ENV/bin:$PATH"
  export PATH
elif [ -x "${HOME:-}/.local/bin/stacktrace" ]; then
  PATH="$HOME/.local/bin:$PATH"
  export PATH
fi
output=$(stacktrace remote policy hooks "$@" 2>/dev/null) || exit 0
if [ -n "$output" ]; then
  printf '%s\n' "$output"
fi
