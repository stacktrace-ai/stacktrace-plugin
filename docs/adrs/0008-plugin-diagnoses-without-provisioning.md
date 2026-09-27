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

Stacktrace ADR-0072 moves daemon lifecycle out of agent adapters. The host or a
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
   Remediation lives in one named rule per condition: install or find the CLI,
   upgrade the CLI resolved by `PATH`, start or recover the daemon, and restart
   onto the installed version. Diagnostic branches refer to those rules rather
   than restating their commands. A CLI failure stops before prescribing a
   daemon action; the user repairs the CLI and reruns status so the next check
   can observe daemon state. The skill does not offer to run a mutating command.
2. **Report a broken prerequisite at every affected session start.** The hook
   emits one short `systemMessage` when the CLI is absent or the daemon socket
   is absent. It states the observed failure and routes to `/stacktrace:status`;
   it contains no installation, upgrade or daemon-lifecycle prescription. The
   socket test stays in shell so a healthy session does not start Python merely
   to prove health. These messages diagnose; they do not fix.
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
   before blaming the daemon: a CLI older than 0.5.2 does not implement the
   host-owned lifecycle contract, and the line names the resolved version and
   routes to `/stacktrace:status`. When
   `CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC` or `DISABLE_TELEMETRY` is set,
   the hook names it, because Claude Code skips plugin monitors under either.
   Both are shell tests except the version read, which runs only on the
   broken path.

Stacktrace 0.5.2 implements ADR-0072. `daemon status` reports `running: yes`,
`running: no` or `running: unresponsive`; for a running daemon it also reports
both the daemon's `version:` and the CLI's `installed:` build.
`/stacktrace:status` reads those rows rather than treating the command's exit
status as daemon availability, and owns the install-mode-specific remediation.

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
- **Share lifecycle prose between the shell hook and the Markdown skill.**
  Rejected because the skill has no include mechanism; generation would add a
  build-time dependency while leaving two runtime surfaces responsible for the
  same decision. The hook reports facts and routes to the one remediation
  owner instead.
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
daemon startup, restart policy and telemetry changes have one owner each,
outside the plugin. A detached daemon remains resident after the agent session
ends; continuous crash recovery belongs to the host's service manager.

A user who installs only the plugin no longer gets silence: the first startup
line explains which prerequisite is missing and routes to
`/stacktrace:status`, which provides the ordered diagnosis and the one
install-mode-aware remediation.

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
