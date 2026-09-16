# Stacktrace Claude Code Plugin

Stacktrace adds local runtime detection and opt-in automatic Cloud sync to
Claude Code. After each completed turn it checks the changed session; when the
session ends it also checks the endpoint's agent composition. Both hooks run in
the background, so Claude does not wait for collection or upload.

The plugin is a thin host integration around the `stacktrace` CLI. It contains
no detection rules, uploader, credential, or independent sync cursor.

## Requirements

- Claude Code with plugin support
- A `stacktrace` CLI release that includes `remote auto-sync`
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
| `Stop` | If the transcript changed, analyze and sync only the current Claude session. |
| `SessionEnd` | Make the final runtime pass, then sync endpoint composition only if its redacted payload changed. |

Claude Code starts both hooks with `async: true`. A small launcher forwards only
`session_id`, `transcript_path`, `cwd`, and `hook_event_name`, then detaches the
CLI worker so a non-interactive Claude teardown cannot cancel it. The CLI owns
the machine-wide lock, checkpoints, retries, local status, and log.

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
