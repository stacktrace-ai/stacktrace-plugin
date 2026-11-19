#!/bin/sh
# CLI usage errors exit 2, which Claude treats as an explicit block.
# Forward native verdicts only after a successful adapter run.
#
# `--without-transcript` first: forward the event only when the payload names
# no transcript, as in a Cowork VM, where the CLI journals it (stacktrace
# ADR-0260). Anywhere else this exits before the CLI starts.
#
# In a Claude Cowork VM, the CLI and the daemon may not be ready: Cowork runs
# the first prompt's hooks before SessionStart ends, and a VM restart stops the
# daemon. A hook that decides waits for `cowork_setup.sh` first. A journal-only
# hook starts it and does not wait; the journal needs no daemon.
if [ "${CLAUDE_CODE_ENTRYPOINT:-}" = remote_cowork ]; then
  cowork_wait=50
  [ "${1:-}" = --without-transcript ] && cowork_wait=0
  sh "$(dirname -- "$0")/cowork_setup.sh" "$cowork_wait" </dev/null >/dev/null 2>&1 || true
fi
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
