# Architecture decisions

- [0001](0001-detach-a-metadata-only-cli-worker.md) — **Detach a metadata-only CLI worker.** Claude's hook process strips content-bearing fields and detaches the Stacktrace CLI so `SessionEnd` survives non-interactive teardown; the CLI remains the sole owner of consent, state, locking, retries, and upload.
- [0002](0002-render-findings-in-a-bounded-synchronous-hook.md) — **Detect and surface a stall from the transcript.** A synchronous `PostToolUseFailure` hook measures the trailing run of one identical failure in the transcript and reports it to the terminal and to Claude; stateless, CLI-free, and early enough to still matter.
