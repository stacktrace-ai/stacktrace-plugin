---
id: 0010
title: Pin production plugin commits in the marketplace
status: proposed
date: 2026-10-18
supersedes: null
superseded-by: null
---

## Context

The marketplace lists the plugin with `source: "./"`.
That source follows the marketplace repository's current checkout.
Fresh installations and plugin updates can therefore select development code after a merge.
A manifest version supports caching but does not select released source files.

## Decision

Keep the existing marketplace name and repository URL.
Replace the relative plugin source with an explicit HTTPS `url` source for this
repository, not a `github` source. Claude Code fetches an entry's `github`
source without the SSH-to-HTTPS fallback that `/plugin marketplace add` and
`claude plugin install` apply; an in-session `/plugin install` or an
auto-update of a `github`-sourced entry fails outright for a user with no
GitHub SSH key. An explicit `https://` `url` source clones the public
repository over HTTPS directly, so it carries no such fallback gap.
Pin that source with a full commit SHA.
Read the installed plugin version from that commit's `plugin.json`.
Keep one version authority instead of duplicating it in the marketplace entry.

Repeat `plugin.json`'s display fields (`displayName`, `description`, `author`,
`homepage`, `repository`, `keywords`) on the marketplace entry. Claude Code can
read `plugin.json` before install only for a relative-path source; a pinned
`url` source would otherwise show users just the plugin's name until they
install it.

Ordinary development merges leave the marketplace pin unchanged.
Test development checkouts with `--plugin-dir`.
Promote a tested commit through a separate marketplace update.
The promotion changes the SHA after the candidate passes validation and native installation checks.
A runtime release uses a new manifest version and a tag for the tested commit.
Never move an existing release tag or change content under an existing release version.

The initial pin freezes the currently served `0.3.2` commit, `bb0095731ad8471ed25c28c143dc07f80737c244`.
The repository has no existing release tags or GitHub releases.
This establishes a fixed baseline without changing the currently served runtime code.
It does not undo code that users already installed.

Validate that the production entry selects only the official repository and an exact lowercase commit SHA.
Reject relative sources, branch-only sources, tag-only sources, and malformed pins.
The validator does not require development files to match the pinned version.
A development version change must not promote that version implicitly.

CLI and plugin release numbers remain independent.
Test a candidate against its supported published CLI before promotion.
Unavailable CLI commands retain their existing permissive behavior.
Installer publication remains a separate change.

## Alternatives considered

**Keep a relative source and bump versions carefully.**
Fresh installations can still select unreleased files from the current checkout.

**Track a stable branch or tag without an exact commit.**
Moving that reference can change installed source without changing the catalog pin.

**Create another marketplace repository.**
The existing catalog can select an external commit from this same repository.
A second repository adds migration and maintenance without improving this boundary.

**Pin with a `github` source instead of an explicit `url` source.**
A `github` source still requires `git`, and its entry-level fetch skips the
SSH-to-HTTPS fallback that marketplace add and shell installs apply, so an
in-session install or auto-update fails outright for a user with no GitHub SSH
key. The explicit HTTPS `url` source names the same commit without that gap.

## Verification

Use native Claude installation and update commands with a source repository containing a later development commit.
Confirm that installation and update retain the pinned version.
Advance the catalog pin explicitly and confirm that the next update selects the promoted version.

Source: [Claude marketplace source reference](https://code.claude.com/docs/en/plugins/marketplace-reference#plugin-sources).
