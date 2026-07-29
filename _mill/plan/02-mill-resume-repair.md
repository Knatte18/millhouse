# Batch: mill-resume-repair

```yaml
task: "Cross-machine resume, wiki-daemon health-check, and hub-in-subdirectory config resolution gaps"
batch: "mill-resume-repair"
number: 2
cards: 6
verify: "PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-worktree.py test-paths.py test-resume-repair.py"
depends-on: []
```

## Batch Scope

Closes #729: `mill-resume` Phase 1 today unconditionally tells the user to run `mill-setup` when `.millhouse/config.local.yaml` or the `.wiki` junction is missing at cwd — the wrong remedy for a task worktree that already exists at a non-canonical, hand-created path with `_mill/status.md` already committed on its branch. This batch adds the low-level git-worktree-move primitive (`_worktree.move`), a small orchestration module for the repair sequence (`_resume_repair.py`), a pure path-join helper for the canonical worktree location (`_paths.resolve_canonical_worktree_path`), and rewrites `mill-resume/SKILL.md`'s Phase 1 plus a new Phase 1b to use them. This batch is independent of Batch 1 (`wiki-health-check-and-messaging`): it adds its own `_client.health_check(wiki_path)` call site to Phase 1 using the function's existing, unchanged signature — it does not need Batch 1's git-validity/staleness logic to have landed first to compile or be reviewable, since `health_check()`'s public contract (`wiki_path: Path) -> bool`) does not change.

External interface this batch produces: `_worktree.move()` (mirrors `_worktree.create()`/`_worktree.remove()`'s existing shape) and `_resume_repair.py`'s two functions are reusable primitives any future skill could call; no other in-plan batch consumes them.

## Cards

### Card 6: `_paths.resolve_canonical_worktree_path()`

- **Context:** none
- **Edits:**
  - `plugins/mill/scripts/_paths.py`
  - `plugins/mill/unit_tests/test-paths.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Add `resolve_canonical_worktree_path(container_path: Path, slug: str) -> Path` to `plugins/mill/scripts/_paths.py`, placed near `resolve_container_path` (`_paths.py:289`). Body: `return container_path / "wts" / slug` — a pure path-join with no existence check or validation, mirroring the inline expression already used at `_paths.py:436` inside `resolve_active_worktree` (that function additionally validates branch/slug against an *existing* worktree; this new function has none of that — it computes where the canonical worktree *should* live, whether or not anything is there yet, per `CLAUDE.md`'s "no inline `container / "wts" / slug` outside `_paths.py`" invariant). Add a docstring one-liner: "Return the canonical worktree path for `slug` under `container_path`, with no existence check." Add a matching entry to `_paths.py`'s module-docstring "Public API" list (`_paths.py:9`) and to its `__all__` export list (`_paths.py:106`), matching how `resolve_container_path` and every other public resolver is already listed there. Extend `plugins/mill/unit_tests/test-paths.py` with a case asserting `resolve_canonical_worktree_path(Path("/c"), "my-slug") == Path("/c") / "wts" / "my-slug"`, matching the file's existing assertion style.
- **Commit:** `feat(paths): add resolve_canonical_worktree_path for mill-resume's off-canonical repair`

### Card 7: `_worktree.move()`

- **Context:**
  - `plugins/mill/scripts/_subprocess_util.py`
- **Edits:**
  - `plugins/mill/scripts/_worktree.py`
  - `plugins/mill/unit_tests/test-worktree.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Add `move(old: Path, new: Path, cwd: Path) -> None` to `plugins/mill/scripts/_worktree.py`, placed after `create()` (`_worktree.py:49-80`). Unlike `create()`'s exact pattern (which relies on git's `-C` flag alone, with no explicit `cwd=` kwarg to `_subprocess_util.run`), `move()` MUST pass `cwd=cwd` explicitly to `_subprocess_util.run` in addition to `-C str(cwd)` in argv: `_subprocess_util.run(["git", "-C", str(cwd), "worktree", "move", str(old), str(new)], cwd=cwd)`. This distinction matters here specifically: per `_subprocess_util.run`'s own docstring, `cwd=None` inherits the *caller's* OS-level working directory, and Phase 1b (Card 10) invokes this function from inside `old` itself (`old_worktree` is, by construction, the directory the invoking session's shell cwd is in) — a bare `-C` flag tells git which repo to operate on but does not change the spawned subprocess's own OS-level cwd, so without the explicit `cwd=` kwarg the subprocess would still have its OS-level working directory pointed inside the very directory `git worktree move` is renaming, a well-known cause of lock failures on Windows (NTFS holds a directory open while a process's cwd points into it — `_worktree.py`'s own `remove_safe`/`WorktreeLockedError` exists for exactly this failure class on `remove()`). On non-zero exit raise `WorktreeError(f"git worktree move failed (old={old}, new={new}): {result.stderr.strip()!r}")` (same message-construction style as `create`'s `WorktreeError`); if the stderr matches the same lock-pattern set `remove_safe` already checks (`"Permission denied"`, `"is in use"`, `"Access is denied"`, `"Invalid argument"`), raise `WorktreeLockedError` instead (already a `WorktreeError` subclass), mirroring `remove_safe`'s existing lock-detection so the failure is diagnosable rather than a generic `WorktreeError`. On success print `f"[worktree] move: old={old} new={new}"` to stderr (mirrors `create`'s and `remove`'s existing `print(..., file=sys.stderr)` convention at the end of each function). Add a docstring matching `create`'s style, noting that `cwd` should be a stable worktree in the same repo (e.g. the hub) rather than `old` itself, since `old` is the directory being relocated by the very command being run, and that `cwd` is passed to the subprocess explicitly (not just via `-C`) precisely because the caller's own OS-level cwd cannot be trusted to already be outside `old`. Update the module docstring's Public API list to include `move(old, new, cwd) -> None -- git worktree move.`. Extend `plugins/mill/unit_tests/test-worktree.py` (which already has a real-tempdir-git fixture via its `_git_init` helper, see the file's existing `list_worktrees`/`remove` tests) with two cases: successful move (create a worktree via `create()`, then `move()` it to a new sibling path, assert `list_worktrees()` reports the new path and not the old one, and that `git -C <cwd> worktree list` no longer lists the old path); a failure case (`move()` to a target path that already exists as a directory) raises `WorktreeError`.
- **Commit:** `feat(worktree): add move() wrapping git worktree move`

### Card 8: New module `_resume_repair.py`

- **Context:**
  - `plugins/mill/scripts/_worktree.py`
  - `plugins/mill/scripts/_junction.py`
  - `plugins/mill/scripts/_pygit2_util.py`
  - `plugins/mill/scripts/_paths.py`
- **Edits:** none
- **Creates:**
  - `plugins/mill/scripts/_resume_repair.py`
- **Deletes:** none
- **Moves:** none
- **Requirements:** New module, following the `_spawn_core.py` pattern of a small per-skill orchestration helper (module docstring with a "Public API" list, same style as `_worktree.py`/`_spawn_core.py`). Public API:
  - `check_uncommitted_changes(worktree: Path) -> list[str]` — returns `_pygit2_util.status_porcelain(worktree, include_untracked=True)` verbatim. An empty list means the worktree is clean.
  - `relocate_and_scaffold(old_worktree: Path, canonical_path: Path, hub_root: Path, wiki_path: Path) -> None` — calls, in order: `_worktree.move(old_worktree, canonical_path, cwd=hub_root)` (pass `hub_root` as `cwd`, not `old_worktree`, since `old_worktree` is the directory being relocated by the very command); `_worktree.copy_millhouse(hub_root / ".millhouse", canonical_path / ".millhouse", exclude={"wiki", "active"})` (same exclude set `mill-spawn` uses via this same helper); `_junction.create(wiki_path, canonical_path / ".wiki")`. Document in the docstring that `hub_root` MUST be the directory that actually contains `.millhouse/` for the hub -- resolved by the caller via `_paths.resolve_hub_path(cwd=_paths.resolve_main_worktree_root(git_root))` (Card 10 Step 4 does this) so the resolution is both immune to `old_worktree`'s own cwd (never consults `old_worktree`'s own `.millhouse/`, since `old_worktree` is, by construction, the under-scaffolded worktree this function is relocating) and `hub_relative_path`-aware (correct for a main worktree whose own hub `.millhouse` lives in a git subdirectory). Passing `_paths.resolve_main_worktree_root`'s result directly, with no `resolve_hub_path` step, is NOT sufficient -- it is not `hub_relative_path`-aware and `_worktree.copy_millhouse` silently no-ops (does not raise) when its `src` argument does not exist, turning a wrong `hub_root` into a silent empty-`.millhouse` scaffold rather than a visible error.
  This function does **not** re-verify cleanliness or re-check the canonical-path collision itself — those are the caller's responsibility, run as separate pre-check steps by `mill-resume/SKILL.md`'s Phase 1b (Card 10) before this function is ever invoked. Let `_worktree.WorktreeError` (from `move`), `ValueError` (from `_junction.create` when `link_path` already exists), and `OSError` (from `copy_millhouse`) propagate uncaught — Phase 1b's embedded Python snippet catches and reports them to the operator.
- **Commit:** `feat: add _resume_repair module for mill-resume's off-canonical worktree repair`

### Card 9: New unit test `test-resume-repair.py`

- **Context:**
  - `plugins/mill/scripts/_resume_repair.py`
  - `plugins/mill/scripts/_worktree.py`
  - `plugins/mill/scripts/_junction.py`
  - `plugins/mill/scripts/_pygit2_util.py`
  - `plugins/mill/unit_tests/test-worktree.py`
- **Edits:** none
- **Creates:**
  - `plugins/mill/unit_tests/test-resume-repair.py`
- **Deletes:** none
- **Moves:** none
- **Requirements:** New test file using the same real-tempdir-git fixture pattern as `test-worktree.py`'s `_git_init` helper. Cover: `check_uncommitted_changes()` returns `[]` for a freshly-committed clean worktree, and a non-empty list when a tracked file is modified and separately when an untracked file is added (two distinct assertions, both against `_pygit2_util.status_porcelain`'s real output — no mocking of the porcelain call itself, since this is exercising the real git-status contract this function is a thin wrapper over). `relocate_and_scaffold()` end-to-end against real tempdir fixtures: create an "old" worktree via `_worktree.create()`, a fake "hub" directory tree with a `.millhouse/` subdirectory containing a marker file plus `wiki`/`active` junction-alias subdirectories, and a fake "wiki" clone directory; call `relocate_and_scaffold(old, canonical, hub, wiki)`; assert the worktree is registered at `canonical` (via `_worktree.list_worktrees`) and no longer at `old`; assert `canonical / ".millhouse"` contains the marker file but not `wiki`/`active`; assert `canonical / ".wiki"` exists and resolves to the fake wiki path (POSIX symlink — no special privilege needed to create or assert against in CI, matching how `_junction.create` behaves on non-Windows per its own docstring).
- **Commit:** `test: add _resume_repair coverage for dirty-check and relocate-and-scaffold`

### Card 10: `mill-resume/SKILL.md` — Phase 1 rewrite, new Phase 1b, Error Conditions table

- **Context:**
  - `plugins/mill/scripts/_resume_repair.py`
  - `plugins/mill/scripts/_worktree.py`
  - `plugins/mill/scripts/_paths.py`
  - `plugins/mill/scripts/_junction.py`
  - `plugins/mill/scripts/wiki/_client.py`
- **Edits:**
  - `plugins/mill/skills/mill-resume/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Replace `### Phase 1: Verify setup` (currently `plugins/mill/skills/mill-resume/SKILL.md:29-33`) with:

  ```
  ### Phase 1: Verify setup

  If `_mill/status.md` exists at cwd (this is a genuine task worktree, just
  missing scaffolding) AND either `.millhouse/config.local.yaml` (or the
  legacy `.millhouse/config.yaml`) or the `.wiki` junction is missing, skip
  the two checks below and go directly to **Phase 1b: Repair an
  off-canonical worktree**.

  Otherwise:

  If `.millhouse/config.local.yaml` (or the legacy `.millhouse/config.yaml`)
  does not exist, stop and tell the user to run `mill-setup` first.

  If the `.wiki` junction does not exist at cwd, stop and tell the user to
  run `mill-setup` first (the wiki junction is required to read task state).

  Both present: verify the wiki daemon is healthy before proceeding to
  Phase 2.

  ```bash
  PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" "$MILL_PYTHON" -c "
  import sys
  import _paths
  from wiki import _client
  wiki_path = _paths.resolve_wiki_path(_paths.resolve_git_root())
  if not _client.health_check(wiki_path):
      print('[mill-resume] wiki daemon health check failed', file=sys.stderr)
      raise SystemExit(1)
  "
  ```

  If this fails, halt: tell the user the wiki daemon is unreachable or
  unhealthy and to inspect the reason `health_check()` printed to stderr
  before retrying.
  ```

  Then insert a new section directly after Phase 1 (before `### Phase 2: Resolve the slug`):

  ```
  ### Phase 1b: Repair an off-canonical worktree

  Reached only when Phase 1 found `_mill/status.md` at cwd but
  `.millhouse/config.local.yaml` or the `.wiki` junction is missing -- a
  task worktree that was hand-created (e.g. via `git worktree add`) outside
  any mill skill, at a non-canonical path, and never scaffolded. This repair
  is scoped to `mill-resume` alone -- if a different skill is run directly
  from inside such a worktree, that skill's own existing missing-scaffolding
  handling applies unchanged; direct the user to run `mill-resume` instead.

  **Step 1 -- read slug and safety pre-check.**

  Read `_mill/status.md` at cwd; parse `slug:` from the YAML block.

  ```bash
  PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" "$MILL_PYTHON" -c "
  import sys
  import _paths, _resume_repair
  lines = _resume_repair.check_uncommitted_changes(_paths.resolve_git_root())
  if lines:
      print('\n'.join(lines), file=sys.stderr)
      raise SystemExit(1)
  "
  ```

  If this halts: tell the user the worktree has uncommitted changes --
  commit or stash them, then re-run `mill-resume`. Do not proceed.

  **Step 2 -- collision check.**

  ```bash
  PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" "$MILL_PYTHON" -c "
  import _paths
  git_root = _paths.resolve_git_root()
  container_path = _paths.resolve_container_path(git_root)
  canonical = _paths.resolve_canonical_worktree_path(container_path, '<slug>')
  print(canonical)
  print('EXISTS' if canonical.exists() else 'FREE')
  "
  ```

  If `EXISTS`: halt -- tell the user the canonical path already exists
  (stale entry or another worktree) and to resolve manually before
  re-running `mill-resume`. Do not proceed; no mutation attempted.

  **Step 3 -- confirm with the user.**

  Present as a numbered-options prompt:

  ```
  Worktree at <cwd> is task '<slug>' but is missing .millhouse/.wiki
  scaffolding.
    1) Relocate to <canonical> and scaffold it (recommended)
    2) Cancel, do nothing
  ```

  If the user picks 2 (or anything but 1), stop without mutating anything.

  **Step 4 -- relocate and scaffold.**

  ```bash
  PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" "$MILL_PYTHON" -c "
  import sys
  import _paths, _resume_repair
  git_root = _paths.resolve_git_root()
  container_path = _paths.resolve_container_path(git_root)
  canonical = _paths.resolve_canonical_worktree_path(container_path, '<slug>')
  main_root = _paths.resolve_main_worktree_root(git_root)
  hub_root = _paths.resolve_hub_path(cwd=main_root)
  wiki_path = _paths.resolve_wiki_path(git_root)
  try:
      _resume_repair.relocate_and_scaffold(git_root, canonical, hub_root, wiki_path)
  except Exception as e:
      print(str(e), file=sys.stderr)
      raise SystemExit(1)
  print(canonical)
  "
  ```

  If this fails (`git worktree move` itself failed -- locked worktree,
  cross-filesystem move, permission error -- or the scaffold steps failed),
  report the printed stderr and stop. No further mutation is attempted.

  `hub_root` resolution is two steps, each closing a different bug: first
  `main_root = _paths.resolve_main_worktree_root(git_root)` -- resolved
  purely from git's own common-directory metadata, never consulting cwd's
  own `.millhouse/`. This step alone is necessary because Phase 1 branches
  into Phase 1b when *either* `.millhouse/config.local.yaml` *or* `.wiki`
  is missing, so `.millhouse/config.local.yaml` can still exist at cwd
  (the `.wiki`-only-missing case) -- a bare `_paths.resolve_hub_path()`
  call (which cwd-walks from `Path.cwd()` by default) would find that
  local file immediately and return the broken worktree itself, exactly
  the `cwd == old_worktree` situation `move()`'s own docstring (Card 7)
  warns against. Second, `hub_root = _paths.resolve_hub_path(cwd=main_root)`
  -- passing the already-resolved `main_root` as `resolve_hub_path`'s
  explicit `cwd` argument runs its normal stub/`hub_relative_path`-aware
  walk (`_paths.py:159-225`) rooted at the true main worktree instead of
  at the broken worktree's cwd, so an M2+sub repo whose main-worktree hub
  `.millhouse` lives in a subdirectory (e.g. `src/csharp/NORCE.Models/.millhouse`
  -- the same repo shape Batches 3/4 fix elsewhere in this task) still
  resolves to the correct `.millhouse` source. Using `resolve_main_worktree_root`
  alone (an earlier draft of this step) would silently source `.millhouse`
  from the wrong directory for exactly that repo shape -- `_worktree.copy_millhouse`
  no-ops without raising when its `src` argument does not exist
  (`_worktree.py:104-105`), so the failure would be silent, not an
  exception.

  **Step 5 -- report and continue.**

  The worktree now lives at `<canonical>`. Report this explicitly:
  "Relocated to `<canonical>`." Every subsequent step in this session must
  reference `<canonical>` by absolute path -- do not assume the current
  shell's cwd followed the move. Continue directly to **Phase 9: Read and
  report phase**, using `<canonical>` as the worktree path; skip Phases
  2-8 (the slug is already known from `_mill/status.md`, the worktree
  already exists, and scaffolding is already done by Step 4 above).
  ```

  Finally, update the `## Error Conditions` table (`plugins/mill/skills/mill-resume/SKILL.md:161-171`): change the `.millhouse/config.local.yaml missing` and `.wiki junction missing` rows' Action column to `Stop, tell user to run mill-setup (only when _mill/status.md is also absent at cwd -- otherwise branch to Phase 1b)`, and add four new rows: `wiki daemon health check fails (Phase 1)` -> `Halt; tell user to inspect the printed reason`; `Phase 1b: worktree has uncommitted changes` -> `Halt with a clear message; worktree untouched`; `Phase 1b: canonical path already occupied` -> `Halt identifying the collision; no mutation attempted`; `Phase 1b: git worktree move fails` -> `Report the error with stderr; no further mutation attempted`.
- **Commit:** `feat(mill-resume): repair off-canonical under-scaffolded worktrees in a new Phase 1b`

### Card 11: New integration test `test-resume-relocate.py`

- **Context:**
  - `plugins/mill/scripts/_resume_repair.py`
  - `plugins/mill/scripts/_worktree.py`
  - `plugins/mill/scripts/_paths.py`
  - `plugins/mill/scripts/_junction.py`
  - `plugins/mill/skills/mill-resume/SKILL.md`
  - `plugins/mill/integration_tests/test-hub-relative-path.py`
  - `plugins/mill/integration_tests/test-worktree-sibling-resolution.py`
- **Edits:** none
- **Creates:**
  - `plugins/mill/integration_tests/test-resume-relocate.py`
- **Deletes:** none
- **Moves:** none
- **Requirements:** New standalone integration test (real `git worktree`/`git init` operations under `tempfile`, per the established `plugins/mill/integration_tests/` convention for real-git-topology tests — no LLM, no claude subprocess), following `test-worktree-sibling-resolution.py`'s and `test-hub-relative-path.py`'s structure (module docstring with a "Run from hub root: `PYTHONPATH= uv run --project plugins/mill python plugins/mill/integration_tests/test-resume-relocate.py`" line; exits 0 on PASS, 1 on any assertion failure). Build a fixture: a bare "origin" repo, a main worktree clone of it (acting as the hub, with a `.millhouse/` dir and a fake wiki clone dir), and a second worktree created via `_worktree.create()` at a **non-canonical** path (not `<container>/wts/<slug>`) with a committed `_mill/status.md` on its branch but no `.millhouse`/`.wiki` of its own. Cover the five scenarios from `discussion.md`'s Testing section: (a) clean off-canonical worktree with `_mill/status.md` present, `.millhouse`/`.wiki` missing -> `_resume_repair.relocate_and_scaffold` (called directly, simulating Phase 1b's Step 4) succeeds: worktree now registered at the canonical path, `.millhouse`/`.wiki` present there. (b) same fixture but with an uncommitted modified file -> `_resume_repair.check_uncommitted_changes` (simulating Step 1) returns non-empty, and the test asserts the worktree is left untouched when the caller halts on that result (no `relocate_and_scaffold` call made). (c) simulate the "user declines" path by simply asserting no filesystem/git mutation occurs when the test does not call `relocate_and_scaffold` at all (Step 3 has no python component to test directly -- documented as a no-op assertion with a comment explaining why). (d) canonical path already occupied (create a stub directory there first) -> assert the caller's collision check (`canonical.exists()`, simulating Step 2) is `True` and, separately, that calling `relocate_and_scaffold` anyway raises (git refuses to move onto an existing path) -- both worktrees left untouched afterward. (e) after a successful `relocate_and_scaffold` call, assert the returned/computed canonical path is what a subsequent `_paths.resolve_hub_path()`/`_paths.require_status_path()`-style read against the new location would use -- i.e. assert `(canonical / "_mill" / "status.md").exists()` and the pre-move path no longer does, covering `mill-resume-cwd-after-move`'s "operate on the new path" requirement. (f) hub-in-subdirectory main worktree (mirroring issue #728's NORCE.Models repro, e.g. the hub's own `.millhouse/` lives at `<main-worktree>/src/csharp/NORCE.Models/.millhouse` with a `hub_relative_path` stub at the main worktree root, rather than at `<main-worktree>/.millhouse` directly) -- run Card 10 Step 4's exact two-step resolution (`main_root = _paths.resolve_main_worktree_root(git_root)` then `hub_root = _paths.resolve_hub_path(cwd=main_root)`) against this fixture and assert `hub_root` resolves to the subdirectory, not the main worktree root; then call `relocate_and_scaffold` with that `hub_root` and assert the canonical path's `.millhouse/` contains the subdirectory hub's marker file (not empty) -- regression-guards the silent-no-op failure mode where `_worktree.copy_millhouse` does not raise when its `src` argument does not exist.
- **Commit:** `test(integration): add mill-resume off-canonical relocate+scaffold coverage`

## Batch Tests

`verify:` runs the three fast unit test files this batch adds/extends: `test-worktree.py` (Card 7's `move()`), `test-paths.py` (Card 6's `resolve_canonical_worktree_path`), and `test-resume-repair.py` (Card 9, new -- Card 8's `_resume_repair` module). The integration test (`test-resume-relocate.py`, Card 11) uses real `git worktree` topology and is intentionally **not** part of the per-round `verify:` gate (matching how `test-hub-relative-path.py` and `test-worktree-sibling-resolution.py`, the closest existing analogs, are also excluded from `unit_tests/run-all.py` and instead run standalone) -- run it once manually as part of implementing Card 11, and have the code reviewer confirm its PASS output rather than wiring it into the repeated fast gate. Card 10 (`mill-resume/SKILL.md` text) has no automated test in this repo; verified by direct text review during code review.
