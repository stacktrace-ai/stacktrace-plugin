---
id: 0006
title: Welcome someone once, and ask about analytics there
status: accepted
date: 2026-09-21
supersedes: null
superseded-by: null
amended-by: 0007
---

Subsystem: the agent plugin. The CLI half, which sends the events, is
`stacktrace-ai/stacktrace` ADR-0037.

## Motivation

A first run says nothing. `scripts/session_start.sh` emits its guidance as
`additionalContext`, which reaches the model and is never shown to the user.
Someone installs the plugin, relaunches, and waits for a sign that it worked.
Nothing arrives, because nothing is meant to.

They also do not know what they have bought. A person who installs a tool
called Stacktrace and is told nothing will assume it watches for everything,
notice that most of what they feared is not reported, and conclude it is broken
rather than deliberately narrow.

Separately, if this product measures its own use, the moment to ask is the same
moment. Asking later means asking someone who has already been measured.

## Use cases

A developer installs the plugin, relaunches, and runs `/stacktrace:welcome`.
They see what will be detected, what is sent if they opt in, and they answer one
question.

A developer who wants none of it moves one line down and is not asked again.

A developer reading the output with `NO_COLOR` set gets the same words with no
glyphs.

Someone evaluating the tool for a security team reads the same screen and can
tell a colleague exactly what it sends.

A developer who opted in wants to check what was actually sent, and runs
`stacktrace telemetry show`.

## Functionality

The welcome runs when a person asks for it, once, and records one answer.

It states what is detected as it is on the day it runs.

It names every event before asking about any of them, and says plainly that a
finding's content is never among them.

It asks once, records the answer, and never asks again. Usage metrics are
already running when the screen appears, so it discloses first and offers the
off switch second. Keeping them on is the highlighted answer.

It is a screen, not a wizard. No progress bar, no multi-step flow, no waiting on
the network.

## Alternatives considered

**Wait for someone to run `/stacktrace:welcome`.** Rejected, and it was the
first draft's answer. It works while nothing is sent until the screen is read.
It stops working the moment usage metrics are on by default, because then the
screen is a disclosure and a disclosure that waits to be asked for is not one.
Nothing makes a person run the command.

**Show it on every session start.** Rejected: a banner on the first prompt of
the day is the thing people disable, and the fourth one teaches the reader to
skip it. What survives is showing it exactly once.

**Fold it into `/stacktrace:configure`.** Rejected: configure answers "is this
working", which someone runs when it is not. The welcome answers "what is this",
asked at a different time, and merging them makes the failure path longer.

**Ask before anything is sent.** Rejected, and this is the decision that
shapes the rest of the screen. `stacktrace-ai/stacktrace` ADR-0039 makes usage
metrics on by default, so they are already running before anyone opens this
screen. A screen that asked "may we?" would be asking about something that had
already happened, which is the failure this ADR was written to avoid in the
first place.

What is left is worth more than a question: disclosure that arrives before the
user has anything to regret, and an off switch in the same breath. The screen
therefore states every event and every field first, and offers the switch
second. It never uses the words "opt in", because there is nothing to opt into.

**Say nothing and leave it to the README.** Rejected. The README is read by
people evaluating the tool, not by people running it, and a default that only
appears in a document nobody opens is a default nobody can find. ADR-0039
requires that a user be able to disable telemetry before normal use; this screen
is how that requirement is met for the plugin.

**Highlight turning it off.** Rejected. Most people take the highlighted answer,
and a product that wants to know which rules fire needs enough installs
reporting for the numbers to mean anything. The screen states every event and
every field above the cursor, so whoever takes the highlight has read what it
does.

**One last event recording the opt-out.** Rejected: it is a transmission from
someone who has just said stop transmitting, and no wording makes it read
otherwise. Under an opt-in default it is also unnecessary, because nothing was
ever sent to stop.

**Three states, with counting held locally by default.** Rejected once events
became immediate. Local counting existed so a default could collect without
transmitting. When each event is sent as it happens there is nothing to
accumulate, so the middle state has no content and would only be a name for
"off" that sounds busier.

**Batch the events and send once a day.** Rejected: the signal a maintainer
needs is that a rule fired, and a day's delay on that is a day of not knowing
whether the tool works. The cost is real and is recorded under Consequences: a
stream of immediate events discloses when someone works, which a daily total
does not.

**Count which `/stacktrace:` commands are run.** Rejected: nobody would act on
it. It also required counting inside the CLI's command dispatch, which put a
filesystem write on every invocation of a tool that otherwise does not touch
disk to answer `--help`.

**Send the finding so we can see what fired.** Rejected without qualification.
A finding names a rule, a session and an anchor, and the product's whole claim
is that session-derived material stays on the machine. The counter answers the
question that matters, which is whether the tool produced anything at all.

**Say "security findings" and leave it there.** Rejected: that claim is what
makes the tool look broken. Someone told "security", who then never sees a
finding about a category we removed on purpose, has been misled by omission.

**Skip the logo.** Rejected: it costs three lines and it is the only moment the
product introduces itself. Kept small enough that it does not become the point.

## Design

### Where it lives

A new skill, `skills/welcome/SKILL.md`, invoked as `/stacktrace:welcome`. It
sets `disable-model-invocation: true`, so the model never starts it mid-task on
its own reading of a conversation.

### Showing it once, without being asked

`scripts/session_start.sh` looks for `~/.claude/stacktrace-welcomed`. When it is
absent, the hook creates it and returns the screen as `systemMessage`, which
Claude Code shows to the user at session start with no prompt and without the
model. When it is present the hook emits the monitor contract alone.

`additionalContext` was the first attempt and could not work. It reaches the
model, and the model says nothing until the user does, so the screen appeared
nowhere at start. It also asked the model to run `/stacktrace:welcome`, which
sets `disable-model-invocation: true` and is therefore closed to it.

The hook reads the screen out of `skills/welcome/SKILL.md` rather than carrying
a copy. A startup message cannot take an answer, so the hook replaces the two
option lines with the off command. `/stacktrace:welcome` still shows the full
screen and asks the question when someone runs it.

The marker is written *before* the screen is shown, not after. A crash between
the two costs one welcome. The other order costs a welcome on every session
until something succeeds, which is the banner rejected above.

A marker is not a preference. It records that we have said hello, not what the
user answered, and the CLI still owns every setting.

If the marker cannot be written — a read-only home, a full disk — the hook emits
the contract and no welcome. Detection is the hook's job and the screen is not;
a disclosure that takes the monitor down with it is a worse trade than a missed
disclosure.

`scripts/validate_plugin.py` names it, so gaining or losing it fails review
rather than a session.

### The screen

One screen. Everything is 72 columns or narrower, so it survives an 80-column
terminal with a prompt gutter.

```
  ┌─┐┌┬┐┌─┐┌─┐┬┌─┌┬┐┬─┐┌─┐┌─┐┌─┐
  └─┐ │ ├─┤│  ├┴┐ │ ├┬┘├─┤│  ├┤ 
  └─┘ ┴ ┴ ┴└─┘┴ ┴ ┴ ┴└─┴ ┴└─┘└─┘

  we watch your agents, so you don't have to


  DETECTION POLICIES

  credential-egress
    Credential-shaped material reached an outbound call.

  agent-blocked
    Why the agent stopped, in words, with what to do about it.

      quota_exhausted     Spend limit reached. Stops the session.
      policy_blocked      A safety check refused. Stops the session.
      upstream_refused    A service refused the request.
      provider_throttled  Too many requests, too quickly.


  USAGE METRICS

  We publish 4 events, as they happen: you installed, a session
  started, a finding was delivered and which one it was, an error
  and its type. Every event also carries the install id, CLI
  version and OS name.

  We NEVER publish the finding itself, or any prompts, file names,
  paths or repo names. We only publish those counters and that
  metadata, so we know the tool works.

  > Keep it on    Publish those                 (default)
    Turn it off   Publish nothing

  See exactly what can be sent:  stacktrace telemetry show
```

### The wordmark

Three rows, 30 columns, box-drawing characters. It renders in one line of output
rather than a paint.

Row two ends in a trailing space. Without it the `E` sits one column short and
the wordmark looks broken in any terminal or editor that strips trailing
whitespace. A test asserts all three rows are the same length.

Under `NO_COLOR` the wordmark is replaced by the word, because a wordmark drawn
from box characters is decoration, and the rule about colour not carrying
meaning applies to it too.

### The four events

Named in full on the screen before the question is asked. The list is
exhaustive.

| Event | Carries | When |
| --- | --- | --- |
| `installed` | nothing | first run |
| `session_started` | nothing | a session begins |
| `finding_delivered` | rule, severity, sink, reason | a finding reaches a sink |
| `error` | exception class name | an error is caught |

Every event also carries the install id, the CLI version and the OS name.

`finding_delivered` carries a rule name drawn from the catalogue, a severity
from `Literal["low","medium","high"]`, a sink name from the registry in that
repository's ADR-0036, and for `agent-blocked` a reason code. Four closed sets,
no free-text field, and no part of the finding itself.

### The reason codes

`agent-blocked` is the rule a person is most likely to see, and "the agent
stopped" is not a number anyone can act on. Counting the reason is what
separates a spend limit from a rate limit.

The codes are listed under the rule that produces them, not under the usage
question. They are what the tool can tell you, which is the thing someone
reading a welcome screen wants. Listing them a second time beside the consent
question would make a capability read as a disclosure, and pad the one section
that has to stay short enough to be read.

The usage paragraph says a finding was delivered "and which one it was", which
covers the rule and the reason without repeating a list that is already on the
screen. Someone answering the question has seen the whole vocabulary.

| Reason | What happened | Who can act | Ends the session |
| --- | --- | --- | --- |
| `quota_exhausted` | Spend limit reached; calls stop until it resets | user | yes |
| `policy_blocked` | A safety check refused, and will keep refusing | user | yes |
| `upstream_refused` | A service refused the request | upstream | no |
| `provider_throttled` | Too many requests too quickly; clears itself | upstream | no |

Only the code is sent. The other three columns are functions of it, held in
`detector/blocked.py`, so sending them would be sending the same fact three
more times and inviting the copies to disagree.

`error` carries the exception class name and never the message. A message
carries paths, and `RemoteServerError: could not reach api.internal.acme.com` is
a customer's hostname in an event property.

### Reading back what was sent

Every event that is accepted is also written to a local file, so the screen's
claim can be checked rather than believed. `stacktrace telemetry show` prints
it, newest first, along with the exact body of the most recent one.

The plugin does not implement this. It names the command, and ADR-0037
specifies the file, the cap and the format.

### Where the preference lives

Not here. The welcome screen runs `stacktrace telemetry off` when someone asks
for that, and the CLI owns the setting.

The CLI has to own it because the CLI sends the events and runs without this
plugin. A preference in `~/.claude/stacktrace-plugin.json` would be read by
nothing on a machine that never installed the plugin, and a second copy of the
setting is a second answer to the same question.

`scripts/preferences.py` gains no key.

### What the screen can and cannot change

| | Value | Owned by |
| --- | --- | --- |
| A missing settings file | `on` | the CLI, ADR-0039 |
| Unreadable or invalid settings | `off` | the CLI, ADR-0039 |
| The screen's cursor | keep it on | this ADR |

The screen changes the cursor and nothing else. It does not decide the default,
it reports it. Someone who installs the CLI and never runs
`/stacktrace:welcome` is already sending, which is exactly why the screen leads
with the list rather than with the question.

The second row is the one to leave alone. A preference that cannot be read
resolves to `off` rather than to the default, so a corrupted file can never
re-enable what somebody turned off.

## Consequences

A person can answer "what does it do" from one screen, and a security reviewer
can answer "what does it send" from the same one.

The screen is a claim that has to stay true. It names the rules that exist, so
it is wrong the day one lands or one is removed.

**Immediate events disclose when someone works.** A stream of `session_started`
carries start times, and across weeks that is working hours, timezone and
absences, per install id. A daily total would not have carried it. This is the
price of seeing a finding land on the day it fires, it was taken deliberately,
and `session_started` is the event that carries it. Dropping that one event
removes the profile and keeps the finding signal.

The welcome depends on the CLI for the setting. It already refuses to run
without the CLI, so the failure stays in one place.

The data describes everyone who did not turn it off, including people who never
opened this screen. That is a larger and less self-selected sample than an
opt-in default would produce, and it moves the obligation from consent to
disclosure: the screen has to be findable, and it has to be true on the day it
is read.

That obligation is the reason this screen exists at all, and it is also its
weakest point. Nothing makes a person run `/stacktrace:welcome`.

## Open issues

Nothing checks the welcome against the real catalogue. The rules live in
`stacktrace-ai/stacktrace`, this repository cannot import them, and a screen
that drifts from the detector is worse than no screen. The options are a
generated file, a check that runs only when the CLI is installed, or accepting
the drift and dating the claim.

Whether `/stacktrace:welcome` and the onboarding in ADR-0005 are one skill or
two is unsettled. Both open with a person asking, both hand off to the CLI, and
two commands that each half-introduce the product is worse than either alone.

The `NO_COLOR` fallback for the wordmark is asserted here and implemented in the
skill's own text, so nothing enforces it.

The screen says "as they happen" and the CLI queues events when the machine is
offline. A person who reads the screen literally and then watches a plane
journey produce nothing has been told something slightly untrue. ADR-0037 owns
the queue; whether the screen should mention it is unresolved.
