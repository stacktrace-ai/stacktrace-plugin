#!/bin/sh
# CLI usage errors exit 2, which Claude treats as an explicit block.
# Forward native verdicts only after a successful adapter run.
output=$(stacktrace remote policy hooks "$@" 2>/dev/null) || exit 0
if [ -n "$output" ]; then
  printf '%s\n' "$output"
fi
