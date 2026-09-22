---
name: welcome
description: Introduce Stacktrace, show what it detects, and disclose usage metrics once.
disable-model-invocation: true
---

# Stacktrace welcome

One screen, one question, once. Not a wizard: no progress bar, no second
question, no waiting on the network.

Usage metrics are already running when this screen appears. It discloses first
and offers the off switch second. Never say "opt in" — there is nothing to opt
into.

## 1. Check the CLI is there

Run `command -v stacktrace`. If it is absent, say so, point at
`/stacktrace:configure`, and stop. Do not install anything and do not print the
screen: every claim on it is about a program that is not on this machine.

## 2. Print the screen

Verbatim. Do not summarise it, reflow it, or add a preamble.

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

Row two of the wordmark ends in a trailing space. Keep it, or the `E` sits a
column short.

With `NO_COLOR` set, replace the three wordmark rows with the word
`STACKTRACE`. Everything else is unchanged.

## 3. Ask

`AskUserQuestion`, one call, two options, in this order:

- **Keep it on** — the four events above, as they happen.
- **Turn it off** — nothing is published, and the identifier, the queue and the
  record of what was sent are deleted.

Never guess the answer, and never skip the call because the screen shows a
highlighted option. A highlight is not an answer.

Do not ask which findings they care about. That is a policy question and the
policy system owns it.

## 4. Record it

Keeping it on needs no command. It is already the state, and writing a
preference to say so would turn a default into an answer.

Turning it off is one command:

```
stacktrace telemetry off
```

Report what it printed. If it fails, say telemetry is still on and repeat the
command for them to run — do not retry it, and do not write a file instead.
This plugin writes no preference of its own; the CLI owns the setting
(ADR-0039).

To see what has actually been sent, at any time: `stacktrace telemetry show`.

## 5. Close

One short paragraph: what is running now, and that the question will not be
asked again. If the command failed, say that instead of implying it worked.

Do not offer to run it again. Do not repeat the command list.
