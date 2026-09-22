---
id: 0006
title: Welcome someone once, and ask about analytics there
status: accepted
date: 2026-09-21
supersedes: null
superseded-by: null
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

It asks once, records the answer, and never asks again. Opt in is the
highlighted answer and a keystroke is still required to take it.

It is a screen, not a wizard. No progress bar, no multi-step flow, no waiting on
the network.

## Alternatives considered

**Show it automatically on first run.** Rejected: `SessionStart` guidance is
model context, not user output, and the plugin has nowhere to print at session
start without inventing one. A banner that appears unbidden on the first prompt
of the day is also the thing people disable.

**Fold it into `/stacktrace:configure`.** Rejected: configure answers "is this
working", which someone runs when it is not. The welcome answers "what is this",
asked at a different time, and merging them makes the failure path longer.

**Send without asking, with an opt-out flag somewhere.** Rejected on law.
ePrivacy Directive Article 5(3) requires consent before storing or accessing
information on a user's terminal equipment. EDPB Guidelines 2/2023, adopted 7
October 2024, closes each exit: paragraph 6, the trigger is "information" rather
than personal data, so anonymity is irrelevant; paragraph 36, the scope includes
"customized software", so not being a browser does not help; paragraph 53, *"The
fact that this information is being produced locally does not preclude the
application of Article 5(3) ePD"*, which defeats the argument that counts
computed here are ours to send. France permits a narrow exemption under CNIL
Sheet n°16 on seven cumulative conditions. The UK ICO requires consent.

**Highlight opt out instead.** Rejected. Most people take the highlighted
answer, and a product that wants to know which rules fire needs enough installs
answering yes for the number to mean anything. The screen states every event
before the cursor gets there, so the person taking the highlighted answer has
read what it does.

This is a different question from the one above and is not settled by the same
paragraphs. A pre-selected answer is not consent by itself: *Planet49*
C-673/17 held a pre-ticked box invalid, and it is the same case cited above for
anonymity. What distinguishes this screen is that nothing proceeds until the
person presses a key, so the selection is a highlight rather than a completed
answer. That is a real distinction and it is arguable rather than safe.
Confidence that a regulator would accept it: moderate. The design is built so
that losing the argument costs one character, because the default lives in the
screen and not in the CLI.

The clause that carries the risk is the one that must not move: absence of an
answer is `off`. A machine that never ran the welcome sends nothing. Whoever
revisits this should change the highlight before changing that.

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
sets `disable-model-invocation: true`, so a person opens it and the model never
starts it mid-task.

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

  > Opt in    Send those                        (default)
    Opt out   Send nothing

  Read back anything sent:  stacktrace telemetry show
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

Not here. The welcome screen runs `stacktrace telemetry on` or
`stacktrace telemetry off`, and the CLI owns the setting, in the same idiom
ADR-0005 already uses for Slack, where the welcome runs `stacktrace slack
connect` rather than writing a credential.

The CLI has to own it because the CLI sends the events and runs without this
plugin. A preference in `~/.claude/stacktrace-plugin.json` would be read by
nothing on a machine that never installed the plugin, and a second copy of the
setting is a second answer to the same question.

`scripts/preferences.py` gains no key.

### The highlight is not the stored default

Two different defaults, and conflating them is the mistake this section exists
to prevent.

| | Default | Why |
| --- | --- | --- |
| The screen's cursor | opt in | most people take the highlighted answer, and the events are stated above it |
| A missing settings file | `off` | nobody answered, and silence is not consent |

Someone who installs the CLI and never runs `/stacktrace:welcome` sends
nothing, forever, with no prompt and no flag. That is the clause Article 5(3)
actually turns on. The highlight only moves the cursor for a person looking at
a screen that has already told them what it will send.

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

The welcome now depends on the CLI for the setting as well as for Slack. The
screen already refuses to run without the CLI, so the failure stays in one
place.

Opt in is the highlighted answer, so the data will describe people who saw the
screen and did not move off it. That is a larger and less self-selected group
than an opt-out default would produce, and it is still not everyone: an install
that never runs the welcome is absent entirely. Any decision made from the data
has to say which population it rests on.

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
