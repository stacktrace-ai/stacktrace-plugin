---
name: status
description: Show Stacktrace Cloud and automatic-sync status when the user asks whether Stacktrace is connected, syncing, healthy, or last succeeded.
allowed-tools:
  - Bash
---

# Stacktrace Status

Run both local status commands:

```bash
stacktrace remote status
stacktrace remote auto-sync status
```

Summarize whether Cloud is configured, whether automatic sync is enabled, the
last attempt and success, and any last error. The status commands mask or omit
credentials; never read the underlying configuration file to retrieve a token.

If automatic sync failed, point the user to the log path printed by the status
command. Read that log only when the user asks to diagnose the failure.
