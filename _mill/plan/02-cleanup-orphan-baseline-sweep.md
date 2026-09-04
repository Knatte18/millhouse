# Batch: cleanup-orphan-baseline-sweep

```yaml
task: 'millpy-implement/bg: Windows baseline-worktree teardown (WinError 145) and stale liveness reporting'
batch: cleanup-orphan-baseline-sweep
number: 2
cards: 2
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-cleanup.py
depends-on: []
```

## Batch Scope

Even with batch 1's strengthened retry, `_worktree.remove_safe` cannot guarantee teardown succeeds
against an arbitrarily long-lived Windows `dotnet` build-server lock — GitHub issues #929/#928/#918/#909
confirm the orphaned `.scratch/verify-baseline-<hash>/` directory currently persists forever, never
reclaimed by any later gate. This batch adds a safety-net sweep to `millpy-cleanup.py`: for each
active task worktree, glob `.scratch/verify-baseline-*` and remove any directory no longer
registered in that worktree's `git worktree list` — the correct detection criterion, empirically
verified during discussion (`git worktree remove --force` deregisters the `.git/worktrees/<id>`
administrative entry internally, before it ever attempts to delete the working directory, regardless
of the deletion's own exit code — matching #918's/#909's own field reports verbatim). Reuses
`_worktree.remove_safe` directly for the actual removal (junction-safe, and picks up batch 1's
strengthened retry automatically) rather than a bespoke rmtree call.

## Cards

### Card 3: Orphaned verify-baseline directory scan + sweep in millpy-cleanup.py

- **Context:**
  - `plugins/mill/scripts/_worktree.py`
- **Edits:**
  - `plugins/mill/scripts/millpy-cleanup.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  Add a new field `orphan_baseline_dirs: list[Path] = field(default_factory=list)` to the
  `CleanupPlan` dataclass (`plugins/mill/scripts/millpy-cleanup.py`), alongside the existing
  `orphan_portals: list[Path] = field(default_factory=list)` field.

  Add a new function `_scan_orphan_baseline_dirs(wt_path: Path) -> list[Path]`, placed immediately
  after `_scan_orphan_portals` (which it mirrors in shape and docstring style). Implementation:
  glob `wt_path / ".scratch"` for entries matching `verify-baseline-*` (skip entirely, returning
  `[]`, when `wt_path / ".scratch"` does not exist or is not a directory — mirror
  `_scan_orphan_portals`'s own `if not portals_dir.is_dir(): return []` guard). For each matching
  directory, resolve its absolute path. Get the set of currently-registered worktree paths for that
  repo by calling `_worktree.list_worktrees(wt_path)` (already imported in this file — `millpy-cleanup.py`
  already uses this exact helper the same way at its own `_worktree.list_worktrees(hub_root)` call
  site) wrapped in `try: ... except _worktree.WorktreeError: return []` (fail safe toward "sweep
  nothing" rather than risk misclassifying a still-registered, in-progress baseline computation as
  orphaned, when the underlying `git worktree list` call itself fails) — build a `set[Path]` from
  each returned dict's `"path"` value, resolved. Return the list of matched
  `.scratch/verify-baseline-*` directories whose resolved path is NOT in that registered set (i.e.,
  orphaned — deregistered by a `git worktree remove --force` that failed only on the physical
  directory deletion, per this batch's Batch Scope). Do not hand-roll `git worktree list --porcelain`
  parsing — `_worktree.list_worktrees` already provides exactly this parsing and this file already
  depends on it.

  In `build_plan`, declare `orphan_baseline_dirs: list[Path] = []` alongside the other accumulator
  lists near the top of the function (with `to_remove_done`, `to_remove_abandoned`, etc.). Inside the
  `for wt_path in active_worktrees:` loop, immediately after the existing `active_slugs.add(slug)`
  line, add `orphan_baseline_dirs.extend(_scan_orphan_baseline_dirs(wt_path))` — this scans every
  worktree that reaches that point in the loop (i.e., one whose branch resolved and whose slug is
  tracked in Home.md, matching the loop's existing early-`continue` guards for untracked/unresolved
  worktrees). Thread the accumulated list into the `CleanupPlan(...)` constructor call at the end of
  `build_plan` as a new `orphan_baseline_dirs=orphan_baseline_dirs` keyword argument, alongside the
  existing `orphan_portals=orphan_portals` keyword argument.

  Add a new function `_apply_orphan_baseline_dir(dir_path: Path, wt_path: Path) -> None`, placed
  immediately after `_apply_orphan_portal` (which it mirrors in shape): calls
  `_worktree.remove_safe(dir_path, cwd=wt_path, junctions_cfg={})` (empty `junctions_cfg` — matches
  `_verify_baseline.compute_baseline`'s own `_worktree.remove_safe(tmp_path, cwd=git_root,
  junctions_cfg={})` call, since `_junction.strip_all_in_worktree` — which `remove_safe` calls
  internally — no longer reads `junctions_cfg` and scans for any junction/symlink regardless of
  declaration; this matters here because `_link_dependency_dirs` may have junctioned `.venv` /
  `node_modules` / etc. into the orphaned checkout, and those must be stripped before any recursive
  delete, exactly as `remove_safe`'s own docstring already mandates), then prints
  `f"[cleanup] removed orphan baseline dir: {dir_path}"` to stderr on success (mirroring
  `_apply_orphan_portal`'s own print-on-success shape).

  In `apply_plan`, add a new loop over `plan.orphan_baseline_dirs`, placed immediately after the
  existing `for portal_path in plan.orphan_portals: _apply_orphan_portal(portal_path)` loop. For each
  `dir_path`, call `_apply_orphan_baseline_dir(dir_path, dir_path.parent.parent)` (the dir is always
  `<wt_path>/.scratch/verify-baseline-<hash>`, so `.parent.parent` recovers `wt_path` without
  threading a second parallel list of worktree roots) wrapped in a
  `try: ... except _worktree.WorktreeError as exc: ...` (the base class, not the narrower
  `WorktreeLockedError` subclass — a `.scratch/verify-baseline-*` dir is never a registered git
  worktree, so `remove_safe`'s initial `git worktree remove` call is likely to hit an "unrecognized
  git failure" shape and raise plain `WorktreeError`, not `WorktreeLockedError`; catching only the
  subclass would let that case propagate uncaught and abort the rest of `apply_plan`) that prints
  `f"REPORT: orphan baseline dir removal failed ({dir_path}): {exc}"` to stderr and continues to the
  next entry — mirroring `apply_plan`'s existing `except _worktree.WorktreeError as exc:` handling
  for `_apply_worktree_record` (a single stubborn lock must never abort the rest of the cleanup run).

  In `_print_plan`, add `plan.orphan_baseline_dirs` to the existing `if not any([...])` early-return
  check's list (alongside `plan.orphan_portals`), and add a new loop
  `for p in plan.orphan_baseline_dirs: print(f"ORPHAN-BASELINE-DIR: {p}  [not registered in git worktree list]")`
  immediately after the existing `for p in plan.orphan_portals:` print loop.
- **Commit:** `feat(cleanup): sweep orphaned .scratch/verify-baseline-* dirs`

### Card 4: Unit tests for the orphaned verify-baseline sweep

- **Context:**
  - `plugins/mill/scripts/millpy-cleanup.py`
  - `plugins/mill/scripts/_worktree.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-cleanup.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  Add new test cases to `test-cleanup.py`, following this file's existing `test_scan_orphan_portals`
  as the direct template (same `mod._scan_orphan_portals`-via-`importlib` module-loading pattern
  already at the top of this file; use `mod._scan_orphan_baseline_dirs` the same way).

  `test_scan_orphan_baseline_dirs`: using a `tempfile.TemporaryDirectory()` as a fixture worktree
  root, (a) no `.scratch/` dir at all -> `[]`. (b) `.scratch/verify-baseline-<hash>/` exists on disk
  but `mod._worktree.list_worktrees` is mocked (patch) to return a list of dicts whose `"path"`
  values do NOT include that directory's resolved path -> the directory is returned (orphaned).
  (c) same setup but the mocked `list_worktrees` return value DOES include that directory's resolved
  path as one entry's `"path"` -> `[]` (still a live, registered worktree — not orphaned, must never
  be swept out from under an in-progress baseline computation). (d) the mocked
  `mod._worktree.list_worktrees` raises `mod._worktree.WorktreeError` -> `[]` (fail-safe: sweep
  nothing rather than misclassify).

  `test_apply_orphan_baseline_dir`: patch `mod._worktree.remove_safe` and assert
  `_apply_orphan_baseline_dir(dir_path, wt_path)` calls it with
  `(dir_path, cwd=wt_path, junctions_cfg={})`. Separately, for EACH of the two exception cases below,
  assert `apply_plan` (constructed with a `CleanupPlan` whose `orphan_baseline_dirs` is a one-item
  list) does not propagate the exception — it prints a `REPORT:` line to stderr (capture via
  `contextlib.redirect_stderr`/`io.StringIO`, matching this file's existing stderr-capture convention
  used elsewhere in this file) and returns normally: (i) the patched `remove_safe` raises
  `_worktree.WorktreeLockedError("locked")` (the subclass); (ii) the patched `remove_safe` raises
  plain `_worktree.WorktreeError("unrecognized git failure")` (the base class — this is the actual
  bug scenario the round-2 plan review caught: a narrower `except WorktreeLockedError` would let this
  case propagate uncaught and abort the rest of `apply_plan`, so this case must be covered
  separately from the subclass case, not assumed equivalent).
- **Commit:** `test(cleanup): cover the orphaned verify-baseline dir sweep`

## Batch Tests

`verify:` runs `test-cleanup.py` directly (single file, matches this batch's sole edited module).
Card 4's new cases exercise both the detection function (`_scan_orphan_baseline_dirs`, via mocked
`_worktree.list_worktrees` output) and the apply path (`_apply_orphan_baseline_dir`/`apply_plan`,
via mocked `_worktree.remove_safe`) — no real git worktree, no real filesystem deletion.
