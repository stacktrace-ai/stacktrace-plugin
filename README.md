# Stacktrace Plugin

Stacktrace host integrations automatically analyze agent runtime activity and
return high-severity findings to the session that produced them. Claude Code is
the first supported host.

Each host integration is a thin adapter over the Stacktrace CLI and daemon. The
Claude adapter declares one session-lifetime monitor, adds notification guidance
at session start, and provides configure, status, and findings workflows.
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
```

`/stacktrace:configure` verifies or installs the `stacktrace` CLI. After a new
installation, run `/reload-plugins` once so Claude starts the monitor with the
CLI available.

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
/stacktrace:configure
/stacktrace:status
/stacktrace:findings
/stacktrace:slack
```

Background monitors are currently a Claude Code experimental component and run
only in interactive CLI sessions where the Monitor tool is available.

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
