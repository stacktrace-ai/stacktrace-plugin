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
   - Absent: `uv tool install stacktrace-cli`, then `/reload-plugins`.
   - Older than 0.4.0: `uv tool upgrade stacktrace-cli`. 0.4.0 is the first
     release with the daemon the monitor subscribes to.
2. **Daemon reachable.** `stacktrace daemon status`.
   - Exit 1: the daemon is not running. Today the session monitor starts it,
     so `/reload-plugins` or a new session is the fix. If
     `CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC` or `DISABLE_TELEMETRY` is set,
     Claude Code skips plugin monitors and nothing starts it; name the
     variable.
3. **Daemon and CLI versions agree.** The CLI does not yet report the running
   daemon's version, so this check cannot run. Say so and continue.
4. **Monitor connected.** `pgrep -fl "stacktrace daemon subscribe"`. A match
   shows a monitor on this machine, not proof it belongs to this session; say
   that. No match: run `claude --version` and report it, and say the monitor
   declaration needs an interactive Claude Code CLI session. The fix is
   `/reload-plugins`, or a Claude Code upgrade if the host cannot run plugin
   monitors.
5. **`PushNotification` available.** Check whether the `PushNotification`
   tool is available to you in this session. Run this check even when the
   monitor is connected: a host can run monitors without supporting push. If
   it is missing, the fix is a Claude Code upgrade.

When every check passes, say so in one line with the CLI version.
