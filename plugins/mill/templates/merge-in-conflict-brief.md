<!--
Template tokens used by this file:
  <CONFLICTING_FILES> — markdown bullet list of files with conflict markers
  <PROJECT_ROOT>      — absolute path to the worktree root (cwd of sub-agent)
  <TASK_INTENT>       — excerpts from this branch's _mill/discussion.md and _mill/plan/*.md so the resolver can recognize an intentional delete or rewrite. Empty string when neither is present.
-->
# Conflict Resolution Brief

Your sole job is to resolve git conflict markers in the listed files, stage each resolved file, and report success. Do NOT commit. Do NOT run `git merge --continue` — the SKILL does that after receiving `{"status":"success"}`.

## Task intent

These excerpts describe what THIS branch is trying to accomplish. When the merge introduces a parent-side change that conflicts with this branch's intent, the resolution preserves THIS branch's intent. In particular: if a file appears under a batch's `Deletes:` list and the merge introduces a modified version of that file from the parent, the resolution is to delete the file (your branch's intent overrides). Stage the deletion with `git -C <PROJECT_ROOT> rm <file>`.

<TASK_INTENT>

## Conflicting files

<CONFLICTING_FILES>

## Instructions

For each file listed above:

1. Read the file and locate every conflict block (`<<<<<<<`, `=======`, `>>>>>>>`).
2. Understand both sides of the conflict — what each branch intended.
3. Write a resolution that preserves the intent of both sides.
4. Run `git -C <PROJECT_ROOT> add <file>` to stage the resolved file.
5. For modify/delete (DU) conflicts: if Task intent above lists this file under a batch's `Deletes:`, run `git -C <PROJECT_ROOT> rm <file>` instead of editing; that stages the intentional deletion.
6. For UD conflicts — files this branch **modified** that the parent branch **deleted**: do not silently keep the modification. Instead:
   a. Run `git log --diff-filter=D --oneline MERGE_HEAD -- <file>` to find the deletion commit on the parent.
   b. Run `git show <deletion-commit>` to inspect context.
   c. If the deletion commit message mentions a replacement file (e.g. "replaced by", "moved to", "consolidated into"), or the commit also adds a file in the same directory with overlapping content: stage the deletion — `git -C <PROJECT_ROOT> rm <file>`.
   d. If detection is inconclusive: report `{"status":"stuck","stuck_type":"logic","reason":"modify/delete conflict on <file>: cannot determine if parent deletion is a replacement -- operator must decide"}` and halt. Do NOT silently keep the modification.

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
