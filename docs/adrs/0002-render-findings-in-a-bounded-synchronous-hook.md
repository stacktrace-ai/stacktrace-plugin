---
id: 0002
title: Render findings in a bounded synchronous hook
status: accepted
date: 2026-09-17
supersedes: null
superseded-by: null
---

## Context

ADR-0001 made both lifecycle hooks asynchronous so a sync outliving the turn is
never cancelled. An asynchronous hook is fire-and-forget: Claude Code does not
read its stdout, so nothing it prints can reach the operator.

A finding nobody sees is not a notification. Stacktrace detects that an agent
repeated a failure or reported work it did not do, and the operator learns about
it on a dashboard they are not looking at. The host integration is the only
place able to put that in front of them at the moment it matters.

Claude Code renders a hook's `systemMessage` only for a synchronous hook, and
prefixes it with the hook's event name, so the surface is fixed: a `Stop` hook
that returns quickly.

## Decision

`Stop` carries two handlers. The existing asynchronous launcher is unchanged and
still detaches the sync worker. A second, synchronous handler runs
`scripts/render_finding.py`, which:

1. accepts only a `Stop` document and reads only `session_id`;
2. runs `stacktrace notify next --session <id> --format json`;
3. renders the returned finding to `systemMessage` and exits;
4. prints nothing when the CLI is absent, fails, times out, answers with no
   finding, or answers with a malformed one.

The query is capped at two seconds. It performs no detection, no upload and no
network call: the CLI answers it from state the detached worker already wrote.

**The plugin owns nothing.** It does not queue findings, mark them delivered,
track which have been shown, count firings, or hold suppression state. Every one
of those answers arrives inside the CLI's JSON — including `fired_here` and
`show_actions`, which decide the repeat count and whether the action row appears.
The renderer is a formatter with no memory.

## Alternatives considered

- **Keep `Stop` asynchronous and notify out of band.** Rejected: a desktop or
  Slack notification cannot show the operator the evidence in the place they are
  already working, which is the entire value of a host integration.
- **Let the plugin read the CLI's state directory.** Rejected: it would give the
  plugin a second opinion about what is pending, and a path it must keep in step
  with the CLI's own layout. ADR-0001 kept that ownership in one place.
- **Render at `SessionEnd`.** Rejected: the operator has stopped working, and a
  stalled agent is worth interrupting while the session is still open.
- **Render from `PreToolUse` mid-turn.** Deferred, not rejected. It is the only
  way to reach the operator before a turn completes, and it needs its own
  argument about interrupting work in progress.

## Consequences

`Stop` now blocks on a local CLI query bounded at two seconds. That is a
different class of blocking from the sync ADR-0001 detached: it makes no network
call and cannot outlive the turn. An install without `stacktrace` on `PATH` pays
one failed `shutil.which` and prints nothing.

Claude Code prefixes the rendered block with `Stop says:`. The prefix is the
event name and cannot be configured, so the format opens with a blank line and
lets the prefix occupy its own row rather than crowding the headline.

The CLI must provide `stacktrace notify next`, and the three finding commands the
action row advertises. Until that release lands, the hook is inert by design: no
subcommand, non-zero exit, nothing rendered.
