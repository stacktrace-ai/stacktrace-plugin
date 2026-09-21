---
id: 0006
title: Welcome someone once, and ask about analytics there
status: accepted
date: 2026-09-21
supersedes: null
superseded-by: null
---

Subsystem: the agent plugin.

## Motivation

A first run says nothing. `scripts/session_start.sh` emits its guidance as
`additionalContext`, which reaches the model and is never shown to the user.
Someone installs the plugin, relaunches, and waits for a sign that it worked.
Nothing arrives, because nothing is meant to.

They also do not know what they have bought. The catalogue is three rules. Two
run on every session and one only when asked for. A person who installs a tool
called Stacktrace and is told nothing will assume it watches for everything,
notice that most of what they feared is not reported, and conclude it is broken
rather than deliberately narrow.

Separately, if this product ever measures its own use, the moment to ask is the
same moment. Asking later means asking someone who has already been measured.

## Use cases

A developer installs the plugin, relaunches, and runs `/stacktrace:welcome`.
They see what will be detected, what will not, what never leaves the machine,
and they answer one question about usage counts.

A developer who wants none of it picks "count nothing" and is not asked again.

A developer reading the output with `NO_COLOR` set gets the same words with no
glyphs.

Someone evaluating the tool for a security team reads the same screen and can
tell a colleague exactly what it sends.

A maintainer deciding which rule to delete reads counts that a user chose to
send, and can say which rules fired and which were acted on.

## Functionality

The welcome runs when a person asks for it, once, and records one answer.

It states the catalogue as it is on the day it runs, including that the list is
short on purpose.

It names the one stage that sends anything off the machine, and that the stage
is off unless asked for.

It lists every usage event by name before asking about any of them.

It asks once, records the answer, and never asks again. The default answer
transmits nothing.

It is a screen, not a wizard. No progress bar, no multi-step flow, no waiting
on the network.

## Alternatives considered

**Show it automatically on first run.** Rejected: `SessionStart` guidance is
model context, not user output, and the plugin has nowhere to print at session
start without inventing one. A banner that appears unbidden on the first prompt
of the day is also the thing people disable.

**Fold it into `/stacktrace:configure`.** Rejected: configure answers "is this
working", which someone runs when it is not. The welcome answers "what is
this", asked at a different time, and merging them makes the failure path
longer.

**List every rule with its severity ladder.** Rejected: a person deciding
whether to keep the tool wants the shape, not the catalogue.
`/stacktrace:findings` already prints what actually fired, which is the honest
form of that detail.

**Say "security findings" and leave it there.** Rejected: that claim is what
makes the tool look broken. Someone told "security", who then never sees a
finding about a category we removed on purpose, has been misled by omission.

**Ask about analytics on first send rather than at welcome.** Rejected: the
first send has already happened by then. Asking afterwards is asking someone to
consent to something already done.

**Default on, with an opt-out.** Rejected on law, not on taste. The instrument
is ePrivacy Directive Article 5(3), which governs reading or writing anything on
someone's terminal equipment and requires consent before it happens. EDPB
Guidelines 2/2023, adopted 7 October 2024, closes the three exits we would have
reached for. Paragraph 6: the trigger is "information", not personal data, so
anonymity does not help. Paragraph 36: "customized software" is in scope, so not
being a browser does not help. Paragraph 53: "The fact that this information is
being produced locally does not preclude the application of Article 5(3) ePD",
so "we only send counts we computed here" does not help either. France permits a
narrow exemption under CNIL Sheet n°16 on seven cumulative conditions. The UK
ICO requires consent. A default that is lawful in Paris and unlawful in London
is not a default.

**A binary yes or no.** Rejected: it forces a choice between the project
learning nothing and the user transmitting. Counting locally gives the user a
file they can read and gives us a number they can choose to send later, which is
strictly more than "no" offers either side.

**One last event recording the opt-out.** Rejected: it is a transmission from
someone who has just said stop transmitting, and there is no wording that makes
it read otherwise. Under the tri-state it is also unnecessary, because nothing
was sent to stop.

**A third-party vendor: PostHog, Google Analytics or Cloudflare Web
Analytics.** Rejected for now: each adds a processor, and its own
sub-processors, to the privacy page of a product whose pitch is that data does
not leave the machine. The service already has a batched, spooled uploader in
`remote/client.py` and one Postgres table is enough at this volume. PostHog
Cloud EU is the runner-up if first-party collection stalls.

**Skip the logo.** Rejected: it costs three lines and it is the only moment the
product introduces itself. Kept small enough that it does not become the point.

## Design

### Where it lives

A new skill, `skills/welcome/SKILL.md`, invoked as `/stacktrace:welcome`. It
sets `disable-model-invocation: true`, so a person opens it and the model never
starts it mid-task.

`scripts/validate_plugin.py` names it, so gaining or losing it fails review
rather than a session.

### The whole flow

Three screens. The first two are printed, the third follows the answer.

```
  ┌─┐┌┬┐┌─┐┌─┐┬┌─┌┬┐┬─┐┌─┐┌─┐┌─┐
  └─┐ │ ├─┤│  ├┴┐ │ ├┬┘├─┤│  ├┤ 
  └─┘ ┴ ┴ ┴└─┘┴ ┴ ┴ ┴└─┴ ┴└─┘└─┘

  Watches what your coding agent actually did, and tells you
  when something needs you.


  WHAT GETS DETECTED

  Always on
    credential-egress     Credential-shaped material reached an
                          outbound call
    agent-blocked         Why the agent stopped, in words, with
                          what to do about it

  Only when you ask for it
    deceptive-completion  Success was reported against evidence
                          of failure
                          Needs --reasoning. This is the one stage
                          that sends session content off this
                          machine, to your agent's own provider.

  Three rules, on purpose. More than ten others were written and
  removed after measuring them against real sessions. A rule earns
  its place by producing a finding somebody acted on.


  WHAT NEVER LEAVES THIS MACHINE

    no prompt, argument or tool result
    no file contents, no file paths
    no finding text

  The one exception is --reasoning above, and it is off unless you
  turn it on.


  One question next, about usage counts. Then you're set.
```

```
  USAGE COUNTS

  We count how the tool is used so we know which rules to keep.
  Counting starts now. Sending does not, unless you say so.

  What gets counted, in full:

    installed           once, on first run
    session_started     a session began
    finding_delivered   rule name, severity, and where it went
    command_run         which /stacktrace: command, nothing else
    error               error type and the CLI version

  Never counted: prompts, tool results, file contents, file paths,
  repository names, remote URLs, branch names, finding text,
  usernames, email addresses, or anything typed into a session.

  > Keep them here   Counted in ~/.claude/stacktrace/counts.json.
                     Nothing is sent. This is the default.
    Send them        Uploaded once a day to api.stacktrace.ai.
    Count nothing    The file is never written.

  Either way, you can read the file yourself:
    stacktrace telemetry show
```

```
  Counting locally. Nothing is sent.

  Change it any time:  stacktrace telemetry on | off | show
  Recorded in:         ~/.claude/stacktrace-plugin.json

  You're set. Findings appear in this session as they happen.
  Ask any time with /stacktrace:findings.
```

Everything is 72 columns or narrower, so it survives an 80-column terminal with
a prompt gutter.

### The wordmark

Three rows, 30 columns, box-drawing characters. It renders in one line of
output rather than a paint.

Row two ends in a trailing space. Without it the `E` sits one column short and
the wordmark looks broken in any terminal or editor that strips trailing
whitespace. A test asserts all three rows are the same length.

Under `NO_COLOR` the wordmark is replaced by the word, because a wordmark drawn
from box characters is decoration, and the rule about colour not carrying
meaning applies to it too.

### What it says is detected

Stated from the catalogue, not from a category name:

| Runs always | What it means |
| --- | --- |
| `stacktrace-credential-egress` | Credential-shaped material reached an outbound call |
| `stacktrace-agent-blocked` | Why the agent stopped, in words, with what to do |

| Runs only when asked | What it means |
| --- | --- |
| `stacktrace-deceptive-completion` | Success was reported against evidence of failure |

And the sentence that stops the tool looking broken: the catalogue is three
rules because more than ten others were written and removed after measurement
against real sessions. A rule earns its place by a finding somebody acted on.

`stacktrace-deceptive-completion` needs `--reasoning`, the only stage that sends
session content off the machine, to the agent's own provider. The welcome says
this in the same breath as the rule, not in a footnote.

### The three states

Named after Go's telemetry, which solved the same problem: a project that needs
usage data and a user base that will not accept an uploader.

| State | Counts written | Anything sent | Default |
| --- | --- | --- | --- |
| `local` | yes | no | yes |
| `on` | yes | once a day | no |
| `off` | no | no | no |

`local` is the default because it engages no consent requirement. Article 5(3)
governs gaining access to information on terminal equipment. A file this machine
writes and only this machine reads is not access by anyone else. Paragraph 53
above is about the moment data is sent back over the network, and in `local`
that moment never comes.

The commands:

```
stacktrace telemetry             print the current state
stacktrace telemetry local       count here, send nothing
stacktrace telemetry on          count here, upload once a day
stacktrace telemetry off         count nothing, delete file and id
stacktrace telemetry show        print the bytes that would upload
```

`show` is the load-bearing one. It converts "trust us" into "look for
yourself", which for this product is the whole argument.

### The events

Five, and the list is exhaustive. Anything not here is not counted.

| Event | Fields | When |
| --- | --- | --- |
| `installed` | none | first run |
| `session_started` | none | a session begins |
| `finding_delivered` | rule name, severity, sink | a finding reaches a sink |
| `command_run` | command name | a `/stacktrace:` command runs |
| `error` | error type, CLI version | an error is caught |

Sent with every event when the state is `on`: a random install id, the CLI
version, the OS name. Nothing else.

`finding_delivered` carries the rule name, not the finding. The rule name comes
from a fixed set of three. The severity comes from `Literal["low","medium","high"]`,
owned by `stacktrace_cli.detector.finding` per that repository's ADR-0010. The
sink comes from a fixed set of three. None of the three can carry user content,
which is why the event is safe to send and why no free-text field is admitted to
this table.

### Where the preference lives

`scripts/preferences.py` records it under `analytics`, in
`~/.claude/stacktrace-plugin.json`, the one file this plugin writes. A missing
file means `local`.

The counts do not live there. They belong to the CLI and the daemon, which are
the things that observe the events, and they go in
`~/.claude/stacktrace/counts.json`. The plugin records a preference and reads
nothing back.

## Consequences

A person can answer "what does it do" from one screen, and a security reviewer
can answer "what does it send" from the same one.

The screen is a claim that has to stay true. It names three rules, so it is
wrong the day a fourth lands or one is removed.

The default state writes a file nobody reads until an uploader exists. That
looks like dead code, and it is the correct order: the events are specified
before anything can send them, so the consent question is not written to
describe whatever a vendor happened to collect.

The counts file has to be worth reading on its own, because in the default
state it is the only artefact. If `stacktrace telemetry show` prints something
a user cannot interpret, the local state is theatre.

Splitting the preference from the counts puts the setting in the plugin and the
data in the CLI. Two repositories now have to agree on the name `analytics` and
on the three state values.

## Open issues

The detection section is not settled. It is carried over unchanged from the
first draft and a revision has been proposed on the team. Until that lands, the
screen above is accurate to the current catalogue and not to the intended
wording.

Nothing checks the welcome against the real catalogue. The rules live in
`stacktrace-ai/stacktrace`, this repository cannot import them, and a screen
that drifts from the detector is worse than no screen. The options are a
generated file, a check that runs only when the CLI is installed, or accepting
the drift and dating the claim.

Whether `/stacktrace:welcome` and the onboarding in ADR-0005 are one skill or
two is unsettled. Both open with a person asking, both write the same file, and
two commands that each half-introduce the product is worse than either alone.

The `NO_COLOR` fallback for the wordmark is asserted here and implemented in the
skill's own text, so nothing enforces it.

No uploader exists. The `on` state is specified and unbuilt, and this ADR does
not decide the endpoint's schema, its retention, or who at Stacktrace can query
it.

The CLI README has a "What leaves your machine" section that lists one outbound
call. The `on` state adds a second, and that section has to be rewritten in the
same change or the two documents contradict each other.
