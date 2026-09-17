# Stacktrace Claude Code Plugin

## What this repo is

This repository packages Stacktrace for Claude Code. It is a thin host
integration: explicit skills help an operator configure and inspect Stacktrace,
while lifecycle hooks forward minimal metadata to the installed `stacktrace`
CLI. Detection, upload, consent, locking, retries, and checkpoints belong to
the CLI, not this plugin.

## Common commands

```bash
python3 scripts/validate_plugin.py
python3 -m unittest discover -s tests -v
claude plugin validate .
bash scripts/install-hooks.sh
```

## Safety boundaries

- Installing or enabling this plugin must not configure credentials or enable
  upload.
- Hook launchers may forward only `session_id`, `transcript_path`, `cwd`, and
  `hook_event_name`. Never persist or forward prompt, response, or tool content.
- Sync work must remain asynchronous and non-blocking. The one synchronous hook
  is the stall detector (ADR-0002): local transcript read only, capped at five
  seconds, and silent whenever anything is missing or malformed.
- Sync state and logs belong under Stacktrace's own state directory; the plugin
  owns no cursor or retry state, and no notification state either — a streak is
  re-derived from the transcript, never remembered between firings.
- The detector may read the transcript in process. It must never persist or
  forward what it read; a failure leaves the hook as a signature and a count.
- Keep the plugin thin. Product logic belongs in `stacktrace-cli`.

## Presentation

- The plugin renders findings; it never decides that one exists.
- Severity and confidence are orthogonal and are always labelled as such.
- Colour is never the only carrier of meaning: honour `NO_COLOR`, keep the words.
- Partial coverage is stated on the finding. What a detector could not see is
  part of its claim, not a caveat to bury.

## Repo conventions

- Skills use `skills/<name>/SKILL.md`.
- Hooks use `hooks/hooks.json` and paths through `${CLAUDE_PLUGIN_ROOT}`.
- The plugin manifest and marketplace entry omit versions so the source commit
  drives update identity.
- Update `scripts/validate_plugin.py` when the intended plugin surface changes.
