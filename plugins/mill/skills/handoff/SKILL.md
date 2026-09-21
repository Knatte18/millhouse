---
name: handoff
description: Write a handoff document so a fresh session can continue this conversation's work. Explicit invocation only.
argument-hint: "[path/to/file.md] [what will the next session focus on?]"
disable-model-invocation: true
---

Write a handoff document summarising the current conversation so a fresh agent can continue the work. Save to `.scratch/handoff.md` under the current working directory by default — never the OS temp directory (see `conversation`'s file-writing rule).

If the arguments include a file path, save there instead (resolved relative to the current working directory unless absolute).

The document's first line instructs the next agent to load `mill:conversation` before reading the rest of the document.

Include a "suggested skills" section in the document, naming which skills the next agent should call the Skill tool for.

Do not duplicate content already captured in other artifacts (specs, plans, ADRs, issues, commits, diffs). Reference them by path or URL instead.

**This document carries current state and durable facts, not history.** Apply this test to every line before writing it: would a fresh agent act differently if this line were missing? If not, cut it. This test removes passing test counts, timings, and descriptions of already-finished edits. It keeps open PRs, in-flight work, and constraints.

**Never include a session changelog, under any heading.** Reject these anti-pattern headings on sight — none of them belongs in a handoff: "Done this session", "Changes made", "Completed work", "Recent commits". Work already committed is described by its commit; work already merged is described by its PR — never restated in the handoff. Anti-pattern examples, each with why it fails the test above:
- A committed refactor — already captured by its commit; a fresh agent reads the commit, not a restatement.
- A green test run with its duration — not durable state; it doesn't change what a fresh agent does next.
- A merged PR's contents — already captured by the PR; reference its number/URL instead.
- A review whose file is already committed at a known path — reference the path instead of restating its findings.

**If this handoff replaces an existing handoff document, re-derive every section from this skill's own rules.** Treat the previous file only as a source of facts (e.g. "PR #183 is still open") — never as a section template or outline to inherit. Copying a prior handoff's structure carries forward any violation it contained.

Redact any sensitive information, such as API keys, passwords, or personally identifiable information.

If the arguments include anything other than a path, treat that part as a description of what the next session will focus on and tailor the doc accordingly.
