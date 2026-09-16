# Architecture decisions

- [0001](0001-detach-a-metadata-only-cli-worker.md) — **Detach a metadata-only CLI worker.** Claude's hook process strips content-bearing fields and detaches the Stacktrace CLI so `SessionEnd` survives non-interactive teardown; the CLI remains the sole owner of consent, state, locking, retries, and upload.
