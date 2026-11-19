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

1. When `CLAUDE_CODE_ENTRYPOINT=remote_cowork`, `scripts/cowork_setup.sh`
   makes the VM ready once for each boot. It installs the CLI with
   `uv tool install` if `$HOME/.local/bin/stacktrace` is absent: the wheel
   that the zip carries, else the version the plugin pins on PyPI. It enrolls,
   starts the daemon, and marks the boot ready only when the daemon holds the
   organization's policy. The kernel's `boot_id` names the boot. On every
   other host nothing installs, as ADR-0008 says.
2. The setup reads `cowork/enroll.env` from the plugin root. It takes only
   `STACKTRACE_REMOTE_TOKEN`, `STACKTRACE_REMOTE_API_URL` and
   `STACKTRACE_CLI_WHEEL`, and only plain values.
3. Session start and every hook that decides (`PreToolUse`,
   `UserPromptSubmit`, `UserPromptExpansion`) call the setup before they
   answer, and wait for it at most 50 seconds. The setup runs once, under a
   lock, in its own session, so a hook that times out does not stop it. A
   journal-only hook starts it and does not wait. A failure is kept for its
   boot for five minutes, so later hooks do not wait on it again.
4. The SessionStart hook and the deciding hooks have a timeout of 60 seconds.
   Elsewhere they answer at once, so the longer limit matters only if the CLI
   stops answering. Codex, Cursor and Devin keep their limits.
5. `scripts/build_cowork_zip.sh` builds the zip with `enroll.env`.
6. In Cowork, when the install fails or the API does not answer, session
   start shows one line that names the organization's network setting. The
   task continues.

Every other decision in ADR-0008 and ADR-0013 stays.

## Alternatives considered

- **Set up in SessionStart only.** Rejected: Cowork runs the first prompt's
  hooks while SessionStart still runs. Claude Code's hook reference says
  that SessionStart hooks run in the background, and a probe in a Cowork VM
  saw `UserPromptSubmit` before `SessionStart`. Cowork also restarts the VM
  about four minutes into a task, which stops the daemon. Live tasks showed a
  token prompt and a token write go through in both windows.
- **Install the CLI in the background and return at once.** Rejected: the
  first prompt and its tool calls would run before the CLI exists, and so
  without policy.
- **Deny every action until the boot is ready.** Rejected: Cowork shows
  nothing for a blocked prompt, so the person's first message would vanish.
  A wait keeps the message and checks it.
- **Ready when the daemon answers.** Rejected: a daemon answers before it
  has the policy, and until then it allows every action.
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
- The first message of a new Cowork task waits for the setup, a few
  seconds to tens of seconds. After a VM restart, the first deciding hook
  waits for the daemon. A resumed task finds the CLI on its disk.
- If the daemon stops with no restart, the next boot check does not see it.
  Hooks allow every action until the next restart.
- A pinned version moves only with a plugin release.

## When to revisit

- Cowork gets plugin settings or environment settings.
- Cowork runs tasks on the user's computer for this account, where the CLI is
  already installed.
