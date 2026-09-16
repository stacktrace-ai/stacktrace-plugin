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
- Hooks must remain asynchronous and non-blocking.
- Sync state and logs belong under Stacktrace's own state directory; the plugin
  owns no cursor or retry state.
- Keep the plugin thin. Product logic belongs in `stacktrace-cli`.

## Repo conventions

- Skills use `skills/<name>/SKILL.md`.
- Hooks use `hooks/hooks.json` and paths through `${CLAUDE_PLUGIN_ROOT}`.
- The plugin manifest and marketplace entry omit versions so the source commit
  drives update identity.
- Update `scripts/validate_plugin.py` when the intended plugin surface changes.
