---
id: 0004
title: Own the Slack bridge in the CLI, publish findings from the daemon
status: accepted
date: 2026-09-20
supersedes: null
superseded-by: null
---

## Context

The plugin owns a Slack bridge. `scripts/slack.py` validates a small JSON
request — an HTTPS origin with no credentials, path, query or fragment; a
simple connection name; an opaque project id; short printable labels that are
not filesystem paths — and dispatches a fixed argument list to the installed
`stacktrace-slack` executable. `skills/slack/SKILL.md` drives it and
`tests/test_slack.py` covers it: 345 lines across the three.

That validation is product logic, and it is a security boundary. It decides
what may leave this machine as a project identity and a display label, and it
is the only thing standing between a local filesystem path and a message in
someone's Slack. Codex and Cursor adapters belong in this repository. Each
would carry its own copy, and duplicated boundaries drift.

Separately, and more seriously, no finding reaches Slack at all. The daemon
already decides which findings are eligible — `severity in {"high",
"critical"} and confidence == "high"` — and publishes them to the session
monitor. It does not publish them anywhere else. Nothing in the installed CLI
reads `STACKTRACE_SLACK_URL` or invokes the adapter, so a connection that is
paired, subscribed and healthy still carries nothing. Every Slack message this
project has delivered was sent by hand.

The capability is not missing, only uncalled. `stacktrace-slack-app` installs
four console scripts, and only one of them runs on a developer's machine:
`stacktrace-slack` (`client:main`). The other three — `stacktrace-slack-app`,
`stacktrace-slack-hosted`, `stacktrace-slack-publish` — are the multi-tenant
Slack service, its views and its operator-side publisher, and they run where
that service is deployed, against a bot token and a database. The laptop-side
client already implements `publish`: it enqueues a finding under a session id,
flushes the durable queue, and returns an event id, bounded at 32 KiB and
idempotent on that id, so a retry cannot duplicate a finding.

## Decision

Three changes, in this order, because only the first is observable.

The daemon publishes eligible findings to Slack. Where it publishes a monitor
notification today it also writes the canonical finding and invokes
`stacktrace-slack --service-url <origin> --connection <name> publish <file>
--session-id <id>`, behind the eligibility rule it already applies, flushing
the queue on startup and periodically thereafter. Slack stays optional: an
absent adapter, an unconfigured origin, or an unpaired connection is reported
and never degrades the native path.

The CLI owns the bridge. The validation now in `scripts/slack.py` becomes
`stacktrace slack <action>` for `connect`, `status`, `test`, `flush` and
`disconnect`, so one implementation serves every host adapter.

The plugin stops owning it. Once those commands exist, `scripts/slack.py` and
`tests/test_slack.py` are removed, `skills/slack/SKILL.md` shrinks to naming
the CLI commands and the consent language that belongs in front of a user, and
the `slack` entry leaves `scripts/validate_plugin.py`.

Nothing moves out of `stacktrace-slack-app`. Folding it into the CLI would put
a Slack OAuth server, tenancy and hosted delivery inside a local security tool
and would make Slack a hard dependency of it, which would in turn make the
honest "adapter not installed" state unreachable.

`publish` is not added to the plugin's action list at any point. The monitor
feed is a notification stream, not a publish API; reconstructing a finding from
its text would invent a second schema for a record the daemon already holds.

## Consequences

Until the first change lands, Slack delivery does not exist, and the plugin
says so rather than presenting it as unconfigured. `/stacktrace:status` states
that the core does not deliver findings to Slack in every Slack state,
including a connected one, because a "connected" row that says nothing further
reads as a working delivery path and leaves a user waiting for a message that
was never going to be sent.

The second change is housekeeping and ships no behaviour. It is worth doing
before a second host adapter exists rather than after, because its value is
preventing a divergence, and a divergence is cheapest to prevent while there
is only one copy.

The plugin keeps a Slack surface either way. Connection management needs a
person: OAuth, a pairing code confirmed in Slack, an explicit subscription.
What moves is the validation and dispatch beneath that conversation, not the
conversation.

Two of the three changes are implemented in `stacktrace-ai/stacktrace`, not
here. This ADR records the decision and the interface the plugin depends on; it
does not describe code in this repository until the third change lands.
