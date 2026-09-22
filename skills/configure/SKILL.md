---
name: configure
description: Install or verify the Stacktrace CLI used by this plugin.
disable-model-invocation: true
---

# Configure Stacktrace

1. Run `command -v stacktrace` and `stacktrace --version`. The plugin needs
   `stacktrace-cli` 0.4.0 or newer: that is the first release with the daemon
   the session monitor subscribes to. An older CLI is present but cannot serve
   the plugin, so treat it the same as absent.
2. If the command is absent or the version is older than 0.4.0, check for
   `uv`. With the user's approval, run
   `uv tool install --upgrade 'stacktrace-cli>=0.4.0'`, then re-run
   `stacktrace --version`.
   - If it is still not found, the tool executable directory
     (`uv tool dir --bin`) is likely missing from `PATH`; run
     `uv tool update-shell` and tell the user to fully restart Claude before
     continuing — `/reload-plugins` cannot refresh the `PATH` already
     inherited by the running Claude process.
   - If it is found but still reports a version older than 0.4.0, an
     install from something other than `uv` (pip, pipx, a system package
     manager) sits earlier on `PATH` and is shadowing the one `uv` just
     installed — `uv` will not overwrite an executable it did not create.
     Stop and tell the user to remove or upgrade that other install, or
     reorder `PATH` so the `uv`-managed one resolves first, then retry.
   If `uv` is absent, stop and give the user the install command from
   https://docs.astral.sh/uv/getting-started/installation/.
3. Tell the user to run `/reload-plugins` so the session monitor starts with the
   newly installed CLI.
4. Run `stacktrace daemon status` after the reload. Configuration is complete
   when the CLI reports its version and the daemon reports that it is running.
