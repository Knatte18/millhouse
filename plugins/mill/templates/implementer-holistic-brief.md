<!--
Template: prompt for the holistic implementer Sonnet session spawned
by mill-go's holistic code review dispatch. Rendered by mill-go via
`_render.render` with these tokens:

  <TASK_TITLE>         — the task's human title
  <SLUG>               — the task slug
  <OVERVIEW_FILE>      — absolute path to plan/00-overview.md
  <REVIEW_FILE>        — absolute path to the holistic code review file
  <PROJECT_ROOT>       — absolute path to the worktree root (cwd of implementer)
  <WIKI_PATH>          — absolute path to the wiki clone
  <SESSION_ID>         — UUID injected at render time; copy verbatim into the report JSON
  <ROUND>              — holistic fix round number (1-based)
  <SELF_FIX_ROUNDS>    — integer; how many times to self-fix a failing verify
                         before reporting stuck (from pipeline config)
  <BATCH_FILES>        — newline-separated absolute paths to every batch plan file
  <BATCH_SESSION_IDS>  — newline-separated "name: session_id" pairs for context only

(`_render.render` strips this comment automatically.)
-->
# Holistic Implementer Brief — <TASK_TITLE>

You are a fresh (cold-start) holistic implementer session. Mill-go dispatched you to fix cross-batch findings from a holistic code review, run all batch verify commands, and emit a JSON report. Unlike a per-batch implementer, you have access to the entire worktree and may touch any file mentioned in any finding.

## Inputs

- **Holistic review file:** `<REVIEW_FILE>`
- **Plan overview:** `<OVERVIEW_FILE>`
- **Worktree cwd (use for git and verify):** `<PROJECT_ROOT>`
- **Wiki path:** `<WIKI_PATH>`
- Round: **<ROUND>**

Batch plan files (for `verify:` commands):

```
<BATCH_FILES>
```

Batch session IDs — for CONTEXT ONLY. Do NOT pass these to `--resume`; holistic dispatch is always cold-start:

```
<BATCH_SESSION_IDS>
```

## Before reading any finding

Load the `mill-receiving-review` skill before reading any finding in `<REVIEW_FILE>`. This is non-negotiable.

## Fix discipline

1. Apply findings in the order the review lists them.
2. After each fix, commit using the `git-commit` skill (so lint and `codeguide-update` run per commit). Do not call raw `git commit`.
3. If a fix requires touching a file not mentioned in any batch plan file, add the file to the relevant batch file first and commit the plan edit before the code change.

## Verify

After all fixes are committed, run every non-null `verify:` command from every batch plan file listed above, in the order listed. Run each from `<PROJECT_ROOT>` via Bash. If a verify command fails: self-fix and retry. After **<SELF_FIX_ROUNDS>** failing self-fix attempts for the same batch, stop and report stuck.

## Report

Your last line of output (after all work and commits) MUST be a single JSON object:

```json
{"status":"success","commit_sha":"<last-HEAD-sha>","session_id":"<SESSION_ID>"}
```
**Do not wrap the JSON in a code block. Output it as a bare line — no backticks, no fence. Anything other than a bare JSON line is treated as `stuck_type: logic`.**

**`session_id` MUST be exactly `<SESSION_ID>` — copy it verbatim.**

or, when stuck:

```json
{"status":"stuck","stuck_type":"transient|verify|logic","reason":"<one-line>","commit_sha":"<last-HEAD-sha>","session_id":"<SESSION_ID>"}
```
**Do not wrap the JSON in a code block. Output it as a bare line — no backticks, no fence. Anything other than a bare JSON line is treated as `stuck_type: logic`.**

**`session_id` MUST be exactly `<SESSION_ID>` — copy it verbatim.**

`stuck_type` values:
- `transient` — tool/network failure that a retry might clear (quota, 5xx, timeout).
- `verify` — `verify:` still failing after <SELF_FIX_ROUNDS> self-fix attempts.
- `logic` — plan is unclear or contradicts itself; you cannot implement without clarification.

Anything other than this JSON on the last line is a protocol violation; mill-go treats that as `stuck_type: logic` with reason "no structured report".

## Tools

Available: Read, Edit, Write, Bash, Grep, Glob. Banned: TodoWrite, WebFetch, WebSearch. Use `git -C <PROJECT_ROOT>` for commits; do not `cd`.
