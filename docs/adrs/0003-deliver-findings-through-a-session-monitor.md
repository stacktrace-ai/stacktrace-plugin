---
id: 0003
title: Deliver findings through a session monitor, not lifecycle hooks
status: accepted
date: 2026-09-18
supersedes: [0001, 0002]
superseded-by: null
---

## Context

ADR-0001 and ADR-0002 were decided against a host surface that offered hooks
and nothing else. Both are shaped by the same constraint: a hook fires, prints,
and dies. ADR-0001 detached a worker because an async hook is killed at
teardown. ADR-0002 made one hook synchronous because an async hook's stdout is
never read, so `PostToolUseFailure` was the only place a finding could still
reach a person while it mattered.

Claude Code now exposes background monitors. A monitor is a long-lived process
for the life of the session with a stdout channel the host reads, which removes
the constraint both earlier decisions were built around. In parallel, detection
moved into a per-user Stacktrace daemon, which is where session state, policy,
and routing already live.

Two mechanisms for one job is worse than either. The hook-side detector had to
re-derive a stall from the transcript on every firing, because it was forbidden
to keep state; the daemon has that state already.

## Decision

Findings reach the session through one session-lifetime monitor,
`stacktrace daemon subscribe --agent-kind claude-code`, declared in
`monitors/monitors.json`. `SessionStart` contributes notification guidance only
— it teaches the model the `STACKTRACE_NOTIFY_V1` contract and emits no
finding of its own.

The `Stop` and `SessionEnd` launcher and the `PostToolUseFailure` stall
detector are removed, with their scripts and tests. `scripts/validate_plugin.py`
fails on any hook event other than `SessionStart`.

The architecture is specified in [`spec.md`](../../spec.md).

## Consequences

Detection no longer depends on a turn ending, so the class of finding ADR-0002
existed to catch — a loop inside one long turn — is still caught, by the daemon
reading the session log rather than by a hook re-reading the transcript.

The plugin no longer reads the transcript in process at all, which retires the
whole question of what a hook may hold in memory. It forwards no transcript
content and holds no notification state.

Background monitors are an experimental Claude Code component and run only in
interactive CLI sessions where the Monitor tool is available. Where they are
unavailable there is no fallback delivery path; the CLI-backed triage skills
(`detect`, `why`, `dismiss`, `mute`) remain reachable, and `/stacktrace:status`
reports the monitor as unavailable rather than implying it is live.

The daemon is a hard dependency of the delivery path, where the hook detector
required no CLI at all. That dependency is reported, not assumed: see the
runtime-dependency table in the README.
