---
name: onboarding
description: Ask once how you want Stacktrace to reach you, and connect Slack if you choose it.
disable-model-invocation: true
---

# Stacktrace onboarding

Two questions, asked once. Ask them with `AskUserQuestion`, one question per
call, in order. Never guess an answer.

Do not ask which kinds of finding the user cares about. That is a policy
question and the policy system owns it. Collecting an answer here would create a
second place where delivery is filtered.

## Before asking

Run `command -v stacktrace`. If it is absent, say so, point the user at
`/stacktrace:configure`, and stop. Do not install anything.

## 1. How do you want to be notified?

- **This session** — the alert appears in the conversation.
- **This session and the desktop** — also calls `PushNotification`. Say that the
  host suppresses the desktop banner while the terminal has focus, so a quiet
  desktop during testing is expected rather than broken.
- **This session, the desktop, and Slack** — reaches the user when no session is
  running, which the first two cannot.

Write the answer to `~/.claude/stacktrace-plugin.json`, creating it if needed
and preserving any other keys already in it:

```json
{
  "desktop_notifications": true
}
```

That is the only file this plugin writes. `scripts/session_start.sh` reads it at
session start and tells the model what to do. Nothing else reads it, and no
delivery state ever goes in it.

The change takes effect at the next session start, because the contract is
handed to the model once. Say so rather than implying it applies immediately.

## 2. Slack, only if they chose it

Hand off to the CLI. Run `stacktrace slack connect`, passing a stable opaque
project id and a short safe project label. Never send a filesystem path as a
label or an identity.

The command prints a verification URL and a pairing code. Tell the user to open
the URL, confirm the code in Slack, confirm the device and project, and
subscribe. Installing the workspace is not subscribing, so do not report success
until the CLI does.

There is no Slack preference to store. A subscribed connection is the answer,
and the adapter already records it.

Never read a credential file into the conversation, never ask the user to paste
a token, and never print a recipient id. Report a pending or admin-blocked state
as what it is.

## When it is done

Say in one short paragraph what was recorded and what was not. If Slack is
pending, say the in-session path already works and Slack will start carrying
findings once the pairing completes. Never the reverse.
