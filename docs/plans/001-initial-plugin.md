# Plan 001 — Initial Claude Code plugin

**Goal:** Package Stacktrace as a Claude Code plugin whose opt-in runtime and
composition sync runs automatically without blocking the agent.

**Decision:** [ADR-0001](../adrs/0001-detach-a-metadata-only-cli-worker.md).

## Success criteria

- [x] Installing the plugin neither configures credentials nor enables upload.
- [x] `Stop` and `SessionEnd` are the only automatic events and both are async.
- [x] Only lifecycle metadata reaches the detached Stacktrace worker.
- [x] A missing CLI or malformed hook event cannot disrupt Claude.
- [x] Setup keeps token entry out of chat and requires explicit enablement.
- [x] Structure, unit tests, Claude validation, and a real hook smoke test pass.

## Tasks

- [x] Add manifest, marketplace, hooks, launcher, skills, docs, and CI.
- [x] Test input minimization, detachment, hook contract, and failure behavior.
- [x] Run `claude plugin validate`.
- [x] Exercise real `Stop` and `SessionEnd` events with a fake Stacktrace sink.
- [ ] Push a ready PR. The plugin requires the unreleased `remote auto-sync`
      CLI surface until the Stacktrace change ships in an immutable package.
