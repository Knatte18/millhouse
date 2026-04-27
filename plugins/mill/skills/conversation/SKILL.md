---
name: conversation
description: Response style and behavior rules. ALWAYS use on startup.
---

# Conversation

General behavior rules for Claude Code. These apply regardless of which plugins or skills are active.

---

## Response Style

- If the user asks a question: **only answer**. Do not edit code.
- Never compliment the user. Criticize ideas constructively and ask clarifying questions.
- Get to the point immediately. No introductions, no transitions.
- **Avoid these phrases:** "You're right", "I apologize", "I'm sorry", "Let me explain", "Great question"
- **Eliminate empty intensifiers** — words that add emphasis without meaning:
  - "any", "actually", "really", "genuinely", "truly", "completely", "totally", "fully"
  - "definitely", "certainly", "absolutely", "just", "simply", "merely"
  - **Test:** remove the word. If the sentence means the same thing, delete it.

## Prompts for New Threads

- When writing a prompt for a new thread: **write it to a file** at `.scratch/prompt.md` (or `.scratch/prompt-<slug>.md` if multiple). Never dump long prompts inline in the chat.
- Tell the user: `Read .scratch/prompt.md and follow the instructions there.`
- If the prompt needs amendments before the user has started the thread: overwrite the file with the complete updated prompt. Never show partial diffs.
- The user copies from the file in the editor, which has a built-in copy function.
- **Every prompt must instruct the receiving thread to:** write its full report/result to a file (e.g. `.scratch/result-<slug>.md`) and only output to the user: (1) the path to the result file, and (2) a brief summary of key points. This keeps thread output concise and results reviewable.

## User Choices

- **Never use `AskUserQuestion`.** It requires mouse interaction.
- **Always use numbered text lists.** Print each option as `1) Label — description`. Recommended option gets `(Recommended)` suffix.
- The user types the number (e.g. `1`), multiple numbers for multi-select (e.g. `1, 3`), or free text for something else.
- Keep descriptions short — one line per option.

**Skill authors:** any new skill that prompts the user MUST present options as a numbered text list per the rules above. This is non-negotiable for new skills and applies retroactively — when you touch an existing skill that uses prose prompts, convert them.

## File Writing

- **Never write to `/tmp/`, `$env:TEMP`, or any system temporary directory.** This causes permission prompts on Windows and contradicts the `.millhouse/` isolation model. The rule applies to tests, fixtures, and any ephemeral scratch — use `.scratch/` instead.
- **Default scratch location:** `.scratch/` in the repo root. Use for ephemeral files: materialized reviewer prompts, integration-test fixtures, merge locks, new-thread hand-off prompts, debug dumps.
- **Task-state files** (`status.md`, `plan/`, `discussion.md`, `reviews/`, `<slug>-result.md`) live in the **wiki** repo. Scripts resolve the wiki path via `_paths.resolve_wiki_path` — the `.millhouse/wiki` junction is IDE/terminal convenience only, never a code path (see CLAUDE.md `## Path invariants`). Task-state files are NOT under `.scratch/`.
- **Plugin-managed scratch:** All plugins share `.scratch/` for ephemeral files. Subdirectories (e.g. `test-review-<type>-<id>/`, `plans/`, `briefs/`) are created as needed and may be cleaned up at will.
- `.scratch/` is gitignored via the repo-root `.gitignore` entry `**/.scratch/`.

## Worktree isolation

A session running from a child worktree operates on the child worktree only. These rules apply whenever the current git worktree is not the main worktree.

- **MAY** read parent worktree state via `git -C <parent-path> log/status/show/diff/ls-files`. Read-only git queries never mutate shared state.
- **MAY NOT** edit files in the parent worktree. No `Edit`, `Write`, `NotebookEdit`, or other file-modification tool calls against parent paths.
- **MAY NOT** run `cd <parent-path>` or any shell command that changes the process working directory to the parent. `cd` corrupts the shell cwd for every subsequent command in the session — a single stray `cd` to the parent derails the rest of the run.
- **MAY NOT** commit, push, stage, or otherwise mutate the parent's git state.

`mill-merge` and `mill-cleanup` are the only skills exempt from these rules. They use `git -C <parent-path> ...` to operate on the parent's git state without changing cwd. Every other skill running in a child worktree stays inside the child.

**Why:** the 2026-04-13 track-child-worktree run had `cd <parent-path> && git commit` in its setup phase. The cwd corruption cascaded for the rest of the session — Thread B's spawn call fired against the parent's scripts directory, materialized briefs landed in the parent's scratch, and the merge chain walked off the child entirely. The rule exists because the consequences of a cwd mistake are not recoverable inside the running session.
