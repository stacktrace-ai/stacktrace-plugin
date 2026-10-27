---
id: 0011
title: Install the Cursor plugin from a release tag
status: proposed
date: 2026-10-26
supersedes: null
superseded-by: null
---

## Context

The Cursor CLI installs plugins only from a marketplace.
`agent plugin marketplace add <host>/<owner>/<repo> --git-ref <ref>` clones the marketplace at that ref.
Cursor reads `.cursor-plugin/marketplace.json` first and `.claude-plugin/marketplace.json` second.

Cursor accepts a `url` plugin source pinned by `sha`, as the Claude catalog uses (ADR-0010).
But Cursor does not install a pinned commit whose tree holds a catalog with a non-relative source.
It reads the commit's manifests and stops before it fills its plugin cache.
Every release commit holds `.claude-plugin/marketplace.json` with a `url` source.
So a `sha` pin to this repository installs no hooks in Cursor.

## Decision

1. Add `.cursor-plugin/marketplace.json` with one entry, `"source": "./"`.
   The validator rejects any other Cursor catalog.
2. Document the Cursor install with `--git-ref v<release>`.
   The release tag selects the commit, and release tags never move.
3. Document the upgrade as the same command with the new tag.
   Cursor replaces the ref and keeps the plugin enabled.

## Alternatives considered

**Pin the Cursor entry with a `url` source and the Claude catalog's `sha`.**
One promotion would then release both hosts.
Cursor installs nothing from such a commit, as the context describes.

**No Cursor catalog. Cursor falls back to the Claude catalog.**
The Claude catalog has the same `url` source, so Cursor installs nothing.
Before a Cursor release, the fallback selects `0.3.2`, and Cursor runs its Claude hooks.

**Install from `main` without `--git-ref`.**
Every merge then reaches Cursor users. ADR-0010 rejects this for Claude.

## Verification

Use the Cursor CLI `2026.10.22-27dcf5f`.
Add a copy of this repository at a tag, with a later commit on `main`.
Confirm that a session runs the tag's `sessionStart` hook with `--agent-kind cursor`.
Pin a copy of a release commit with a `url` source, and confirm that no hook runs.
Remove both catalogs from that commit, and confirm that the hook runs.
