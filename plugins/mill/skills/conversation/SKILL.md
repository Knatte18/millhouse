---
name: conversation
description: Interaction rules for chat replies — tone, user choices, file/shell conventions, worktree isolation. Always active. Builds on `prose`.
---

# Conversation

Rules for talking to the user directly, in chat.
`prose` governs how any text is written;
this skill adds what's specific to a live conversation with a person and to this orchestrator's own operating conventions.
Load `prose` first — this skill assumes those rules already apply.

---

## Response Style

- If the user asks a question: **only answer**.
  Do not edit code.
- Never compliment the user.
  Criticize ideas constructively and ask clarifying questions.
- **Avoid these phrases:** "You're right", "I apologize", "I'm sorry", "Let me explain", "Great question"
- **Default to short.**
  One paragraph, or a short list, is the default reply length for a chat turn — not multiple bolded subsections.
  Sentence-level economy (`prose`'s rules) isn't enough on its own: a reply can follow every one of those rules per-sentence and still balloon to five headed sections.
  Match the terseness of the exchange — a rapid back-and-forth (Q&A, corrections, banter) gets a sentence or two, never headers.
  Expand past one paragraph only when the request is inherently multi-part (a plan, a list of file changes, a comparison) or the user asks for elaboration.
- **Match the user's language.**
  Reply in the language the user is writing in.
  Don't drift to English mid-conversation because a source file, tool output, or GitHub issue you just read was in English — translate what you relay, don't switch languages to match it.

## Prompts for New Threads

- When writing a prompt for a new thread: **write it to a file** at `.scratch/prompt.md` (or `.scratch/prompt-<slug>.md` if multiple).
  Never dump long prompts inline in the chat.
- Tell the user: `Read .scratch/prompt.md and follow the instructions there.`
- If the prompt needs amendments before the user has started the thread: overwrite the file with the complete updated prompt.
  Never show partial diffs.
- The user copies from the file in the editor, which has a built-in copy function.
- **Every prompt must instruct the receiving thread to:** write its full report/result to a file (e.g. `.scratch/result-<slug>.md`) and only output to the user: (1) the path to the result file, and (2) a brief summary of key points.
  This keeps thread output concise and results reviewable.

## User Choices

- **Never use `AskUserQuestion`.**
  It requires mouse interaction.
- **Always use numbered text lists.**
  Print each option as `1) Label — description`.
  The recommended option, if any, MUST be option 1;
  remaining options follow in any order.
  The `(Recommended)` suffix appears after the label of option 1.
- The user types the number (e.g. `1`), multiple numbers for multi-select (e.g. `1, 3`), or free text for something else.
- Keep descriptions short — one line per option.

**Skill authors:** any new skill that prompts the user MUST present options as a numbered text list per the rules above.
This is non-negotiable for new skills and applies retroactively — when you touch an existing skill that uses prose prompts, convert them.

## File Writing

- **Never write to `/tmp/`, `$env:TEMP`,
  or any system temporary directory.**
  This causes permission prompts on Windows and contradicts the `.millhouse/` isolation model.
  The rule applies to tests, fixtures, and any ephemeral scratch — use `.scratch/` instead.
- **Default scratch location:** `.scratch/` in the repo root.
  Use for ephemeral files: materialized reviewer prompts, integration-test fixtures, merge locks, new-thread hand-off prompts, debug dumps.
- **Task-state files** (`status.md`, `plan/`, `discussion.md`, `reviews/`, `<slug>-result.md`) live in the **wiki** repo.
  Scripts resolve the wiki path via `_paths.resolve_wiki_path` — the `.wiki` junction is IDE/terminal convenience only, never a code path (see CLAUDE.md `## Path invariants`).
  Task-state files are NOT under `.scratch/`.
- **Plugin-managed scratch:** All plugins share `.scratch/` for ephemeral files.
  Subdirectories (e.g. `test-review-<type>-<id>/`, `plans/`, `briefs/`) are created as needed and may be cleaned up at will.
- `.scratch/` is gitignored via the repo-root `.gitignore` entry `**/.scratch/`.

## Shell Commands

- **Never use `sed`.**
  It triggers a permission prompt on every invocation, which blocks unattended/autonomous runs.
  Use `Edit`/`Read`/`Write`, or `awk`/`grep`/plain `cat` for a genuine one-liner.
  Applies to every Bash call made directly by the orchestrator (mill-start, mill-plan, mill-go, mill-go2,
  and any skill that loads this file) and to any `Agent(subagent_type: "fork")` dispatch, which inherits this rule along with the rest of the parent's context.

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
