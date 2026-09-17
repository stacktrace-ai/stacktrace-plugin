# Stacktrace Claude Code Plugin

Stacktrace adds local runtime detection and opt-in automatic Cloud sync to
Claude Code. After each completed turn it checks the changed session; when the
session ends it also checks the endpoint's agent composition. Both hooks run in
the background, so Claude does not wait for collection or upload.

The plugin is a thin host integration around the `stacktrace` CLI. It contains
no detection rules, uploader, credential, or independent sync cursor.

## Requirements

- Claude Code with plugin support
- A `stacktrace` CLI release that includes `remote auto-sync`, and — for the
  notification surface below — `notify next` and `finding dismiss|mute|why`
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

## Findings in the terminal

A finding nobody reads is not a notification, and Claude Code never reads an
asynchronous hook's output. So `Stop` carries a second, synchronous handler that
asks the CLI what is pending and prints it — a local query, capped at two
seconds, with no detection and no network call of its own (ADR-0002).

```
▐ medium · high · stacktrace-progress-stall ×4 here
▐ Same test failing since turn 22 — three attempts, no change between them
▐   • turns 22, 26, 31 · identical failure signature
▐   • 0 successful runs in the window
▐   → This isn't converging. Change the approach or take it back.
```

The two grades are separate on purpose: **severity** is how much it matters,
**confidence** is how sure we are it happened. The gutter and headline take
their colour from severity, and the words carry the same information for a
terminal with `NO_COLOR`, a piped session, or a reader who cannot separate the
hues. Set `STACKTRACE_COLOR=never` to turn colour off, `always` to force it.

When a finding could not see everything, it says so inline
(`◐ partial coverage · insufficient_context`) rather than presenting a hedged
claim as a confident one. Full coverage is left for `/stacktrace:why`.

The plugin keeps no state behind any of this. Which finding is pending, how many
times its rule has fired, and whether the action row still needs showing are all
answers the CLI returns.

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
