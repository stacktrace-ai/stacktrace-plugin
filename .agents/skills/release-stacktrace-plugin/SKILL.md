---
name: release-stacktrace-plugin
description: Use when cutting a new Stacktrace Claude Code plugin release or promoting a plugin version to the marketplace. Walks through the version bump, release notes, candidate validation with a native install and update probe, the tag, the marketplace pin promotion PR, and the GitHub Release.
---

# release-stacktrace-plugin

This is the end-to-end release procedure for the `stacktrace` Claude Code
plugin. The production marketplace pins this repository by an exact commit
SHA ([ADR-0010](../../../docs/adrs/0010-pin-production-plugin-commits.md)).
A merge to `main` does not release anything. A release is the promotion PR
that moves the pin to a tested, tagged commit.

`scripts/validate_plugin.py` enforces the shape of the pin. No workflow gates
the tag or the release, so this skill does the checks that a workflow cannot.

**Announce at start:** "I'm using the release-stacktrace-plugin skill to cut a
new plugin release."

## When to invoke

Invoke this skill when the user says "cut a plugin release", "ship plugin
0.N.N", "release the plugin", "promote the plugin" or "bump the plugin
version". Also invoke it when someone edits `version` in
`.claude-plugin/plugin.json` or the `sha` in `.claude-plugin/marketplace.json`.

## The release in three PR-shaped steps

| Step | Changes | Effect for users |
| --- | --- | --- |
| Release PR | `plugin.json` `version`, `docs/releases/v<version>.md` | None. The pin does not move. |
| Tag | `v<version>` on the merged release commit | None. |
| Promotion PR | The `marketplace.json` entry only: `source.sha` and its display fields | Fresh installs and `claude plugin update` select `<version>`. |

The GitHub Release comes last, after the promotion PR merges. The Releases
page then never lists a version that the marketplace does not serve.

## Inputs

1. **Target version**, for example `0.4.0`. It must be higher than the pinned
   version. Claude Code caches a plugin by its version, so an installed copy
   ignores new code under an unchanged version. Ask the user for the number.
2. **Theme**, the H1 line of the notes file. Ask the user. A commit log cannot
   supply it.

## Procedure

Run every command from the repository root.

### Step 1. Pre-flight checks

Stop and ask if a check fails. Do not "fix" a dirty tree or an out-of-date
`main` automatically. Both are signs of work in progress.

```bash
git rev-parse --abbrev-ref HEAD                    # must be main
git status --porcelain                             # must be empty
git fetch --tags origin main
test "$(git rev-parse HEAD)" = "$(git rev-parse origin/main)"
git rev-parse --verify "v<version>" 2>/dev/null    # MUST FAIL: the tag must not exist
git ls-remote --tags origin "v<version>"           # must print nothing
```

Read the current pin and the version that it serves:

```bash
pin=$(python3 -c 'import json; print(json.load(open(".claude-plugin/marketplace.json"))["plugins"][0]["source"]["sha"])')
pinned_version=$(git show "$pin:.claude-plugin/plugin.json" | python3 -c 'import json,sys; print(json.load(sys.stdin)["version"])')
echo "$pinned_version at $pin"
```

Confirm that `<version>` is higher than `$pinned_version`:

```bash
pin=$(python3 -c 'import json; print(json.load(open(".claude-plugin/marketplace.json"))["plugins"][0]["source"]["sha"])')
pinned_version=$(git show "$pin:.claude-plugin/plugin.json" | python3 -c 'import json,sys; print(json.load(sys.stdin)["version"])')
python3 -c 'import sys; a, b = (tuple(map(int, v.split("."))) for v in sys.argv[1:]); sys.exit(a <= b)' "<version>" "$pinned_version"
```

Release tags and versions are immutable. If a tag for `<version>` exists, pick
the next number.

### Step 2. Gather the commit log

The pin, not a tag, marks the previous release. The first pinned version,
`0.3.2`, has no tag.

```bash
pin=$(python3 -c 'import json; print(json.load(open(".claude-plugin/marketplace.json"))["plugins"][0]["source"]["sha"])')
git log --oneline "$pin..origin/main"
```

If the range is empty, there is nothing to release. Stop and tell the user.
Use the log as raw material only. Do not copy it into the notes file.

### Step 3. Draft `docs/releases/v<version>.md`

Use this shape. If `docs/releases/` already has files, follow them instead.

~~~markdown
# <version> — <theme>

## Highlights

- **<Theme A>.** One to three sentences for someone who uses the plugin in
  Claude Code. Refer to ADRs by number when a design record backs the change.
- **Bug fixes.** Put small fixes in one bullet, separated by commas.

## Install

```text
/plugin marketplace add stacktrace-ai/stacktrace-plugin
/plugin install stacktrace@stacktrace
```

Existing installations update with `claude plugin update stacktrace@stacktrace`
or with marketplace auto-update. Restart Claude Code to apply the update.

## Compatibility

- Requires `stacktrace-cli` <minimum> or newer.
- Requires Claude Code <minimum> or newer.
- <Behavior changes that existing users will notice.>
~~~

Take the minimum `stacktrace-cli` and Claude Code versions from
`.claude/CLAUDE.md` and `README.md` at the candidate. Do not guess them.

Apply these rules when you write the notes:

- **Group by theme, not by commit.** Five commits that add one capability are
  one bullet.
- **Lead with what a user sees.** Hooks, the monitor, notifications, skills
  and session-start messages are user-visible. Validator and test changes are
  not.
- **Cut chore, format, docs-only and release-process commits.**
- **State breaking changes under `## Compatibility`.** A higher minimum CLI, a
  renamed skill or a changed hook contract goes there.

Write the notes in ASD-STE100 Simplified Technical English, as
`.claude/CLAUDE.md` requires. Show the draft to the user. Change it until the
user agrees that it describes what ships.

### Step 4. Release PR

If the user did not explicitly ask to cut, ship or publish a release, stop
before the push and ask. An edit to the version field invokes this skill. It
does not give permission to publish.

Change only the version and add the notes. Do not touch
`.claude-plugin/marketplace.json`. The pin stays where it is. Development can
bump the version on `main` ahead of a release. If `plugin.json` on `main`
already carries `<version>`, skip the bump and add only the notes.

```bash
git checkout -b release/<version>
python3 - "<version>" <<'EOF'
import json, sys
path = ".claude-plugin/plugin.json"
manifest = json.load(open(path))
manifest["version"] = sys.argv[1]
open(path, "w").write(json.dumps(manifest, indent=2) + "\n")
EOF
git diff --stat                                    # plugin.json only, or nothing if main already carries <version>
python3 scripts/validate_plugin.py
python3 -m unittest discover -s tests -v
claude plugin validate --strict .
git add .claude-plugin/plugin.json docs/releases/v<version>.md
git status --porcelain                             # inspect anything still unstaged
git commit -m "release: <version> — <theme>"
git push -u origin release/<version>
```

Open the PR only when the user asks for it:

```bash
pin=$(python3 -c 'import json; print(json.load(open(".claude-plugin/marketplace.json"))["plugins"][0]["source"]["sha"])')
pinned_version=$(git show "$pin:.claude-plugin/plugin.json" | python3 -c 'import json,sys; print(json.load(sys.stdin)["version"])')
gh pr create --title "release: <version>" --body "Release prep for plugin <version>.

- Bumps \`.claude-plugin/plugin.json\` to <version>.
- Adds release notes at \`docs/releases/v<version>.md\`.
- Leaves the marketplace pin unchanged. Users still get $pinned_version.
- After merge: validate the merged commit, tag \`v<version>\`, then open the promotion PR."
```

Give the user the PR URL. **Stop here.** The user reviews and merges it.

### Step 5. Validate the candidate

After the release PR merges, the candidate is the commit on `main` that
added the notes file. Only the release PR adds it. Do not select the commit
that last changed `plugin.json`, because development can bump the version
earlier. `--first-parent` selects the merge or squash commit on `main`, not
the commit on the release branch.

```bash
git checkout main
git pull --ff-only
candidate=$(git log --first-parent -n 1 --format=%H origin/main -- docs/releases/v<version>.md)
git show "$candidate:.claude-plugin/plugin.json" | python3 -c 'import json,sys; print(json.load(sys.stdin)["version"])'   # must print <version>
git merge-base --is-ancestor "$candidate" origin/main                                                                  # the candidate must be on main
```

Run the three repository gates on a checkout of the candidate:

```bash
candidate=$(git log --first-parent -n 1 --format=%H origin/main -- docs/releases/v<version>.md)
git checkout --detach "$candidate"
python3 scripts/validate_plugin.py
python3 -m unittest discover -s tests -v
claude plugin validate --strict .
git checkout main
```

Run the native install and update probe. It uses an isolated
`CLAUDE_CONFIG_DIR`, so it does not touch the user's own plugins. It installs
the current pin, moves a scratch catalog to the candidate, and updates. The
same path is what an existing user takes. The candidate must already be on
GitHub, because the `url` source clones it from there.

```bash
candidate=$(git log --first-parent -n 1 --format=%H origin/main -- docs/releases/v<version>.md)
probe=$(mktemp -d)
set_pin() {
  python3 - "$1/.claude-plugin/marketplace.json" "$2" <<'EOF'
import json, sys
path, sha = sys.argv[1:]
catalog = json.load(open(path))
catalog["plugins"][0]["source"]["sha"] = sha
open(path, "w").write(json.dumps(catalog, indent=2) + "\n")
EOF
}
installed() {
  python3 -c 'import json,sys; (e,) = json.load(open(sys.argv[1]))["plugins"]["stacktrace@stacktrace"]; print(e["version"], e["gitCommitSha"])' \
    "$CLAUDE_CONFIG_DIR/plugins/installed_plugins.json"
}
git worktree add --detach "$probe/catalog" origin/main
export CLAUDE_CONFIG_DIR="$probe/config"
claude plugin marketplace add "$probe/catalog"
claude plugin install stacktrace@stacktrace
installed                                          # must print "$pinned_version $pin"
set_pin "$probe/catalog" "$candidate"
claude plugin marketplace update stacktrace
claude plugin update stacktrace@stacktrace
installed                                          # must print "<version> $candidate"
unset CLAUDE_CONFIG_DIR
git worktree remove --force "$probe/catalog"
rm -rf "$probe"
```

Check the CLI that the candidate needs. `.claude/CLAUDE.md` says to upgrade
the CLI before this plugin. The minimum `stacktrace-cli` must already be on
PyPI:

```bash
curl -s https://pypi.org/pypi/stacktrace-cli/json | python3 -c 'import json,sys; print(sorted(json.load(sys.stdin)["releases"]))'
```

If the minimum is not on PyPI, stop. Release the CLI first with the
`release-stacktrace` skill in `stacktrace-ai/stacktrace`.

Ask the user for a live session check on a machine with the minimum published
CLI and a running daemon:

```bash
uv tool install "stacktrace-cli==<minimum>"
stacktrace daemon start
claude --plugin-dir "$(pwd)"                       # from a checkout of the candidate
```

In that session, the session-start message must not report a missing CLI or
daemon, and `/stacktrace:status` must report a healthy setup. If you cannot run
this check, say so. Do not report it as passed.

Stop and ask if any check fails. A failed candidate needs a fix on `main` and
a new release PR. Do not reuse `<version>` for a different commit if anyone
outside this procedure could have installed it.

### Step 6. Tag the candidate

Tag only after the user confirms that the candidate passed Step 5.

```bash
candidate=$(git log --first-parent -n 1 --format=%H origin/main -- docs/releases/v<version>.md)
git tag v<version> "$candidate"
git push origin v<version>
```

Never move or delete a pushed release tag.

### Step 7. Promotion PR

The promotion PR changes only the entry in `.claude-plugin/marketplace.json`.
It sets `source.sha` to the candidate. It also copies the display fields from
the candidate's `plugin.json`. Users see the entry's fields before install and
the pinned commit's `plugin.json` after install. The validator checks only the
shape of these fields (ADR-0010), so this step is the only place that keeps
them equal. Base the PR on the current `main`.

```bash
git checkout main
git pull --ff-only
git checkout -b release/promote-<version>
candidate=$(git rev-parse "v<version>")
python3 - "$candidate" <<'EOF'
import json, subprocess, sys
path = ".claude-plugin/marketplace.json"
catalog = json.load(open(path))
(entry,) = catalog["plugins"]
pinned = json.loads(subprocess.check_output(["git", "show", f"{sys.argv[1]}:.claude-plugin/plugin.json"]))
for field in ("displayName", "description", "author", "homepage", "repository", "keywords"):
    entry[field] = pinned[field]
entry["source"]["sha"] = sys.argv[1]
open(path, "w").write(json.dumps(catalog, indent=2) + "\n")
EOF
git diff                                           # must touch only .claude-plugin/marketplace.json
```

Show the user any display field that changed in the diff. Those changes come
from the candidate's `plugin.json` and become visible in the marketplace.

Run the gates, then commit and push:

```bash
python3 scripts/validate_plugin.py
python3 -m unittest discover -s tests -v
claude plugin validate --strict .
git add .claude-plugin/marketplace.json
git commit -m "release: promote plugin <version>"
git push -u origin release/promote-<version>
```

Open the PR only when the user asks for it:

```bash
pin=$(git show origin/main:.claude-plugin/marketplace.json | python3 -c 'import json,sys; print(json.load(sys.stdin)["plugins"][0]["source"]["sha"])')
pinned_version=$(git show "$pin:.claude-plugin/plugin.json" | python3 -c 'import json,sys; print(json.load(sys.stdin)["version"])')
candidate=$(git rev-parse "v<version>")
gh pr create --title "release: promote plugin <version>" --body "Promotes plugin <version> to the production marketplace.

- Moves the pin from $pin ($pinned_version) to $candidate (v<version>).
- The candidate passed the repository gates, strict validation and a native install-then-update probe.
- Release notes: \`docs/releases/v<version>.md\`.
- After merge: verify a fresh install from GitHub and create the GitHub Release."
```

Give the user the PR URL. **Stop here.** The merge is the release.

### Step 8. After merge: verify and publish the GitHub Release

After the user confirms the merge, install from GitHub into an isolated
configuration:

```bash
probe=$(mktemp -d)
export CLAUDE_CONFIG_DIR="$probe/config"
claude plugin marketplace add stacktrace-ai/stacktrace-plugin
claude plugin install stacktrace@stacktrace
claude plugin list --json                          # must show version <version>
unset CLAUDE_CONFIG_DIR
rm -rf "$probe"
```

Then create the GitHub Release from the notes file at the tag:

```bash
notes=$(mktemp)
git show "v<version>:docs/releases/v<version>.md" > "$notes"
gh release create v<version> --repo stacktrace-ai/stacktrace-plugin \
  --verify-tag --title "<version> — <theme>" --notes-file "$notes"
rm "$notes"
gh release view v<version> --repo stacktrace-ai/stacktrace-plugin --json name,tagName
```

If any step fails, show the failing output. Do not guess the cause.

## Failure modes this prevents

1. **A merge to `main` reaches users.** Only the promotion PR moves the pin.
2. **New code under an old version.** Step 1 requires a higher version, so
   Claude Code does not serve stale cached files.
3. **A pin to an untested or unmerged commit.** Step 5 takes the candidate
   from `main` and installs it natively before the tag.
4. **A broken update path.** The probe updates from the current pin, as
   existing users do, and does not only test a fresh install.
5. **The plugin needs a CLI that users cannot install.** Step 5 checks PyPI
   for the minimum `stacktrace-cli`.
6. **Marketplace display fields that differ from the installed plugin.**
   Step 7 copies them from the candidate's `plugin.json`.
7. **A Releases page entry for a version that nobody can install.** Step 8
   creates the GitHub Release only after the promotion merges.

## What this skill does NOT do

- **It does not merge PRs.** The user merges the release PR and the
  promotion PR.
- **It does not roll back by moving the pin to an older commit.** Ship a fix
  under a new version. Existing caches keep the newer version.
- **It does not release `stacktrace-cli`.** Use the `release-stacktrace` skill
  in `stacktrace-ai/stacktrace` for that.
- **It does not write a CHANGELOG.md.** Release notes are per-release files
  under `docs/releases/`.
