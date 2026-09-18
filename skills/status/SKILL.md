---
name: status
description: Check automatic Stacktrace monitoring for this Claude session.
disable-model-invocation: true
---

# Stacktrace status

Run `stacktrace --version`, then `stacktrace daemon status`. Report both results
concisely. If the daemon is not running, tell the user to run
`/stacktrace:configure` and then `/reload-plugins`.
