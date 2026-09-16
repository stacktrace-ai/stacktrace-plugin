---
name: detect
description: Run local Stacktrace runtime detection when the user asks to inspect Claude Code activity, agent behavior, credential egress, prompt injection, vulnerable component use, stalls, or hung calls.
argument-hint: "[optional time window]"
allowed-tools:
  - Bash
---

# Detect Runtime Findings

Run Stacktrace locally for the narrowest time window that answers the request:

```bash
stacktrace detect --agent-kind claude-code --since 7d --detail
```

Adjust `--since` when the user gives a time window. Do not enable `--reasoning`
unless the user explicitly requests model-assisted escalation and understands
that flagged session content is sent to the model provider used by the agent.

Summarize findings by severity and rule, identify the session and affected
component when Stacktrace placed one, and distinguish an absence of findings
from proof that the session was safe.

This command is local. Do not configure or enable Cloud sync as a side effect.
