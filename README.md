# Stacktrace Claude Code Plugin

Stacktrace automatically analyzes Claude Code runtime activity and returns
high-severity findings to the session that produced them.

The plugin is a thin adapter over the Stacktrace CLI. It declares one
session-lifetime monitor, adds notification guidance at session start, and
provides configure, status, and findings workflows. Parsing, detection, policy,
persistence, and routing remain in Stacktrace.

## Install

During early testing, install directly from this repository:

```text
/plugin marketplace add stacktrace-ai/stacktrace-claude-plugin
/plugin install stacktrace@stacktrace
/stacktrace:configure
```

`/stacktrace:configure` verifies or installs the `stacktrace` CLI. After a new
installation, run `/reload-plugins` once so Claude starts the monitor with the
CLI available.

## Automatic flow

For each interactive Claude session, the plugin runs:

```text
stacktrace daemon subscribe --host claude-code
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
```

Background monitors are currently a Claude Code experimental component and run
only in interactive CLI sessions where the Monitor tool is available.

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
