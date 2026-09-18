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
/stacktrace:detect
/stacktrace:why
/stacktrace:dismiss
/stacktrace:mute
```

Background monitors are currently a Claude Code experimental component and run
only in interactive CLI sessions where the Monitor tool is available. Where they
are not, the triage workflows below still work: they reach the CLI directly and
do not depend on how a finding was delivered.

## Finding triage

- `/stacktrace:detect` — run local detection over a time window without
  enabling upload.
- `/stacktrace:why` — show the evidence behind the last finding, coverage
  included.
- `/stacktrace:dismiss` — record that one finding was not worth surfacing.
- `/stacktrace:mute` — stop a rule in this project, without silencing the rest.

`dismiss` and `mute` are deliberately different actions. Dismissing judges one
finding and leaves the rule running; muting changes what reaches you and leaves
findings already surfaced in place, so a mute never quietly rewrites the record
a rule's dismissal rate is computed from.

Severity and confidence are reported as separate grades throughout: severity is
how much a finding matters, confidence is how sure the detector is that it
happened. Coverage — what the detector could not see — is part of the claim.

## Optional Slack connection

`/stacktrace:slack connect`, `status`, `test`, and `disconnect` use the shared
`stacktrace-slack` adapter. The existing native session monitor keeps working
without Slack. A synthetic test is sent only when requested.

The adapter ships in
[stacktrace-slack-app](https://github.com/stacktrace-ai/stacktrace-slack-app)
`main` and is not on PyPI. Install it from a checked-out copy:

```bash
uv tool install /path/to/stacktrace-slack-app
```

Set `STACKTRACE_SLACK_URL` to the configured HTTPS service origin before
starting Claude, or supply the origin when invoking the workflow. Bring the
stable opaque project ID from Stacktrace and a safe project label when
connecting; do not use a local filesystem path.

The workflow opens Slack OAuth and asks the user to confirm the pairing code,
device/project, and subscription in Slack. No copied tokens or recipient IDs
are required. Credentials stay in the adapter's private local state. Admin
restrictions may keep a connection pending or blocked.

`/stacktrace:slack flush` drains the adapter's durable queue after an outage.
Flush is idempotent on event ID, so a retry cannot duplicate a finding.

This plugin implements connection management and queue recovery only.
Automatic finding publishing still requires the shared core/daemon to call the
adapter with sanitized, eligible canonical findings and stable event/session
IDs, then flush on startup and periodically. This plugin's native monitor feed
is not a Slack publish API; do not reconstruct findings from its notification
text or upload transcripts. `accepted`, `delivered`, and `read` remain distinct.

## Current runtime dependencies

Two dependencies gate what actually runs today. Neither is a defect in this
repository, and both are checked at runtime rather than assumed:

| Dependency | State | Effect when unmet |
| --- | --- | --- |
| `stacktrace daemon` ([stacktrace#36](https://github.com/stacktrace-ai/stacktrace/pull/36)) | Open, unmerged | `daemon subscribe` and `daemon status` are unavailable, so the monitor cannot subscribe. `/stacktrace:status` reports this rather than implying monitoring is live. |
| Hosted Slack service public OAuth | Not activated | `connect` cannot complete. The workflow reports pending or unavailable; it never reports success. |

The hosted service at `stacktrace-slack-app-production.up.railway.app` runs the
single-workspace entrypoint. Public OAuth additionally needs `SLACK_CLIENT_ID`,
`SLACK_CLIENT_SECRET`, and `SLACK_SIGNING_SECRET`, and the container command set
to `stacktrace-slack-hosted`. Until both are done, treat Slack connect as
unavailable and do not report OAuth as working.

## Development

Validate the repository contract and tests:

```bash
python3 scripts/validate_plugin.py
python3 -m unittest discover -s tests -v
claude plugin validate .
bash scripts/install-hooks.sh
```

`install-hooks.sh` points `core.hooksPath` at `scripts/git-hooks`, so a push
runs the validator and the tests first. Architecture decisions are recorded in
[`docs/adrs`](docs/adrs/INDEX.md); the delivery path is
[ADR-0003](docs/adrs/0003-deliver-findings-through-a-session-monitor.md).

The manifest intentionally omits an explicit version while the plugin is under
active development, so Claude derives updates from the source commit. Current
Claude releases report that choice as a non-fatal validation warning.
