---
name: configure
description: Install or repair the Stacktrace CLI this plugin drives, and say whether findings can reach this session.
disable-model-invocation: true
---

# Configure Stacktrace

Run the doctor first. It probes the whole path in dependency order and names
the one thing that is actually blocking delivery:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/doctor.py"
```

Report its verdict as written. Then act only on the verdict you got.

## Ready or Monitoring is live

Configuration is done. Say so and stop.

**Do not treat a stopped daemon as a failure.** The daemon is started by a
subscriber and exits about five seconds after the last one disconnects, so
outside a subscribed session it is always down. `Ready` means the CLI can
subscribe and the session has an identity, which is everything setup controls.

## Findings cannot reach this session — CLI not on PATH

Check for `uv`. If it is absent, stop and give the user the install command
from https://docs.astral.sh/uv/getting-started/installation/.

With the user's approval, install the CLI. While the daemon is unreleased this
must come from source — the published package cannot subscribe:

```bash
uv tool install --force --from git+https://github.com/stacktrace-ai/stacktrace.git stacktrace-cli
```

Re-run `command -v stacktrace`. If it is still missing, the tool executable
directory (`uv tool dir --bin`) is not on `PATH`: run `uv tool update-shell`.

Then tell the user to **fully restart Claude** — quit and relaunch, not
`/reload-plugins`. Two separate reasons, both of which survive a reload: a
reload cannot refresh the `PATH` this process already inherited, and the
session monitor starts at session start, so a session that began without a
working CLI cannot acquire one.

## Findings cannot reach this session — no daemon command

A CLI is installed but predates the daemon, so nothing can subscribe. Install
from source with the command above, then have the user fully restart Claude.

Say which build you installed. A CLI that reports a version is not a CLI that
can subscribe, and reporting the first as though it were the second is the
failure this skill exists to prevent.

## Findings cannot be routed — no session id

`CLAUDE_CODE_SESSION_ID` is unset. Report it and stop. Never substitute the
working directory, a project path, or the newest transcript as a stand-in
identity.

## If the plugin itself would not install

A managed host can refuse the marketplace before any of this is reachable:

```text
Marketplace source '…' is blocked by enterprise policy.
```

That is a host policy decision, not a plugin fault, and the allowlist lives in
a root-owned managed-settings file. Say plainly that an administrator has to
allow the marketplace, and do not attempt to edit the policy or work around
it.
