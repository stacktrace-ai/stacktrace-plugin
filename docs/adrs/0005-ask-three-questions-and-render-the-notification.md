---
id: 0005
title: Ask three questions at onboarding, and render the notification rather than improvise it
status: accepted
date: 2026-09-20
supersedes: null
superseded-by: null
---

## Context

The plugin has no onboarding and no renderer, and both absences are invisible
until someone looks for them.

On a healthy first run the plugin says nothing at all. `scripts/session_start.sh`
emits its guidance as `additionalContext`, which reaches the model and is never
shown to the user, and its healthy branch ends "Say nothing about setup unless
the user asks." A user who installs the plugin, relaunches, and waits for a sign
that it is working waits forever. The documented first run ends by telling them
to type `/stacktrace:status`, which is a diagnostic, not a welcome.

The plugin also never asks what the user wants. Every eligible finding is
delivered the same way to everyone: the daemon's gate is
`severity in {"high", "critical"} and confidence == "high"`, and the only
delivery path is the session monitor. Whether this person cares about a stalled
loop as much as a leaked credential, and whether they want to be interrupted in
the terminal, on the desktop, or on their phone, is never asked and has nowhere
to be recorded.

Rendering is in the same state. There is no colour handling anywhere in this
repository: `CLAUDE.md` states that colour is never the only carrier of meaning
and that `NO_COLOR` is honoured, and nothing implements either rule. The alert a
user actually sees today — a warning glyph, the severity, and the daemon's
generic title — is produced by the model improvising from one line of the
`SessionStart` contract. It is not wrong, but it is not specified, so it varies
by model, by session, and by how much context the model is holding at the time.

What the plugin can influence is exactly three surfaces, and two of them are fed
from outside this repository:

| Surface | Controlled by |
| --- | --- |
| `Monitor event: "…"` | `monitors/monitors.json` → `description` |
| `PushNotification(title, body)` | the daemon's `Notification` |
| The inline alert in the conversation | the `SessionStart` contract text |

The wire format bounds the third. `_safe_event` reduces every event to exactly
`event_id`, `rule_id`, `severity`, `title` and `body` before the plugin sees it.
`confidence` is not among them, so the plugin cannot label severity and
confidence separately, which `CLAUDE.md` requires of it.

## Decision

Onboarding asks three questions, in this order, and the plugin stores none of
the answers.

```
  first interactive session after install
              │
              ▼
  ┌───────────────────────────────────────────────┐
  │ 1  What do you care about?                    │
  │    security findings · reliability findings   │
  │    · both                                     │
  └───────────────────┬───────────────────────────┘
                      ▼
  ┌───────────────────────────────────────────────┐
  │ 2  How do you want to be notified?            │
  │    in this session · + desktop notification   │
  │    · + Slack                                  │
  └───────────────────┬───────────────────────────┘
                      │ Slack chosen?
              no ─────┴───── yes
              │              │
              │              ▼
              │   ┌────────────────────────────────┐
              │   │ 3  hand off to the CLI:        │
              │   │    `stacktrace slack connect`  │
              │   │    opens OAuth, user confirms  │
              │   │    the pairing code in Slack   │
              │   └────────────────┬───────────────┘
              │                    │
              ▼                    ▼
        answers are written by the CLI, into the CLI's state
```

The first question is about finding families, not rules: the security family
(a credential reaching an outbound call, an injected instruction, a vulnerable
component reached) and the reliability family (a stalled loop, a hung call)
carry their own severity ladders and are the coarsest honest choice. The second
is about delivery surfaces, not thresholds. The third is a handoff, not a
workflow.

Every answer is recorded by the CLI in the CLI's state. The plugin runs the
conversation and holds nothing: it has no state directory, and a preference that
outlives a session is not its to keep. The onboarding skill is the only place
these questions are asked, it runs once, and a user who skips it gets today's
defaults rather than a broken plugin.

Slack OAuth is kicked off from the CLI and never from the plugin. The plugin
names the command and reports what it printed. No token, recipient id, or
service origin is ever read into the conversation.

The notification is rendered to a fixed specification, written into the
`SessionStart` contract, rather than left to the model. The specification names
the glyph, the order of the fields, and the words:

```
  ⛔ Stacktrace  high severity · high confidence
     A tool result carried obfuscated, instruction-shaped content
     stacktrace-injection-marker · /stacktrace:why for the evidence
```

Severity and confidence are always printed as two labelled grades, never merged
into one word and never implied by colour alone. Severity selects the glyph and
the colour; confidence is printed. A finding whose confidence the daemon does
not send is printed as `confidence unstated` rather than silently assumed, which
is the only honest rendering while the wire format still omits it.

`NO_COLOR` is resolved in `scripts/session_start.sh`, which already reads the
environment and already emits fixed strings. When it is set, the contract tells
the model to drop the glyph and the colour and keep every word. The model cannot
read the environment; the hook can, and this is the only place the two meet.

## Consequences

A user learns what the plugin will do for them in the session where it can still
be changed, instead of discovering the defaults by being surprised by one.

Rendering stops varying between sessions. A specified format can be reviewed,
tested against `NO_COLOR`, and corrected; an improvised one can only be observed.

The plugin gains a question it cannot answer on its own. `confidence` is not on
the wire, so until the daemon sends it every alert prints `confidence unstated`.
That is deliberate: stating the gap is the rule this repository already holds
itself to, and a rendering that invents a grade it was not sent would be worse
than one that admits the field is missing. The daemon-side decision is recorded
in the CLI's own ADR; ADR-0004 in this repository records where the Slack half
of that work belongs.

Three questions is a floor chosen against a ceiling. Anything finer — per-rule
muting, per-project thresholds, quiet hours — is a policy the CLI already owns
or will own, reachable through `/stacktrace:mute` and its siblings. Onboarding
that grows a fourth question should be read as evidence that the CLI needs a
settings surface, not that this skill needs another page.

The three questions are asked by the plugin and answered into the CLI, so an
onboarding that runs against a CLI too old to record them must say so and stop,
rather than collect answers into nothing.
