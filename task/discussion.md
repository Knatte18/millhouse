# Discussion: 32 (A) — Bug-fix batch 2

```yaml
task: '32 (A) — Bug-fix batch 2'
slug: mill-misc-fixes-2
status: discussing
parent: main
```

## Problem

Seven small, independent defects surfaced from the GitHub-issue triage on 2026-05-08. Each is a self-contained bug or doc gap inside the mill plugin; none requires architectural change. Bundling them as one task keeps the plan/review/merge overhead amortised across all seven, which is appropriate because each individual fix is too small to justify its own pipeline run.

**Why now:** the holistic-implement crash (#200) silently breaks every holistic dispatch and the `_gh_issues.detect_repo` cwd-bug (#202) blocks `gh issue close --repo …wiki` paths in mill-autofix. The remaining items (logging consistency, doc gaps, validator completeness, spawn-push) are bookkeeping that has accumulated over recent task batches.

## Scope

**In:**

- `plugins/mill/scripts/millpy-implement-holistic.py` — prefix `task/` on three local-path constructions.
- `plugins/mill/scripts/_plan_validate.py` — extend the cards-side union in `_check_all_files_touched_mismatch` to include `Deletes:` tokens.
- `plugins/mill/scripts/_gh_issues.py` — make `detect_repo` accept an explicit `git_root` and drop `gh repo view` from the resolution chain. Update `fetch` and `close_with_comment` to pass it through.
- `plugins/mill/skills/mill-autofix/SKILL.md` — update the two `_gh_issues` call sites (`fetch` at line 45, `close_with_comment` at line 377) to pass `git_root=<hub-path>` per the `detect-repo-explicit-git-root` Decision's MUST requirement.
- `plugins/mill/skills/mill-ghissues-to-tasks/SKILL.md` — update the three `_gh_issues` call sites (`fetch` at line 27, `detect_repo` at line 32, `close_with_comment` at line 127) to pass `git_root=<hub-path>` per the same Decision. The line-32 detect_repo() call records the repo name for the close step; under the new scheme it can either pass `git_root=` to stay correct or be dropped (`close_with_comment` now takes `git_root=` directly, making the recorded repo name redundant). Plan should choose whichever yields a cleaner SKILL.md flow.
- `plugins/mill/scripts/_spawn_core.py` — in `write_initial_status`, push the initial `spawn: init status for <slug>` commit with `--set-upstream origin <branch>` after the existing add+commit.
- `plugins/mill/scripts/millpy-builder-lock.py` — emit `[builder-lock] acquired by <slug>` on **stderr** after a successful `_builder_lock.acquire` call.
- `plugins/mill/skills/mill-plan/SKILL.md` — document the `--holistic-only` and `--no-holistic` flags in the Plan Review phase invocation.
- `CLAUDE.md` (repo root) — add a `$CLAUDE_PLUGIN_ROOT` warning next to the existing `PYTHONPATH` note.
- `plugins/mill/unit_tests/test-plan-validate.py` — add a Deletes case for `all-files-touched-mismatch`.
- `plugins/mill/unit_tests/test-gh-issues.py` — add `detect_repo` unit tests covering the new `git_root` parameter and a wiki-cwd repro.

**Out:**

- The path-resolution audit (task 35) — `detect_repo` is fixed in isolation; broader `resolve_active_worktree`/`resolve_active_hub` work belongs in Layer B.
- Renaming `task/` → `_mill/` (task 33) — the #200 fix uses the current `task/` prefix; the rename is a separate Layer C task.
- Reviewer-registry / `wiki/reviewers.yaml` work (task 34) — unrelated.
- Adding new `--flag` behaviour to `millpy-review-plan.py` — the flags already exist; we only document them.
- New integration-test infrastructure — the script-only fixes (#200, #191, #192) are verified post-merge via the normal smoke; no new harness work.
- `_builder_lock.acquire` itself — the log line lives in the CLI script, not the helper, so the helper stays a pure mutex with no I/O side-effects.

## Decisions

### log-stream-builder-lock

- Decision: Emit `[builder-lock] acquired by <slug>` on **stderr** from `millpy-builder-lock.py acquire` after `_builder_lock.acquire` returns.
- Rationale: matches `_wiki._acquire`'s actual behaviour (which writes its `[wiki] _acquire: acquired by …` line to stderr); keeps stdout reserved for parseable CLI output (the `read` subcommand's `slug:` / `timestamp:` lines remain on stdout).
- Rejected: stdout (Home.md text) — would mix log output with the existing parseable stdout from `read` and silently break any future caller that grepped stdout for the lock holder.

### detect-repo-explicit-git-root

- Decision: Add `git_root: Path | None = None` parameter to `detect_repo()`, `fetch()`, and `close_with_comment()` in `_gh_issues.py`. Drop the `gh repo view` call entirely; resolve repo via `git -C <git_root> remote get-url origin` and the existing https/ssh regex. When `git_root is None`, fall back to `_paths.resolve_git_root()` (cwd-derived) for backward compatibility — but the two in-tree callers (`mill-autofix`, `mill-ghissues-to-tasks`) MUST pass the hub git root explicitly.
- Rationale: the cwd-sensitive bug exists because `gh repo view` reads the current shell's git context. Removing it eliminates the failure class. Threading an explicit param keeps the helper testable (mock subprocess once) and makes the calling convention explicit at every call site.
- Rejected: auto-walking up via `_paths.resolve_main_worktree_root(_paths.resolve_git_root())` — fails when cwd is in the wiki because the wiki is its own git repo; `--git-common-dir` returns the wiki's `.git`, not the hub's.

### deletes-counted-in-all-files-touched

- Decision: In `_check_all_files_touched_mismatch`, union `_parse_deletes_only(batch_path)` for each batch into the `cards_set`. The function already exists and is used by `_check_non_existent_path`. Also update both finding-message strings (`_plan_validate.py:692-694` and `:702-704`) from `"Edits: or Creates:"` / `"Edits:/Creates:"` to `"Edits:, Creates:, or Deletes:"` / `"Edits:/Creates:/Deletes:"` so the post-fix diagnostics match the broadened union.
- Rationale: All Files Touched is "the union of every path mentioned in cards". Deletes are touched (they vanish), so they belong. The honest fix is one line; documenting "deleted files belong elsewhere" would create a special-case readers must remember. Updating the message strings keeps the validator's diagnostic honest about what is being checked.
- Rejected: documentation-only fix — adds a footnote operators have to recall mid-plan-review; brittle. Leaving the message strings stale — would mislead the next reader into thinking Deletes is still excluded.

### push-with-upstream-in-spawn

- Decision: Inside `_spawn_core.write_initial_status`, after the existing `git add` + `git commit`, run `git -C <worktree_path> push --set-upstream origin <branch>`. Branch name comes from the existing `branch:` parameter. Treat non-zero exit as `RuntimeError` with subprocess stderr included (same shape as the existing add/commit checks).
- Rationale: the helper already mutates remote-bound state on the task branch (commit). Push is the natural completion. Keeping the call in `write_initial_status` means there's one source of truth for "the spawn commit was published". The function name covers it: rendering + writing + persisting.
- Rejected: pushing in `millpy-spawn.py main()` after the helper returns — splits a single logical operation (write + commit + push) across two files; future readers would need to remember to inspect both.

### plan-flag-documentation

- Decision: Add a one-paragraph note immediately after the bash invocation block in `mill-plan/SKILL.md` Phase: Plan Review step 2. Note shape: "The CLI accepts two optional scope flags: `--holistic-only` (skip per-batch reviews; run only holistic) and `--no-holistic` (run per-batch only; skip holistic). Mutually exclusive. Default — both run per `review.plan.batch`/`holistic` config."
- Rationale: matches the existing inline-paragraph documentation style for the `--max-rounds` flag in step 6. Keeps everything for one phase in one place.
- Rejected: a new "Flags" sub-section — overstates importance for two optional flags; fragments the Plan Review phase text.

### holistic-implement-paths

- Decision: In `millpy-implement-holistic.py`, change four lines to prefix `task/`:
  - line 77: `status_path = project_root / "status.md"` → `project_root / "task" / "status.md"`
  - line 91: `overview_path = project_root / "plan" / "00-overview.md"` → `project_root / "task" / "plan" / "00-overview.md"`
  - line 103: `str(project_root / "plan" / b["file"]) for b in batches` → `str(project_root / "task" / "plan" / b["file"]) for b in batches` (the `BATCH_FILES` token sent to the LLM prompt)
  - line 123: `["git", "add", "status.md", review_file_arg]` → `["git", "add", "task/status.md", review_file_arg]`
  Also update the corresponding error messages so they reference the `task/`-prefixed paths.
- Rationale: every other implementer/reviewer script reads working state from `task/`. This was the lone outlier and crashes immediately on dispatch.
- Rejected: refactoring to use `cfg["paths"]["discussion_file"]` and friends — out of scope; matches the codebase's current approach of referencing `task/...` literals (see `mill-plan/SKILL.md` and `_review_common.py`). Task 33 (paths cleanup) will rationalise this.

### claude-plugin-root-doc-note

- Decision: Inside the existing `**Mill scripts are invoked via `uv run`, not `python`.**` bullet in `CLAUDE.md`'s "Conventions worth carrying" section, append a sentence after the existing PYTHONPATH note. Wording: "Similarly, `${CLAUDE_PLUGIN_ROOT}` may be empty in some Bash subshells (observed on Windows VS Code); when empty, fall back to `plugins/mill/` source-tree paths only when running from the millhouse repo itself, otherwise hardcode the cache path the user shows you."
- Rationale: the warning lives next to the related env-var note, so an operator who hits one of the two failure modes finds both. Doesn't introduce a new top-level bullet.
- Rejected: a separate top-level bullet — duplicates context; readers would have to cross-reference.

## Technical context

**Files and helpers reused by multiple cards:**

- `_paths.resolve_git_root()` and `_paths.resolve_main_worktree_root()` — used by the new `detect_repo(git_root=...)` callers.
- `_subprocess_util.run` — already used by `_gh_issues` and `_spawn_core`; the push and git-remote-get-url calls use it.
- `_parse_deletes_only` already exists in `_plan_validate.py:178-214`. The fix in `_check_all_files_touched_mismatch` is one extra line that unions it into `cards_set`.
- `_builder_lock.acquire` — pure helper; the log line is added in the CLI wrapper (`millpy-builder-lock.py:36-41`), not the helper, to keep `_builder_lock.py` I/O-free.

**Where each fix lands:**

- `#200` — `plugins/mill/scripts/millpy-implement-holistic.py` lines 77, 91, 103, 123 (and the matching error-message lines 88, 93).
- `#196` — `CLAUDE.md` "Conventions worth carrying" section, the existing `**Mill scripts are invoked via `uv run`...**` bullet.
- `#194` — `plugins/mill/skills/mill-plan/SKILL.md`, Phase: Plan Review section, immediately after step 2's bash invocation block.
- `#193` — `plugins/mill/scripts/_plan_validate.py:_check_all_files_touched_mismatch` (lines 651–707). The cards_set union is on lines 678–682; the two finding-message strings are on lines 692–694 and 702–704.
- `#192` — `plugins/mill/scripts/millpy-builder-lock.py` lines 35–41 (the `acquire` subcommand body), one new `print(..., file=sys.stderr)` after `_builder_lock.acquire`.
- `#191` — `plugins/mill/scripts/_spawn_core.py:write_initial_status` (lines 682–743). Add a third `_subprocess_util.run` call for `git push --set-upstream origin <branch>` after the commit succeeds, with the same error-shape pattern.
- `#202` — `plugins/mill/scripts/_gh_issues.py:35-57` (`detect_repo`), `:89-132` (`fetch`), `:135-169` (`close_with_comment`). Add `git_root` param to all three; remove the `gh repo view` call from `detect_repo`. Update SKILL.md callers in `mill-autofix/SKILL.md` and `mill-ghissues-to-tasks/SKILL.md` to pass the hub git_root explicitly.

**Gotchas:**

- The `git push --set-upstream` call must run on the task worktree, not the hub. `write_initial_status` already uses `git -C <worktree_path> ...` for add/commit, so the push must use the same `-C`.
- `_gh_issues.detect_repo`'s ssh-URL regex (`^git@github\.com:(.+?)(?:\.git)?$`) and https-URL regex are correct as-is. Only the lookup mechanism changes; the parsing keeps current behaviour.
- The `mill-autofix` SKILL.md `_gh_issues.fetch(label_filter=['bug'])` call (line 45) and `_gh_issues.close_with_comment(...)` call (line 377) need the `git_root=...` kwarg added; same for `mill-ghissues-to-tasks/SKILL.md` lines 27, 32 (`detect_repo`), and 127.
- The flag block `scope_group = parser.add_mutually_exclusive_group()` in `millpy-review-plan.py:38-48` is the source of truth for the documented behaviour — the SKILL.md note must match (mutually exclusive, default = both run).
- `millpy-review-plan.py` is invoked via `millpy-bg.py` in mill-plan. Flag documentation lives in mill-plan's SKILL.md only — the bg wrapper passes through extra args, so the SKILL.md note can show the user adding the flag as a final argument to the inner `uv run …millpy-review-plan.py` part of the pipeline.

## Constraints

- Junction usage: the doc-edit cards must NOT reference `.wiki` or `.active` as code paths (CLAUDE.md `## Path invariants`); only the operator-facing prose may mention them.
- `${CLAUDE_PLUGIN_ROOT}` rule: the new sentence in CLAUDE.md must say `plugins/mill/` (without the `${CLAUDE_PLUGIN_ROOT}` template) only as the *fallback string the operator types when the env var is empty*; do not advise hardcoding `plugins/mill/` paths in scripts or SKILLs.
- Working state: every change touches `plugins/mill/...` source under the worktree root, not the wiki. No wiki writes anywhere in this batch.
- Commit pattern in `write_initial_status`: must keep the existing "spawn: init status for {slug}" commit message (downstream `git log` filters watch for it).

## Testing

**TDD candidates (write the test first):**

- `_plan_validate._check_all_files_touched_mismatch` Deletes case — extend `test-plan-validate.py` with a fixture where:
  1. Overview's All Files Touched lists `foo.md`.
  2. Card has `Deletes: foo.md` and no `Edits:`/`Creates:` for it.
  3. Pre-fix: validator reports an `all-files-touched-mismatch` (false positive). Post-fix: no finding.
- `_gh_issues.detect_repo` — extend `test-gh-issues.py` with three cases:
  1. `git_root=<hub>` and `git remote get-url origin` returns the hub URL → returns hub's `owner/repo`.
  2. `git_root=<wiki>` and `git remote get-url origin` returns the wiki URL → returns wiki's `owner/repo` (proves the parameter is honoured).
  3. `git_root=None` falls back to `_paths.resolve_git_root()` — mock that to return a stub path; verify the same `git -C ... remote get-url origin` is invoked. (Optional but cheap.)
  All three patch `_subprocess_util.run` only; no real git invocation.

**Verified by reading + smoke (no new tests):**

- #200 (millpy-implement-holistic path prefixes) — pure literal change; correctness obvious from the diff.
- #191 (push --set-upstream) — verified the next time mill-spawn fires; the existing first downstream `git push` from mill-plan/mill-go will succeed without the "no upstream" error.
- #192 (builder-lock log line) — visible in mill-go logs the next time a batch acquires.
- #196 (CLAUDE.md doc note) — doc-only.
- #194 (mill-plan SKILL.md flag note) — doc-only.

**Existing tests not affected:**

- `test-plan-validate.py` already covers Edits/Creates cases for All Files Touched. Adding the Deletes case follows the same fixture pattern.
- `test-gh-issues.py` already mocks `_gh_issues._subprocess_util.run`. The new tests follow the existing `with patch("_gh_issues._subprocess_util.run", side_effect=_mock_run):` pattern.

**Test runner:** `python plugins/mill/unit_tests/run-all.py` (the standard runner per CLAUDE.md `## Repo layout pointers`).

## Q&A log

- **Q:** Stream for `[builder-lock] acquired by <slug>` — stdout (Home.md) or stderr (matches `_wiki._acquire`)? **A:** stderr. Keep stdout reserved for parseable output.
- **Q:** Should `_gh_issues.detect_repo` auto-detect the hub or take an explicit `git_root`? **A:** Explicit `git_root` parameter; drop `gh repo view`. Auto-detect breaks when cwd is the wiki.
- **Q:** Count `Deletes:` in `all-files-touched-mismatch`, or document the gap? **A:** Count them — `_parse_deletes_only` already exists; the fix is one line.
- **Q:** Where does the `git push --set-upstream` for the spawn commit live? **A:** Inside `_spawn_core.write_initial_status`, after the existing add+commit.
- **Q:** Where do the `--holistic-only` / `--no-holistic` docs go in `mill-plan/SKILL.md`? **A:** A short paragraph after the bash invocation block in Phase: Plan Review step 2.
- **Q:** Test coverage scope? **A:** Unit tests for `_plan_validate` Deletes case and `_gh_issues.detect_repo`. Other fixes verified by code-read + post-merge smoke.
- **Q (review-r1, GAP):** Are mill-autofix and mill-ghissues-to-tasks SKILL.md files in scope for #202? **A:** Yes — both must be updated to pass `git_root=` to `_gh_issues.fetch` and `close_with_comment` so the explicit-param Decision is realised at every call site. Added to Scope **In:**.
- **Q (review-r1, NOTE):** After unioning Deletes in `all-files-touched-mismatch`, do the finding-message strings need updating? **A:** Yes — `_plan_validate.py:692-694` and `:702-704` currently say "Edits: or Creates:"; updated to include "Deletes:" so the diagnostics match the broadened union.
- **Q (review-r2, GAP):** Was line 103 of `millpy-implement-holistic.py` covered by the planned #200 fix? **A:** No — original issue triage missed it. The `BATCH_FILES` token construction `str(project_root / "plan" / b["file"])` is the same `task/` prefix omission and now sits in the holistic-implement-paths Decision alongside lines 77/91/123.
- **Q (review-r2, NOTE):** Is `mill-ghissues-to-tasks/SKILL.md:32` `detect_repo()` covered? **A:** Now yes — added to Scope. Plan may either pass `git_root=` or drop the line (since `close_with_comment(git_root=...)` makes the recorded repo name redundant). Plan picks whichever flows cleaner.
