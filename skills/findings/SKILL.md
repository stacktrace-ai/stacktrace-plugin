---
name: findings
description: Show Stacktrace findings for the current Claude session.
disable-model-invocation: true
---

# Stacktrace findings

Run `stacktrace findings --agent-kind claude-code`. The command reads the native
session ID from `CLAUDE_CODE_SESSION_ID`. Present its output without inventing
missing evidence or taking remediation action.

A Session cost finding (`stacktrace-cost-runaway-session`) lists up to three
`Reason:` entries, largest share of the extra first. Present each one as the
command prints it: its name and share, what it says, and its `Fix:` line, with
the exact command or setting shown there. Never run the fix yourself. The user
decides whether to take it.
