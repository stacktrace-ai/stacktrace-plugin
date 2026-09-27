---
name: status
description: Diagnose automatic Stacktrace monitoring for this Claude session, and name the fix for the first thing that is wrong.
disable-model-invocation: true
---

# Stacktrace status

Diagnose only (ADR-0008). Never run a command that installs, starts or
changes anything, and never offer to. Name the fix; the user runs it.

Check in this order. Stop at the first failure, report it with its fix, and
say which checks did not run.

1. **CLI on PATH.** `command -v stacktrace`, then `stacktrace --version`.
   - Absent: `uv tool install stacktrace-cli`, then `stacktrace daemon start`,
     then `/reload-plugins`.
   - Older than 0.5.2: `uv tool upgrade stacktrace-cli`, then `stacktrace
     daemon start`. 0.5.2 is the first release where the host or user starts
     the daemon and the session monitor only subscribes.
2. **Daemon reachable.** `stacktrace daemon status`.
   - Read the `running:` row; command success alone does not mean the daemon is
     running.
   - If the command produces no readable `running:` row, report its output and
     stop.
   - `running: no`: the fix is `stacktrace daemon start`.
   - `running: unresponsive`: report it for the host supervisor or operator to
     handle. Do not remove the socket, discover a PID or suggest a force-stop.
3. **Daemon and CLI versions agree.** When `running: yes`, compare the
   `version:` and `installed:` rows.
   - If they differ, say the installed upgrade is not active. A detached
     installation runs `stacktrace daemon stop` followed by `stacktrace daemon
     start`; a host-managed installation must restart its service. Name both
     paths without running either.
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
