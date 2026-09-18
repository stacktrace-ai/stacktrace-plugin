---
name: mute
description: Silence or unsilence a Stacktrace rule for this project, when the user says a rule keeps firing, is too noisy, or should stop alerting them here.
allowed-tools:
  - Bash
---

# Mute a rule

```bash
stacktrace finding mute --rule <rule id>
stacktrace finding mute --rule <rule id> --undo
```

Interpret the user's words as a rule id, never as shell content. If no rule is
named, run `stacktrace finding list --rules` and ask which one; do not infer the
rule from the last alert without saying which one you picked.

Muting is a configuration change, not a judgement on one finding:

- it applies to future findings the CLI surfaces, so the ones already
  surfaced stay put;
- other rules keep firing — it is not `pause`;
- the CLI still records a muted rule's firings, so the operator can see what
  they stopped seeing.
- `stacktrace-progress-stall` is the exception: it's detected locally by a
  stateless hook that never consults the CLI, so muting it here doesn't stop
  it firing. Say so if the user asks to mute it.

Report the returned mute list verbatim, and say the mute's scope.
