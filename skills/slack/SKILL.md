---
name: slack
description: Connect Stacktrace to Slack, inspect connection status, send a synthetic test, or disconnect a device.
---

# Stacktrace Slack

Use the installed `stacktrace-slack` adapter through
`${CLAUDE_PLUGIN_ROOT}/scripts/slack.py`. Slack is optional; preserve the native
Claude monitor and local detection regardless of this workflow's outcome.

Select `connect`, `status`, `test`, or `disconnect` from the user's intent.
If no action was given, inspect `status`. Invoke `test` only when the user
requests a synthetic Slack message; invoke `disconnect` only when they request
revoking this connection. No Slack token or recipient ID is needed.

Run the script with Python 3 and pass one JSON object on stdin. Fields:

| Field | Meaning |
| --- | --- |
| `action` | One of the four actions above. |
| `service_url` | Optional HTTPS origin; otherwise adapter uses `STACKTRACE_SLACK_URL`. Use the configured deployment, never invent an endpoint. |
| `connection` | Optional local connection name, defaults to `default`. |
| `project_id` | Connect only: stable opaque project identity from Stacktrace. |
| `project_label` | Connect only: short safe display label. |
| `device_label` | Connect only: optional safe display label, defaults to `My device`. |

Pass JSON as stdin data, or a properly quoted literal heredoc with a delimiter
absent from the data. Never interpolate raw user text or `$ARGUMENTS` into a
shell command. The script dispatches a fixed executable with an argument list.
Never read credential files into the conversation or ask users to paste tokens.

Connect opens OAuth, then the user confirms the code and device/project in
Slack and explicitly subscribes. Installing a workspace alone does not
subscribe anyone. If a required service origin, project identity, or safe
project label is missing, ask for that value; never send a local filesystem
path as a label or identity. Explain pending/admin-blocked states without
claiming connection succeeded. Retrying connect resumes an unexpired pairing.

Report the adapter's actual outcome. A test marked `accepted` is queued, not
proof of delivery or reading; `uncertain` means check Slack before trying
another message. If the adapter is missing, follow the optional installation
instructions in the repository README with the user's authorization. Do not
install it automatically merely because the plugin loaded.

This workflow manages the connection only. It does not turn Claude monitor
lines or transcripts into Slack messages.

Automatic finding delivery belongs in the shared Stacktrace core/daemon through
the Slack adapter, and the installed core does not implement it. No CLI code
path hands a finding to the adapter, so a healthy, subscribed connection still
carries nothing on its own: every Slack message to date was sent by hand. When
a user asks why a finding did not reach Slack, say that the delivery path does
not exist yet rather than treating it as a configuration fault. Never
compensate by publishing from here -- that is the boundary this bridge exists
to hold, not an inconvenience to route around.
