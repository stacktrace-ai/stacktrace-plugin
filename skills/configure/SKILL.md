---
name: configure
description: Install or verify the Stacktrace CLI used by this plugin.
disable-model-invocation: true
---

# Configure Stacktrace

1. Run `command -v stacktrace` and `stacktrace --version`.
2. If the command is absent, check for `uv`. With the user's approval, run
   `uv tool install stacktrace-cli`, then re-run `command -v stacktrace`. If it
   is still not found, the tool executable directory (`uv tool dir --bin`) is
   likely missing from `PATH`; run `uv tool update-shell` and tell the user to
   fully restart Claude before continuing — `/reload-plugins` cannot refresh
   the `PATH` already inherited by the running Claude process. If `uv` is
   absent, stop and give the user the install command from
   https://docs.astral.sh/uv/getting-started/installation/.
3. Tell the user to run `/reload-plugins` so the session monitor starts with the
   newly installed CLI.
4. Run `stacktrace daemon status` after the reload. Configuration is complete
   when the CLI reports its version and the daemon reports that it is running.

If step 4 answers `No such command 'daemon'`, the installed release predates
the daemon. PyPI's latest is 0.3.1 and the daemon merged after it, so a plain
`uv tool install stacktrace-cli` cannot produce a working monitor. With the
user's approval, install from source instead:

```bash
uv tool install --force --from git+https://github.com/stacktrace-ai/stacktrace.git stacktrace-cli
```

Say which one you installed. A CLI that reports a version is not the same as a
CLI that can subscribe, and reporting the first as if it were the second is the
failure this step exists to prevent.
