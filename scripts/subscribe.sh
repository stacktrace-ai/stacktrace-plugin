#!/bin/sh
# Claude can start before uv's shell PATH update takes effect.
if ! command -v stacktrace >/dev/null 2>&1 && [ -x "$HOME/.local/bin/stacktrace" ]; then
  PATH="$HOME/.local/bin:$PATH"
  export PATH
fi
exec stacktrace daemon subscribe --agent-kind claude-code
