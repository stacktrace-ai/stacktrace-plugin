---
id: 0009
title: Delegate session registration and remote bootstrap to the CLI
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
Laptop sessions share a daemon whose lifecycle belongs to the installer or host.

## Decision

Add a SessionStart handler that calls the stable CLI adapter:

```text
stacktrace remote policy hooks session-start --adapter-version 1
```

The adapter registers the project on laptops.
On remote workers, it first ensures daemon readiness.
The CLI owns lifecycle locks, enrollment, socket requests, and background work.
The daemon owns evidence collection and policy evaluation.

The plugin contains no lifecycle implementation.
Its existing guidance script remains diagnostic.
The new handler has a five-second timeout and continues on failure.
An older CLI can reject the command without blocking the session.
CLI and plugin versions do not need to match.

The installer checks this handler before it removes an older installer-owned registration.
The installer uses Claude's user-scoped plugin commands.
It does not add hook declarations to user settings.

The cross-repository contract lives in
[Stacktrace ADR-0139](https://github.com/stacktrace-ai/stacktrace/pull/253).

## Consequences

The plugin owns all Stacktrace hooks on both hosts.
The laptop lifecycle stays outside sessions.
Remote start and resume can recover lost daemon processes.
The notification guidance script can still run without a compatible CLI.
Hosted cloud start and worker-resume tests remain rollout gates.
