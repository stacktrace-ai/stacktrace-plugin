# Architecture decisions

- [0001](0001-detach-a-metadata-only-cli-worker.md) — **Detach a metadata-only CLI worker.** Claude's hook process strips content-bearing fields and detaches the Stacktrace CLI so `SessionEnd` survives non-interactive teardown; the CLI remains the sole owner of consent, state, locking, retries, and upload.
- [0002](0002-render-findings-in-a-bounded-synchronous-hook.md) — **Render findings in a bounded synchronous hook.** A second, synchronous `Stop` handler asks the CLI for the pending finding and formats it for the terminal; the plugin keeps no queue, no delivery marks, and no suppression state.
