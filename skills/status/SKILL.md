---
name: status
description: Diagnose automatic Stacktrace monitoring for this Claude session, and name the fix for the first thing that is wrong.
disable-model-invocation: true
---

# Stacktrace status

Diagnose only (ADR-0008). Never run a command that installs, starts or
changes anything, and never offer to. Name the fix; the user runs it.

## Remediation rules

These rules are the single source of remediation guidance. Apply a rule only
after a check below establishes its condition.

- **Install or find the CLI**. For a new installation, recommend
  `uv tool install stacktrace-cli`. If an installation should already exist,
  correct `PATH` instead of installing a second copy. Then rerun
  `/stacktrace:status`.
- **Upgrade the resolved CLI**. Use `uv tool upgrade stacktrace-cli` only when
  the installation resolved by `command -v stacktrace` is the uv-managed tool.
  Otherwise correct `PATH` or upgrade the resolved installation directly. Then
  rerun `/stacktrace:status`.
- **Start or recover the daemon**. A detached installation runs
  `stacktrace daemon start`; a host-managed installation recovers its service
  running `stacktrace daemon run`. Name both paths without running either.
- **Restart onto the installed version**. A detached installation runs
  `stacktrace daemon stop` followed by `stacktrace daemon start`; a
  host-managed installation must restart its service. Name both paths without
  running either.

## Checks

Check in this order. Stop at the first failure, report it with its fix, and
say which checks did not run.

1. **CLI on PATH.** `command -v stacktrace`, then `stacktrace --version`.
   - Absent: apply **Install or find the CLI**, then stop. Daemon state is not
     known yet.
   - Older than 0.5.2: apply **Upgrade the resolved CLI**, then stop. 0.5.2 is
     the first release where the host or user starts the daemon and the session
     monitor only subscribes; the next status run determines whether that
     daemon needs attention.
2. **Daemon reachable.** `stacktrace daemon status`.
   - Read the `running:` row; command success alone does not mean the daemon is
     running.
   - If the command produces no readable `running:` row, report its output and
     stop.
   - `running: no`: apply **Start or recover the daemon**.
   - `running: unresponsive`: report it for the host supervisor or operator to
     handle. Do not remove the socket, discover a PID or suggest a force-stop.
3. **Daemon and CLI versions agree.** When `running: yes`, compare the
   `version:` and `installed:` rows.
   - If `installed:` is newer, say the installed upgrade is not active and
     apply **Restart onto the installed version**.
   - If `version:` is newer, the running daemon is ahead of the resolved CLI
     (a rollback, or `PATH` resolving an older install). Say so and name the
     fix by applying **Upgrade the resolved CLI**, so `command -v stacktrace`
     is no older than the running daemon. Do not suggest restarting the daemon.
4. **Monitor connected.** `pgrep -fl "stacktrace daemon subscribe"`. A match
   shows a monitor on this machine, not proof it belongs to this session; say
   that. No match: first check whether
   `CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC` or `DISABLE_TELEMETRY` is set;
   Claude Code skips plugin monitors under either variable, so name it as the
   failure. Otherwise run `claude --version` and report it, and say the monitor
   declaration needs an interactive Claude Code CLI session. The fix is
   `/reload-plugins`, or a Claude Code upgrade if the host cannot run plugin
   monitors.
5. **`PushNotification` available.** Check whether the `PushNotification`
   tool is available to you in this session. Run this check even when the
   monitor is connected: a host can run monitors without supporting push. If
   it is missing, the fix is a Claude Code upgrade.

When every check passes, say so in one line with the CLI version.
