<!--
Template tokens used by this file:
  <VERIFY_CMD>        — the verify command to run (from the plan's frontmatter)
  <VERIFY_OUTPUT>     — stdout + stderr from the failing verify command run
  <MERGE_DIFF>        — output of git diff <checkpoint>..HEAD (what the merge changed)
  <VERIFY_FIX_ROUNDS> — maximum number of fix attempts before reporting stuck
  <PROJECT_ROOT>      — absolute path to the worktree root (cwd of sub-agent)
-->
# Verify-Fix Brief

The verify command `<VERIFY_CMD>` failed after a merge. Your job is to diagnose the failures and fix the code so the verify command passes.

## Verify Output

```
<VERIFY_OUTPUT>
```

## Merge Diff

```diff
<MERGE_DIFF>
```

## Instructions

1. Read the failing tests and the source files they exercise.
2. Fix the root cause of the failures. Do not modify tests unless they are genuinely wrong due to the merge (e.g. a test asserted against a value that the merge legitimately changed).
3. Re-run `<VERIFY_CMD>` after each fix attempt using `git -C <PROJECT_ROOT>` for git commands.
4. Commit each fix attempt with a clear commit message.
5. Self-fix up to `<VERIFY_FIX_ROUNDS>` times. If the verify command still fails after `<VERIFY_FIX_ROUNDS>` attempts, stop and report stuck.

## Report

Your last output line MUST be a bare JSON object (no code fence, no backticks):

On success:

{"status":"success","commit_sha":"<last-HEAD-sha>"}

After exhausting fix rounds:

{"status":"stuck","stuck_type":"verify","reason":"<one-line description of what still fails>","commit_sha":"<last-HEAD-sha>"}

Anything other than this JSON object on the last line is a protocol violation; the merge-in dispatcher treats that as stuck_type: logic with reason "no structured report" — your work is lost. Do not wrap the JSON in a code fence; do not add commentary after it.

## Tools

Available: Read, Edit, Write, Bash, Grep, Glob. Use `git -C <PROJECT_ROOT>` for git commands; do not `cd`. Worktree cwd is `<PROJECT_ROOT>`.
