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

A developer who wants none of it takes the default and is not asked again.

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

It asks once, records the answer, and never asks again. The default sends
nothing.

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

**Default on, with an opt-out.** Rejected on law. ePrivacy Directive Article
5(3) requires consent before storing or accessing information on a user's
terminal equipment. EDPB Guidelines 2/2023, adopted 7 October 2024, closes each
exit: paragraph 6, the trigger is "information" rather than personal data, so
anonymity is irrelevant; paragraph 36, the scope includes "customized software",
so not being a browser does not help; paragraph 53, *"The fact that this
information is being produced locally does not preclude the application of
Article 5(3) ePD"*, which defeats the argument that counts computed here are
ours to send. France permits a narrow exemption under CNIL Sheet n°16 on seven
cumulative conditions. The UK ICO requires consent.

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

  Watches what your coding agent actually did, and tells you
  when something needs you.


  WHAT GETS DETECTED

    credential-egress   Credential-shaped material reached an
                        outbound call
    agent-blocked       Why the agent stopped, in words, with
                        what to do about it


  USAGE

  Opt in and we send four things as they happen: that you
  installed, that a session started, that a finding was
  delivered, and the type of any error.

  When the agent is blocked we also send why, from this list
  and nothing else:

    quota_exhausted     Spend limit reached
    policy_blocked      A safety check refused
    upstream_refused    A service refused the request
    provider_throttled  Too many requests, too quickly

  The finding itself is never sent. We count that one was
  delivered, which is how we tell the tool is working.

  Nothing else leaves this machine. Not a prompt, a file, a path,
  a repo name, a command you ran or the text of a finding.

  > Opt out   Nothing is sent                        (default)
    Opt in    The four above, as they happen

  Everything we send is also written down here, so you can read
  it back at any time:  stacktrace telemetry show
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

Opting out is the default, so most installs will send nothing and the data will
describe the people who chose to be described. Any decision made from it has to
say so.

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
