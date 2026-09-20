---
id: 0005
title: Ask two questions at onboarding, and specify how the alert is rendered
status: accepted
date: 2026-09-20
supersedes: null
superseded-by: null
---

## Context

The plugin has no onboarding and no renderer. Neither absence is visible until
you look for it.

On a healthy first run the plugin says nothing. `scripts/session_start.sh` emits
its guidance as `additionalContext`, which goes to the model and is never shown
to the user. The healthy branch ends with "Say nothing about setup unless the
user asks." Someone who installs the plugin, relaunches, and waits for a sign
that it works will wait forever.

The plugin also never asks how the user wants to be told. Everyone gets the same
delivery, and there is nowhere to record a different answer.

Rendering is in the same state. There is no colour handling anywhere in this
repository. `CLAUDE.md` says colour is never the only carrier of meaning and
that `NO_COLOR` is honoured, and nothing implements either rule. The alert a
user sees today is the model improvising from one line of the `SessionStart`
contract. It is not wrong, but it is not specified, so it varies by model, by
session, and by how much context the model is holding.

## How an alert actually reaches the screen

The plugin runs no code when a finding arrives. It contributes two declarations,
and both are read at session start.

```
SESSION START — the plugin's whole contribution, both declarative
═══════════════════════════════════════════════════════════════════
 hooks/hooks.json ──> scripts/session_start.sh
                       emits additionalContext  ─────────────┐
                       = THE CONTRACT: what a line means     │
                                                             ▼
 monitors/monitors.json ──> harness spawns, session-lifetime: │
     "stacktrace daemon subscribe --agent-kind claude-code"   │
                  │                                    [model context]
                  │ env: CLAUDE_CODE_SESSION_ID         holds the rule
                  ▼                                     for the session
        connect AF_UNIX socket
        send {type:"subscribe", host, session_id}
        recv {type:"subscribed", …}  ← must match exactly, else ProtocolError
                  │
                  ▼
        blocked on reader.readline()   ← no poll, no timer, no cursor

RUNTIME — once per notification
═══════════════════════════════════════════════════════════════════
 daemon ──> {version:1, type:"notification", event:{…}}
                  │
                  ▼
        _safe_event()  — validate, then copy out
          · version==1, type=="notification"
          · event.session == this subscriber's session  (else refuse)
          · five required fields all str
          · returns only those fields  ← confidence is dropped here today
                  │
                  ▼
        stdout:  STACKTRACE_NOTIFY_V1 {…}\n   +  flush
                  │
                  ├──> harness reads the monitor's stdout
                  │          │
                  │          ▼
                  │    model applies the contract it was given at start:
                  │      prefix match? parses as an object? required fields?
                  │      → PushNotification once per event_id
                  │      → render inline, per the specification below
                  │
                  └──> send {type:"ack", event_id}   ← only after the flush
```

Two things follow. The trigger is a line appearing on a stream, and the rule for
what to do with it was installed at session start. And there is nowhere for
plugin code to format anything, because nothing of ours runs between the
monitor's stdout and the conversation.

So the specification is the artefact. It is the only thing that makes one
session's alert look like the next one's.

## Decision

### Onboarding asks two questions

Not three. An earlier draft also asked which kinds of finding the user cares
about. That is a policy question, the policy system owns it, and this plugin
should not collect an answer to it.

```
  1  How do you want to be notified?
       this session · + desktop · + Slack

  2  Slack chosen? ──> run `stacktrace slack connect`
                        prints a URL and a pairing code;
                        the user confirms both in Slack
```

Ask them with `AskUserQuestion`, one call per question, in order. The skill is
`disable-model-invocation: true`, so the user opens this conversation and the
model never starts it in the middle of their work.

### Where each answer is stored

| Answer | Acted on by | Stored by |
| --- | --- | --- |
| inline alert format | the model, via the contract | the plugin |
| desktop notification on/off | the model, via `PushNotification` | the plugin |
| Slack on/off | the daemon | nothing — a subscribed connection is the answer |

The plugin stores its own presentation preferences. An earlier draft sent them
to the CLI, which was wrong: the CLI is host-agnostic and has no business
holding "should Claude Code show a desktop notification".

Slack needs no preference at all. The connection either exists and is
subscribed, or it does not, and the adapter already records that.

```jsonc
// ~/.claude/stacktrace-plugin.json — written by the onboarding skill,
// read by scripts/session_start.sh. Absent means "defaults".
{
  "desktop_notifications": true
}
```

`session_start.sh` already reads the environment, so it reads this too and emits
different guidance. Nothing else in the plugin reads it, and no delivery state
ever goes in it.

### The alert has a fixed shape

```
  ⛔ Stacktrace  high severity · high confidence
     A tool result carried obfuscated, instruction-shaped content
     stacktrace-injection-marker · /stacktrace:findings for the evidence
```

Severity picks the glyph and the emphasis. Confidence is always printed as its
own labelled grade. Both are always shown, and neither is ever implied by a
glyph or a colour on its own.

The event carries no `confidence` field today, because `_safe_event` drops it.
Until that changes the alert prints `confidence unstated`. It never guesses a
confidence from a severity.

### `NO_COLOR` is resolved in the hook

The model cannot read the environment and the hook can, so the hook decides and
tells the model.

```sh
colour_note() {
    if [ -n "${NO_COLOR-}" ]; then
        printf '%s' 'NO_COLOR is set: omit the glyph and any emphasis, keep every word.'
        return
    fi
    printf '%s' 'NO_COLOR is not set: prefix with the severity glyph and bold the grade.'
}
```

Each branch emits a fixed string the file controls, and no command output is
interpolated into the JSON, so a strange environment cannot reshape the
document. The existing guarantee that hook input never reaches hook output is
tested on both branches.

## Consequences

The user finds out what the plugin will do while they can still change it.

Rendering stops varying between sessions. A specified format can be reviewed and
tested against `NO_COLOR`. An improvised one can only be observed.

Alerts print `confidence unstated` until the daemon sends the field and the
relay stops dropping it. That is `stacktrace-ai/stacktrace#46`. Printing a grade
we were not sent would be worse than saying we do not have one.

Two questions is a floor. Anything finer — per-rule muting, per-project
thresholds, quiet hours — belongs to the policy system or to the CLI, and is
reachable through `/stacktrace:mute` and its siblings. If onboarding grows a
third question, that is evidence the policy system needs a settings surface, not
that this skill needs another page.

The plugin now writes one file. It holds presentation choices only. Delivery
state stays where ADR-0031 put it, and nothing about a cursor, a retry or an
acknowledgement goes near it.
