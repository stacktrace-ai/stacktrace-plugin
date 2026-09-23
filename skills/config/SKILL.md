---
name: config
description: Show what Stacktrace detects and what usage metrics it sends, and turn the metrics off.
disable-model-invocation: true
---

# Stacktrace config

The same screen the session-start hook shows once after install, on demand,
with the one question the hook cannot ask. No wizard, no second question, no
waiting on the network.

Usage metrics are already running when this screen appears. It discloses first
and offers the off switch second. Never say "opt in": there is nothing to opt
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

Row two of the wordmark ends in a trailing space. Keep it, or the `E` sits a
column short.

With `NO_COLOR` set, replace the three wordmark rows with the word
`STACKTRACE`. Everything else is unchanged.

## 3. Ask

`AskUserQuestion`, one call, two options, in this order:

- **Keep it on**: the events above, as they happen.
- **Turn it off**: nothing is published, and the identifier is deleted.

Never guess the answer.

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
command for them to run. Do not retry it, and do not write a file instead.
This plugin writes no preference of its own; the CLI owns the setting
(stacktrace ADR-0039).

## 5. Close

One short paragraph: what is running now. If the command failed, say that
instead of implying it worked.

Do not offer to run it again. Do not repeat the command list.
