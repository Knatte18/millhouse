# Discussion: mill-merge misjudges worktree topology and mishandles Step 5 squash-restore checkout

```yaml
task: mill-merge misjudges worktree topology and mishandles Step 5 squash-restore checkout
slug: mill-merge-topology-and-squash-restore-gaps
status: discussing
parent: main
```

## Problem

Two independent bugs, both filed against `mill-merge`'s topology/merge machinery (GitHub issues #735 and #736, both closed and folded into this task):

1. **`_inplace.is_inplace` misdetects topology by path existence, not git truth.** `_inplace.is_inplace(slug, git_root, cfg)` in `plugins/mill/scripts/_inplace.py` decides "in-place mode" (task branch checked out directly in the hub, no separate linked worktree) with a single check: `not (resolve_worktrees_dir(cfg, git_root) / slug).is_dir()` — i.e. "no directory exists at the canonical `<wts>/<slug>/` path." A real, separate task worktree parked at any *non-canonical* path (nested elsewhere, differently named, created outside `mill-spawn`'s own layout) is misdetected as in-place, because the canonical-path directory check finds nothing. `mill-merge`'s Entry step then takes the in-place bypass (skips merge-lock acquisition and `mill-merge-in`, treats parent and child as the same working tree) against a genuinely separate worktree — a branch-checkout conflict at best, a wrong-worktree squash/push straight to `main` at worst.

2. **`mill-merge` Step 5's restore-checkout is not actually a no-op.** `mill-merge/SKILL.md`'s Step 5 (Direct squash) restore sequence runs:
   ```bash
   git -C <parent-path> reset -q HEAD -- "$TASK_DIR_REL"
   git -C <parent-path> checkout -- "$TASK_DIR_REL"
   ```
   The skill's prose documents this as "a clean no-op when the parent tracks nothing at `task_dir`." In the common worktree-mode case (task state lives only on the task branch, never on parent/main), `git checkout -- "$TASK_DIR_REL"` actually exits 1 with `error: pathspec '_mill' did not match any file(s) known to git` — not a no-op, and the documented bash block has no guard (no `|| true`, no existence check), so a strict/scripted execution halts here incorrectly.

**Why now:** both were observed live during real `mill-go` → `mill-finalize` → `mill-merge` runs (issue #735 during a `native-clients-migration` task in a sibling repo; issue #736 during `mill-merge-conflict-robustness-gaps` in this repo) and worked around by hand in the moment. Both are latent correctness bugs in the merge path with real damage potential (topology misdetection can route a squash/push at the wrong worktree; the checkout error, if a caller ever treats `mill-merge` as scriptable/automatable, would incorrectly halt an otherwise-successful merge).

## Scope

**In:**
- Rewrite `_inplace.is_inplace`'s detection criterion from path-existence to git-verifiable topology.
- Guard `mill-merge/SKILL.md` Step 5's restore-checkout so the documented no-op claim is actually true.
- Update/add unit tests in `test-inplace.py`, `test-paths.py`, `test-review-common.py` whose fixtures currently rely on `is_inplace`'s old path-existence mechanism (`_inplace.resolve_worktrees_dir` patches) to work with the new topology mechanism.
- Correct `_inplace.py`'s module/function docstrings, which currently describe the old detection mechanism (and contain a stale path example — `<container>/worktrees/<slug>/` vs. the actual default `<container>/wts/<slug>/` resolved by `_paths.resolve_worktrees_dir`).

**Out:**
- The "stale-worktree edge" ambiguity path (`_inplace.prompt_stale_worktree`, and its callers in `millpy-cleanup.py` / `_paths.resolve_active_worktree`) — this is a deliberately separate ambiguity-resolution flow (branch matches the active task's recorded branch AND a worktree directory already exists at the canonical path) that neither #735 nor #736 touches. Its own canonical-path assumption is out of scope here.
- Any other `mill-merge/SKILL.md` step besides Step 5's restore-checkout guard.
- `millpy-cleanup.py`'s own `_resolve_inplace_mode` logic beyond the fact that it calls `_inplace.is_inplace` (whose behavior changes transparently; `_resolve_inplace_mode` itself is not edited).

## Decisions

### is-inplace-topology-check

- Decision: Replace `_inplace.is_inplace`'s body with a git-topology comparison: in-place iff `git_root` is the same directory as `_paths.resolve_main_worktree_root(git_root)`. Use `git_root.samefile(main_root)`, falling back to `git_root.resolve() == main_root.resolve()` on `OSError` — the same fallback pattern already used in `_paths.resolve_git_root` (see `_paths.py` around line 145-150) for comparing worktree paths. `slug` and `cfg` stay in the function signature for API compatibility with both existing call sites (`_paths.py:433`, `millpy-cleanup.py:434`) and the structural signature test in `test-inplace.py`, but no longer participate in the check — the docstring must say so explicitly.
- Rationale: `_paths.resolve_main_worktree_root(git_root)` already exists and does exactly the git-verifiable check issue #735's "Expected" section asks for (comparable to `git worktree list --porcelain` reasoning, but via pygit2's common-dir resolution, matching the codebase's existing convention). No circular-import risk: `_paths.py` only imports `_inplace` lazily inside a function body (`_paths.py:418`), so `_inplace.py` importing `resolve_main_worktree_root` from `_paths` at module level (alongside the existing `resolve_worktrees_dir` import) is safe. Both existing callers only ever invoke `is_inplace` after already confirming the checkout's current branch matches the slug in question (`_paths.resolve_active_worktree`'s marker-slug match; `millpy-cleanup._resolve_inplace_mode`'s `slug_for_record != record.slug` early-return) — combined with git's own invariant that a branch cannot be checked out in two worktrees simultaneously, "is `git_root` the main worktree" is unambiguous and equivalent to "is this task's branch checked out in-place" for both callers.
- Rejected: Hybrid approach (keep path-existence as primary signal, consult topology only when path-existence says "in-place") — this doesn't fix the bug (path-existence still gates the branch that's true), just narrows it. Rejected as not actually solving #735.

### step5-checkout-guard

- Decision: Change `mill-merge/SKILL.md`'s Step 5 restore sequence from:
  ```bash
  git -C <parent-path> checkout -- "$TASK_DIR_REL"
  ```
  to:
  ```bash
  git -C <parent-path> checkout -- "$TASK_DIR_REL" 2>/dev/null || true
  ```
  and correct the surrounding prose (currently: "This is a clean no-op when the parent tracks nothing at `task_dir`") to describe the guard explicitly rather than asserting a false no-op claim about bare `git checkout`.
- Rationale: matches issue #736's primary suggested fix verbatim, and matches the existing swallow-idiom already used one skill over in `mill-merge-in/SKILL.md` (`OLD_CHK_SHA=$(git rev-parse --verify --quiet "$CHK" || true)`). The realistic failure mode being swallowed is narrow — a read against `HEAD`'s tree, not a risky filesystem operation — so blanket-swallowing via `|| true` doesn't hide anything an operator needs to see; the two other commands in the sequence (`reset -q HEAD -- ...`, and the eventual `commit`) still surface real problems.
- Rejected: Pre-check via `git -C <parent-path> ls-tree -d HEAD -- "$TASK_DIR_REL"` before attempting checkout (issue #736's secondary suggested fix) — functionally equivalent but adds a second command and a conditional-execution step to a skill file already dense with bash blocks, for no behavioral difference over the `|| true` swallow given how narrow the swallowed failure mode is.

## Technical context

- `plugins/mill/scripts/_inplace.py` — the file being rewritten. Currently imports `resolve_worktrees_dir` from `_paths` at module level; that import is removed and replaced with `resolve_main_worktree_root`.
- `plugins/mill/scripts/_paths.py:228` — `resolve_main_worktree_root(git_root: Path) -> Path`, already implements the git-topology resolution via `_pygit2_util.resolve_common_dir_parent`. Reuse directly; do not reimplement.
- `plugins/mill/scripts/_paths.py:145-150` (inside `resolve_git_root`) — the `samefile`-with-`resolve()`-fallback pattern to copy for the new `is_inplace` body.
- Callers of `is_inplace` (unchanged call sites, behavior changes transparently):
  - `plugins/mill/scripts/_paths.py:433` (inside `resolve_active_worktree`)
  - `plugins/mill/scripts/millpy-cleanup.py:434` (inside `_resolve_inplace_mode`)
- `plugins/mill/skills/mill-merge/SKILL.md` lines 155-187 — Step 5 "Direct squash", the restore sequence and its surrounding prose (including the `Why:` paragraph at line 185 asserting the false no-op claim, which also needs a wording fix).
- `plugins/mill/skills/mill-merge-in/SKILL.md:37` — existing `|| true` swallow-idiom precedent to match stylistically.

## Constraints

None beyond the codebase-wide conventions already in `CLAUDE.md` (verify command shape, path-resolution invariants) — no `CONSTRAINTS.md` exists in this repo.

## Testing

- **`plugins/mill/unit_tests/test-inplace.py`** (TDD candidate — write the new/updated tests before the implementation change):
  - Rewrite the three existing `_test_is_inplace_*` tests (currently at lines 21-73, patching `_inplace.resolve_worktrees_dir`) to instead patch `_inplace.resolve_main_worktree_root`: `return_value=git_root` to simulate in-place, any other path to simulate worktree-mode. Keep the same three scenario names/intents (no-worktree-dir case, worktree-dir-exists-default case, worktree-dir-exists-override case) reframed for the new mechanism, OR consolidate them into fewer cases if the "default vs. override worktrees_dir" distinction is no longer meaningful once `is_inplace` no longer calls `resolve_worktrees_dir` at all (judgment call for mill-plan — the distinction was only ever about which `resolve_worktrees_dir` return value fed the old check).
  - Add a new regression test reproducing #735's exact false-positive: `git_root` differs from the mocked `resolve_main_worktree_root` return value (simulating a real separate worktree) AND no directory exists at the canonical `<wts>/<slug>/` path — expect `is_inplace` to return `False` (worktree mode), where the old implementation would have wrongly returned `True`.
  - The structural signature test (`_test_is_inplace_importable_and_callable`, asserting `params == ["slug", "git_root", "cfg"]`) stays unchanged — signature isn't changing, only the body.
- **`plugins/mill/unit_tests/test-paths.py`** — six sites patch `_inplace.resolve_worktrees_dir` (lines ~754, 769, 827, 934, 949, 978 as of this writing; re-grep before editing, line numbers will drift). For each: if the fixture already builds a real git repo via `_test_helpers.init_minimal_git_repo` (e.g. the `skip_slug_validation=True` case around line 823, where `git_root` is a genuine single-worktree repo with no separate worktree), the topology check resolves correctly for free — drop the now-obsolete `_inplace.resolve_worktrees_dir` patch entirely rather than replacing it. If the fixture uses a bare `git_root = tmp_path / "hub"; git_root.mkdir()` (no real git), add `patch("_inplace.resolve_main_worktree_root", return_value=git_root)` for in-place scenarios (or a differing path for worktree-mode scenarios) in place of the old patch.
- **`plugins/mill/unit_tests/test-review-common.py`** — two sites (lines ~568, ~615) already patch `_paths.resolve_main_worktree_root` (for a different code path within `resolve_path`'s resolution chain) alongside `_inplace.resolve_worktrees_dir`. Add a matching `patch("_inplace.resolve_main_worktree_root", return_value=git_root)` alongside the existing `_paths.resolve_main_worktree_root` patch, and drop the obsolete `_inplace.resolve_worktrees_dir` patch.
- **`plugins/mill/unit_tests/test-cleanup.py`** — no changes needed. Its one site referencing `_inplace` (`mill_cleanup._inplace.prompt_stale_worktree`, line ~702) exercises the stale-worktree edge, which short-circuits before ever reaching `_inplace.is_inplace`; every other `_resolve_inplace_mode`-adjacent test in that file mocks `_resolve_inplace_mode` wholesale and never touches `is_inplace`'s internals. Verify this holds during implementation before skipping it outright.
- **Step 5 guard** — no dedicated unit test exists for `mill-merge/SKILL.md`'s bash blocks (they're orchestrator-executed prose, not Python). Verification is: re-read the corrected Step 5 block and confirm the `|| true` guard is present and the prose no longer asserts a false no-op claim about unguarded `git checkout`. If an integration test harness for `mill-merge` already exercises Step 5 end-to-end (check `plugins/mill/integration_tests/`), confirm it covers the parent-has-no-`_mill/`-at-`task_dir` case; add one if it's missing and the harness pattern makes it cheap.

## Q&A log

- **Q:** How should `_inplace.is_inplace` determine in-place mode? **A:** [auto-pick] Replace the path-existence check with git-topology comparison via `_paths.resolve_main_worktree_root`, keeping `slug`/`cfg` in the signature unused. **Why:** matches issue #735's Expected section exactly; git's own single-checkout-per-branch invariant makes this unambiguous for both existing callers, which already validate branch==slug before calling.
- **Q:** How should `mill-merge/SKILL.md` Step 5's restore-checkout be guarded? **A:** [auto-pick] `git checkout -- "$TASK_DIR_REL" 2>/dev/null || true`. **Why:** matches issue #736's primary suggested fix and the existing `|| true` swallow-idiom already used in `mill-merge-in/SKILL.md`; the swallowed failure mode is narrow (HEAD-tree read, not filesystem-risky).
- **Q:** How should the ~13 test-fixture sites that patch `_inplace.resolve_worktrees_dir` be migrated? **A:** [auto-pick] Redirect each to `_inplace.resolve_main_worktree_root` (or drop the patch outright where a real git-repo fixture already supplies correct topology for free), and add a dedicated #735 false-positive regression test to `test-inplace.py`. **Why:** the alternative (leaving `resolve_worktrees_dir` imported-but-unused just to keep old patches working) keeps dead code and doesn't actually exercise the new detection path — it papers over the bug rather than testing the fix.
- **Q:** Should `_inplace.py`'s docstrings be corrected while rewriting the function bodies? **A:** [auto-pick] Yes — the module and function docstrings currently describe the old mechanism and contain a stale path example (`<container>/worktrees/<slug>/` vs. actual `<container>/wts/<slug>/`). **Why:** the file is being substantively rewritten regardless; leaving a doc bug next to a just-fixed logic bug is the kind of drift this project actively guards against elsewhere.
- **Q:** Should this task also rework the stale-worktree edge (`prompt_stale_worktree`, canonical-path assumption in `millpy-cleanup.py`/`resolve_active_worktree`) for consistency with the topology-based fix? **A:** [auto-pick] No — out of scope. **Why:** YAGNI; neither #735 nor #736 touches that path, and it's a deliberately separate ambiguity-resolution flow with its own semantics.
