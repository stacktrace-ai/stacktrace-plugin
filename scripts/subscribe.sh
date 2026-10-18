#!/bin/sh
# Claude can start before uv's shell PATH update takes effect.
if [ -x "$HOME/.local/bin/stacktrace" ] && { [ -z "${VIRTUAL_ENV:-}" ] || [ "$(command -v stacktrace 2>/dev/null || true)" != "$VIRTUAL_ENV/bin/stacktrace" ]; }; then
  PATH="$HOME/.local/bin:$PATH"
  export PATH
fi
exec stacktrace daemon subscribe --agent-kind claude-code
