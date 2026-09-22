# Stacktrace Plugin

Stacktrace host integrations automatically analyze agent runtime activity and
return high-severity findings to the session that produced them. Claude Code is
the first supported host.

Each host integration is a thin adapter over the Stacktrace CLI and daemon. The
Claude adapter declares one session-lifetime monitor, adds notification guidance
at session start, and provides welcome, configure, status, and findings
workflows.
Parsing, detection, policy, persistence, and routing remain in Stacktrace.

Future Codex and Cursor adapters belong in this repository. Host-specific
packaging and lifecycle integration stay separate; they share the Stacktrace
daemon interface rather than duplicating detection logic.

## Install

During early testing, install directly from this repository:

```text
/plugin marketplace add stacktrace-ai/stacktrace-plugin
/plugin install stacktrace@stacktrace
/stacktrace:configure
/stacktrace:welcome
```

`/stacktrace:configure` verifies or installs the `stacktrace` CLI. After a new
installation, run `/reload-plugins` once so Claude starts the monitor with the
CLI available.

`/stacktrace:welcome` shows one screen: what the plugin detects, the four usage
events the CLI can send, and one question about sending them. See
[Welcome and usage telemetry](#welcome-and-usage-telemetry).

## Automatic flow

For each interactive Claude session, the plugin runs:

```text
stacktrace daemon subscribe --agent-kind claude-code
```

The command subscribes with Claude's native session ID and starts the per-user
daemon if needed. The daemon reads Claude's native session log, runs detection,
and sends only notification-worthy events back to that exact session. Raw
transcript content is not copied into notification events.

The available workflows are:

```text
/stacktrace:welcome
/stacktrace:configure
/stacktrace:status
/stacktrace:findings
/stacktrace:slack
```

Background monitors are currently a Claude Code experimental component and run
only in interactive CLI sessions where the Monitor tool is available.

## Welcome and usage telemetry

`/stacktrace:welcome` runs only when a person asks for it. It prints one
screen, 72 columns or narrower, that names the detection rules and every usage
event, then asks one question with two answers. Opt in is the highlighted
answer; a keystroke is still required to take it.

The four events are `installed`, `session_started`, `finding_delivered` (rule,
severity, sink, and for `agent-blocked` the reason code) and `error` (the
exception class name). The finding itself, prompts, file names, paths and
repository names are never sent.

The plugin stores nothing. The screen runs `stacktrace telemetry on` or
`stacktrace telemetry off`, and the CLI owns the setting. A machine that never
runs the welcome has no setting, which the CLI reads as off. `stacktrace
telemetry show` prints every event that was sent. The command ships with the
CLI half of this design, `stacktrace-ai/stacktrace` ADR-0037; an older CLI
exits non-zero and the skill reports that nothing was recorded.

The decision record is [ADR-0006](docs/adrs/0006-welcome-someone-once-and-ask-about-analytics-there.md).

## Optional Slack connection

`/stacktrace:slack connect`, `status`, `test`, and `disconnect` use the shared
`stacktrace-slack` adapter. The existing native session monitor keeps working
without Slack. A synthetic test is sent only when requested.

The adapter is supplied by
[stacktrace-slack-app](https://github.com/stacktrace-ai/stacktrace-slack-app),
not a published package yet. After its reviewed implementation merges, install
from a checked-out copy with `uv tool install /path/to/stacktrace-slack-app`.
Reviewers can use the implementation branch explicitly; do not assume its
current `main` already includes the adapter. Set `STACKTRACE_SLACK_URL` to the
configured HTTPS service origin before starting Claude, or supply the origin
when invoking the workflow. Bring the stable opaque project ID from Stacktrace
and a safe project label when connecting; do not use a local filesystem path.

The workflow opens Slack OAuth and asks the user to confirm the pairing code,
device/project, and subscription in Slack. No copied tokens or recipient IDs
are required. Credentials stay in the adapter's private local state. Admin
restrictions may keep a connection pending or blocked.

This addition implements connection management. Automatic finding publishing
still requires the shared core/daemon to call the adapter with sanitized,
eligible canonical findings and stable event/session IDs, then flush its
durable queue on startup and periodically. This plugin's native monitor feed
is not a Slack publish API; do not reconstruct findings from its notification
text or upload transcripts. `accepted`, `delivered`, and `read` remain distinct.

## Development

Validate the repository contract and tests:

```bash
python3 scripts/validate_plugin.py
python3 -m unittest discover -s tests -v
claude plugin validate .
```

The manifest intentionally omits an explicit version while the plugin is under
active development, so Claude derives updates from the source commit. Current
Claude releases report that choice as a non-fatal validation warning.

Review automation: [managed PR review and fixes](docs/managed-autofix.md).
