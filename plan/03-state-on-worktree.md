# Batch: state-on-worktree

```yaml
task: 11 — par-C — Container layout overhaul + cwd-as-hub everywhere + gitignore-split
batch: state-on-worktree
cards: 5
verify: python plugins/mill/unit_tests/run-all.py
depends-on: [create-hub-links]
```

## Batch Scope

This batch moves task working state out of the wiki and onto the task branch in the worktree itself: `status.md`, `discussion.md`, `plan/`, and `reviews/` now live at the worktree root (`<wts>/<slug>/`), tracked by git on the task branch. The review subsystem (`_review_common.resolve_path` and the three review CLI scripts) switches its base-path resolution from "wiki + slug template" to "active worktree + worktree-relative template". `wiki/config.yaml` `paths:` block is updated to the worktree-relative shape so that `_review_common.resolve_path` reads the new templates. The `mill-start` and `mill-plan` SKILL.md files are rewritten to write `discussion.md` and `plan/` files to the worktree root and commit them on the task branch (replacing the previous `_wiki.write_commit_push` calls) — these prose changes land in this batch, not batch 04, so the read-side change (Card 12) and the write-side change (Card 15) are deployed together and the half-deployed state where reads expect the worktree but writes still go to the wiki cannot occur. After this batch lands, a fresh `mill-spawn` writes `status.md` to the new worktree, `mill-start` writes `discussion.md` there, `mill-plan` writes `plan/` there, and review scripts read all three from the worktree. The cleanup-on-merge story (the `git rm -r reviews/ discussion.md plan/ status.md` commit before squash) is wired in batch 04 with the rest of `mill-merge` SKILL.md changes; no merge happens in this batch. Local decision diverging from shared: `_spawn_core.write_initial_status` and the equivalent prose paths in mill-start/mill-plan now commit to the task branch in the new worktree, not to the wiki — this is a workflow shift, not just a path shift.

## Cards

### Card 11: `_spawn_core.write_initial_status` writes to worktree root + commits to task branch

- **Reads:**
  - `plugins/mill/scripts/_spawn_core.py`
  - `plugins/mill/scripts/_status.py`
  - `plugins/mill/scripts/_subprocess_util.py`
  - `plugins/mill/scripts/millpy-spawn.py`
  - `plugins/mill/unit_tests/test-spawn-core.py`
  - `plugins/mill/unit_tests/test-millpy-spawn.py`
  - `wiki/active/container-restructure/discussion.md`
- **Modifies:**
  - `plugins/mill/scripts/_spawn_core.py`
  - `plugins/mill/scripts/millpy-spawn.py`
  - `plugins/mill/unit_tests/test-spawn-core.py`
  - `plugins/mill/unit_tests/test-millpy-spawn.py`
- **Creates:** none
- **Requirements:** Change `_spawn_core.write_initial_status`'s signature from `write_initial_status(wiki_path, slug, title, ts, parent_branch, branch)` to `write_initial_status(worktree_path, slug, title, ts, parent_branch, branch)`. The function now writes `status.md` directly at `worktree_path / "status.md"` (worktree root, NOT `worktree_path / ".millhouse" / "status.md"` — the file is git-tracked on the task branch). After writing, the function stages and commits the file ON THE TASK BRANCH inside the worktree: run `git -C <worktree_path> add status.md`, then `git -C <worktree_path> commit -m "spawn: init status for {slug}"`. Both subprocess calls go through `_subprocess_util.run`; the function checks `returncode != 0` after each and raises `RuntimeError` with `result.stderr.strip()` included, mirroring the existing discipline in `_spawn_core.capture_parent_branch`. Do NOT push — pushing the task branch is a separate operation handled later by mill-go or mill-merge (the wiki is no longer in the loop for this commit). The wiki commit-push call (`_wiki.write_commit_push(wiki_path, [status_rel], ...)`) is removed entirely from this function. Return the absolute path to the written status.md (still `<worktree_path>/status.md`). Update the `millpy-spawn.py` callsite to pass `worktree_path` instead of `wiki_path` and adjust the live-run status-path log line. Also update `millpy-spawn.py`'s `--dry-run` branch (currently prints `wiki_path / 'active' / slug / 'status.md'`): change the printed path to `worktree_path / 'status.md'` so dry-run output matches what the live run would do. Tests in `test-spawn-core.py` use a temp git repo (initialised in the fixture, following the `_make_git_repo` pattern already in `test-spawn-core.py`) and assert: status.md exists at worktree root, `git log --oneline status.md` returns one commit with the expected message, file content matches the rendered template, and a forced-failure case raises `RuntimeError` with stderr in the message — the concrete technique is to delete `<repo>/.git/index` (or set the file to read-only on POSIX) just before calling `write_initial_status`, which produces a real non-zero exit from the `git add` subprocess. Do NOT patch `_subprocess_util.run` for this case — the test must drive the real subprocess error path so we are confident the error-handling discipline works in production. ALSO update the `_spawn_core.py` module-level docstring API summary entry for `write_initial_status`: rename the documented parameter from `wiki_path` to `worktree_path` and change the summary line from "Render + write `active/<slug>/status.md`; lock + commit+push" to "Render + write `status.md` at worktree root; stage + commit on task branch" so the docstring matches the new behaviour. Tests in `test-millpy-spawn.py` extend the spawn fixture to assert (a) no status.md is written into the wiki for the new slug (`wiki/active/<slug>/` does NOT appear), and (b) the dry-run output prints `<worktree_path>/status.md` rather than the legacy wiki path.
- **Commit:** `refactor(spawn): write status.md to worktree root on task branch`

### Card 12: `_review_common.resolve_path` worktree-relative

- **Reads:**
  - `plugins/mill/scripts/_review_common.py`
  - `plugins/mill/scripts/_paths.py`
  - `plugins/mill/unit_tests/test-review-common.py`
  - `wiki/active/container-restructure/discussion.md`
- **Modifies:**
  - `plugins/mill/scripts/_review_common.py`
  - `plugins/mill/unit_tests/test-review-common.py`
- **Creates:** none
- **Requirements:** Change `resolve_path(path_tmpl, slug, wiki_root)` to `resolve_path(path_tmpl, slug)`. The new body computes `container_path` internally via `_paths.resolve_container_path(Path.cwd())` (using the helper added in Card 4 — handles both container-form and prefix-form correctly; do NOT use `resolve_main_worktree_root(Path.cwd()).parent` which returns `<container>/wts/` in container-form and would land `resolve_active_worktree(container_path, slug)` at `<container>/wts/wts/<slug>`, an empty phantom directory). Then `active_worktree = _paths.resolve_active_worktree(container_path, slug)`, and the function returns `active_worktree / path_tmpl` after stripping any `<SLUG>` substitution from `path_tmpl`. Note on the `<SLUG>` strip: it prevents a path-segment like `<SLUG>` from appearing literally in the joined result if a stale config still has the old templates; paths still fail at file-open time until Card 14 deploys the new `paths:` block, so this is purely a "don't crash on the token" guard, not a backward-compat correctness bridge. Drop the `wiki_root` parameter and any reference to it in the docstring. The function still returns an absolute `Path` with no on-disk-existence check — the caller chooses to read or write. The slug parameter remains for forward-compatibility with future per-slug routing inside the worktree, even though the current templates don't substitute it. Tests in `test-review-common.py`: use a real-git-repo fixture (initialise git inside the tempdir, following `_make_git_repo` in `test-spawn-core.py` as the pattern), then create `<container>/wts/<slug>/.millhouse/active.slug.md` via `_active.write` inside the fixture so `_paths.resolve_main_worktree_root` returns the fixture's `<container>/wts/<slug>` and `_paths.resolve_active_worktree(container_path, slug)` finds it. Use `os.chdir` (with try/finally to restore) to make `Path.cwd()` resolve inside the fixture. Tests assert: `resolve_path("discussion.md", slug)` → `<container>/wts/<slug>/discussion.md`; cover `plan/`, `reviews/`, and a nested template like `reviews/r1/holistic.md`; cover the slug-mismatch error from `_paths.resolve_active_worktree`. Do NOT mock `_paths.resolve_main_worktree_root` or `_subprocess_util.run` — the real-git-repo fixture is preferred because it exercises the same code path the live CLI does.
- **Commit:** `refactor(review-common): resolve_path returns worktree-relative path`

### Card 13: `_review_*.py` + `millpy-review-*.py` updated for new resolve_path

- **Reads:**
  - `plugins/mill/scripts/_review_discussion.py`
  - `plugins/mill/scripts/_review_plan.py`
  - `plugins/mill/scripts/_review_code.py`
  - `plugins/mill/scripts/millpy-review-discussion.py`
  - `plugins/mill/scripts/millpy-review-plan.py`
  - `plugins/mill/scripts/millpy-review-code.py`
  - `plugins/mill/scripts/_review_common.py`
  - `plugins/mill/unit_tests/test-review-discussion-flow.py`
  - `plugins/mill/unit_tests/test-review-plan-flow.py`
  - `plugins/mill/unit_tests/test-review-code-flow.py`
- **Modifies:**
  - `plugins/mill/scripts/_review_discussion.py`
  - `plugins/mill/scripts/_review_plan.py`
  - `plugins/mill/scripts/_review_code.py`
  - `plugins/mill/scripts/millpy-review-discussion.py`
  - `plugins/mill/scripts/millpy-review-plan.py`
  - `plugins/mill/scripts/millpy-review-code.py`
  - `plugins/mill/unit_tests/test-review-discussion-flow.py`
  - `plugins/mill/unit_tests/test-review-plan-flow.py`
  - `plugins/mill/unit_tests/test-review-code-flow.py`
- **Creates:** none
- **Requirements:** Update every `resolve_path(...)` call inside the three `_review_*.py` backend modules to use the new two-arg signature (drop the trailing `wiki_root` argument). Update each module's `run(...)` signature: the `wiki_root` parameter stays in the signature ONLY where it is still used for OTHER purposes (e.g. constraints reading, lockfile paths) — drop it from each function that no longer needs it after this refactor. The three CLI scripts (`millpy-review-discussion.py`, `millpy-review-plan.py`, `millpy-review-code.py`) currently set `wiki_root = (mill_dir / "wiki").resolve()` from the junction — replace this with `wiki_root = _paths.resolve_wiki_path(Path.cwd())` if `wiki_root` is still passed to `_review_*.run(...)`; otherwise drop the variable. The `project_root = Path.cwd()` line stays. The CLI scripts must continue to accept zero positional args (per the existing argparse setup). Extend the three flow tests: instead of asserting review files land at `<wiki>/active/<slug>/reviews/...`, assert they land at `<container>/wts/<slug>/reviews/...`. Use the same real-git-repo fixture shape as Card 12 (init git inside the tempdir, populate `<container>/wts/<slug>/.millhouse/active.slug.md` via `_active.write`, and use `os.chdir` with try/finally to make `Path.cwd()` resolve inside the fixture). Do NOT use mocks for `_paths.resolve_main_worktree_root` — the live CLI calls it through subprocess, and tests should match. Note: this card depends on Card 14 (paths block update) for the new `paths:` shape to actually be in `wiki/config.yaml`; land Card 14 immediately after this one to avoid a half-deployed state where the code expects worktree-relative templates but the config still has `active/<SLUG>/discussion.md`.
- **Commit:** `refactor(review): drop wiki_root from resolve_path callers`

### Card 14: `wiki/config.yaml` `paths:` block worktree-relative

- **Reads:**
  - `wiki/config.yaml`
  - `wiki/active/container-restructure/discussion.md`
- **Modifies:**
  - `wiki/config.yaml`
- **Creates:** none
- **Requirements:** Replace the existing `paths:` block:
  ```yaml
  paths:
    discussion_file: active/<SLUG>/discussion.md
    plan_dir:        active/<SLUG>/plan/
    reviews_dir:     active/<SLUG>/reviews/
  ```
  with the worktree-relative shape:
  ```yaml
  paths:
    discussion_file: discussion.md
    plan_dir:        plan/
    reviews_dir:     reviews/
  ```
  No `<SLUG>` token in the new templates — the slug is consumed by `_paths.resolve_active_worktree(container_path, slug)` to pick the worktree, and the templates are joined onto that worktree path. The header comment above `paths:` must be updated: drop the line referencing `<SLUG>` substitution by `_review_common.resolve_path`, since the templates no longer contain `<SLUG>`. Other config blocks unchanged. Commit goes to the wiki repo via `_wiki.write_commit_push`.
- **Commit:** `chore(wiki-config): paths block becomes worktree-relative (drop <SLUG>)`

### Card 15: `mill-start` + `mill-plan` SKILL.md prose — write state to worktree on task branch

- **Reads:**
  - `plugins/mill/skills/mill-start/SKILL.md`
  - `plugins/mill/skills/mill-plan/SKILL.md`
  - `plugins/mill/scripts/_status.py`
  - `plugins/mill/scripts/_wiki.py`
  - `plugins/mill/scripts/_subprocess_util.py`
  - `plugins/mill/templates/discussion.md`
  - `plugins/mill/templates/plan-overview.md`
  - `plugins/mill/templates/plan-batch.md`
  - `wiki/active/container-restructure/discussion.md`
- **Modifies:**
  - `plugins/mill/skills/mill-start/SKILL.md`
  - `plugins/mill/skills/mill-plan/SKILL.md`
- **Creates:** none
- **Requirements:** Both SKILL.md files currently render templates into `<WIKI_PATH>/active/<slug>/discussion.md` (mill-start) and `<WIKI_PATH>/active/<slug>/plan/00-overview.md` + per-batch files (mill-plan), then commit via `_wiki.write_commit_push(wiki_path, [...], "...")`. After this card: both files render to the WORKTREE root and commit on the TASK BRANCH. Phases that must be updated explicitly (in addition to the catch-all "drop wiki/active/<slug>/ references" rule, since that rule is easily missed when working through enumerated phases): mill-start Phase: Active (verifies `status.md` exists at the wiki path → change verification target to `<worktree_root>/status.md` written by mill-spawn after Card 11); mill-start Phase: Discussion File; mill-start Phase: Discussion Review; mill-start Phase: Handoff; mill-plan Phase: Plan; mill-plan Phase: Plan Review; mill-plan Phase: Handoff. Every prose reference to `<WIKI_PATH>/active/<slug>/...` for status/discussion/plan/reviews paths is converted in place. Specifically. (a) mill-start Phase: Discussion File rewrites the render target from `<WIKI_PATH>/active/<slug>/discussion.md` to `<worktree_root>/discussion.md` and replaces the `_wiki.write_commit_push(wiki_path, [f"active/{slug}/discussion.md"], ...)` call with: `git -C <worktree_root> add discussion.md`, then `git -C <worktree_root> commit -m "mill-start: write discussion.md for {slug}"`. The status-update calls (`_status.append_phase`, `_status.update_field`) target `<worktree_root>/status.md` directly — no `<WIKI_PATH>` indirection — and the resulting commit follows the same `git add status.md` / `git commit -m "..."` pattern. mill-start's Phase: Discussion Review subsection uses the same shape for the per-round status flips. mill-start's Phase: Handoff appends `discussed` and commits status.md on the task branch. (b) mill-plan Phase: Plan rewrites the render targets from `<WIKI_PATH>/active/<slug>/plan/00-overview.md` and `<WIKI_PATH>/active/<slug>/plan/NN-<slug>.md` to `<worktree_root>/plan/00-overview.md` and `<worktree_root>/plan/NN-<slug>.md`. The `_wiki.write_commit_push(wiki_path, [f"active/{slug}/plan/", f"active/{slug}/status.md"], ...)` call becomes: `git -C <worktree_root> add plan/ status.md` then `git -C <worktree_root> commit -m "mill-plan: write plan for {slug}"`. mill-plan Phase: Plan Review's status update + per-round commits (and the fixer-report writes under `<worktree_root>/reviews/`) follow the same shape. mill-plan Phase: Handoff also commits via the worktree-branch path. (c) Both SKILL.md files prose calls out that wiki commits are no longer used for per-task state — only `Home.md` and `_Sidebar.md` (cross-task index) still go to wiki via `_wiki.write_commit_push`; per-task `discussion.md`, `plan/`, `status.md`, `reviews/` go through `git add`+`git commit` on the task branch in the worktree. Drop any prose that still references `<WIKI_PATH>/active/<slug>/...` for these files. (d) Both files preserve the existing operator-facing flow (Phase ordering, prose voice, `mill:markdown` style); the diff is mechanical path/commit-method substitution, not a phase restructure. (e) Each `git -C ...` invocation in the prose includes a returncode check (the prose can phrase it as "raise on non-zero exit, surface stderr"); the SKILL prose follows the existing convention of using `_subprocess_util.run` for git invocations where a Python snippet is shown. (f) No scripts under `plugins/mill/scripts/` are touched in this card — these are SKILL.md prose changes only. The matching review-subsystem write paths (review files written to `<worktree_root>/reviews/...`) are already routed through `_review_common.resolve_path` per Card 12, so no additional script edits are needed for the review-file path.
- **Commit:** `docs(skills): mill-start + mill-plan write state to worktree on task branch`

## Batch Tests

`verify: python plugins/mill/unit_tests/run-all.py` — passes including the rewired flow tests in `test-review-*.py`. Implementer should land Cards 13, 14, and 15 in the same review round if practical; once all three are in, a fresh /mill-start invocation on a throwaway slug writes `discussion.md` to the worktree and the subsequent review picks it up at the same path — full end-to-end coherence. The five cards together close the wiki-as-state-storage path for `status.md`, `discussion.md`, `plan/`, and `reviews/`. State READ helpers in cross-worktree consumers (`millpy-status`, `millpy-list`, `millpy-inspect`, `millpy-cleanup`) are still reading from wiki paths until batch 04 lands; this is acceptable because the wiki side is fully empty for new slugs after this batch (mill-start no longer writes there) — the consumers will simply not find any entries until they update their discovery in batch 04. Smoke-test sequence after this batch lands and before batch 04 lands: spawn a throwaway slug; the new worktree has `status.md` + `discussion.md` (after running /mill-start) + later `plan/` (after /mill-plan) at its root, all on the task branch. `mill-status` still reads the wiki and reports an empty backlog (correct, no wiki state for this task). That transient is closed by batch 04.
