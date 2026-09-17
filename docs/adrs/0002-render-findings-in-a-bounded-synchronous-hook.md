---
id: 0002
title: Detect and surface a stall from the transcript
status: accepted
date: 2026-09-17
supersedes: null
superseded-by: null
---

## Context

ADR-0001 made both lifecycle hooks asynchronous so a sync outliving the turn is
never cancelled. An asynchronous hook is fire-and-forget: Claude Code does not
read its stdout, so nothing it prints can reach anybody.

A finding nobody sees is not a notification. Two further constraints decide the
shape of the fix.

**`Stop` is too late for the findings worth interrupting.** It fires when a turn
ends. An agent looping on one failing call inside a single long turn produces no
`Stop` until the loop is already over, which is exactly when knowing costs
nothing. `PostToolUseFailure` fires on each failure instead.

**The plugin cannot assume the CLI.** Requiring a `stacktrace` release for the
plugin to say anything makes the notification surface undeployable until that
release lands, on every machine, in step.

## Decision

`PostToolUseFailure` runs `scripts/detect_and_notify.py` synchronously, capped at
five seconds. It reads the tail of `transcript_path`, which Claude Code already
supplies, joins `tool_use` blocks to their `tool_result` blocks, and measures the
trailing run of one identical failure signature. At exactly three it emits a
finding. `Stop` and `SessionEnd` are unchanged and still detach the sync worker.

The detector is **stateless**. A streak is re-derived from the transcript on each
firing rather than remembered, and suppression falls out of firing on the
threshold exactly: the fourth identical failure is the same finding, so it
produces nothing. No state file, no cursor, no delivery marks.

Output has two audiences:

- `systemMessage` renders the finding for the person at the terminal.
- `additionalContext` tells Claude a finding exists and to call
  `PushNotification` if the operator may be away. That tool suppresses itself
  when the terminal is active, so the judgement it needs is one it already makes.
  The notice bounds Claude explicitly: report, do not investigate, do not repeat.

## Alternatives considered

- **Keep everything asynchronous.** Rejected: an async hook's output is never
  read, so the plugin could detect and still tell nobody.
- **Query the CLI for a pending finding.** Rejected after first building it: it
  made every notification wait on an unreleased `stacktrace notify next`.
- **Detect at `Stop`.** Rejected: see above, the loop has already ended.
- **Track streaks in a plugin-owned state file.** Rejected: the transcript is
  already an append-only record of exactly these events, and a second copy can
  disagree with it.
- **`PreToolUse` to block the next call.** Deferred. Halting an agent needs its
  own argument, and nothing here halts anything.

## Consequences

The plugin now contains one detection rule, which ADR-0001 deliberately kept out
of it. That boundary is narrowed rather than abandoned: the rule is
deterministic, reads only the local transcript, writes nothing, uploads nothing,
and does not duplicate the CLI's consent, cursor, lock or retry model. A richer
catalogue still belongs in `stacktrace-cli`.

Reading the transcript means the plugin touches tool content. It is read in
process, reduced to a signature, and never persisted or forwarded — the
forwarding boundary from ADR-0001 is unchanged.

`PostToolUseFailure` appears in this Claude Code build's hook schema but not in
its published event list. If it is renamed or withdrawn, the hook stops firing
and the plugin goes quiet rather than breaking; the contract test pins the name
so the failure is visible in CI.
