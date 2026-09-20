---
id: 0005
title: Ask two questions at onboarding, and specify how the alert is rendered
status: accepted
date: 2026-09-20
supersedes: null
superseded-by: null
---

Subsystem: the agent plugin. The integration view across the plugin, daemon,
sinks and CLI is `docs/specs/notification-delivery.md` in
`stacktrace-ai/stacktrace`.

## Motivation

The plugin has no onboarding and no renderer. Neither absence is visible until
you look for it.

On a healthy first run the plugin says nothing. `scripts/session_start.sh` emits
its guidance as `additionalContext`, which goes to the model and is never shown
to the user. The healthy branch ends with "Say nothing about setup unless the
user asks." Someone who installs the plugin, relaunches and waits for a sign
that it works will wait forever.

The plugin also never asks how the user wants to be told, and has nowhere to
record a different answer.

There is no colour handling anywhere in this repository. `CLAUDE.md` says colour
is never the only carrier of meaning and that `NO_COLOR` is honoured, and
nothing implements either rule. The alert a user sees is the model improvising
from one line of the contract. It is not wrong, but it is not specified, so it
varies by model, by session and by how much context the model is holding.

## Use cases

A developer installs the plugin and relaunches. Onboarding asks how they want to
be notified, connects Slack if they chose it, and says what was recorded.

A finding arrives while the developer is working. The alert appears in the
conversation in a fixed shape, with severity and confidence both shown.

A developer runs with `NO_COLOR` set. The same alert appears without the glyph
or emphasis, and loses no information.

A developer declines desktop notifications. No `PushNotification` call is made
for the rest of that session or any later one.

## Functionality

Onboarding runs once, is started by the user, and asks two questions. It records
presentation choices locally, through a script rather than by writing the file
itself. It does not record anything about which findings matter, because the
policy system owns that.

The alert has one specified shape. Severity and confidence are always both
printed as labelled grades. Neither is ever carried by a glyph or colour alone.

`NO_COLOR` is resolved by the hook, because the model cannot read the
environment.

## How an alert reaches the screen

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

The trigger is a line appearing on a stream, and the rule for handling it was
installed at session start. Nothing of the plugin's runs between the monitor's
stdout and the conversation, so there is nowhere for plugin code to format
anything. The specification is the artefact.

## Alternatives considered

**Let the skill write the preferences file directly.** An earlier revision of
this ADR said it would, and it is one less script to ship. Rejected: the three
ways a hand-written file goes wrong are all invisible after the fact, and the
skill would have to restate the file's schema in prose, where nothing checks it
against the hook that reads it.

**Leave rendering to the model.** It already produces a reasonable line.
Rejected: an unspecified format cannot be reviewed or tested, and it changes
between sessions for reasons the user cannot see.

**Ask a third question, about which findings matter.** Rejected: that is a
policy question and the policy system owns it. Collecting an answer here would
create a second place where delivery is filtered.

**Store presentation preferences in the CLI.** An earlier draft did this.
Rejected: the CLI is host-agnostic and has no business holding "should Claude
Code show a desktop notification".

**Store a Slack on/off preference.** Rejected: a subscribed connection is the
answer, and the adapter already records it. A second copy would go stale.

**Read `NO_COLOR` in the model.** Rejected: the model cannot read the
environment. The hook can, so the hook decides and tells it.

## Design

### Onboarding

```
  1  How do you want to be notified?
       this session · + desktop · + Slack

  2  Slack chosen? ──> run `stacktrace slack connect`
                        prints a URL and a pairing code;
                        the user confirms both in Slack
```

Asked with `AskUserQuestion`, one call per question, in order. The skill sets
`disable-model-invocation: true`, so the user opens this conversation and the
model never starts it mid-task.

Slack is a handoff. The plugin names the command and reports what it printed. No
token, recipient id or service origin is read into the conversation.

### Where each answer is stored

| Answer | Acted on by | Stored by |
| --- | --- | --- |
| inline alert format | the model, via the contract | the plugin |
| desktop notification on/off | the model, via `PushNotification` | the plugin |
| Slack on/off | the daemon | nothing; a subscribed connection is the answer |

```jsonc
// ~/.claude/stacktrace-plugin.json — written by scripts/preferences.py on the
// onboarding skill's behalf, read by scripts/session_start.sh.
// Absent means defaults.
{
  "desktop_notifications": true
}
```

`session_start.sh` already reads the environment, so it reads this too and emits
different guidance. Nothing else in the plugin reads it. No delivery state goes
in it.

The skill runs `scripts/preferences.py set <key> <true|false>` rather than
writing the file itself. A model writing JSON by hand has three failures nobody
can see afterwards: replacing the file instead of updating it, so keys it was
never asked about are gone; writing something that does not parse, which the
hook then treats as absent; and writing a key the hook does not read, which
looks like a preference that was recorded and does nothing.

The script updates one key, keeps keys it does not own, writes through a
temporary file in the same directory, and refuses an unknown key. Absent,
unreadable and malformed are one answer, and the same answer the hook reaches on
its own, because a preferences file is not load-bearing and failing a session
over one is worse than ignoring it.

Both find the file the same way, through `CLAUDE_CONFIG_DIR` and then `~/.claude`.
A reader and a writer that disagree about the path produce a preference recorded
where nothing looks, which is indistinguishable from one that was ignored. That
is why it is tested by writing with the script and reading through the hook,
rather than testing each side alone.

### Alert shape

```
  ⛔ Stacktrace  high severity · high confidence
     A tool result carried obfuscated, instruction-shaped content
     stacktrace-injection-marker · /stacktrace:findings for the evidence
```

Severity picks the glyph and the emphasis. Confidence is printed as its own
labelled grade. Both are always shown.

The event carries no `confidence` field today, because `_safe_event` drops it.
Until that changes the alert prints `confidence unstated`, and never guesses a
confidence from a severity.

### `NO_COLOR`

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
tested against `NO_COLOR`.

Alerts print `confidence unstated` until the daemon sends the field and the
relay stops dropping it. That is `stacktrace-ai/stacktrace#46`. Printing a grade
we were not sent would be worse than saying we do not have one.

The plugin now writes one file, holding presentation choices only. Delivery
state stays where ADR-0031 put it.

## Open issues

Two questions is a floor. Per-rule muting, per-project thresholds and quiet
hours belong to the policy system or the CLI. If onboarding grows a third
question, that is evidence the policy system needs a settings surface, not that
this skill needs another page.

The desktop notification is suppressed by the harness while the terminal has
focus. Onboarding says so, but a user who tests it with the terminal focused
will still see nothing and may read that as broken.

The alert points at evidence that cannot be fetched. It ends with
`/stacktrace:findings`, which works. `/stacktrace:why`, `/stacktrace:dismiss`
and `/stacktrace:mute` do not: they call `stacktrace finding`, and no such
command exists. A user reads an alert, asks why it fired, and gets an error.

That is not fixable here. The event carries five fields, which is enough to say
a rule fired and not enough to explain it. The evidence is in the daemon's
finding store, so `why` is a read from it by `event_id`. `dismiss` and `mute`
are writes that have to survive the session and mean the same thing whether they
come from this plugin or from Slack, so the mute key belongs to the policy
system's vocabulary. Tracked in ADR-0036 in `stacktrace-ai/stacktrace`.
