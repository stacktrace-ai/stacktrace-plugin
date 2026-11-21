---
id: 0016
title: Cursor sends its shell commands, writes, deletes and reads to the policy hook
status: proposed
date: 2026-11-20
supersedes: null
superseded-by: null
amends: null
amended-by: null
---

## Context

The Cursor hooks file sends MCP calls and prompts to the CLI. It sends no
built-in call. The CLI has judged Cursor's `preToolUse` for `Shell`, `Write`
and `Delete` since stacktrace-cli 0.22.0 (stacktrace ADR-0158), and the
daemon blocks a call that a detection rule with a `block` entry matches. The
Codex hooks file already sends `Bash` and `apply_patch` for the same reason.
Without this entry, Fleet's detection blocks never reach a Cursor session:
a credential written to a file, a key sent with `curl` or a piped install
script runs.

Cursor's `preToolUse` fires before every tool. Its `matcher` is a regex
tested against the tool's name ([Cursor hooks](https://cursor.com/docs/hooks),
"Matcher Configuration"). On Cursor CLI 2026.10.22-27dcf5f a recorded run
gave these payloads:

| Tool | `tool_input` keys |
| --- | --- |
| `Shell` | `command`, `cwd`, `timeout` |
| `Write` (a new file and every edit) | `file_path`, `content` |
| `Read` | `file_path` |

Each carries `tool_use_id` and `conversation_id`. An MCP call is
`MCP:<tool>`, with no server.

## Decision

1. `hooks/cursor.json` adds one `preToolUse` entry. It runs
   `sh ./scripts/policy_hook.sh admit --agent-kind cursor` with a timeout of
   five seconds, matched to `^(Shell|Write|Delete|Read)$`.
2. The matcher never selects `MCP:`. `beforeMCPExecution` names the server,
   so Fleet's exact MCP targets keep deciding a local MCP call. The CLI would
   decide `MCP:<tool>` by Fleet's MCP default alone, which is the cloud path
   (stacktrace ADR-0172).
3. The entry has no `failClosed`. A missing, old or failed CLI, or a stopped
   daemon, adds no block, as for every other Cursor hook. The wrapper prints
   nothing on a failure, so Cursor never parses a deny the CLI did not give.
4. `Read` is sent ahead of the CLI that judges it. A CLI before that release
   reads no action from a `Read` payload and prints nothing, so the read runs.

## Alternatives considered

**`beforeShellExecution` and `beforeReadFile`.** They block too, but each
covers one tool, and no hook runs before a write: `afterFileEdit` runs after
it. One `preToolUse` entry covers all four tools, in the shape the CLI
already reads.

**Match every tool.** Each hook run starts the CLI. `Grep`, `Task` and the
rest reach no rule that blocks before the call, so they would only add
latency.

**Wait for the CLI release before sending `Read`.** The plugin and the CLI
ship separately. Sending it now costs one CLI start per read on an older CLI
and needs no second plugin release.

## Consequences

- A detection block entry in Fleet now stops a Cursor shell command, write or
  delete in the CLI and the desktop app, with the CLI that customers already
  run (0.22.0 and later). A read is stopped once the CLI judges `Read`.
- Each shell command, write, delete and read starts the CLI once. The CLI
  waits at most 1.5 s for the daemon's decision.
- Cloud agents run no plugin hooks (stacktrace ADR-0171). The installer's own
  `preToolUse` entry decides what reaches the CLI there.

## Verification

Run `tests/test_cursor_hooks.py` and `scripts/validate_plugin.py`. On
2026-11-20 Cursor CLI 2026.10.22-27dcf5f, signed in, ran with this entry as a
project hook, stacktrace-cli 0.27.0 and an isolated daemon whose policy had
`block` entries. A `Write` of a token to `deploy.env`, a `curl` that sent the
token and `curl … | sh` were each denied with Stacktrace's message, and no
file was written. `ls -la` ran. The desktop app was not run.
