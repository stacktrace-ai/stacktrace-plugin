---
name: status
description: Report what Stacktrace is actually doing for this Claude session, including whether monitoring is live and whether Slack is connected.
disable-model-invocation: true
---

# Stacktrace status

Report what is actually running. Never infer that monitoring is live from the
plugin being loaded, and never round a partial state up to a working one.

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/doctor.py"
```

Present its five lines — CLI, daemon command, session, daemon, Slack — and its
verdict. The doctor already distinguishes the states that look alike; do not
re-derive them, and do not soften a `FAIL` into a warning.

## The distinction that matters most

**A stopped daemon is not a fault.** It runs only while a subscriber holds it
open and exits about five seconds after the last one leaves. Three different
situations produce "not running":

| Situation | What the doctor says | What it means |
| --- | --- | --- |
| Nothing ever subscribed | `Ready. No monitor is currently subscribed.` | Setup is fine. The monitor starts at session start; restart Claude if the plugin was installed after this session began. |
| A subscriber is holding it | `Monitoring is live.` | Findings from this session will arrive. |
| The CLI cannot subscribe at all | `Findings cannot reach this session.` | Real fault. The doctor names which link is broken. |

Only the third is a problem to fix. Reporting the first as a failure sends the
user chasing a healthy install, which is the specific mistake this skill was
rewritten to stop making.

## Slack

Slack is a second destination, not part of the native path. Report it on its
own line and never let it change the native verdict:

| Doctor line | Meaning |
| --- | --- |
| `adapter not installed (optional)` | Slack is unconfigured. Native monitoring is unaffected. |
| `no STACKTRACE_SLACK_URL set (optional)` | Installed but given no service origin. Supply one when invoking `/stacktrace:slack`. |
| `paired but not subscribed` | Pending, possibly awaiting workspace admin approval. Pending is not connected. |
| `unreachable or not paired` | Outage or a revoked pairing. Local detection and native notifications continue; queued findings are retained, and `/stacktrace:slack flush` drains them once it recovers. |
| `connected, N delivered` | Working. `accepted`, `delivered`, and `read` remain distinct — a delivered count is not a read count. |

Slack being absent, pending, or broken never degrades the native path, and
saying otherwise misrepresents the product.

## Evidence

Never read the credential file to enrich any of this. If the user wants the
findings themselves rather than the health of the pipe, use
`/stacktrace:findings`.
