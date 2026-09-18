---
name: configure
description: Install or verify the Stacktrace CLI used by this plugin.
disable-model-invocation: true
---

# Configure Stacktrace

1. Run `command -v stacktrace` and `stacktrace --version`.
2. If the command is absent, check for `uv`. With the user's approval, run
   `uv tool install stacktrace-cli`. If `uv` is absent, stop and give the user
   the install command from https://docs.astral.sh/uv/getting-started/installation/.
3. Tell the user to run `/reload-plugins` so the session monitor starts with the
   newly installed CLI.
4. Run `stacktrace daemon status` after the reload. Configuration is complete
   when the CLI reports its version and the daemon reports that it is running.
