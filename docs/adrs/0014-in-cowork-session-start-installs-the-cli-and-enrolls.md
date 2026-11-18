---
id: 0014
title: In a Cowork VM, session start installs the CLI and enrolls with the zip's token
status: proposed
date: 2026-11-18
supersedes: null
superseded-by: null
amends: [0008, 0013]
amended-by: null
---

## Context

Claude Cowork runs each task in a new Linux VM in Anthropic's cloud. The
plugin's hooks run there as root, with `CLAUDE_CODE_ENTRYPOINT=remote_cowork`
(stacktrace `docs/specs/cowork.md`). Nothing else runs in that VM before the
task. Cowork has no setup script, no environment settings and no plugin
settings. The organization can upload a plugin zip and mark it Required.

So the CLI is never on the VM, and the hooks allow every action. ADR-0008
keeps the plugin from installing software, because a person or the host's
setup mechanism provisions it. In Cowork, the plugin is the only mechanism.

## Decision

1. When `CLAUDE_CODE_ENTRYPOINT=remote_cowork`, `session_start.sh` installs
   the CLI with `uv tool install` if `$HOME/.local/bin/stacktrace` is absent.
   It installs the wheel that the zip carries, else the version the plugin
   pins on PyPI. On every other host the script installs nothing, as ADR-0008
   says.
2. In Cowork, the script reads `cowork/enroll.env` from the plugin root. It
   takes only `STACKTRACE_REMOTE_TOKEN`, `STACKTRACE_REMOTE_API_URL` and
   `STACKTRACE_CLI_WHEEL`, and only plain values. It exports the first two for
   the CLI's registration, which enrolls and starts the daemon.
3. `scripts/build_cowork_zip.sh` builds the zip with that file.
4. The Claude Code SessionStart hook has a timeout of 60 seconds, so the
   install can finish. Codex, Cursor and Devin keep fifteen seconds.
5. In Cowork, when the install fails or the API does not answer, the script
   shows one line that names the organization's network setting. The task
   continues.

Every other decision in ADR-0008 and ADR-0013 stays.

## Alternatives considered

- **Install the CLI in the background and return at once.** Rejected: the
  first prompt and its tool calls would run before the CLI exists, and so
  without policy.
- **Install from `stacktrace.ai/install.sh`.** Rejected: the installer gets
  `uv` from `astral.sh`, which a Cowork VM with "Package managers only" cannot
  reach. The VM already has `uv`, and PyPI is a package manager.
- **Ask each user to sign in at session start.** Rejected: a Cowork hook has
  no way to show a sign-in step, and a Required plugin must work for every
  member.
- **Wait for Cowork to support plugin settings.** Rejected for now: no date
  exists. The token moves out of the zip when it does.

## Consequences

- The zip holds an organization token. Anthropic stores the zip, and each
  task's VM gets a copy. An Owner rotates the token when a member who had the
  zip leaves.
- Each new Cowork task spends the install time once. A resumed task finds
  the CLI on its disk.
- A pinned version moves only with a plugin release.

## When to revisit

- Cowork gets plugin settings or environment settings.
- Cowork runs tasks on the user's computer for this account, where the CLI is
  already installed.
