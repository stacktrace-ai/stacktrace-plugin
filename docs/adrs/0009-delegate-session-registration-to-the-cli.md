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

Use one SessionStart shell entrypoint that calls the generic CLI runner:

```text
stacktrace remote policy hooks run "${CLAUDE_PLUGIN_ROOT}/scripts/claude_adapter.py"
```

The plugin adapter translates native events into bounded registration or admission requests.
It owns selector extraction, fixed launch context, remote-host detection, and native denial rendering.
The CLI validates normalized requests before socket calls or daemon recovery.
The shared recovery worker ensures daemon readiness before registration on both hosts.
The CLI launches detached work and reuses a healthy daemon.
Only remote recovery checks for CLI updates.
The CLI owns lifecycle locks, enrollment, socket requests, and background work.
The daemon owns evidence collection and policy evaluation.

The adapter declares `API_VERSION = 1`, `request(payload, environment)`, and `deny(payload, decision)`.
The CLI runs the trusted adapter with its own Python runtime in one process.
The adapter imports only the standard library.
No separate Python installation or SDK release is required.
The CLI passes only confirmed daemon denials to the native renderer.
Allow and defer emit no native permission grant.
The runner discards adapter diagnostics and partial output on failures.
The plugin contains no lifecycle implementation.
The shell entrypoint discards CLI output and errors before it emits notification guidance.
It has a fifteen-second timeout and continues on failure.
It gives the detached worker five seconds before it reports an unavailable daemon.
The subscription and hook scripts prefer the default per-user CLI over an older system copy.
An active development virtualenv keeps its CLI selection.
An older CLI can reject the command without blocking the session.
CLI and plugin versions do not need to match.
Both packages must support runner contract version 1.
The old native admission commands retire during this transition.
Upgrade both packages before checking enforcement readiness.

The installer checks native plugin installation and enablement before it removes an older installer-owned registration.
Plugin validation and native conformance tests check hook declarations and failure behavior.
The shared installer directly runs Claude's user-scoped marketplace and plugin commands.
The CLI exposes no plugin installation command.
Plugin setup requires neither enrollment nor a running daemon.
The daemon serves hook policy automatically after enrollment.
It does not add hook declarations to user settings.

The cross-repository contract lives in
[Stacktrace ADR-0143](https://github.com/stacktrace-ai/stacktrace/pull/253).

## Alternatives considered

Keep native parsing in the CLI.
This requires CLI changes for each native event format and duplicates plugin integration ownership.
Keep native parsing in the plugin and share transport and lifecycle through the runner instead.

Invoke a separate Python interpreter from the plugin.
This adds a runtime prerequisite and another process on each covered action.
Use the CLI runtime for both translation and transport instead.

## Consequences

The plugin owns all Stacktrace hooks on both hosts.
Laptop and remote start or resume can recover lost daemon processes.
The plugin contains no daemon launcher or restart loop.
The CLI retains lifecycle ownership.
The notification guidance script can still run without a compatible CLI.
Hosted cloud start and worker-resume tests remain rollout gates.
