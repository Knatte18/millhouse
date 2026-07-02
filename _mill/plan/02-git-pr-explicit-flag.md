# Batch: git-pr-explicit-flag

```yaml
task: Fix daemon health-check race, finalize env-var delivery, skills-index drop, and encoding crash
batch: git-pr-explicit-flag
number: 2
cards: 2
verify: null
depends-on: []
```

## Batch Scope

Fixes #591: mill-finalize's Step 5 currently instructs invoking `/git-pr <parent_branch>` with a shell-style env-var prefix, `MILL_FINALIZE_PR_CLEANUP=1 /git-pr <parent_branch>`, intending for git-pr's Step 1.5 guard to see `$MILL_FINALIZE_PR_CLEANUP` and skip its task-branch halt. Because `/git-pr` is invoked via the Skill tool (not as a literal Bash subprocess), the env-var prefix never reaches git-pr's own later Bash tool calls — each Bash tool call is a fresh subprocess with no persisted shell state, and nothing threads an outer env var into a Skill-tool dispatch. This batch replaces the env-var contract with an explicit `--skip-task-branch-guard` flag token in the `/git-pr` invocation string, following the same `$ARGUMENTS` token-walk pattern mill-setup already uses for its own flags (e.g. `--from-url`, `--branch`). The flag stays undocumented on git-pr's public `## Usage` surface — it exists solely to coordinate an already-completed cleanup handoff between mill-finalize and git-pr, not as something an interactive operator should invoke directly.

## Cards

### Card 3: Replace env-var guard-skip with `--skip-task-branch-guard` flag in git-pr

- **Context:** none
- **Edits:**
  - `plugins/mill/skills/git-pr/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** In "### 1.5 Detect task branch": replace the explanatory sentence "Skip this entire check if the environment variable `MILL_FINALIZE_PR_CLEANUP` is set (non-empty) — mill-finalize sets this after it has already handled cleanup (removed or restored task_dir), so the guard must not block PR creation." with equivalent prose describing a `--skip-task-branch-guard` token in `$ARGUMENTS` instead of an env var. In the bash block, replace the `if [ -n "$MILL_FINALIZE_PR_CLEANUP" ]; then` branch condition with a check for whether `--skip-task-branch-guard` is present among the tokens of `$ARGUMENTS` (e.g. `case " $ARGUMENTS " in *" --skip-task-branch-guard "*)` or an equivalent presence test consistent with the token-walk style mill-setup's SKILL.md "Phase 0 — Parse arguments" uses for `--from-url`/`--branch`), keeping the `:` no-op body and the existing `elif`/`else` branches (config-based resolution, then standalone literal-path fallback) unchanged. In "### 2. Determine base branch", update item 1 ("**Argument** — if the user provided one (e.g. `/git-pr develop`), use it.") to specify that the base-branch argument is resolved as the first non-flag token of `$ARGUMENTS` — i.e., `--skip-task-branch-guard` must be stripped/ignored before determining the positional base-branch argument, so `/git-pr <parent_branch> --skip-task-branch-guard` resolves `<parent_branch>` as the base branch rather than treating the two-token string as one argument. Do NOT change the `## Usage` block or the `argument-hint: "[base-branch]"` frontmatter field — the flag stays undocumented on the public usage surface.
- **Commit:** `fix(git-pr): replace unusable env-var guard-skip with --skip-task-branch-guard flag (#591)`

### Card 4: Update mill-finalize Step 5 to invoke git-pr with the new flag

- **Context:**
  - `plugins/mill/skills/git-pr/SKILL.md`
- **Edits:**
  - `plugins/mill/skills/mill-finalize/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** In "### Step 5: Create PR", replace the instruction "Invoke `/git-pr <parent_branch>` with environment variable `MILL_FINALIZE_PR_CLEANUP=1`:" and the fenced bash block containing `MILL_FINALIZE_PR_CLEANUP=1 /git-pr <parent_branch>` with an instruction to invoke `/git-pr <parent_branch> --skip-task-branch-guard` directly (no env var, no bash fenced block needed since this is a skill invocation, not a literal shell command — match the invocation-instruction style used elsewhere in this SKILL.md for other slash-command invocations). Update the following explanatory sentence ("Cleanup has already run in Step 3 ... and `MILL_FINALIZE_PR_CLEANUP=1` tells git-pr's guard to skip its task-branch halt so PR creation proceeds in both cases.") to reference the `--skip-task-branch-guard` flag instead of the env var, keeping the rest of the sentence (referencing Step 3's cleanup already having run, and the restore-vs-remove path distinction) unchanged. Leave the remainder of Step 5 (the "If `/git-pr` fails" error-handling sentence) unchanged.
- **Commit:** `fix(mill-finalize): invoke git-pr with --skip-task-branch-guard flag (#591)`

## Batch Tests

`verify: null` — both cards edit prose+bash SKILL.md instructions consumed by an LLM orchestrator (the assistant reading and following the documented steps), not code executed by a test harness. No existing unit or integration test covers `git-pr` or `mill-finalize` (confirmed: no matches for either name under `plugins/mill/unit_tests/` or `plugins/mill/integration_tests/`). Manual verification: after implementation, run mill-finalize's PR step on a stacked-branch (restore-path, `base_tracks_task_dir` true) fixture and confirm `/git-pr <parent_branch> --skip-task-branch-guard` does not halt on git-pr's task-branch guard.
