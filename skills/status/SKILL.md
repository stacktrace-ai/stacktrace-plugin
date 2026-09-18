---
name: status
description: Check automatic Stacktrace monitoring for this Claude session.
disable-model-invocation: true
---

# Stacktrace status

Report what is actually running. Never infer that monitoring is live from the
plugin being loaded, and never round a partial state up to a working one.

Run these, in order, and let each failure stand on its own:

1. `command -v stacktrace` — is the CLI on this process's `PATH`?
2. `stacktrace --version`
3. `stacktrace daemon status`
4. `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/slack.py"` with `{"action":"status"}`
   on stdin — only to report the optional Slack connection.

Report four lines: CLI, Daemon, Session, Slack. Then diagnose from this table,
which distinguishes states that look alike and are not:

| Observation | Meaning | What to say |
| --- | --- | --- |
| `command -v stacktrace` empty | Not installed, **or** installed outside this process's inherited `PATH` | Run `/stacktrace:configure`. If it was just installed, Claude must be fully restarted — `/reload-plugins` cannot refresh an inherited `PATH`. |
| CLI present, `daemon` is not a known command | The daemon is not in the installed CLI version | Automatic monitoring is unavailable in this build. Say so plainly. Do not tell the user to reload; a reload will not add the command. |
| `daemon status` reports not running | Daemon installed but down | It starts on subscribe; run `/reload-plugins` so the session monitor starts it. |
| `CLAUDE_CODE_SESSION_ID` unset | No session identity to route to | Report it. Never substitute cwd, a project path, or the newest transcript. |
| Slack `status` exit 127 | Optional adapter not installed | Slack is optional and unconfigured. Native monitoring is unaffected. |
| Slack reports pending | Install or pairing incomplete, possibly awaiting workspace admin approval | Pending is not connected. Say what is still needed. |
| Slack reports disconnected or revoked | Pairing was revoked from Slack or by `disconnect` | Reconnect with `/stacktrace:slack connect`. Queued findings are retained. |
| Slack unreachable or 5xx | Service outage | Report the outage. Local detection and native Claude notifications continue. Queued findings are retained; `/stacktrace:slack flush` drains them once it recovers. |

Slack being absent, pending, or broken never degrades the native path, and
saying otherwise misrepresents the product. Report them independently.
