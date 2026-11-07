---
id: 0013
title: Run one session start script on every host and log its failures
status: proposed
date: 2026-11-02
supersedes: null
superseded-by: null
amends: [0009, 0012]
amended-by: null
---

## Context

ADR-0009 asks for one SessionStart shell entrypoint. Only Claude Code uses
`scripts/session_start.sh`. Codex, Cursor and Devin run
`scripts/policy_hook.sh register` instead. That path has no watchdog and no
diagnosis, and it exits 0 silently on every failure. Codex also gives it five
seconds, while the other hosts give fifteen.

All hosts discard the stderr of the script. Nothing records a failure. A person
who asks why a session did not register has no evidence to read.

The hosts show different SessionStart output. Claude Code shows `systemMessage`
to the user. The Codex hooks documentation says that SessionStart accepts the
common `systemMessage` field and shows it "as a warning in the UI or event
stream" ([Codex hooks](https://learn.chatgpt.com/docs/hooks)). The Cursor
documentation says that the `sessionStart` schema accepts `user_message`, but
that callers do not enforce it, and it does not say where it shows
([Cursor hooks](https://cursor.com/docs/agent/hooks)). The Devin documentation
names only `additionalContext` for `SessionStart`, which goes to the agent
([Devin lifecycle hooks](https://docs.devin.ai/cli/extensibility/hooks/lifecycle-hooks.md)).

## Decision

1. Every host's SessionStart hook runs `scripts/session_start.sh --agent-kind
   <kind>`. The script does the same steps for every kind. It registers with
   `stacktrace remote policy hooks register --agent-kind <kind>` under the
   watchdog, then runs the diagnosis. Only the monitor variable check stays
   Claude-only. `devin/scripts/session_start.sh` is a byte copy, and the Devin
   folder holds the two scripts. This changes decisions 1 and 2 of ADR-0012.
2. Every SessionStart hook has a timeout of fifteen seconds.
3. Claude Code keeps its output. Codex gets the same warnings as one
   `systemMessage`, without the `/stacktrace:status` route that only Claude
   has. Cursor and Devin get no output, because their documentation names no
   user-visible SessionStart field.
4. Each failure appends one line to
   `${STACKTRACE_STATE_DIR:-$HOME/.local/state/stacktrace}/session-start.log`.
   The line is `<UTC time> <kind> plugin <stage> <detail>`. The CLI writes
   `cli` in the third field. The detail is fixed text or digits only. A healthy
   session writes nothing. A failed write never changes the hook result.

## Alternatives considered

**Keep `policy_hook.sh register` for Codex, Cursor and Devin.** Those hosts
then keep no watchdog and no diagnosis, and a failure stays invisible.

**Write diagnostics to stderr.** Claude Code discards it, and each host
treats stderr differently. A person cannot read it after the session.

**Let only the CLI write the log.** The CLI cannot record that it is missing,
that it timed out, or that it rejected `--agent-kind`.

**Log the hook input or the CLI output.** Hook input can hold a prompt, a path
or a secret. Fixed stages give enough evidence to debug startup.

**Show Cursor `user_message` and Devin output.** Neither host documents a
user-visible SessionStart message. Output that a host does not show adds a
risk and no value.

**Default `--agent-kind` to `claude-code`.** Every hooks file names its kind,
and the validator enforces it. A default hides a missing argument.

## Consequences

- One script carries every host's startup behavior. A change to it changes the
  Devin copy too, and the validator fails until both match.
- Codex, Cursor and Devin sessions can wait for the daemon for up to five
  seconds when its socket is absent, as Claude Code sessions already do.
- Claude Code now passes `--agent-kind claude-code`. The CLI accepts it from
  0.14.0. On CLI 0.13 Claude Code registration fails with exit 2, and the log
  records `register-exit 2`.
- The log can lose a line when the CLI appends during a trim. The file stays
  bounded at 500 lines.
- `/stacktrace:status` stays Claude-only. A Codex warning names the observed
  fact without a route.

## Verification

Run the tests in `tests/test_session_start.py`. They check each host's hook
declaration, each log stage for each kind, the healthy path, the stdin
boundary and the output for each kind. No signed-in Codex session ran the
Codex warning.
