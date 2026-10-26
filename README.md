# Stacktrace Plugin

Stacktrace host integrations automatically analyze agent runtime activity and
return high-severity findings to the session that produced them. Claude Code is
the first supported host.

Each host integration is a thin adapter over the Stacktrace CLI and daemon. The
Claude adapter declares one session-lifetime monitor, adds notification guidance
at session start, and provides status and findings workflows.
Parsing, detection, policy, persistence, and routing remain in Stacktrace.

The Codex and Cursor policy adapters belong in this repository. Host-specific
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
The production marketplace selects an exact plugin commit with an explicit HTTPS `url` source and `sha` field.
The initial pin selects `0.3.2` at `bb0095731ad8471ed25c28c143dc07f80737c244`.
Ordinary code merges and development version changes leave that pin unchanged.
Existing marketplace names and installation commands remain the same.
The marketplace entry also repeats `plugin.json`'s display fields, because Claude Code can read
`plugin.json` itself only for a relative-path source, before install.

Test unreleased code directly:

```sh
claude --plugin-dir /absolute/path/to/stacktrace-plugin
```

### Promote a plugin release

The `release-stacktrace-plugin` skill in `.agents/skills/` runs these steps. `.claude/skills/` links to it.

1. Select a candidate commit from `main` with a new runtime release version in `plugin.json`.
2. Run the repository tests, strict Claude validation, and native installation checks against the supported published CLI.
3. Tag the tested commit with its plugin version.
4. Open a promotion PR that changes only the marketplace source `sha` and necessary release documentation.
5. Merge that PR to make the release available to marketplace installations and updates.

Keep `source.source` as `url` and `source.url` as `https://github.com/stacktrace-ai/stacktrace-plugin.git`.
Use the full 40-character commit SHA.
Keep the version in the pinned commit's `plugin.json`.
Do not add another version to the marketplace entry.
Keep the entry's display fields equal to the pinned commit's `plugin.json` values.

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
The hooks restore its executable path if a login shell reorders `PATH`.
A local native-host test does not verify hosted worker migration.
Verify a hosted start and resume before remote rollout.

See [ADR-0009](docs/adrs/0009-delegate-session-registration-to-the-cli.md).

## Codex CLI policy hooks

The development adapter covers MCP tool use, including MCP servers with known plugin ownership.
It calls the same user daemon as Claude.
It does not add a notification monitor or a skill admission event.
Desktop and cloud need separate conformance tests before rollout.

The CLI needs the Codex admission commands and the public Codex evidence collector.
An older or missing CLI continues through native permissions.
An unavailable daemon also continues.
Unknown namespaces follow the MCP policy default.
Plugin loading and skill context injection remain outside hook coverage.

Codex reads `.codex-plugin/plugin.json` and `hooks/codex.json`.
The plugin reuses `scripts/policy_hook.sh` to discard output after failed CLI commands.
The command performs no evaluation in this repository.

The production marketplace pin remains unchanged.
Use a temporary local marketplace to test this development checkout:

```bash
TEST_MARKETPLACE="$(mktemp -d /tmp/stacktrace-codex-marketplace.XXXXXX)"
mkdir -p "$TEST_MARKETPLACE/.claude-plugin" "$TEST_MARKETPLACE/plugins"
ln -s "$(git rev-parse --show-toplevel)" "$TEST_MARKETPLACE/plugins/stacktrace"
cat > "$TEST_MARKETPLACE/.claude-plugin/marketplace.json" <<'JSON'
{"name":"stacktrace-dev","plugins":[{"name":"stacktrace","source":"./plugins/stacktrace"}]}
JSON
codex plugin marketplace add "$TEST_MARKETPLACE"
codex plugin add stacktrace@stacktrace-dev
```

Start Codex and review the Stacktrace hooks in `/hooks`.
Installation alone does not grant native hook trust.
Start a new session after trust changes.
Send a message that does not need a tool, such as `Say ready without calling a tool.`
In the tested app-server path, SessionStart runs when the first user turn starts.
Opening a session alone does not register the project.
Check the project with `stacktrace remote policy hooks status --agent-kind codex`.
Use `stacktrace remote policy show` to see the active policy.
Wait for a valid scope before testing a blocked MCP tool.

Stable Codex 0.163.0 is the conformance reference.
The Codex manifest mirrors the shared version in `.claude-plugin/plugin.json`.
The validator rejects different versions between the native manifests.
Native Codex can skip cache refresh when the manifest version does not change.
The release skill updates both runtime manifests together.
The production marketplace keeps its immutable source commit.
A release promotion must test both native hosts before changing that pin.

## Cursor policy hooks

The Cursor adapter covers MCP tool use, including MCP servers that a plugin bundles.
It calls the same user daemon as Claude and Codex.
It adds no notification monitor and no skill, command or sub-agent admission.
The Cursor CLI fires no admission event for those.

Add the marketplace to the Cursor CLI at a release tag:

```sh
agent plugin marketplace add github.com/stacktrace-ai/stacktrace-plugin --git-ref v<release>
```

Then run `agent`, open `/plugins` and enable `stacktrace`.
Start a new session after you enable it.
Plugin 0.3.3 is the first release with the Cursor adapter.

Cursor reads `.cursor-plugin/marketplace.json`, which lists this repository's root (ADR-0011).
The tag selects the commit.
Without `--git-ref`, Cursor follows `main`, which holds unreleased code.
To move to a newer release, run the same command with the new tag.
Cursor replaces the tag and keeps the plugin enabled.

Test a checkout with `agent --plugin-dir <checkout>`.
Cursor reads `~/.cursor/plugins/local` only when a team admin allows user plugin imports.

Cursor reads `.cursor-plugin/plugin.json` and `hooks/cursor.json`.
The `sessionStart` hook registers the project.
The `beforeMCPExecution` hook asks the daemon for a decision.
Both hooks run `scripts/policy_hook.sh` from the plugin root.
The wrapper prints nothing when the CLI fails, so Cursor's own approval decides.
The hooks do not set `failClosed`.

The CLI needs `--agent-kind cursor` and an OpenACA release that collects Cursor evidence.
Check the project with `stacktrace remote policy hooks status --agent-kind cursor`.
Wait for a valid scope before testing a blocked MCP tool.

The Cursor CLI `2026.10.22-27dcf5f` is the conformance reference.
Its local-inference build runs the native tests with no account.
The stacktrace repository holds the conformance test, and stacktrace-demo holds the end-to-end suite.
The Cursor manifest mirrors the shared version in `.claude-plugin/plugin.json`.
The desktop app and Cursor's public marketplace are not yet tested.
