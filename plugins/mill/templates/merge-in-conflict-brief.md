<!--
Template tokens used by this file:
  <CONFLICTING_FILES> — markdown bullet list of files with conflict markers
  <PROJECT_ROOT>      — absolute path to the worktree root (cwd of sub-agent)
-->
# Conflict Resolution Brief

Your sole job is to resolve git conflict markers in the listed files, stage each resolved file, and report success. Do NOT commit. Do NOT run `git merge --continue` — the SKILL does that after receiving `{"status":"success"}`.

## Conflicting files

<CONFLICTING_FILES>

## Instructions

For each file listed above:

1. Read the file and locate every conflict block (`<<<<<<<`, `=======`, `>>>>>>>`).
2. Understand both sides of the conflict — what each branch intended.
3. Write a resolution that preserves the intent of both sides.
4. Run `git -C <PROJECT_ROOT> add <file>` to stage the resolved file.

Never use `git checkout --ours` or `git checkout --theirs` — they silently discard one side of the conflict.

## Report

Your last output line MUST be a bare JSON object (no code fence, no backticks):

On success:

{"status":"success"}

If you cannot resolve one or more conflicts:

{"status":"stuck","stuck_type":"logic","reason":"<one-line description of what you could not resolve>"}

Anything other than this JSON object on the last line is a protocol violation; the merge-in dispatcher treats that as stuck_type: logic with reason "no structured report" — your work is lost. Do not wrap the JSON in a code fence; do not add commentary after it.

## Tools

Available: Read, Edit, Write, Bash, Grep, Glob. Use `git -C <PROJECT_ROOT>` for any git commands; do not `cd`. Worktree cwd is `<PROJECT_ROOT>`.
