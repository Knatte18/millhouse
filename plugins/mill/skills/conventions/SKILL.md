---
name: conventions
description: Mill-specific operating rules — new-thread prompts, task-state and scratch locations, sed reach into dispatched agents, worktree isolation. Builds on scribe:prose and scribe:conversation.
---

# Mill Conventions

The rules specific to working in a mill repo.
This skill builds on `scribe:prose` and `scribe:conversation`: Load `scribe:prose`, then `scribe:conversation` before this skill.

---

## Prompts for new threads

- When writing a prompt for a new thread: **write it to a file** at `.scratch/prompt.md` (or `.scratch/prompt-<slug>.md` if multiple).
  Never dump long prompts inline in the chat.
- Tell the user: `Read .scratch/prompt.md and follow the instructions there.`
- If the prompt needs amendments before the user has started the thread: overwrite the file with the complete updated prompt.
  Never show partial diffs.
- The user copies from the file in the editor, which has a built-in copy function.
- **Every prompt must instruct the receiving thread to:** write its full report/result to a file (e.g. `.scratch/result-<slug>.md`) and only output to the user: (1) the path to the result file, and (2) a brief summary of key points.
  This keeps thread output concise and results reviewable.

## Task-state and scratch locations

- Per-task working state (`status.md`, `discussion.md`, `plan/`, `reviews/`, `briefs/`) lives in `_mill/` on the task branch.
- The wiki holds only `Home.md` and daemon-rendered files.
  Scripts resolve the wiki through `_paths.resolve_wiki_path`, never the `.wiki` junction (see CLAUDE.md `## Path invariants`).
- **Scratch override of `scribe:conversation`:** in a mill worktree, `.scratch/` means the worktree root's `.scratch/`.
  Mill's scripts, fixtures and new-thread prompts resolve it from the worktree root.
  This intentionally narrows `scribe:conversation`'s "`.scratch/` under the current working directory" for mill sessions.
- **Plugin-managed scratch:** all plugins share `.scratch/` for ephemeral files.
  Subdirectories (e.g. `test-review-<type>-<id>/`, `plans/`, `briefs/`) are created as needed and may be cleaned up at will.
- `.scratch/` is gitignored via the repo-root `.gitignore` entry `**/.scratch/`.

## sed in generated prompts

The no-`sed` rule also binds every prompt, brief or script a mill orchestrator generates for a dispatched implementer, reviewer or fixer.

## Worktree isolation

A session running from a child worktree operates on the child worktree only.
These rules apply whenever the current git worktree is not the main worktree.

- **MAY** read parent worktree state via `git -C <parent-path> log/status/show/diff/ls-files`.
  Read-only git queries never mutate shared state.
- **MAY NOT** edit files in the parent worktree.
  No `Edit`, `Write`, `NotebookEdit`, or other file-modification tool calls against parent paths.
- **MAY NOT** run `cd <parent-path>` or any shell command that changes the process working directory to the parent. `cd` corrupts the shell cwd for every subsequent command in the session — a single stray `cd` to the parent derails the rest of the run.
- **MAY NOT** commit, push, stage, or otherwise mutate the parent's git state.

`mill-merge` and `mill-cleanup` are the only skills exempt from these rules.
They use `git -C <parent-path> ...` to operate on the parent's git state without changing cwd.
Every other skill running in a child worktree stays inside the child.

**Why:** the 2026-04-13 track-child-worktree run had `cd <parent-path> && git commit` in its setup phase.
The cwd corruption cascaded for the rest of the session — Thread B's spawn call fired against the parent's scripts directory, materialized briefs landed in the parent's scratch,
and the merge chain walked off the child entirely.
The rule exists because the consequences of a cwd mistake are not recoverable inside the running session.

## Skill authors

When you touch an existing mill skill whose operator prompts are prose, convert them to `scribe:conversation`'s numbered-list form.
