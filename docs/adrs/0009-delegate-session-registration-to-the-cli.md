---
id: 0009
title: Delegate session registration and shared recovery to the CLI
status: proposed
date: 2026-10-18
supersedes: null
superseded-by: null
amends: 0008
amended-by: null
---

## Context

The installer currently owns a separate remote SessionStart hook.
The plugin already owns policy admission hooks and notification guidance.
Users need one named owner for these hooks.

Remote worker migration preserves installed files and configuration but removes processes.
The resume hook must restore the daemon before project registration.
Laptop sessions also need recovery after a reboot or process loss.
The existing CLI locks let concurrent sessions restore one shared daemon.

## Decision

Use one SessionStart shell entrypoint that calls the stable CLI adapter:

```text
stacktrace remote policy hooks session-start
```

The adapter ensures daemon readiness before project registration on both hosts.
It launches detached work and reuses a healthy daemon.
Only remote recovery checks for CLI updates.
The CLI owns lifecycle locks, enrollment, socket requests, and background work.
The daemon owns evidence collection and policy evaluation.

The plugin contains no lifecycle implementation.
The shell entrypoint discards CLI output and errors before it emits notification guidance.
It has a fifteen-second timeout and continues on failure.
It gives the detached worker five seconds before it reports an unavailable daemon.
The subscription and hook scripts prefer the default per-user CLI over an older system copy.
An active development virtualenv keeps its CLI selection.
An older CLI can reject the command without blocking the session.
CLI and plugin versions do not need to match.

The installer checks native plugin installation and enablement before it removes an older installer-owned registration.
Plugin validation and native conformance tests check hook declarations and failure behavior.
The shared installer directly runs Claude's user-scoped marketplace and plugin commands.
The CLI exposes no plugin installation command.
Plugin setup requires neither enrollment nor a running daemon.
The daemon serves hook policy automatically after enrollment.
It does not add hook declarations to user settings.

The cross-repository contract lives in
[Stacktrace ADR-0143](https://github.com/stacktrace-ai/stacktrace/pull/253).

## Consequences

The plugin owns all Stacktrace hooks on both hosts.
Laptop and remote start or resume can recover lost daemon processes.
The plugin contains no daemon launcher or restart loop.
The CLI retains lifecycle ownership.
The notification guidance script can still run without a compatible CLI.
Hosted cloud start and worker-resume tests remain rollout gates.
