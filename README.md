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

The plugin needs the `stacktrace` CLI, 0.5.2 or newer, which it does not
install (ADR-0008):

```text
uv tool install stacktrace-cli
stacktrace daemon start
```

`daemon start` launches one detached daemon. A host-managed installation runs
`stacktrace daemon run` under its native service manager instead. Then run
`/reload-plugins` once so Claude starts the monitor with the CLI available.
Each session start says when the CLI or the daemon is missing, and
`/stacktrace:status` gives the full diagnosis. After upgrading the CLI, restart
the detached daemon with `stacktrace daemon stop` followed by `stacktrace daemon
start`, or restart the host-managed service.

## Automatic flow

For each interactive Claude session, the plugin runs:

```text
stacktrace daemon subscribe --agent-kind claude-code
```

The command subscribes with Claude's native session ID to the already-running
per-user daemon. On laptops, the host or installer starts the daemon.
On remote workers, the SessionStart adapter asks the CLI to ensure daemon readiness.
The daemon reads Claude's native session log, runs detection,
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

The manifest carries a semver `version`, currently `0.3.1`, and `claude plugin
validate --strict .` passes. Claude Code treats that string as the plugin's
identity: an installed copy updates only when the version changes, so **every
release bumps it**. `scripts/validate_plugin.py` fails a manifest without one.

Review automation: [managed PR review and fixes](.github/managed-autofix.md).


## Hook policy admission

Require **Claude Code 2.1.302 or newer** and the CLI release containing `stacktrace remote policy hooks`.
Upgrade the CLI before this plugin.
A missing or older CLI command continues without a policy decision.
A compatible CLI keeps admission off until activation succeeds.

Enroll the CLI and start its user daemon.
Run:

```sh
stacktrace remote policy hooks enable
stacktrace remote policy hooks status
```

Start a new Claude session.
The synchronous `PreToolUse` hook covers MCP tools, Skill calls and namespaced plugin-agent calls.
MCP selection uses native server provenance.
`UserPromptExpansion` covers direct slash-command expansion.
Neither allow nor defer grants a native permission.

Unknown or ambiguous subjects use the known category default.
Before the first completed snapshot, missing evidence uses a known default where possible.
Failed refreshes retain the last completed decisions and defaults.
Age alone does not remove those decisions.
A configured blocked default still applies.
Missing vulnerability coordinates add no block.

Unavailable checks, protocol errors, daemon outages and hook launch or timeout failures continue through native permissions.
Confirmed policy restrictions and risk matches block according to the active snapshot.

Policies retain OpenACA MCP/plugin allowlists and denylists, category defaults,
skill defaults, vulnerability gates and posture gates. Plugin children inherit
their owning plugin's decision. The plugin contains no evaluator, scanner,
policy cache or privileged helper.

Coverage is **hook-visible use**. Plugin loading, startup hooks, MCP connection,
resources/prompts, LSP startup and preloaded skill context can occur before a
blocking hook. Disabled or unlaunched hooks remain a host coverage gap.
In-session `/cd` configuration switching is unsupported and cannot always be
distinguished from ordinary shell directory changes; start a new session in the
target project. Status reports declarations and observed calls, not proof of
complete mediation or current adapter health.

For old root-owned managed policies, enable and verify hooks first, then run
`stacktrace remote policy hooks migration` for explicit one-time administrator
cleanup instructions. Ordinary installation and ongoing admission need no sudo.
The shared evidence API must be published and pinned before activation; this
source change does not publish a release or alter an existing enrollment.


## CLI compatibility failures

An older CLI can exit `2` for an unknown policy-hook command.
Claude treats exit `2` as an explicit block on admission events.
`onFailure: "continue"` does not override that verdict.
See [Claude hook exit handling](https://code.claude.com/docs/en/hooks#exit-code-2).

The plugin forwards CLI output only after a successful exit.
Failed or missing CLI commands produce no policy verdict.
The hook command also guards a missing wrapper script.
Successful JSON policy denials still block the action.
Claude applies its normal permissions when Stacktrace produces no verdict.
## Session registration

The plugin owns all Stacktrace hook declarations on laptops and remote workers.
SessionStart calls `stacktrace remote policy hooks session-start --adapter-version 1`.
The CLI registers the launch project with the daemon.
The daemon collects evidence and updates decisions asynchronously.

The laptop adapter never starts or updates the daemon.
The remote adapter first ensures the daemon runs, including after worker migration.
Remote installation runs from the environment startup script.
Installed files and configuration survive migration; processes can disappear.

The adapter command stays stable across independent CLI and plugin releases.
An older CLI can reject this command without blocking the session.
Run `stacktrace remote policy hooks setup` to install a compatible plugin and activate policy hooks.
Setup checks the actual adapter command before it removes an older installer-owned hook.

The existing notification guidance script remains diagnostic.
It does not own project registration or remote daemon startup.
A local native-host test does not verify hosted worker migration.
Verify a hosted start and resume before remote rollout.

See [ADR-0009](docs/adrs/0009-delegate-session-registration-to-the-cli.md).
