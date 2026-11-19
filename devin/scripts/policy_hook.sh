#!/bin/sh
# CLI usage errors exit 2, which Claude treats as an explicit block.
# Forward native verdicts only after a successful adapter run.
#
# `--without-transcript` first: forward the event only when the payload names
# no transcript, as in a Cowork VM, where the CLI journals it (stacktrace
# ADR-0260). Anywhere else this exits before the CLI starts.
input=''
if [ "${1:-}" = --without-transcript ]; then
  shift
  input=$(cat) || exit 0
  case $input in
    *'"transcript_path":""'*|*'"transcript_path": ""'*) ;;
    *) exit 0 ;;
  esac
fi
if [ -n "${VIRTUAL_ENV:-}" ] && [ -x "$VIRTUAL_ENV/bin/stacktrace" ]; then
  PATH="$VIRTUAL_ENV/bin:$PATH"
  export PATH
elif [ -x "${HOME:-}/.local/bin/stacktrace" ]; then
  PATH="$HOME/.local/bin:$PATH"
  export PATH
fi
if [ -n "$input" ]; then
  output=$(printf '%s\n' "$input" | stacktrace remote policy hooks "$@" 2>/dev/null) || exit 0
else
  output=$(stacktrace remote policy hooks "$@" 2>/dev/null) || exit 0
fi
if [ -n "$output" ]; then
  printf '%s\n' "$output"
fi
