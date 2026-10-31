#!/bin/sh
# Claude can start before uv's shell PATH update takes effect.
if [ -n "${VIRTUAL_ENV:-}" ] && [ -x "$VIRTUAL_ENV/bin/stacktrace" ]; then
  PATH="$VIRTUAL_ENV/bin:$PATH"
  export PATH
elif [ -x "$HOME/.local/bin/stacktrace" ]; then
  PATH="$HOME/.local/bin:$PATH"
  export PATH
fi
exec stacktrace daemon subscribe --agent-kind claude-code
