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
per-user daemon. The installer starts a detached daemon on both hosts.
SessionStart asks the CLI to restore a missing daemon before project registration.
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

The working manifest carries a semver version.
The production marketplace selects an exact plugin commit with its GitHub source and `sha` field.
The initial pin selects `0.3.2` at `bb0095731ad8471ed25c28c143dc07f80737c244`.
Ordinary code merges and development version changes leave that pin unchanged.
Existing marketplace names and installation commands remain the same.

Test unreleased code directly:

```sh
claude --plugin-dir /absolute/path/to/stacktrace-plugin
```

### Promote a plugin release

1. Select a candidate commit from `main` with a new runtime release version in `plugin.json`.
2. Run the repository tests, strict Claude validation, and native installation checks against the supported published CLI.
3. Tag the tested commit with its plugin version.
4. Open a promotion PR that changes only the marketplace source `sha` and necessary release documentation.
5. Merge that PR to make the release available to marketplace installations and updates.

Keep `source.source` as `github` and `source.repo` as `stacktrace-ai/stacktrace-plugin`.
Use the full 40-character commit SHA.
Keep the version in the pinned commit's `plugin.json`.
Do not add another version to the marketplace entry.

A runtime release needs a new version because Claude can retain cached files when the version stays unchanged.
Keep existing release tags and versions immutable.
CLI and plugin versions do not need matching numbers.

The initial pin freezes the currently served version without creating a tag or GitHub release.
It prevents future merges from changing the selected plugin code.
It does not remove code from existing plugin caches.
The installer release boundary remains separate.

See [ADR-0010](docs/adrs/0010-pin-production-plugin-commits.md).

Review automation: [managed PR review and fixes](.github/managed-autofix.md).


## Hook policy admission

Require **Claude Code 2.1.274 or newer** and the CLI release containing `stacktrace remote policy hooks`.
Upgrade the CLI before this plugin.
A missing or older CLI command continues without a policy decision.
The daemon serves policy automatically after Fleet enrollment.

Install the plugin with:

```sh
(
  set -e
  installer="$(mktemp)"
  trap 'rm -f "$installer"' EXIT
  curl -fsSL https://stacktrace.ai/install.sh -o "$installer"
  sh "$installer"
)
```

Plugin setup requires neither enrollment nor a running daemon.
Enroll the CLI and start its user daemon when credentials are available.
Check readiness with:

```sh
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

For old root-owned managed policies, install the plugin and verify hooks first, then run
`stacktrace remote policy hooks migration` for explicit one-time administrator
cleanup instructions. Ordinary installation and ongoing admission need no sudo.
The shared evidence API must be published and pinned before general policy rollout; this
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
SessionStart calls `stacktrace remote policy hooks register`.
The CLI registers the launch project with the daemon.
The daemon collects evidence and updates decisions asynchronously.

The adapter ensures the daemon runs on both hosts, including after worker migration.
Concurrent sessions share the CLI bootstrap and daemon locks.
Healthy daemons remain running.
Only remote recovery checks for CLI updates.
Remote installation runs from the environment startup script.
Installed files and configuration survive migration; processes can disappear.

The adapter command stays stable across independent CLI and plugin releases.
An older CLI can reject this command without blocking the session.
Run the shared installer to install or update the user plugin.
The installer directly runs native Claude marketplace and plugin commands.
It checks installation and enablement before it removes an older installer-owned hook.
The CLI exposes no plugin installation command.
Plugin validation and native conformance tests check hook declarations and failure behavior.

One SessionStart script quietly invokes the CLI adapter before it emits notification guidance.
A missing or incompatible CLI cannot corrupt that guidance or block Claude.
The script implements no daemon lifecycle or policy logic.
The subscription and hook scripts prefer the default per-user CLI over an older system copy.
An active development virtualenv keeps its CLI selection.
A local native-host test does not verify hosted worker migration.
Verify a hosted start and resume before remote rollout.

See [ADR-0009](docs/adrs/0009-delegate-session-registration-to-the-cli.md).
