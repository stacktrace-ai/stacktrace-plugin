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
setup mechanism provisions it. In Cowork, the plugin zip is the only
mechanism.

Two more facts shape the decision. Claude Code runs SessionStart hooks in the
background, and a probe in a Cowork VM saw `UserPromptSubmit` before
`SessionStart`. Cowork also restarts the VM about four minutes into a task,
which stops the daemon. Live tasks showed a token prompt and a token write go
through in both windows.

## Decision

1. Only the Cowork zip changes. The `cowork` folder holds `hooks.json`,
   `setup.sh`, `session_start.sh` and `policy_hook.sh`.
   `scripts/build_cowork_zip.sh` puts `cowork/hooks.json` in the zip as
   `hooks/hooks.json`. The plugin's own hooks and scripts stay the same for
   every host, and they never call the `cowork` folder.
2. Each hook in `cowork/hooks.json` is the plugin's own hook, with the same
   events and matchers. It calls a wrapper in `cowork`, which runs
   `cowork/setup.sh` and then the plugin's own script with the hook's input.
3. `cowork/setup.sh` makes the VM ready once for each boot. It installs the
   CLI with `uv tool install --compile-bytecode` if
   `$HOME/.local/bin/stacktrace` is absent: the wheel that the zip carries,
   else the version the plugin pins on PyPI. It saves the token with
   `stacktrace remote configure` when `cowork/enroll.env` is newer than the
   last save. Then it runs `stacktrace daemon start` itself. The kernel's
   `boot_id` names the boot.
4. A boot is ready only when the daemon holds the organization's policy.
   The setup asks the daemon's socket for `policy_status` every 0.1 seconds
   from one `python3` process. It stays ready while the daemon answers on its
   socket. A daemon that stops without a restart makes the boot not ready,
   and the next hook sets it up again. When the boot is ready, the setup
   starts `stacktrace remote policy hooks register` and does not wait for
   it. A prompt or a built-in tool call needs no registered project.
5. The setup reads `cowork/enroll.env` from the plugin root. It takes only
   `STACKTRACE_REMOTE_TOKEN`, `STACKTRACE_REMOTE_API_URL` and
   `STACKTRACE_CLI_WHEEL`, and only plain values.
6. A hook that decides (`PreToolUse`, `UserPromptSubmit`,
   `UserPromptExpansion`) waits for the setup at most 50 seconds, and has a
   timeout of 60 seconds. SessionStart waits at most 40 seconds, and has a
   timeout of 60 seconds. Every other hook starts the setup and does not
   wait.
7. One setup runs at a time for each boot. It runs in its own session, so a
   hook that times out does not stop it. A lock from an earlier boot, or from
   a setup that stopped, does not hold the boot back. A failure is kept for
   its boot for five minutes, so later hooks do not wait on it again. The
   age of a lock, these five minutes and each wait use a clock that does not
   step: the kernel's uptime in the VM. A VM that syncs its time steps the
   wall clock, and a live lock must not look stale.
8. The setup writes one line for each step to `cowork-setup.log` in the
   state folder: the time, the boot, the step and its milliseconds or code.
   The steps are `install`, `configure`, `policy` and `ready`. It never
   writes a value or a payload. A hook that waits checks the boot every 0.2
   seconds.
9. The zip also sends `PostToolUse` for the write tools and `Stop` to the
   CLI, which journals the turn where the agent keeps no transcript
   (stacktrace ADR-0260). The plugin's own hooks do not have them.
10. When the install fails or the API does not answer, session start shows
    one line that names the organization's network setting. The task
    continues. The setup checks that the VM reaches the API only until a
    boot of the task is ready. After that, the daemon reads the policy from
    its own database.
11. Outside a Cowork VM, `cowork/setup.sh` does nothing. A Cowork zip on
    another host installs nothing and reads no token.

Every other decision in ADR-0008 and ADR-0013 stays.

## Alternatives considered

- **Add Cowork branches to the plugin's own hooks and scripts.** Rejected:
  every host gets the longer timeouts and the journal hooks, and every
  script gets a Cowork path. The zip is built apart from the plugin, so the
  Cowork parts can stay in it.
- **Make `cowork/hooks.json` when the zip is built.** Rejected: the builder
  runs on an Owner's computer with `sh` only. A test makes the expected file
  from the plugin's own `hooks.json`, and fails when the two differ.
- **Set up in SessionStart only.** Rejected: Cowork runs the first prompt's
  hooks while SessionStart still runs, and a VM restart stops the daemon.
- **Install the CLI in the background and return at once.** Rejected: the
  first prompt and its tool calls would run before the CLI exists, and so
  without policy.
- **Deny every action until the boot is ready.** Rejected: Cowork shows
  nothing for a blocked prompt, so the person's first message would vanish.
  A wait keeps the message and checks it.
- **Ready when the daemon answers.** Rejected: a daemon answers before it
  has the policy, and until then it allows every action.
- **Start the daemon through `stacktrace remote policy hooks register`, and
  poll `stacktrace remote policy hooks status`.** Rejected: that path starts
  about eight CLI processes before the boot is ready. On a Mac a restart took
  about 3 seconds, and in a Cowork VM 12 to 14 seconds. The direct path takes
  about 0.7 seconds on the same Mac. After a restart the daemon reads the
  policy from its own database, so no network call is on that path.
- **Install from `stacktrace.ai/install.sh`.** Rejected: the installer gets
  `uv` from `astral.sh`, which a Cowork VM with "Package managers only" cannot
  reach. The VM already has `uv`, and PyPI is a package manager.
- **Ask each user to sign in at session start.** Rejected: a Cowork hook has
  no way to show a sign-in step, and a Required plugin must work for every
  member.
- **Wait for Cowork to support plugin settings.** Rejected for now: no date
  exists. The token moves out of the zip when it does.

## Consequences

- The plugin from the marketplace does not change for any host.
- Two hooks files exist. A hook added to the plugin's `hooks.json` fails the
  tests until `cowork/hooks.json` has it too.
- The zip holds an organization token. Anthropic stores the zip, and each
  task's VM gets a copy. An Owner rotates the token when a member who had the
  zip leaves.
- The first message of a new Cowork task waits for the setup, a few
  seconds to tens of seconds. After a VM restart, the first deciding hook
  waits for the daemon, about 1 second on a Mac. A resumed task finds the CLI
  and the saved token on its disk.
- The setup knows the daemon's `policy_status` request and reply. The pinned
  CLI fixes them. `stacktrace remote policy hooks status` is the fallback
  when the VM has no `python3`.
- Each Cowork hook checks the daemon's socket with `python3`, which adds a
  short delay to each hook.
- A pinned version moves only with a plugin release. It must be a release
  that has the CLI's Cowork support.

## When to revisit

- Cowork gets plugin settings or environment settings.
- Cowork runs tasks on the user's computer for this account, where the CLI is
  already installed.
