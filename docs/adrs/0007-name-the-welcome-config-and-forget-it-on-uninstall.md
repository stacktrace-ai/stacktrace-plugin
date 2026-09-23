---
id: 0007
title: Name the welcome config, and forget it on uninstall
status: proposed
date: 2026-09-22
supersedes: null
superseded-by: null
amends: 0006
amended-by: null
---

Subsystem: the agent plugin. Amends ADR-0006's skill name, marker location and
screen.

## Context

A cofounder installed the plugin from the marketplace and never saw the
welcome. ADR-0006 keeps the marker at `~/.claude/stacktrace-welcomed`, which
nothing removes. Once any session has shown the screen, uninstalling and
reinstalling never shows it again, and nothing on the machine says why.

`/stacktrace:welcome` names an event, not a place. After the first session
there is nothing to be welcomed to, and the command people come back for is
the one that shows what is sent and turns it off.

The screen is out of date. Stacktrace ADR-0043 adds `session_id`, `agent_kind`
and `remote` to the events, and the screen does not list them. It also says
"We only publish those counters and that metadata", which is not true: the
PostHog SDK adds its own `$lib`, `$os` and `$python_version` fields, and
`stacktrace telemetry show` lists them.

## Decision

**The skill is `/stacktrace:config`.** `skills/welcome/` moves to
`skills/config/`. Both paths stay: the session-start hook shows the screen
once, unasked, and `/stacktrace:config` shows the same screen on demand and
asks keep-on or turn-off.

**The marker is `${CLAUDE_PLUGIN_DATA}/stacktrace-welcomed`.** Claude Code
exports `CLAUDE_PLUGIN_DATA` to hook processes, creates nothing until it is
referenced, and deletes the directory when the plugin is uninstalled from its
last scope (code.claude.com/docs/en/plugins-reference). A reinstall therefore
welcomes again. When the variable is unset, as it is outside Claude Code, the
hook falls back to ADR-0006's location.

**The screen carries no question.** It ends in three command lines: what is
sent, how to turn it off, and `/stacktrace:config`. The hook shows it
unchanged, so the one copy in the skill is the startup message line for line,
and the hook no longer rewrites option lines.

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
  Settings:       /stacktrace:config
```

## Alternatives considered

- **Fold `/stacktrace:configure` into `/stacktrace:config`.** Not decided here.
  Two commands a letter apart is a trap, but merging moves CLI installation
  into the disclosure skill, and that is a separate call. See Open issues.
- **Keep the marker in `~/.claude` and delete it from an uninstall hook.**
  Rejected. Claude Code has no uninstall hook for plugins; the data directory
  is the uninstall-scoped state it provides.
- **Show the screen on every session until `/stacktrace:config` is run.**
  Rejected for the reason ADR-0006 gives: a banner on every session is the thing
  people disable.

## Consequences

Anyone who already saw the welcome under ADR-0006 sees it once more, because
the new marker does not exist yet. That is the screen with the new fields, so
the repeat is also the disclosure of them.

The welcome still waits for `stacktrace` on PATH. It also still depends on the
surface: the docs do not say whether a SessionStart `systemMessage` shows in
the VS Code extension. In-session alerts need plugin monitors, which the docs
limit to interactive CLI sessions, so on VS Code, JetBrains, the desktop app,
`claude -p`, Bedrock, Vertex, Foundry, or with
`CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC` set, the daemon is never started.

## Open issues

`/stacktrace:config` and `/stacktrace:configure` differ by three letters.
Whether to merge them is open.

The daemon starts only from the plugin monitor. Outside the interactive CLI it
never starts, and `stacktrace daemon status` exits 1. Starting it from the
SessionStart hook, running it as a launchd or systemd user service, or
documenting the plugin as CLI-only are the options; none is chosen.

When `stacktrace` is not on PATH the hook shows nothing. A one-line pointer to
`/stacktrace:configure` would tell a new user why nothing happened.

Whether the screen should say PostHog receives the IP address, which it stores
even with GeoIP disabled, is open.

`stacktrace-deceptive-completion` is in the CLI's `RULE_IDS` and not on the
screen, on the reading that no shipped run produces it. That reading is not
verified.
