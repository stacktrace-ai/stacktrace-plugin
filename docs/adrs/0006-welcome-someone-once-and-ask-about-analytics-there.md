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
and they answer one question about analytics.

A developer who wants none of it answers no and is not asked again.

A developer reading the output with `NO_COLOR` set gets the same words with no
glyphs.

Someone evaluating the tool for a security team reads the same screen and can
tell a colleague exactly what it sends.

## Functionality

The welcome runs when a person asks for it, once, and records one answer.

It states the catalogue as it is on the day it runs, including that the list is
short on purpose.

It names the one stage that sends anything off the machine, and that the stage
is off unless asked for.

It asks about analytics once, records the answer, and never asks again.

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

**Default analytics on, with an opt-out flag nobody reads.** Rejected: this
product's pitch is that it reads sensitive material and does not leak it. A
default that sends anything, however harmless, is the sentence a security
reviewer quotes back.

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

```
  ┌─┐┌┬┐┌─┐┌─┐┬┌─┌┬┐┬─┐┌─┐┌─┐┌─┐
  └─┐ │ ├─┤│  ├┴┐ │ ├┬┘├─┤│  ├┤
  └─┘ ┴ ┴ ┴└─┘┴ ┴ ┴ ┴└─┴ ┴└─┘└─┘

  Watches what your coding agent actually did, and tells you
  when something needs you.
```

Three rows, 32 columns, box-drawing characters. It fits an 80-column terminal
with room and renders in one line of output rather than a paint. Under
`NO_COLOR` the wordmark is replaced by the word, because a wordmark drawn from
box characters is decoration, and the rule about colour not carrying meaning
applies to it too.

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

### The analytics question

One question, asked once:

```
  Send anonymous usage counts to help us decide what to build?

  > No      Nothing is sent. This is the default.
    Yes     Counts only. Never a prompt, a finding, a path or a file name.
```

Default no. The answer is recorded by `scripts/preferences.py` under
`analytics`, in `~/.claude/stacktrace-plugin.json`, the one file this plugin
writes. A missing file means no.

**This ADR decides that we ask, and how. It does not decide what is sent, to
whom, or whether anything is sent at all.** Those need a vendor and an event
list, and neither exists. Until they do, answering yes records a preference and
nothing transmits.

That ordering is deliberate. A consent question written after a vendor is
chosen tends to describe whatever the vendor happens to collect.

### What it says is never sent

Stated plainly, because it is the reason someone would keep the tool:

- no prompt, argument or tool result
- no file contents and no file paths
- no finding text

The exception is named rather than hidden: `--reasoning`, off unless asked for,
hands the session to the agent's own provider.

## Consequences

A person can answer "what does it do" from one screen, and a security reviewer
can answer "what does it send" from the same one.

The screen is a claim that has to stay true. It names three rules, so it is
wrong the day a fourth lands or one is removed.

Asking about analytics before anything sends means the preference sits unused
for a while. That is the correct order, and it looks like dead code until the
other half lands.

## Open issues

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
