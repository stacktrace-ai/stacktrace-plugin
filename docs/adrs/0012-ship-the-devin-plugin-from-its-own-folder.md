---
id: 0012
title: Ship the Devin plugin from its own folder
status: proposed
date: 2026-10-31
supersedes: null
superseded-by: null
---

## Context

Fleet policy does not reach Devin CLI. The product owner wants the Devin
hooks in this plugin, as for Claude Code, Codex and Cursor.

A Devin plugin is a folder with `.devin-plugin/plugin.json`. Devin reads
`hooks.json` at the plugin root. The manifest has no field that names a hooks
file, so `hooks/devin.json` cannot be selected. Devin also loads an
`AGENTS.md` at the plugin root as an always-on rule in every session, and the
`rules/` and `skills/` folders. This repository's root holds `AGENTS.md`,
which links to the developer instructions in `.claude/CLAUDE.md`.

`devin plugins install` takes a GitHub `owner/repo`, a git URL or a local
path, with `#path` for a plugin below the root. It has no option to pin a ref.
A managed manifest can pin a `git-subdir` source by `sha` or `ref`. Devin calls
plugin hooks best effort and fail open. Plugin installs need a Devin sign-in.

Sources: [Devin CLI plugins](https://docs.devin.ai/cli/extensibility/plugins/overview.md),
[Hooks](https://docs.devin.ai/cli/extensibility/hooks/overview.md),
[CognitionAI/team-marketplace-template](https://github.com/CognitionAI/team-marketplace-template),
and `devin plugins install --help` from Devin CLI 3000.11.234.

## Decision

1. The Devin plugin is the `devin` folder. It holds
   `.devin-plugin/plugin.json`, `hooks.json` and `scripts/policy_hook.sh`, and
   nothing else. The validator enforces this list.
2. `hooks.json` runs `register` on `SessionStart` and `admit` on `PreToolUse`
   for MCP calls, with `--agent-kind devin`, through the failure wrapper. The
   hooks do not set `fail_closed`.
3. `devin/scripts/policy_hook.sh` is a byte copy of `scripts/policy_hook.sh`.
   The validator rejects a difference.
4. An organization requires the folder at a release tag in its managed
   manifest. A person installs a checkout of a release tag with `--local`.
   The documented commands never follow `main`.

## Alternatives considered

**A `.devin-plugin/plugin.json` at the repository root.** Devin would then
load the root `AGENTS.md`, which holds this repository's developer
instructions, into every Devin session.

**Remove the root `AGENTS.md`.** Agents that develop this repository read it.
The plugin folder keeps both uses apart.

**`hooks/devin.json`, as for Codex and Cursor.** Devin's manifest names no
hooks file, so Devin would not read it.

**A symlink from `devin/scripts` to `scripts`.** A link to a path outside the
folder breaks when Devin stages the folder alone.

**No Devin manifest. Devin falls back to `.claude-plugin/plugin.json`.**
Devin then runs the Claude hooks and loads the root `AGENTS.md`.

**`devin plugins install stacktrace-ai/stacktrace-plugin#devin`.** The command
has no ref, so every merge to `main` reaches the person. ADR-0010 rejects this
for Claude Code.

## Consequences

- A change to `scripts/policy_hook.sh` changes two files. The validator fails
  until both match.
- The release skill bumps four runtime manifests.
- No signed-in Devin session ran this plugin. The hook format, the root
  variable and the hook output rest on Devin's docs and binary.

## Verification

Use a signed-in Devin CLI.
Install a checkout of a release tag with `devin plugins install --local <checkout>/devin`.
Confirm that `devin plugins info stacktrace` lists the two hooks.
Confirm that a session runs `register --agent-kind devin`.
Confirm that an MCP call that Fleet blocks does not run.
