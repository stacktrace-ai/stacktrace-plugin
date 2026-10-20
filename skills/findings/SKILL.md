---
name: findings
description: Show Stacktrace findings for the current Claude session.
disable-model-invocation: true
---

# Stacktrace findings

Resolve the CLI first. Prefer `~/.local/bin/stacktrace` over an older `PATH`
copy. Keep an active virtual environment's own copy. Run:
```sh
if [ -n "${VIRTUAL_ENV:-}" ] && [ -x "$VIRTUAL_ENV/bin/stacktrace" ]; then echo "$VIRTUAL_ENV/bin/stacktrace"; elif [ -x "$HOME/.local/bin/stacktrace" ]; then echo "$HOME/.local/bin/stacktrace"; else command -v stacktrace; fi
```
Run `<the resolved command> findings --agent-kind claude-code`. The command
reads the native session ID from `CLAUDE_CODE_SESSION_ID`. Present its output
without inventing missing evidence or taking remediation action.
