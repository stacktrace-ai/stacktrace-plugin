---
id: 0007
title: Show the welcome once at start, and forget it on uninstall
status: proposed
date: 2026-09-22
supersedes: null
superseded-by: null
amends: 0006
amended-by: 0008
---

Subsystem: the agent plugin. Amends ADR-0006: removes the welcome skill, moves
the marker, and replaces the screen.

## Context

A cofounder installed the plugin from the marketplace and never saw the
welcome. ADR-0006 keeps the marker at `~/.claude/stacktrace-welcomed`, which
nothing removes. Once any session has shown the screen, uninstalling and
reinstalling never shows it again, and nothing on the machine says why.

ADR-0006 also ships `/stacktrace:welcome`, a skill that shows the screen again
and asks whether to keep usage metrics on. The only setting it changes is one
CLI command, `stacktrace telemetry off`, and Claude can run that when asked.
The skill is a second copy of something the CLI already does.

The screen is out of date. Stacktrace ADR-0043 adds `session_id`, `agent_kind`
and `remote` to the events, and the screen does not list them. It also says
"We only publish those counters and that metadata", which is not true: the
PostHog SDK adds its own `$lib`, `$os` and `$python_version` fields, and
`stacktrace telemetry show` lists them.

## Decision

**The welcome is a startup message and nothing else.** The session-start hook
shows it once per installation as `systemMessage`. There is no welcome or config
skill; `skills/welcome/` is removed. Any setting is a CLI command, which the
screen names and Claude runs when asked.

**The screen is `scripts/welcome.txt`.** The hook shows it as written. Under
`NO_COLOR` the three wordmark rows become the word `STACKTRACE`.

**The marker is `${CLAUDE_PLUGIN_DATA}/stacktrace-welcomed`.** Claude Code
exports `CLAUDE_PLUGIN_DATA` to hook processes, creates nothing until it is
referenced, and deletes the directory when the plugin is uninstalled from its
last scope (code.claude.com/docs/en/plugins-reference). A reinstall therefore
welcomes again. When the variable is unset, as it is outside Claude Code, the
hook falls back to ADR-0006's location.

The screen:

```
  ┌─┐┌┬┐┌─┐┌─┐┬┌─┌┬┐┬─┐┌─┐┌─┐┌─┐
  └─┐ │ ├─┤│  ├┴┐ │ ├┬┘├─┤│  ├┤ 
  └─┘ ┴ ┴ ┴└─┘┴ ┴ ┴ ┴└─┴ ┴└─┘└─┘

  we watch your agents, so you don't have to


  WHAT WE DETECT

  credential-egress   A credential reached an outbound call.
  agent-blocked       Why the agent stopped, and what to do next.
                      quota · policy · throttled · refused


  USAGE METRICS  (on)

  Sent as it happens: install, session start, each finding
  delivered (rule and severity only), errors (type only).
  Each carries a random install id, session id, agent, CLI
  version, OS, and whether it ran in the cloud.

  Never sent: the finding, prompts, files, paths, repo names.

  What is sent:   stacktrace telemetry show
  Turn it off:    stacktrace telemetry off
```

## Alternatives considered

- **Keep a skill that shows the screen again and asks.** Rejected. It changes
  one setting that is already a CLI command, and it is a second place for the
  screen to drift from.
- **Keep the screen inside a skill file, as ADR-0006 did.** Rejected with the
  skill. A plain text file is what the hook reads, and nothing else parses it.
- **Keep the marker in `~/.claude` and delete it from an uninstall hook.**
  Rejected. Claude Code has no uninstall hook for plugins; the data directory
  is the uninstall-scoped state it provides.
- **Show the screen on every session.** Rejected for the reason ADR-0006 gives:
  a banner on every session is the thing people disable.

## Consequences

Nothing in the plugin asks the ADR-0006 question any more. The screen discloses
and names the off command; the answer is whatever the user runs or asks Claude
to run.

Anyone who already saw the welcome under ADR-0006 sees it once more, because
the new marker does not exist yet. That repeat is also the disclosure of the new
fields.

A missed welcome cannot be reopened from the plugin. `stacktrace telemetry show`
covers what it discloses.

The welcome still waits for `stacktrace` on PATH. The docs do not say whether a
SessionStart `systemMessage` shows in the VS Code extension.

## Open issues

When `stacktrace` is not on PATH the hook shows nothing. A one-line pointer to
`/stacktrace:configure` would tell a new user why nothing happened.

The command names on the screen change if the CLI's command surface is
reworked (`telemetry` to `analytics`). The screen and that change must ship
together.

Whether the screen should say PostHog receives the IP address, which it stores
even with GeoIP disabled, is open.

`stacktrace-deceptive-completion` is in the CLI's `RULE_IDS` and not on the
screen, on the reading that no shipped run produces it. That reading is not
verified.
