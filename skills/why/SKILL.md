---
name: why
description: Show the evidence behind the last Stacktrace finding, when the user asks why an alert fired, what triggered it, or whether they should believe it.
allowed-tools:
  - Bash
---

# Why a finding fired

> **This command does not exist yet.** `stacktrace finding` is not in any CLI
> build, including `main`; the CLI answers ``No such command 'finding'``. Run
> it, report that plainly, and stop. Do not substitute `stacktrace findings`,
> which answers a different question, and do not describe what the output would
> have said. The wording below is the contract for when the surface is built.

```bash
stacktrace finding why --session "$CLAUDE_CODE_SESSION_ID" --format json
```

Present the rule id, stage, the two grades, the evidence spans, and how many
times the rule has fired here.

**Always state coverage — what the detector could not see is part of the claim,
not a caveat to omit.** A finding reported at medium confidence because
compaction removed the turns it needed is a different claim from the same
finding at high confidence, and an operator who is not told cannot tell them
apart.

Evidence carries spans, kinds, and coordinates, never the matched content. Do not
supplement it by reading the user's source, transcript, or credentials to explain
a finding further.
