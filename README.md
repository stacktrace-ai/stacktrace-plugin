# Stacktrace Plugin

Stacktrace host integrations automatically analyze agent runtime activity and
return high-severity findings to the session that produced them. Claude Code is
the first supported host.

Each host integration is a thin adapter over the Stacktrace CLI and daemon. The
Claude adapter declares one session-lifetime monitor, adds notification guidance
at session start, and provides status and findings workflows.
Parsing, detection, policy, persistence, and routing remain in Stacktrace.

Future Codex and Cursor adapters belong in this repository. Host-specific
packaging and lifecycle integration stay separate; they share the Stacktrace
daemon interface rather than duplicating detection logic.

## Install

Install from this repository's marketplace. The repository is private while
the plugin is in closed beta, so `/plugin marketplace add` uses your own GitHub
credentials and you need read access to it:

```text
/plugin marketplace add stacktrace-ai/stacktrace-plugin
/plugin install stacktrace@stacktrace
```

The plugin needs the `stacktrace` CLI, 0.4.0 or newer, which it does not
install (ADR-0008):

```text
uv tool install stacktrace-cli
```

Then run `/reload-plugins` once so Claude starts the monitor with the CLI
available. Each session start says when the CLI or the daemon is missing, and
`/stacktrace:status` gives the full diagnosis.

## Automatic flow

For each interactive Claude session, the plugin runs:

```text
stacktrace daemon subscribe --agent-kind claude-code
```

The command subscribes with Claude's native session ID to the already-running
per-user daemon; the host or user starts the daemon, never the plugin (ADR-0008
in `docs/adrs/`). The daemon reads Claude's native session log, runs detection,
and sends only notification-worthy events back to that exact session. Raw
transcript content is not copied into notification events.

The available workflows are:

```text
/stacktrace:status
/stacktrace:findings
```

Background monitors are currently a Claude Code experimental component and run
only in interactive CLI sessions where the Monitor tool is available.

## Development

Validate the repository contract and tests:

```bash
python3 scripts/validate_plugin.py
python3 -m unittest discover -s tests -v
claude plugin validate --strict .
```

The manifest carries a semver `version`, currently `0.1.0`, and `claude plugin
validate --strict .` passes. Claude Code treats that string as the plugin's
identity: an installed copy updates only when the version changes, so **every
release bumps it**. `scripts/validate_plugin.py` fails a manifest without one.

Review automation: [managed PR review and fixes](.github/managed-autofix.md).
