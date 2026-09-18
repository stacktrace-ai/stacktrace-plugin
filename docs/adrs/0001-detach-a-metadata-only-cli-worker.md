---
id: 0001
title: Detach a metadata-only CLI worker
status: superseded
date: 2026-09-16
supersedes: null
superseded-by: 0003
---

## Context

Stacktrace sync can outlive a Claude turn. Claude Code supports asynchronous
command hooks, but its documented contract kills an async hook still running
when a non-interactive `claude -p` session tears down. Every hook firing also
starts a separate process with no host-side deduplication.

Passing the complete hook document directly to a long-lived worker would expose
fields the worker does not need, including the latest assistant message on a
`Stop` event. Reimplementing synchronization in the plugin would create a
second consent, cursor, lock, and retry model alongside the CLI.

## Decision

Both `Stop` and `SessionEnd` use an asynchronous command hook. That command is a
small standard-library Python launcher which:

1. accepts only the two intended lifecycle events;
2. copies only `session_id`, `transcript_path`, `cwd`, and `hook_event_name`;
3. locates the installed `stacktrace` executable;
4. starts `stacktrace remote auto-sync run` in a detached process group;
5. sends the filtered event on a pipe and exits without waiting.

The launcher exits successfully when input is invalid or Stacktrace is absent.
It never configures or enables sync. The CLI owns consent, validation,
collection, upload, locking, change detection, checkpoints, retries, status,
and logs.

## Alternatives considered

- **Invoke the CLI directly from the async hook.** Simpler, but an unfinished
  `SessionEnd` sync is cancelled at `claude -p` teardown.
- **Persist the hook document for a detached worker.** Rejected because the
  document can contain message content, and a pipe is sufficient.
- **Put the sync worker in the plugin.** Rejected because each future host
  integration would reproduce product behavior and state.
- **Use only `SessionEnd`.** Rejected because crashed and long-lived sessions
  would remain stale.

## Consequences

The plugin requires the same Python runtime as `stacktrace-cli`, but no third
party package. The outer hook returns quickly while the CLI can finish after
Claude exits. Overlapping workers are expected and serialized by the CLI.

Hook failures stay out of Claude's conversation. Operators inspect them through
`stacktrace remote auto-sync status` and the local log it names.
