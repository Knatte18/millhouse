<!--
Template: fix-cycle resume prompt for the per-batch implementer Sonnet
session that mill-go resumes after a code-review round. Rendered by
mill-go via `_render.render` with these tokens:

  <REVIEW_FILE>      — absolute path to the code-review output file
  <BATCH_FILE>       — absolute path to the batch file (NN-<name>.md)
  <SELF_FIX_ROUNDS>  — integer; how many self-fix attempts before reporting stuck
  <ROUND>            — fix-cycle round number

(`_render.render` strips this comment automatically.)
-->
# Fix-cycle Resume — Round <ROUND>

Mill-go is resuming your implementer session after a code review. You have full context from the original implementation pass. Apply the findings, re-run verify, and report the same JSON shape.

## Session identity

You are continuing the **same session** as the original implementation dispatch. Your `session_id` is the UUID that was passed via `--session-id` at first spawn — it remains in your session context. Reuse it in the JSON report below. Do NOT attempt to re-read `--session-id` from argv; it is absent on `--resume`.

## Reading the review

1. Load the **mill-receiving-review** skill before opening any finding.
2. Read the review file: `<REVIEW_FILE>`.
3. Apply the VERIFY → HARM CHECK → FIX or PUSH BACK decision tree per finding. The skill's rules are non-negotiable.

For each finding routed to FIX: edit the relevant file(s), then commit via the `git-commit` skill.

For each finding routed to PUSH BACK: note your rebuttal; do not modify the code.

## Verify

After all fixes are committed, re-run the `verify:` command from the batch frontmatter at `<BATCH_FILE>`. If it fails:

- Self-fix and re-run, committing each attempt.
- After **<SELF_FIX_ROUNDS>** failing attempts, stop and report `stuck` with `stuck_type: verify`.

If `verify: null` in the frontmatter, skip straight to Report.

## Report

Your last line of output MUST be a single JSON object:

```json
{"status":"success","commit_sha":"<last-HEAD-sha>","session_id":"<your-original-uuid>"}
```

or, when stuck:

```json
{"status":"stuck","stuck_type":"transient|verify|logic","reason":"<one-line>","commit_sha":"<last-HEAD-sha>","session_id":"<your-original-uuid>"}
```

`session_id` MUST be the UUID from your session context (set at first dispatch). mill-go uses this field to correlate the fix report with the original session.

Anything other than this JSON on the last line is a protocol violation.
