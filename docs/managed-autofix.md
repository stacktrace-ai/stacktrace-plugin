# Managed PR review and fixes

Repository: `stacktrace-ai/stacktrace-claude-plugin`.

Managed Codex reviews; Anthropic-hosted Claude fixes review findings and CI
failures. The agents run outside GitHub Actions. Normal lint/test CI still uses
GitHub runners. No Actions dispatcher or routine API token is needed for the steady-state loop.

## Configuration

- Codex repository settings: **Review all PRs**, **On every push**.
- One active Claude enrollment routine for this repository, with the exact
  [saved prompt](../.github/managed-autofix-prompt.md).
- Native GitHub trigger: `pull_request.opened`, non-draft only, no author or
  head-branch filter. The session verifies same-repository heads and trusted
  authors before subscribing.
- Anthropic-hosted Default environment; sole repository source is
  `https://github.com/stacktrace-ai/stacktrace-claude-plugin`; no unrelated connectors.
- No schedule or review/push trigger. The enrolled session receives subsequent
  activity; a second trigger would risk duplicate watchers.

Active routine: [trig_01JijKAzDwe3KYKEReBWkdkd](https://claude.ai/code/routines/trig_01JijKAzDwe3KYKEReBWkdkd).
GitHub trigger: `294e66bb-0960-4f7a-9b74-f7b683bbad36`.
Creation accepted the PR-open/non-draft configuration; the management API does
not return saved action/filter values, so verify trigger behavior from run logs.
The saved cloud prompt and this file are separate configuration surfaces:
merging a prompt edit does not deploy it to Claude. Update the routine, read
back its saved prompt, and steer any existing sessions that need the change.

This repository has no legacy review/fix workflows on `main`. The plugin
implementation branches contain normal validation CI, which remains enabled.
Do not add a runner-based review/fix dispatcher.

## When fixes are allowed

```text
PR opened -> subscribe once
  current-head human/Codex review with actionable findings -> fix
  current-head required CI failure -> fix independently of review
  push, pending review/CI, clean review -> wait
fix -> run branch-required checks -> push -> review/CI on new head
```

A prior head's review or CI result cannot authorize edits to a new head. Human
reviews qualify independently of Codex; other review bots and ordinary PR
conversation comments do not open the review gate. Validate findings against
the code and authoritative sources, and ask when a design choice is ambiguous.
Do not merge, force-push, weaken checks, change workflows/permissions, or bypass
pre-push checks. An environment failure is a blocker to report.

## Seven-attempt cap

At most **seven managed fix attempts per PR**, including failed or no-push
attempts. Enrollment, idle wakes and duplicate notifications do not count.
Before beginning an attempt, update one progress comment marked
`<!-- stacktrace-managed-autofix -->` with the count and handled review/check
IDs. The count survives pushes and session restarts; unknown history requires
human help rather than resetting to zero.

After attempt seven, disable Auto-fix/unsubscribe and report **LIMIT REACHED**,
the count, remaining work and session URL. Resume only with explicit human
authorization. Repeated identical failures without progress also require help.
This is an instruction-level limit, not a platform-enforced quota.

## Existing PRs and recovery

PR-open triggers do not backfill old PRs. Manually run the same routine with an
explicit PR URL as run context, first checking existing runs/progress comments
for a watcher to reuse. Confirm an actual `subscribe_pr_activity` success;
merely starting or completing a routine run is not proof of enrollment.
If the current head has no queued, running, or completed Codex review, the
managed session requests `@codex review` once, recording a full-SHA marker in
the request comment. This supplies a fallback when native automatic review is
not configured or misses a push, without starting a GitHub runner. Verify the
review is for the current SHA. Never repeat a marked request for the same head.

Drafts opened before becoming ready also need manual enrollment for now.
Closed or merged PRs stop their watchers. Disabling the enrollment routine
prevents future enrollment; existing PR subscriptions must be stopped separately.

Reference: [Claude Auto-fix](https://code.claude.com/docs/en/claude-code-on-the-web#auto-fix-pull-requests)
and [native routine triggers](https://code.claude.com/docs/en/routines#add-a-github-trigger).
