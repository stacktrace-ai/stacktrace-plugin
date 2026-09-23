# Stacktrace Plugin

## What this repo is

Host integrations for Stacktrace: thin adapters over the `stacktrace` CLI and
its daemon. The Claude Code adapter declares one session-lifetime monitor
(`stacktrace daemon subscribe --agent-kind claude-code`), a SessionStart hook
that teaches the notification contract and shows a one-time welcome, and the
configure, status, and findings skills. Parsing, detection, policy, persistence
and routing stay in the CLI; this repository owns packaging and lifecycle only.

## Common commands

```bash
python3 scripts/validate_plugin.py          # repository contract
python3 -m unittest discover -s tests -v    # tests
claude plugin validate --strict .           # manifest and marketplace
```

## Before pushing a PR

Run the three commands above; CI (`validate` job) runs the first two on every
PR and push to `main`. There is no pre-push hook in this repository. An
automated fixer never skips these; an environment-only failure is a blocker it
reports.

## Repo conventions

- Skills live in `skills/<name>/SKILL.md`; hooks in `hooks/hooks.json`; the
  monitor in `monitors/monitors.json`. Paths go through `${CLAUDE_PLUGIN_ROOT}`.
- `scripts/validate_plugin.py` states the intended plugin surface; update it
  when the surface changes.
- The plugin needs `stacktrace-cli` 0.4.0 or newer, the first release with
  the daemon the monitor subscribes to.
- Hooks forward only session id, transcript path, cwd and event name; never
  prompt, response or tool content. Hooks stay asynchronous and non-blocking.

---

## Behavioral guidelines

**Tradeoff:** these bias toward caution over speed. For trivial tasks,
use judgment.

### 1. Think Before Coding

**Don't assume. Don't hide confusion. Surface tradeoffs.**

Before implementing:
- State your assumptions explicitly. If uncertain, ask.
- If multiple interpretations exist, present them — don't pick silently.
- If a simpler approach exists, say so. Push back when warranted.
- If something is unclear, stop. Name what's confusing. Ask.

### 2. Simplicity First

**Minimum code that solves the problem. Nothing speculative.**

- No features beyond what was asked.
- No abstractions for single-use code.
- No "flexibility" or "configurability" that wasn't requested.
- No error handling for impossible scenarios.
- If you write 200 lines and it could be 50, rewrite it.

Test: would a senior engineer say this is overcomplicated? If yes,
simplify.

### 3. Surgical Changes

**Touch only what you must. Clean up only your own mess.**

When editing existing code:
- Don't "improve" adjacent code, comments, or formatting.
- Don't refactor things that aren't broken.
- Match existing style, even if you'd do it differently.
- If you notice unrelated dead code, mention it — don't delete it.

When your changes create orphans:
- Remove imports/variables/functions that YOUR changes made unused.
- Don't remove pre-existing dead code unless asked.

The test: every changed line should trace directly to the user's
request.

### 4. Goal-Driven Execution

**Define success criteria. Loop until verified.**

Transform tasks into verifiable goals:
- "Add validation" → "Write tests for invalid inputs, then make them pass"
- "Fix the bug" → "Write a test that reproduces it, then make it pass"
- "Refactor X" → "Ensure tests pass before and after"

For multi-step tasks, state a brief plan:
```
1. [Step] → verify: [check]
2. [Step] → verify: [check]
```

### 5. Verify Before Claiming Done

**Evidence before assertions, always.**

- Run the tests; don't say "should pass" — say "passed" only after the
  command exited green.
- If you can't run the verification (no UI access, no test infra), say
  so explicitly. Don't claim success based on type-checks alone.
- Adversarial review before declaring done: re-read the diff and ask
  "what did I miss? what did I assume? does this test the problem
  space or just my implementation?"

## Architecture Decision Records (ADRs)

Durable design notes belong in `docs/adrs/`.

**When to write a new ADR:** when you make a decision where (a) the
rejected alternative is *plausible*, (b) it's *likely to be
re-suggested* (by a future you, a teammate, or another agent), and
(c) the reason isn't obvious from the code alone.

The bar matters. Most decisions don't clear it. The test: would a
future reviewer or agent, looking only at the code, plausibly suggest
the alternative we rejected? If yes, write the ADR.

**Read.** Before changing logic in an area an ADR covers, read the
full ADR. The cost of one Read is much smaller than the cost of
re-deriving or re-litigating a decision.

**Supersede, never edit.** Accepted ADRs are immutable. If a later
decision contradicts an existing ADR, write a NEW ADR with
`supersedes: NNNN` in its frontmatter, and update the old one's
frontmatter to `status: superseded` + `superseded-by: NNNN`. Old PRs
need to remain readable against the rules in effect at the time —
silently editing an accepted ADR breaks that contract.

## Commits and PRs

- Frequent commits, one logical change per commit.
- Commit messages: focus on WHY (the motivation, the constraint), not
  WHAT (the diff already shows that).
- Push to remote at logical points; don't hoard local commits.
- Only create commits when the user requests one. If unclear, ask.
- Only push to a remote when the user requests it.

## TDD for business logic

For non-trivial business logic, write the failing test first, then
make it pass, then refactor. The bite-sized red/green/refactor/commit
cadence keeps the loop tight and the diff reviewable.

Skip TDD discipline for: throwaway scripts, exploratory spikes,
obvious one-line fixes, infrastructure config (Dockerfiles, CI YAML,
shell scripts where tests cost more than the change is worth).

## Verifying claims about external behavior

When a review comment, design decision, or bug report turns on how a
*third party* behaves — an API contract, a file or lockfile format, a
tool's actual output — verify against ground truth before accepting or
rejecting it:

- **Fetch the authoritative source.** Use `WebFetch` for the docs/spec,
  `WebSearch` to find it, or run a script against the real API / a real
  sample.
- **In-repo ADRs, plans, and tests are NOT evidence for an external
  claim.** They record what *we chose*, not what the third party
  requires. A test written by the same author who holds an assumption is
  self-referential: it confirms the assumption rather than falsifying it.
- **Distinguish "I verified this is false" from "I could not disprove
  it."** Absence of in-repo disproof is not disproof. If you lack the
  access to verify (no network, no real sample, a denied tool), say so
  explicitly and **defer** — flag the uncertainty and escalate to a human
  rather than confidently pushing back on a bare citation. A factual
  dispute about external behavior you cannot settle is a stop-and-ask,
  not a win-the-argument.

This applies to every agent — the interactive assistant, a review bot, a
subagent — not just one surface.

## Risky / hard-to-reverse actions

Carefully consider reversibility and blast radius. Local + reversible
(file edits, running tests) — fine to do directly. Hard-to-reverse,
shared-state, or visible-to-others — confirm first:

- Destructive: `rm -rf`, dropping tables, killing processes,
  overwriting uncommitted changes, force-deleting branches.
- Hard-to-reverse: force-pushing, `git reset --hard`, amending
  published commits, removing/downgrading dependencies.
- Visible to others: pushing code, creating/closing/commenting on PRs
  or issues, sending messages (Slack, email), modifying shared
  infrastructure or permissions.
- Uploading to third-party tools (diagram renderers, pastebins,
  gists) — the content gets indexed/cached even if later deleted.

When you encounter an obstacle, don't use destructive actions as a
shortcut to make it go away. Identify the root cause; fix the
underlying issue rather than bypassing safety checks (e.g.,
`--no-verify`).

If you discover unexpected state — unfamiliar files, branches,
configuration — investigate before deleting or overwriting. It may
represent the user's in-progress work.

## Code Review Rules

### Reviewer

- Review the full PR against its base branch. Report all qualifying
  findings together; do not deliberately reserve findings for later rounds.
- Report concrete, actionable defects with supported failure scenarios.
  Respect explicit scope decisions and accepted tradeoffs. Do not present
  speculative hardening or optional improvements as correctness defects.
- Calibrate priority by impact and urgency:
  - P0: critical, broadly applicable failure requiring immediate action.
  - P1: serious defect that should be fixed before this change lands.
  - P2: normal-priority defect eligible for automatic fixing.
  - P3: low-priority suggestion.
  Do not inflate priority to make a finding eligible for automatic fixing.
- On subsequent reviews, verify earlier fixes and inspect their effects on
  callers and dependencies. Older code within the PR remains reviewable.
- When review history supports it, identify a finding as:
  - Regression: introduced since the previous reviewed head.
  - Late discovery: present at a previously reviewed head but not reported.
  - Unresolved: a previously reported defect remains.
  If the history is unavailable or ambiguous, say so rather than guessing.
- Deduplicate by underlying defect and remedy, not by title. Refer to an
  existing thread for an unresolved defect instead of opening another one.

### Automated Fix Rules

- Automatically address actionable CI failures and verified P0, P1,
  and P2 findings, whether raised by an automated reviewer or a human.
- P3 findings require explicit human approval before fixing. Maintain one
  updated summary with links to their threads. Do not mark them resolved
  merely because they are deferred.
- Validate each finding against the current head and relevant contracts.
  If its reasoning or priority is wrong, explain why rather than applying
  it solely because a reviewer requested it. Surface unresolved disputes
  for human judgment.
- Fix the underlying invariant across relevant call sites. Test the
  failure class rather than only the reported example.
- Preserve accepted fixes and regression tests when reviewing a rebased PR or
  when replacing or simplifying its implementation. Remove a test only when
  the behavior it protects is intentionally changed or removed, and explain
  that decision.
- Batch related fixes into one tested update before requesting re-review.
  Avoid duplicate review requests for the same head.
- An automated fixer pushes ordinary commits to the existing PR branch and
  runs every required gate. It does not bypass gates, merge, rebase, or
  force-push, or change workflows, permissions, credentials, or branch
  protection. Report an environment failure or required rebase as a blocker.
- After pushing fixes, wait for CI and a completed review of the current
  head. Silence, an older review, or a running review is not clearance.
- Stop and ask for human input when the same failure repeats without progress.
- Stop the automatic fix cycle when CI passes, the current head has been
  reviewed, and no actionable P0/P1/P2 findings remain. A reviewer
  thumbs-up is not required.
- If only P3 findings remain, report:
  "Automatic fixes complete for <SHA>; CI passed. P3 suggestions await
  author approval."
  Do not claim the PR has no findings or has been approved.
- Count automated fix rounds since the most recent human-authored corrective
  commit, and stop when the count reaches seven. A round is a fix pushed as a
  new head for review; failed local validation does not count. A human-authored
  commit is corrective when it materially addresses the reported blockers; it
  resets the count to zero whether it arrives before or after the cap. Merging,
  rebasing, or otherwise synchronizing the branch does not reset the count. If
  PR and session history are insufficient to determine the count, stop and ask
  the author rather than guessing.
- At the cap, remain subscribed but make no edits. Put a message in the PR:
  "Review cap limit reached. @<author> Please take a step back to review the
  design and push a corrective commit to reset the review cap." In the same
  comment, explain why review has not converged and suggest concrete
  simplifications or spec/ADR changes. Resume only after the reset defined
  above.
