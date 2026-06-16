# Discussion: Fix nested mill layout paths, whole-repo formatter drift, and stacked-branch PR cleanup

```yaml
task: Fix nested mill layout paths, whole-repo formatter drift, and stacked-branch PR cleanup
slug: mill-external-repo-infra
status: discussing
parent: main
```

## Problem

Four defects surface when mill is driven against an **external repo with a
non-trivial layout** — specifically a repo where the mill project root (the
directory that owns `mill-config.yaml`, `.millhouse/`, and `_mill/`) is
**nested below the git toplevel** (e.g. git root `…/wts/replica-owner-contract`,
mill project at `…/wts/replica-owner-contract/src/csharp/NORCE.Models`), and/or
where a task branch is **stacked** on a non-`main` parent.

Three of the bugs are one root cause: several path callsites anchor `_mill/`
resolution on the **git toplevel** (`resolve_git_root()`) or on **raw cwd**
instead of the nesting-aware hub resolver. In a nested layout these point at a
`_mill/` directory that does not exist (#490), or split a single task's briefs
across two different `_mill/` roots (#484, #491). The fourth is two pieces of
cross-task noise that pollute review PRs: whole-solution **formatter drift**
committed onto the task branch (#493-A), and the absence of a clean **PR-to-parent**
path for stacked tasks (#493-B).

**Why now:** these were filed (#484, #490, #491, #493) while running mill on the
NORCE Models C# repo (nested mill layout, stacked task branches). Each forced a
manual workaround — hand-corrected `_mill/` paths, relocated `.out.md` briefs, a
`git revert` of 58 drifted files, and a hand-built PR. Until fixed, mill is not
usable unattended on nested/stacked external repos.

Sources: GitHub #484, #490, #491, #493 (A and B). All resolve to the millhouse
plugin code (`plugins/mill/scripts/` + several `SKILL.md` files); none require
changes to the external repos themselves.

## Scope

**In:**

- **Path resolution (#484/#490/#491):** route every `_mill/` task-state callsite
  through the existing nesting-aware hub resolver (`resolve_hub_path()` /
  `resolve_active_hub()`), eliminating `git_root`- and raw-`cwd`-anchored
  resolution. Specific callsites:
  - `plugins/mill/scripts/millpy-review-discussion.py:96` — `briefs_dir` uses
    `git_root`; change to the already-resolved hub root (`project_root`,
    `= resolve_hub_path()`).
  - `plugins/mill/scripts/millpy-review-discussion.py:88` — `find_active_slug(git_root, …)`
    likewise moves to the hub root, for symmetry with the plan CLI (see
    review-plan-anchor below). The function's glob fallback resolves
    `<arg>/_mill/*.active`, so a `git_root` arg breaks the fallback in a nested
    layout; branch-based slug detection still works from either root.
  - `plugins/mill/scripts/millpy-review-plan.py:102` — `project_root = Path.cwd()`;
    change to `resolve_hub_path()` so both review CLIs resolve briefs/state and
    `find_active_slug` to the same hub root.
  - `plugins/mill/skills/mill-start/SKILL.md` Entry / Path Setup — **add** an
    explicit `worktree_root = _paths.resolve_hub_path()` (plus `git_root`/`hub_root`
    as needed). These SKILLs today *reference* `worktree_root` without ever
    assigning it — it is implicitly `git_root`; this is an addition of an explicit
    hub-rooted definition, not an edit of an existing `worktree_root = git_root` line.
  - `plugins/mill/skills/mill-plan/SKILL.md` Entry / Path Setup — same addition.
  - `plugins/mill/skills/mill-go/SKILL.md:151` — `resolve_task_path(resolve_git_root(), …)`
    → hub root.
  - `plugins/mill/skills/git-pr/SKILL.md` Step 1.5 — `resolve_task_path(git_root, …)`
    → hub root.
  - `plugins/mill/skills/mill-finalize/SKILL.md:17` — `worktree_root = git_root`
    → hub root.
- **Formatter drift (#493-A):**
  - Scope the **writing** formatters in the `{lang}-build` templates to changed
    files (`goimports -w`, `ruff format`/`--fix`); add a convention note that a
    whole-project formatter must never run in write mode during a batch.
  - Add a cleanliness-gate guard (new `_cleanliness.py` helper, invoked from
    mill-go's gate) that **auto-reverts out-of-scope tracked formatter drift**
    and continues, instead of blocking-then-tempting a wholesale commit.
- **Stacked-branch clean PR (#493-B):**
  - Relax mill-finalize's PR-mode trigger so a stacked task (`parent != main`)
    can open a clean PR **to its parent**, reusing the existing
    `_finalize_cleanup.base_tracks_task_dir` restore/remove logic.
- **Tests:** unit tests (tempfile + real `git`, no LLM) for nested-layout path
  resolution, the drift-revert guard, and stacked PR-mode dispatch.

**Out:**

- **#493-C** (detect pre-existing formatter drift at PR build time and offer to
  revert) — dropped. The #493-A guard prevents drift from being committed in the
  first place, so PR-time detection is redundant (YAGNI).
- **A `git-pr --mill-clean` manual mode** — not added. The clean PR path runs
  through mill-finalize; the standalone `git-pr` guard keeps halting on raw task
  branches as today.
- **No changes to `mill-spawn`'s nested-hub bootstrap.** It already writes the
  `hub_relative_path` stub at the worktree root (`millpy-spawn.py:216-222`) that
  `resolve_hub_path()` relies on. Confirmed sufficient; do not touch.
- **No changes to non-writing build/test/lint commands** (`dotnet build/test`,
  `go vet/build/test`, `pytest`, read-only `ruff check`). Whole-project coverage
  there is correct.
- **`resolve_task_path` stays a dumb join** (config-relative + the existing
  `_mill/`→`task/` compat fallback). It does not gain nesting magic.
- **The wiki / Home.md / task-index flow** is untouched.

## Decisions

### path-fix-strategy

- Decision: Route every `_mill/` task-state callsite through the existing
  hub-aware resolver (`resolve_hub_path()` for in-process scripts and the
  mill-start/mill-plan SKILLs; `resolve_active_hub()` where mill-go already uses
  it). `resolve_task_path` remains a plain `worktree_root / cfg_relative_path`
  join with its current `_mill/`→`task/` fallback — callers pass the **hub
  root**, never `git_root` or raw `cwd`.
- Rationale: The nesting-aware machinery already exists and is the documented
  design intent (`resolve_hub_path` cwd-walk + worktree-root stub;
  `resolve_active_hub` two-tier lookup). The bugs are callsites that bypass it.
  Fixing callsites keeps resolution explicit and avoids hiding "wrong root"
  errors behind auto-correction.
- Rejected: Making `resolve_task_path` itself nesting-aware (auto-walk to the hub
  when the given root lacks `_mill/`) — hides resolution and can mask genuine
  mistakes. Rejected the "both" variant (callsite fix + defensive fallback) for
  the same masking reason.

### review-plan-anchor

- Decision: Change `millpy-review-plan.py`'s `project_root = Path.cwd()` to
  `resolve_hub_path()`, matching `millpy-review-discussion.py`. Both review CLIs
  then resolve briefs, `mill_dir`, registry, and active-slug lookup against the
  same hub root.
- Rationale: `Path.cwd()` is the fragile workaround #490 flagged; in a nested
  layout cwd may be the git root (the discussion-review session in #484), which
  diverges from the plan-review cwd and splits briefs (#491). A single resolver
  removes the divergence. Symmetrically, the discussion CLI's
  `find_active_slug(git_root, …)` (`millpy-review-discussion.py:88`) also moves to
  the hub root so both CLIs resolve the active-slug glob fallback
  (`<arg>/_mill/*.active`) to the same `_mill/` — otherwise the discussion CLI's
  fallback looks in `<git_root>/_mill` (nonexistent in a nested layout) while plan
  looks in `<hub>/_mill`.
- Rejected: Fixing only the discussion side and leaving plan on `Path.cwd()` —
  smaller diff but preserves the cwd fragility. Also rejected leaving the
  discussion CLI's `find_active_slug` on `git_root` — the "both CLIs resolve to the
  same hub root" intent requires line 88 to move too, not only line 96.

### formatter-drift-handling

- Decision: Two-pronged. (1) In the `{lang}-build` templates, scope the
  **writing** formatters to changed files only (`goimports -w <changed .go>`,
  `ruff format`/`ruff check --fix <changed>`); csharp ships no formatter — add a
  convention note only. Keep `build`/`test`/read-only `lint` whole-project.
  (2) Add a mill-go cleanliness-gate guard that, on detecting new dirt,
  partitions it into in-scope (under `task_dir` or in the task's parent-diff
  `owned_paths`) vs out-of-scope, **auto-reverts the out-of-scope tracked
  modifications** (`git checkout HEAD -- <file>`), warns, and continues; it
  blocks the batch only if **in-scope** dirt remains.
- Rationale: The "highest leverage" fix is to stop generating drift (scoped
  formatters), but mill cannot control a project's customized build skill, so the
  guard is the robust enforcement. The current gate blocks on any new dirt, which
  is exactly what tempts the implementer to `git add -A` the drift wholesale.
  Reverting out-of-scope drift is safe: after the implementer commits its own
  work, anything still dirty outside the task's owned set is by definition a file
  the implementer was not supposed to touch.
- Rejected: Guard-only (leave templates running whole-project formatters) — wastes
  the cheap, high-leverage template fix. Template-scoping-only (no guard) —
  a project's own customized formatter would still leak drift. Warn-and-block
  without auto-revert — reintroduces the block that drives wholesale commits.

### stacked-pr-path

- Decision: In `mill-finalize`, drop the `parent_branch == base_branch` clause
  from the PR-mode trigger: **PR mode activates whenever `require_pr_to_base` is
  True**, and the PR targets `parent_branch` (which equals `base_branch` in the
  non-stacked case). The existing Step 3 cleanup
  (`_finalize_cleanup.base_tracks_task_dir(git_root, parent_branch, task_dir)` →
  restore-from-parent vs remove) already produces a clean diff for both stacked
  and non-stacked tasks; it is reused unchanged. `git-pr` is still invoked with
  `MILL_FINALIZE_PR_CLEANUP=1`.
- Rationale: `_finalize_cleanup` already knows the correct restore-vs-remove
  move; the only thing blocking stacked tasks from reaching it is the
  `parent == base` gate. Removing one clause unlocks a deterministic clean
  PR-to-parent with no new cleanup logic.
- Rejected: An interactive PR-vs-direct prompt at finalize time — non-deterministic,
  breaks autonomous mode. A standalone `git-pr --mill-clean` mode — duplicates
  `_finalize_cleanup`; the mill-finalize route already covers the need.

### scope-493c

- Decision: Drop #493-C (PR-time pre-existing-drift detection).
- Rationale: With the #493-A guard, drift never reaches a commit, so a
  build-time detector has nothing to find. YAGNI.
- Rejected: A lightweight PR-time "formatting-only churn outside task scope"
  warning — redundant given the guard.

## Technical context

**Hub resolution (the spine of #484/#490/#491):**

- `_paths.resolve_hub_path(cwd=None)` walks **up** from cwd looking for
  `.millhouse/config.local.yaml`; returns the first directory that has it,
  *unless* that directory is the git root and its config declares
  `hub_relative_path`, in which case it returns that subpath (the worktree-root
  stub case). Handles both cwd==nested-mill-dir and cwd==git-root.
- `_paths.resolve_active_hub(container, slug, *, cfg, git_root)` — what mill-go
  uses; resolves the active worktree then applies `hub_relative_path` via a
  two-tier lookup (caller cfg, then the worktree's own stub). Needs `slug` +
  `container`, which mill-go has.
- `mill-spawn` already bootstraps `<worktree_root>/.millhouse/config.local.yaml`
  with `hub_relative_path:` when the hub is nested (`millpy-spawn.py:216-222`), so
  `resolve_hub_path()`'s stub-at-root branch resolves nested layouts correctly.
  **No spawn change needed** — this was verified during discussion.
- `_paths.resolve_task_path(worktree_root, cfg_relative_path)` — plain join with a
  `_mill/`→`task/` compat fallback for in-flight worktrees. Keep as-is; feed it
  the hub root.

**Review CLIs:**

- `millpy-review-discussion.py`: already sets `project_root = resolve_hub_path()`
  (`hub_dir`), but line 96 computes `briefs_dir = resolve_task_path(git_root, …)`
  and line 88 calls `find_active_slug(git_root, …)`. Both must use
  `project_root`/`hub_dir`. Note `find_active_slug`'s glob fallback
  (`<arg>/_mill/*.active`, `_review_common.py:283`) is the path-literal part that a
  `git_root` arg breaks under nesting; the branch-based slug path resolves
  correctly from either root (pygit2 discovers the repo upward), so this is the
  fallback-correctness fix, not a behavior change for the common case.
- `millpy-review-plan.py`: `project_root = Path.cwd()` (line 102) feeds
  `mill_dir`, registry load, `find_active_slug` (line 119), and `briefs_dir`
  (line 151). Switching **only** line 102 to `resolve_hub_path()` corrects all of
  them together — line 119 already passes `project_root` (not `git_root`), so it
  auto-corrects and needs no separate edit. This is the asymmetry with the
  discussion CLI: there, `find_active_slug` is called with `git_root` (line 88) and
  must be moved explicitly; here it already rides on `project_root`. Verify
  `find_active_slug` and `_reviewers.load` behave identically when given the hub
  root instead of cwd (they should — both expect the mill project root).

**Cleanliness gate (#493-A):**

- `plugins/mill/scripts/_cleanliness.py` already has the scope primitives:
  `compute_new_dirt(worktree, snapshot)` (post − pre line-set diff),
  `_parent_diff_names(worktree, parent_branch)` (the task's parent-diff file list —
  this is the *source* of the "owned" set), and
  `_filter_to_task_scope(lines, task_dir, owned_paths)` (keeps lines under
  `task_dir` ∪ the owned set; `owned_paths` is just the parameter name, not a
  standalone helper). The new `revert_out_of_scope_drift` helper computes the
  owned set itself by calling `_parent_diff_names`, then partitions
  `compute_new_dirt` output by the same scope predicate; out-of-scope tracked
  modifications get reverted.
- The guard belongs in `_cleanliness.py` (testable helper, e.g.
  `revert_out_of_scope_drift(worktree, task_dir, parent_branch) -> (reverted, remaining)`),
  invoked from mill-go's **Cleanliness gate (step 2b)** before it decides to
  block. mill-go's gate currently: `compute_new_dirt` non-empty → set batch
  blocked + commit status + cleanup. New flow: revert out-of-scope drift first;
  block only if in-scope dirt remains.
- Revert mechanics: out-of-scope tracked modification = a porcelain line whose
  path is **not** under `task_dir` and **not** in `owned_paths`, with a modified
  status (` M`, `M `, `MM`). Reset with `git checkout HEAD -- <file>` (covers both
  staged and worktree changes). Untracked out-of-scope files are a *separate*
  existing gate (`compute_scope_violations`) — do not fold them in.

**Formatter scoping (#493-A):**

- `plugins/golang/skills/golang-build/SKILL.md` — `goimports -w .` is the only
  writer; scope to changed `.go` files. `go vet/build/test`, `golangci-lint run`
  stay whole-project.
- `plugins/python/skills/python-build/SKILL.md` — today ships only `ruff check .`
  (read-only) and `pytest`; there is **no** write-mode formatter (`ruff format`,
  `ruff check --fix`) to narrow. The edit is therefore precautionary: add the
  convention note so that any future `ruff format`/`--fix` (or other writer) is
  scoped to changed files. `pytest` stays whole-project.
- `plugins/csharp/skills/csharp-build/SKILL.md` — ships no formatter; add the
  convention note only.
- `plugins/mill/skills/git-commit/SKILL.md` already says "lint changed files";
  align its wording with the now-scoped template commands.

**Stacked PR (#493-B):**

- `_finalize_cleanup.base_tracks_task_dir(worktree, base_branch, task_dir)`
  returns True when `<base>` tracks `task_dir/status.md` (stacked → restore from
  base) and False otherwise (normal → remove). Already correct; reused.
- `mill-finalize/SKILL.md` requires **two** coordinated edits, not just the
  trigger clause:
  1. **Dispatch trigger:** PR mode is currently `require_pr is True AND
     parent_branch == base_branch`; drop the `parent_branch == base_branch` clause
     so PR mode = `require_pr is True`.
  2. **PR invocation (Step 5, SKILL.md:94):** the invocation literally reads
     `/git-pr <base_branch>`; change the argument token to `<parent_branch>` so the
     PR is opened against the parent. Changing only the trigger without this token
     swap would still target `base_branch` (= `main`) and fail for a stacked task.
  Step 3 cleanup already calls `base_tracks_task_dir(git_root, parent_branch,
  task_dir)`. `git-pr` is invoked with `MILL_FINALIZE_PR_CLEANUP=1` (already wired;
  its Step 1.5 skips the halt when that env var is set).
- Also fix `mill-finalize/SKILL.md:17` (`worktree_root = git_root`) and `git-pr`
  Step 1.5 (`resolve_task_path(git_root, …)`) to the hub root, so stacked/nested
  finalize+PR resolves `task_dir` correctly.

## Constraints

- **Script invocation:** operational calls use the cache via
  `PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" "$MILL_PYTHON" …`; unit tests use
  `uv run --project plugins/mill`.
- **ASCII-only `print`/`_log` output** (Windows cp1252): `—`→` -- `, `->`→` -> `.
- **All path resolution through `_paths.py`** — no inline `container/wts/slug` or
  `<wt>/hub_relative_path` outside `_paths.py`.
- **POSIX syntax in Bash-tool commands** even though the harness reports
  PowerShell; reserve PowerShell for the PowerShell tool.
- **Verify commands** for this Python project must start with `PYTHONPATH=`
  (literal empty value) so the test subprocess loads worktree code, not the cache.
- **Templates and the hub `mill-config.yaml` stay in sync** if touched (not
  expected here).
- The `{lang}-build` skills are **templates external repos customize** — fixing
  the template default is correct, but the in-repo guard is what enforces the
  no-drift invariant regardless of a project's customization.

## Testing

Unit tests only (tempfile + real `git`, no LLM, no real review dispatch), run via
`plugins/mill/unit_tests/run-all.py`; language-build template edits are exercised
by inspection/doc tests where applicable.

- **Path resolution (`test-paths.py`, extend):** build a **nested-layout
  fixture** — a temp git repo with the mill project (`.millhouse/config.local.yaml`
  + `_mill/`) in a subdirectory and a `hub_relative_path` stub at the worktree
  root. Assert `resolve_hub_path()` returns the nested dir for cwd==nested-dir
  **and** cwd==git-root, and that `resolve_task_path(resolve_hub_path(), '_mill/status.md')`
  points at the file that exists. TDD candidate: write the nested fixture +
  assertions first, then confirm the callsite fixes make the previously-broken
  resolution pass.
- **Drift-revert guard (`test-cleanliness.py`, extend):** fixture with a task
  branch, a `task_dir` (`_mill/`), some owned (parent-diff) files, and a dirtied
  out-of-scope tracked file (simulated formatter touch). Assert the new helper
  reverts the out-of-scope file, leaves in-scope dirt untouched, and reports the
  reverted/remaining split. Cover: out-of-scope drift only → no block; mixed
  in-scope + out-of-scope → out-of-scope reverted, in-scope remains (block);
  untracked out-of-scope files are NOT reverted (still the separate gate). TDD
  candidate.
- **Stacked PR-mode dispatch (`test-mill-finalize-dispatch.py`, extend):** assert
  PR mode activates for `require_pr=True, parent != base` (stacked) and targets
  `parent_branch`; direct mode for `require_pr=False`; and that
  `base_tracks_task_dir` drives restore-vs-remove. Pair with
  `test-finalize-cleanup.py` for the cleanup branch behavior.
- **Review-CLI anchor (`test-review-plan-flow.py` / `test-review-discussion-flow.py`,
  check):** confirm both CLIs resolve `briefs_dir` to the same hub root under a
  nested fixture; no regression for the flat (hub==git-root) layout.
- **Regression:** the flat layout (hub == git root, parent == main) must behave
  exactly as before for every changed callsite — include a flat-layout assertion
  alongside each nested one.

## Q&A log

- **Q:** Path-fix strategy — callsite routing through the hub resolver, dumb
  `resolve_task_path`, vs nesting-aware `resolve_task_path`? **A:** Callsite
  routing; keep `resolve_task_path` a dumb join. Aligns with existing
  `resolve_hub_path`/`resolve_active_hub` design; avoids masking wrong-root errors.
- **Q:** `millpy-review-plan.py` anchor — switch `Path.cwd()` to
  `resolve_hub_path()`? **A:** Yes — both review CLIs must resolve to the same hub
  root; `Path.cwd()` is the fragile #490 workaround.
- **Q:** Formatter drift — template scoping, guard, or both? **A:** Both — scope
  writing formatters in the templates *and* add a gate guard that auto-reverts
  out-of-scope drift.
- **Q:** Stacked clean PR — route through mill-finalize, add `git-pr --mill-clean`,
  or both? **A:** Route through mill-finalize (relax PR-mode to `require_pr`, PR to
  `parent_branch`, reuse Step 3 cleanup). No `--mill-clean` mode.
- **Q:** Include #493-C (PR-time drift detection)? **A:** No — the guard prevents
  drift being committed, making PR-time detection redundant (YAGNI).
- **Q:** Cleanliness guard on out-of-scope drift — auto-revert or warn-and-block?
  **A:** Auto-revert the out-of-scope tracked modifications and continue; block
  only if in-scope dirt remains.
- **Q:** Which build commands get scoped to changed files? **A:** Only the writing
  formatters (`goimports -w`, `ruff format`/`--fix`); keep build/test/read-only
  lint whole-project. csharp: convention note only.
- **Q:** PR-mode trigger for stacked tasks — config-driven or interactive? **A:**
  Config-driven (`require_pr_to_base` True ⇒ PR to `parent_branch`); deterministic,
  preserves autonomous mode.
- **Q:** Fix the remaining `git_root`-hardcoded SKILL callsites
  (`mill-go:151`, `git-pr` Step 1.5, `mill-finalize:17`)? **A:** Yes — same #490
  defect; they would silently break stacked/nested finalize+PR.
- **Q:** Testing approach — unit (tempfile+git) vs add integration? **A:** Unit
  tests with tempfile + real `git`, no LLM; nested-layout, drift-revert, and
  stacked PR-mode fixtures.
- **Q:** (review r1 GAP) Is `worktree_root` an existing assignment to edit in
  mill-start/mill-plan? **A:** No — they reference it without defining it
  (implicitly `git_root`); the plan must **add** an explicit
  `worktree_root = resolve_hub_path()` to Entry of both SKILLs.
- **Q:** (review r1 GAP) Should the discussion CLI's `find_active_slug(git_root)`
  (`millpy-review-discussion.py:88`) also move to the hub root? **A:** Yes — the
  "both CLIs resolve to the same hub root" intent requires line 88 to move, not
  only line 96; the glob fallback `<arg>/_mill/*.active` breaks under nesting
  otherwise.
