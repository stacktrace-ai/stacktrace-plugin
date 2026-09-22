---
name: welcome
description: Introduce Stacktrace once, show what it detects, and settle usage telemetry.
disable-model-invocation: true
---

# Welcome to Stacktrace

One screen and one question. The screen says what the tool detects and names
every usage event before the question is asked. You show it, you ask, and the
CLI records the answer. You never answer for the user.

## Before the screen

Run `command -v stacktrace` and `printenv NO_COLOR` in one Bash call.

If `stacktrace` is absent, stop here. Tell the user to run
`/stacktrace:configure` first and come back. Do not show the screen or ask the
question: the CLI owns the telemetry setting, so there is nothing to record
without it.

## The screen

Print the block below inside a fenced code block, exactly as written. Keep the
two-space indent on every line and the trailing space at the end of the second
wordmark row; without it the last letter sits a column short. Do not shorten,
reflow, reorder or annotate it. It is 72 columns or narrower on purpose.

If `NO_COLOR` was set, replace the three wordmark rows with the single line
`  STACKTRACE` and print everything else unchanged.

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

## The question

Ask with `AskUserQuestion`. One question, two options, in this order so that
`Opt in` is the highlighted answer:

| Option | Description |
| --- | --- |
| `Opt in` | Send the four usage events, as they happen. |
| `Opt out` | Send nothing. |

Wait for the answer. Never pick for the user, never treat silence or a
dismissed prompt as an answer, and never run either command below before the
user has chosen.

## Recording the answer

Run `stacktrace telemetry on` for `Opt in` or `stacktrace telemetry off` for
`Opt out`. Report the command's actual output.

If the command exits non-zero, say so and show its output. Tell the user
nothing was recorded, that the installed CLI does not carry the telemetry
command yet, and that a CLI without it sends nothing. Do not retry with
another command, edit a config file, or write the setting anywhere yourself.
The setting lives in the CLI and nowhere in this plugin.

After a successful run, tell the user in one line that `stacktrace telemetry
show` reads back everything sent, and that running `/stacktrace:welcome`
again changes the answer.
