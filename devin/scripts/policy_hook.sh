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
# DIAGNOSTIC BRANCH, NEVER MERGE. On the suite's Devin block runner only, record
# each hook's input, answer, exit code and time, and for an unanswered
# PreToolUse the daemon's own reason, in the job's uploaded log folder.
trace_dir=/home/runner/work/stacktrace-fleet/stacktrace-fleet/suite-runs/logs-block-devin
if [ -d "$trace_dir" ]; then
  input=$(cat)
  started=$(date +%s.%N)
  output=$(printf '%s' "$input" | stacktrace remote policy hooks "$@" 2>"$trace_dir/.stderr.$$")
  code=$?
  ended=$(date +%s.%N)
  {
    printf '=== %s args=[%s] exit=%s seconds=%s\n' "$(date -u +%FT%T.%NZ)" "$*" "$code" \
      "$(awk "BEGIN{print $ended - $started}")"
    printf 'env DEVIN_PROJECT_DIR=%s PWD=%s HOME=%s XDG_CONFIG_HOME=%s\n' \
      "${DEVIN_PROJECT_DIR:-}" "$PWD" "${HOME:-}" "${XDG_CONFIG_HOME:-}"
    printf 'cli %s -> %s\n' "$(command -v stacktrace)" "$(readlink -f "$(command -v stacktrace)")"
    printf 'stdin %s\n' "$(printf '%s' "$input" | head -c 6000)"
    printf 'stdout %s\n' "$output"
    printf 'stderr %s\n' "$(head -c 2000 "$trace_dir/.stderr.$$")"
    case "$input" in
      *'"PreToolUse"'*)
        if [ -z "$output" ]; then
          python=$(dirname "$(readlink -f "$(command -v stacktrace)")")/python
          printf 'probe %s\n' "$(printf '%s' "$input" | "$python" -I "$(dirname "$0")/trace_probe.py" 2>&1 | head -c 3000)"
        fi
        ;;
    esac
  } >>"$trace_dir/hook-trace.log" 2>&1
  rm -f "$trace_dir/.stderr.$$"
  [ "$code" = 0 ] || exit 0
  if [ -n "$output" ]; then
    printf '%s\n' "$output"
  fi
  exit 0
fi
output=$(stacktrace remote policy hooks "$@" 2>/dev/null) || exit 0
if [ -n "$output" ]; then
  printf '%s\n' "$output"
fi
