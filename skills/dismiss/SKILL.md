---
name: dismiss
description: Record that the last Stacktrace finding was not worth surfacing, when the user says an alert was noise, wrong, unhelpful, or something they already knew.
allowed-tools:
  - Bash
---

# Dismiss a finding

```bash
stacktrace finding dismiss --session "$CLAUDE_SESSION_ID"
```

If the user gave a reason matching `not-useful`, `already-knew`, `wrong`, or
`too-noisy`, pass it as `--reason`. Never infer one from the conversation, and do
not ask a follow-up question to obtain it — omit the flag instead. The closed
vocabulary exists so dismissals aggregate into a per-rule signal; free text does
not, and a guessed reason is worse than a missing one.

Dismissing judges one finding. It does not stop the rule. If the user wants the
rule silenced, offer the `mute` skill rather than dismissing repeatedly.

Report what the command returns. It records locally; the CLI decides whether a
dismissal is ever uploaded.
