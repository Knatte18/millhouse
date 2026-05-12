# Batch: cleanup-orphan-scan

```yaml
task: 33 (A) -- Working-dir rename + portals redesign + junction cleanup
batch: cleanup-orphan-scan
number: 4
cards: 5
verify: python plugins/mill/unit_tests/run-all.py
depends-on: [3]
```

## Batch Scope

Adds orphan portal detection to `millpy-cleanup.py`. A portal entry `portals/<X>` is stale under the two-condition oracle: (a) `X` is not an `[active]` slug in `Home.md`, OR (b) the junction target path does not exist. Stale portals are collected into a new `orphan_portals` list on `CleanupPlan`, reported in dry-run mode, and removed in `--apply` mode. Unit tests cover both conditions and the `--apply` path.

## Cards

### Card 23: Add `_scan_orphan_portals` function to `millpy-cleanup.py`

- **Context:**
  - `plugins/mill/scripts/millpy-cleanup.py`
- **Edits:**
  - `plugins/mill/scripts/millpy-cleanup.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Add a module-level function `_scan_orphan_portals(portals_dir: Path, active_slugs: set[str]) -> list[Path]` to `millpy-cleanup.py`. The function: (1) returns an empty list if `portals_dir` does not exist or is not a directory; (2) iterates over every direct child `entry` of `portals_dir`; (3) marks `entry` as stale if either condition holds: `entry.name not in active_slugs` OR `not entry.exists()` (junction target absent — `Path.exists()` returns False for a broken junction); (4) collects and returns the list of stale portal paths. Add no docstring; a one-line comment `# Two-condition oracle: slug missing from Home.md OR target gone.` above the condition is sufficient.
- **Commit:** `feat(cleanup): add _scan_orphan_portals with two-condition oracle`

### Card 24: Add `orphan_portals` to `CleanupPlan` and wire into `build_plan`

- **Context:**
  - `plugins/mill/scripts/millpy-cleanup.py`
- **Edits:**
  - `plugins/mill/scripts/millpy-cleanup.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  (1) Add `orphan_portals: list[Path] = field(default_factory=list)` to the `CleanupPlan` dataclass (after the existing `to_reap_pr` field).
  (2) In `build_plan`, after the existing orphan worktree detection block, add:
  ```python
  orphan_portals: list[Path] = []
  if container_path is not None:
      orphan_portals = _scan_orphan_portals(
          container_path / "portals", active_slugs
      )
  ```
  (3) Pass `orphan_portals=orphan_portals` to the `CleanupPlan(...)` constructor call at the end of `build_plan`.
  The `active_slugs` set is already computed in `build_plan` (it is populated in the worktree loop). The `container_path` parameter is already available in `build_plan`'s signature.
- **Commit:** `feat(cleanup): add orphan_portals field to CleanupPlan, wire into build_plan`

### Card 25: Add `_apply_orphan_portal` function to `millpy-cleanup.py`

- **Context:**
  - `plugins/mill/scripts/millpy-cleanup.py`
- **Edits:**
  - `plugins/mill/scripts/millpy-cleanup.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Add `_apply_orphan_portal(portal_path: Path) -> None` to `millpy-cleanup.py`. The function calls `_junction.remove(portal_path)` and prints `f"[cleanup] removed orphan portal: {portal_path}"` to stderr. Place it near `_apply_inplace_record` and `_apply_worktree_record` for locality. If `_junction.remove` raises, let the exception propagate — no silent swallow.
- **Commit:** `feat(cleanup): add _apply_orphan_portal`

### Card 26: Wire orphan portal cleanup into `apply_plan` and `_print_plan`

- **Context:**
  - `plugins/mill/scripts/millpy-cleanup.py`
- **Edits:**
  - `plugins/mill/scripts/millpy-cleanup.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  (1) In `_print_plan`: update the "nothing to do" guard to also check `plan.orphan_portals`:
  ```python
  if not any([plan.to_remove_done, plan.to_remove_abandoned, plan.to_reap_pr, plan.to_report, plan.orphan_portals]):
  ```
  Add a loop after the existing print blocks:
  ```python
  for p in plan.orphan_portals:
      print(f"ORPHAN-PORTAL:     {p.name}  [target gone or not in Home.md]")
  ```
  (2) In `apply_plan`: after the `plan.to_reap_pr` loop and before the dangling `.active` check, add:
  ```python
  for portal_path in plan.orphan_portals:
      _apply_orphan_portal(portal_path)
  ```
- **Commit:** `feat(cleanup): wire orphan portal removal into apply_plan and _print_plan`

### Card 27: Add orphan portal unit tests to `test-cleanup.py`

- **Context:**
  - `plugins/mill/unit_tests/test-cleanup.py`
  - `plugins/mill/scripts/millpy-cleanup.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-cleanup.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Add a `test_scan_orphan_portals()` function to `test-cleanup.py` that covers these cases using `tempfile.TemporaryDirectory()`:
  (1) `portals_dir` does not exist -> returns empty list.
  (2) Portal entry whose name IS in `active_slugs` AND whose target exists -> NOT returned (not stale).
  (3) Portal entry whose name is NOT in `active_slugs` -> returned (stale by condition a), regardless of target existence.
  (4) Portal entry whose name IS in `active_slugs` but whose target directory does not exist -> returned (stale by condition b).
  (5) Both conditions true simultaneously -> returned once.
  For case (2), create an actual subdirectory inside `portals_dir` so `entry.exists()` returns True. For cases (3-5), create a plain directory entry name with no valid target (or omit the target dir) as needed.
  Call `test_scan_orphan_portals()` from the `main()` function alongside existing tests.
- **Commit:** `test(cleanup): add test_scan_orphan_portals unit tests`

## Batch Tests

Run `python plugins/mill/unit_tests/run-all.py`. The new `test_scan_orphan_portals` tests must pass. All prior batch tests remain passing.
