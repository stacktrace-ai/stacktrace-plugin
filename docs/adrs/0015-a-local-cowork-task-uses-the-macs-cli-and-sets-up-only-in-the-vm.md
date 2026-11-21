---
id: 0015
title: A local Cowork task uses the Mac's CLI, and the zip sets up only in a VM
status: proposed
date: 2026-11-20
supersedes: null
superseded-by: null
amends: [0014]
amended-by: null
---

## Context

Cowork can run a task on the person's computer. The desktop app starts
Claude Code on the Mac with `CLAUDE_CODE_ENTRYPOINT=local-agent`. The
session loads the person's own plugins from `~/.claude`, the Mac's managed
settings, and the organization's Required plugins. Only the shell and web
fetch run in a Linux VM (stacktrace `docs/specs/cowork.md`, "Local tasks").

The MDM key `requireCoworkFullVmSandbox` moves Claude Code itself into that
VM. The VM then has no CLI, as a cloud VM has none.

ADR-0014 runs the zip's setup only when the entrypoint is `remote_cowork`.
So a local task in the VM installs nothing, and its hooks allow every
action.

## Decision

1. The zip's `cowork/setup.sh` also runs for `local-agent` and `local_agent`
   when `uname -s` is `Linux`. That is a local task whose Claude Code runs in
   the VM. The setup is ADR-0014's, unchanged.
2. On the Mac, a local task's hooks use the CLI that the installer or MDM
   put there. The zip installs nothing and reads no token (ADR-0008). The
   plugin's own session start already says when the CLI is not on PATH.

## Alternatives considered

- **Install the CLI on the Mac from the zip.** Rejected: ADR-0008 keeps the
  plugin from provisioning a computer. The installer and MDM own the Mac's
  CLI, its service and its updates.
- **Keep the setup for `remote_cowork` only.** Rejected: an organization
  that sets `requireCoworkFullVmSandbox` gets no policy in any local task.
- **Tell the VM from the Mac by `CLAUDE_CODE_REMOTE`.** Rejected: the
  desktop app does not set it for a local task in either place. The kernel
  names the system.

## Consequences

- A local task in the VM waits for the setup, as a new cloud task does. It
  needs the same network setting.
- A local task on the Mac runs the zip's hooks and the person's own
  Stacktrace plugin, if it is installed. Both reach the same CLI and give
  the same answer.
- The zip reaches every member's Mac, with the token, in the desktop app's
  folder.

## When to revisit

- Anthropic changes where a local task runs Claude Code.
- The desktop app sets an entrypoint or a variable that names the VM.
