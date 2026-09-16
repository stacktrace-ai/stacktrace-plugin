---
name: setup
description: Configure Stacktrace Cloud and explicitly enable automatic Claude Code lifecycle sync when the user asks to install, configure, connect, or turn on Stacktrace.
allowed-tools:
  - Bash
---

# Set Up Stacktrace

Use this skill when the user asks to configure Stacktrace or enable automatic
sync.

## Check The CLI

Run:

```bash
stacktrace --version
```

If the command is unavailable, tell the user to install the current
`stacktrace-cli` release. Do not install software unless the user asks.

## Configure Cloud

First run:

```bash
stacktrace remote status
```

If it is not configured, ask the user to run this themselves so their token is
entered directly into the CLI and never appears in chat:

```bash
stacktrace remote configure
```

Do not ask the user to paste a token into the conversation and do not pass one
on a command line.

## Enable Automatic Sync

Explain that this opts in to background uploads after completed turns and at
session end. Only after the user confirms, run:

```bash
stacktrace remote auto-sync enable
stacktrace remote auto-sync status
```

Installing the plugin alone does not grant upload consent. Do not enable sync
merely because this skill was invoked.
