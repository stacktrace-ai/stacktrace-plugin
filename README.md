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

**Install the CLI first.** The order matters and is not a formality: Claude
starts the session monitor at session start, and the monitor is the thing that
runs the CLI. A session that begins without a working CLI cannot acquire one
later, so installing the plugin first guarantees that its first session
monitors nothing.

While the daemon is merged but unreleased, the CLI must come from source — the
published package cannot subscribe:

```bash
uv tool install --force --from git+https://github.com/stacktrace-ai/stacktrace.git stacktrace-cli
```

Then add the plugin:

```text
/plugin marketplace add stacktrace-ai/stacktrace-plugin
/plugin install stacktrace@stacktrace
```

Then **quit and relaunch Claude**, and confirm:

```text
/stacktrace:status
```

`/reload-plugins` is not enough, for two independent reasons that both survive
a reload: it cannot refresh the `PATH` the running process already inherited,
and it does not start a session monitor mid-session.

> This rests on the monitor being session-lifetime, as `spec.md` states
> (*"Claude Code starts the plugin monitor once for the lifetime of an
> interactive session"*). That behaviour is assumed here rather than verified
> against the host; if a reload does start a monitor, this section is stricter
> than it needs to be.

If anything looks wrong at any point, `/stacktrace:configure` runs the same
probe and names the one thing that is blocking delivery.

### If the marketplace is refused

```text
Marketplace source '…' is blocked by enterprise policy.
```

A managed host can allowlist marketplaces in a root-owned managed-settings
file, and an empty allowlist blocks every source including a local directory.
This is a host policy decision. An administrator has to allow the marketplace;
the plugin cannot and should not work around it.

### A stopped daemon is usually fine

`stacktrace daemon status` reporting "not running" is the normal idle state.
The daemon is started by a subscriber and exits about five seconds after the
last one disconnects, so asking outside a subscribed session always finds it
down. What matters is whether anything *could* subscribe, which is what
`/stacktrace:status` reports.

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

No core release calls the adapter yet, so a paired and subscribed connection
still carries no finding on its own, and `/stacktrace:status` says so in every
Slack state rather than reporting the gap as missing configuration. Where the
publishing call belongs, and which parts of this bridge move to the CLI with
it, is [ADR-0004](docs/adrs/0004-own-the-slack-bridge-in-the-cli.md).

## Current runtime dependencies

What the plugin declares is ahead of what an installed CLI can do. None of this
is a defect in this repository, and all of it is checked at runtime rather than
assumed. State verified 2026-09-18:

| Dependency | State | Effect |
| --- | --- | --- |
| `stacktrace daemon`, `stacktrace findings` ([stacktrace#36](https://github.com/stacktrace-ai/stacktrace/pull/36)) | Merged, unreleased | Both exist on `stacktrace` `main` (0.4.0) and neither is in a release. PyPI's latest is 0.3.1, uploaded four days before the merge, so `uv tool install stacktrace-cli` yields a CLI with no `daemon`: the monitor cannot subscribe and `/stacktrace:findings` cannot run. Install from git to exercise them. |
| `stacktrace finding why\|dismiss\|mute` | **Not implemented** | No such command exists on `main`; the CLI answers `No such command 'finding'`. `/stacktrace:why`, `/stacktrace:dismiss`, and `/stacktrace:mute` cannot run, and no release will change that until the command surface is built. |
| Hosted Slack service public OAuth | Activated | `connect` can complete. The service runs `stacktrace-slack-hosted` with the three OAuth secrets set, and `/readyz` returns ready. |

Until a release carries the daemon, install the CLI from source to test the
monitor path:

```bash
uv tool install --force --from git+https://github.com/stacktrace-ai/stacktrace.git stacktrace-cli
```

`monitors.json` omits `--session-id`, which `daemon subscribe` marks required
while documenting a default from `CLAUDE_CODE_SESSION_ID`. The monitor
therefore depends on that variable being set in the session's environment.

The three unimplemented triage workflows are kept rather than deleted: they
carry the wording the CLI surface is meant to honour, and the distinction
between dismissing one finding and muting a rule is the part worth not
relitigating. They must report that they cannot run. Inventing output for them
is worse than saying the command does not exist.

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
[ADR-0003](docs/adrs/0003-deliver-findings-through-a-session-monitor.md) and the
Slack bridge is
[ADR-0004](docs/adrs/0004-own-the-slack-bridge-in-the-cli.md).

The manifest intentionally omits an explicit version while the plugin is under
active development, so Claude derives updates from the source commit. Current
Claude releases report that choice as a non-fatal validation warning.
