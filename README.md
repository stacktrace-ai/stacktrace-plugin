# Stacktrace Claude Code Plugin

Stacktrace adds local runtime detection and opt-in automatic Cloud sync to
Claude Code. After each completed turn it checks the changed session; when the
session ends it also checks the endpoint's agent composition. Both hooks run in
the background, so Claude does not wait for collection or upload.

The plugin is a thin host integration around the `stacktrace` CLI. It contains
no detection rules, uploader, credential, or independent sync cursor.

## Requirements

- Claude Code with plugin support
- A `stacktrace` CLI release that includes `remote auto-sync` (the findings
  surface below works without it)
- Python 3.11 or newer (also required by `stacktrace-cli`)

## Install

Add the private marketplace and install the plugin:

```text
/plugin marketplace add stacktrace-ai/stacktrace-claude-plugin
/plugin install stacktrace@stacktrace
/reload-plugins
```

Installing the plugin does not enable upload. Configure Stacktrace through its
interactive credential prompt, then explicitly opt in:

```bash
stacktrace remote configure
stacktrace remote auto-sync enable
stacktrace remote auto-sync status
```

You can also ask Claude to run `/stacktrace:setup`; it will keep token entry in
the CLI and ask before enabling automatic sync.

## What runs automatically

| Claude event | Stacktrace work |
|---|---|
| `Stop` | If the transcript changed, analyze and sync only the current Claude session. Then show any finding the CLI has queued for this session. |
| `SessionEnd` | Make the final runtime pass, then sync endpoint composition only if its redacted payload changed. |

Claude Code starts both hooks with `async: true`. A small launcher forwards only
`session_id`, `transcript_path`, `cwd`, and `hook_event_name`, then detaches the
CLI worker so a non-interactive Claude teardown cannot cancel it. The CLI owns
the machine-wide lock, checkpoints, retries, local status, and log.

## Findings while the session is still running

`Stop` is too late for the findings worth interrupting: an agent looping on one
failing call inside a single long turn produces no `Stop` until the loop is
already over. So detection runs on `PostToolUseFailure`, on each failure.

It reads the tail of the transcript Claude Code already passes the hook, joins
tool calls to their results, and measures the trailing run of one identical
failure signature. At three, it says so:

```
▐ medium · high · stacktrace-progress-stall
▐ Bash has failed 3 times with the same error and no change in between
▐   • 3 consecutive Bash failures · identical error signature
▐   • 0 successful runs between them
▐   → This isn't converging. Change the approach or hand it back.
```

It fires at three and not at four — the fourth identical failure is the same
finding, and re-announcing it is how an alert becomes wallpaper. That is also
what keeps it stateless: no counter is stored, because the streak is re-read from
the transcript every time.

No CLI is required for any of this. No state file either.

The two grades are separate on purpose: **severity** is how much it matters,
**confidence** is how sure we are it happened. Colour reinforces severity and
never carries it alone — `NO_COLOR` is honoured, `STACKTRACE_COLOR=never|always`
overrides, and the words say the same thing on a monochrome terminal.

### Reaching someone who is not at the terminal

The hook also returns `additionalContext`, telling Claude a finding exists and to
call `PushNotification` if the operator may be away. That tool already suppresses
itself when the terminal is active, so it is the right place for the judgement.
The notice bounds Claude to reporting: do not investigate, do not repeat what is
already on screen.

This requires nothing of the operator beyond what Claude Code already does.
Phone delivery additionally needs Remote Control connected.

Automatic runtime sync never enables model reasoning. It uses Stacktrace's
local deterministic rules. Failed work remains uncheckpointed and can retry on
a later lifecycle event.

In a one-shot `claude -p` run, Claude Code may cancel the async `Stop` hook as
the process tears down. The `SessionEnd` hook performs the same final runtime
check, so the completed session still converges before adding the composition
check.

Disable future automatic work without deleting checkpoints:

```bash
stacktrace remote auto-sync disable
```

## Skills

- `/stacktrace:setup` — safely configure and explicitly enable automatic sync.
- `/stacktrace:status` — inspect Cloud and automatic-sync health.
- `/stacktrace:detect` — run local runtime detection without enabling upload.
- `/stacktrace:why` — show the evidence behind the last finding, coverage included.
- `/stacktrace:dismiss` — record that one finding was not worth surfacing.
- `/stacktrace:mute` — stop a rule in this project, without silencing the rest.

`dismiss` and `mute` are deliberately different actions. Dismissing judges one
finding and leaves the rule running; muting changes what reaches you and leaves
findings already surfaced in place, so a mute never quietly rewrites the record
a rule's dismissal rate is computed from.

## Development

```bash
python3 scripts/validate_plugin.py
python3 -m unittest discover -s tests -v
claude plugin validate .
bash scripts/install-hooks.sh
```

The marketplace uses a relative source within this repository. Claude Code
therefore derives the installed plugin version from the marketplace commit; the
manifest intentionally omits a manually maintained version.
