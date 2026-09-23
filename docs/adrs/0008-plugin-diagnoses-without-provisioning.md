---
id: 0008
title: Keep the plugin diagnostic and leave provisioning to the host
status: proposed
date: 2026-09-23
supersedes: null
superseded-by: null
amends: 0007
amended-by: null
---

Subsystem: the agent plugin. Amends ADR-0007 by removing the configure skill,
closing its missing-CLI issue with startup diagnostics and making the welcome
screen report telemetry state instead of assuming it.

## Context

Stacktrace ADR-0048 moves daemon lifecycle out of agent adapters. The host or a
person starts the daemon; a monitor only subscribes. The plugin still crosses
the same ownership boundary through `/stacktrace:configure`, which installs the
CLI with `uv tool install`. Sandbox setup already owns that installation, and a
laptop user can install the CLI directly.

Once installation is removed, configure has no distinct job. Its remaining
checks duplicate `/stacktrace:status`. Keeping both commands would make two
places explain the same broken states while neither should repair them.

Removing provisioning must not make failure silent. ADR-0007 already records
that a missing CLI prevents the startup hook from showing anything. The fixed
`USAGE METRICS  (on)` welcome label has a related problem: telemetry is CLI
configuration, so the plugin can display the wrong state even when everything
else works.

## Decision

The plugin reads and explains machine state; it does not install software,
start services or change configuration. Provisioning belongs to a person or to
the environment's setup mechanism.

1. **Remove `skills/configure/`.** `/stacktrace:status` becomes the single
   diagnostic skill. It checks, in order: `stacktrace` is on `PATH`, the daemon
   is reachable, daemon and CLI versions agree, the current session's monitor
   is connected, and `PushNotification` is available to this session — the
   last check runs even when the monitor connected, since a host can support
   monitors without supporting push. It stops at the first failure. A
   disconnected monitor is diagnosed against the host Claude Code version,
   reporting whether it supports the monitor declaration and
   `CLAUDE_CODE_SESSION_ID`, instead of being read as a silent failure.
   Missing prerequisites name the next command: `uv tool install
   stacktrace-cli`, `stacktrace daemon start`, or `/reload-plugins`; an
   unsupported host or missing `PushNotification` names the Claude Code
   upgrade instead. A version mismatch says the automatic restart has not
   completed and asks the user to check again. The skill does not offer to
   run a mutating command.
2. **Report a broken prerequisite at every affected session start.** The hook
   emits one short `systemMessage` when the CLI is absent or the daemon socket
   is absent, including the relevant command. The socket test stays in shell so
   a healthy session does not start Python merely to prove health. These
   messages diagnose; they do not fix.
3. **Render the telemetry state that the CLI owns.** Only when the one-time
   welcome is going to be shown, the hook asks `stacktrace telemetry` for the
   current setting and prints `USAGE METRICS  (on)` or `(off)`. The enabled
   screen is ADR-0007's text unchanged, keeping `Turn it off: stacktrace
   telemetry off` so normal use begins with the off switch visible, as
   ADR-0039 requires. The disabled screen drops the `Sent as it happens...`
   paragraph and the `Turn it off` line, since nothing is being sent to
   disclose or turn off; `What is sent: stacktrace telemetry show` stays,
   since that command still answers truthfully when metrics are off. No
   telemetry command runs on later healthy starts.
4. **Gate the remote welcome on live telemetry state, not the marker.** When
   `CLAUDE_CODE_REMOTE=true`, the environment recreates plugin data often enough
   that the install-scoped marker cannot be trusted, so the hook does not rely
   on it there. It still asks `stacktrace telemetry` for the current setting on
   every remote session start: when usage metrics are on, it shows the same
   welcome screen so the off switch stays visible before normal use, as
   ADR-0039 requires; when they are off, there is nothing to disclose and the
   hook shows nothing. Broken-prerequisite messages still appear there
   regardless.
5. **Two more startup lines, neither costing a healthy session anything.**
   When the daemon socket is absent, the hook runs `stacktrace --version`
   before blaming the daemon: a CLI older than 0.4.0, the first release with
   the daemon the monitor subscribes to, is the likelier cause, and the line
   names it and its upgrade command. When
   `CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC` or `DISABLE_TELEMETRY` is set,
   the hook names it, because Claude Code skips plugin monitors under either.
   Both are shell tests except the version read, which runs only on the
   broken path.

Until stacktrace ADR-0048 ships `stacktrace daemon start`, no message names
that command. The startup line says the daemon is not running and points at
`/stacktrace:status`, which gives today's fix: the session monitor still starts
the daemon, so `/reload-plugins` or a new session. The daemon-and-CLI version
check in `/stacktrace:status` reports that it cannot run yet, because the CLI
does not report the running daemon's version.

When `stacktrace telemetry` prints anything other than `off`, including
nothing, the welcome shows the `(on)` screen: an unreadable state errs toward
the fuller disclosure.

ADR-0007's install-scoped welcome marker, screen ownership and disclosure
decisions otherwise remain in force.

## Alternatives considered

- **Keep configure as a check-only skill.** Rejected because it would be
  `/stacktrace:status` under another name.
- **Let status offer to install the CLI or start the daemon.** Rejected because
  confirmation does not change ownership: the plugin would still be proposing
  a machine mutation that setup or the user owns.
- **Run `stacktrace daemon status` from SessionStart.** Rejected because the
  common healthy path needs only a socket-existence test and should not pay for
  a Python process on every session.
- **Parse telemetry configuration in shell.** Rejected because it would copy
  the CLI's rules for missing, unreadable and malformed settings into another
  language. The CLI answers once when the welcome actually needs the value.
- **Show the welcome unconditionally in cloud sessions.** Rejected for
  ADR-0006's reason: a screen shown every session regardless of state becomes
  noise people learn to ignore. Gating it on telemetry state instead means a
  correctly provisioned environment, one where telemetry is off before the
  session begins, shows nothing.

## Consequences

Every plugin path becomes read-only with respect to the machine. Installation,
daemon startup and telemetry changes have one owner each, outside the plugin.

A user who installs only the plugin no longer gets silence: the first startup
line explains which prerequisite is missing and names the command that resolves
it. `/stacktrace:status` provides the deeper ordered diagnosis.

Remote users see the welcome exactly when usage metrics are on, since no
marker survives environment recreation there; an environment that turns
telemetry off before the session begins shows nothing. `stacktrace telemetry
show` remains available either way.

## Open issues

The shell socket test can mistake a stale socket for a running daemon.
`/stacktrace:status` remains the authoritative check.

Whether plugin monitors run in Claude Code cloud sessions is unverified.
Organization-required plugins currently do not sync there, which is a separate
host limitation.

Whether the daemon is still there for the *next* session is unresolved.
`spec.md`'s session-end design drains, persists, and exits the daemon once no
session or pending work remains, and explicitly needs no supervisor. Once
`subscribe` no longer starts the daemon, an idle-exited daemon leaves the next
session's monitor unable to connect until someone runs `stacktrace daemon
start` again, degrading "automatic" monitoring into a per-session manual step.
Keeping the daemon resident, adding a host-level supervisor that starts it per
session, or retaining some idempotent-start allowance are the candidate
resolutions; picking one is host/CLI lifecycle work for `stacktrace-ai/stacktrace`
ADR-0048 (stacktrace-ai/stacktrace#66), not a decision this ADR can make alone.
