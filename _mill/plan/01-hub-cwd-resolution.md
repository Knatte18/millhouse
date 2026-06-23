# Batch: hub-cwd-resolution

```yaml
task: "Fix agent-dispatch cwd guard, implementer self-termination, and false-success contracts"
batch: hub-cwd-resolution
number: 1
cards: 5
verify: "PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-paths.py test-millpy-implement.py"
depends-on: []
```

## Batch Scope

Makes the three agent-dispatch stage CLIs resolve the mill hub
cwd-independently so they work when the Builder invokes them from the git
root rather than the nested task hub, and replaces the raw
`ValueError: status file not found` traceback with an actionable error
(#514, #520). Introduces one shared, unit-testable helper in `_paths.py`
(`TaskHubError` + `require_status_path`) and rewires each CLI's common
setup to anchor `project_root` on `_paths.resolve_hub_path()`. This batch
must land before `implementer-finalize-contract` because both edit
`millpy-implement.py`'s setup block.

Batch-local decision: resolve the hub **before** `load_config`, so config
is loaded from the real hub's `.millhouse/` (`load_config(git_root, hub/.millhouse)`)
rather than a cwd-relative `.millhouse/` — otherwise a git-root cwd on a
nested-hub repo loads the wrong (or no) local overlay.

## Cards

### Card 1: Add TaskHubError + require_status_path helper to _paths.py

- **Context:**
  - `plugins/mill/scripts/_status.py`
- **Edits:**
  - `plugins/mill/scripts/_paths.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Add a new exception class `TaskHubError(Exception)` and a new function `require_status_path(project_root: Path, cfg: dict) -> Path` to `_paths.py`. `require_status_path` computes `sp = status_path(project_root, cfg)` (reuse the existing module-level `status_path` function), and if `not sp.exists()` raises `TaskHubError` with the ASCII message `f"mill: task status file not found at {sp} -- run this CLI from the task hub dir ({project_root})"`; otherwise returns `sp`. Keep the message ASCII (use ` -- `, not an em-dash). Add a one-line docstring per the python-comments skill.
- **Commit:** `feat(paths): add TaskHubError and require_status_path helper`

### Card 2: Anchor millpy-implement.py on resolve_hub_path with actionable guard

- **Context:**
  - `plugins/mill/scripts/_review_common.py`
- **Edits:**
  - `plugins/mill/scripts/millpy-implement.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** In `main()` common setup, replace `project_root = Path.cwd()` (line ~102) with `project_root = _paths.resolve_hub_path()` so `mill_dir = project_root / ".millhouse"` and the subsequent `load_config(git_root, mill_dir)` both anchor on the real hub regardless of cwd. Replace the unguarded `status_path = _paths.status_path(project_root, cfg)` + `full = _status.read_full(status_path)` pair (lines ~129-130) so that `status_path` is obtained via `_paths.require_status_path(project_root, cfg)` wrapped in `try/except _paths.TaskHubError as e: print(str(e), file=sys.stderr); return 1`. After the guard, `full = _status.read_full(status_path)` runs as before (the file is now known to exist). Do not change any other resolution (`git_root`, `wiki_path`, `plan_base`) beyond this anchoring.
- **Commit:** `fix(implement): resolve hub cwd-independently with actionable error (#514, #520)`

### Card 3: Anchor millpy-fix.py on resolve_hub_path with actionable guard

- **Context:**
  - `plugins/mill/scripts/_paths.py`
- **Edits:**
  - `plugins/mill/scripts/millpy-fix.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Apply the same change as Card 2 to `millpy-fix.py`: replace `project_root = Path.cwd()` (line ~120) with `project_root = _paths.resolve_hub_path()`, ensure `mill_dir`/`load_config` anchor on the resolved hub, and replace the unguarded `status_path = _paths.status_path(project_root, cfg)` + `full = _status.read_full(status_path)` (lines ~146-147) with `status_path` via `_paths.require_status_path(project_root, cfg)` guarded by `try/except _paths.TaskHubError` returning 1 with the error printed to stderr. Mirror Card 2's structure exactly so the two CLIs stay parallel.
- **Commit:** `fix(fix): resolve hub cwd-independently with actionable error (#514, #520)`

### Card 4: Anchor millpy-review-code.py on resolve_hub_path with actionable guard

- **Context:**
  - `plugins/mill/scripts/_review_code.py`
- **Edits:**
  - `plugins/mill/scripts/millpy-review-code.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** The primary fix here is cwd-independence: in `main()`, replace `project_root = Path.cwd()` (line ~92) with `project_root = _paths.resolve_hub_path()` and set `mill_dir = project_root / ".millhouse"` accordingly. The existing `load_config(resolve_hub_path(), mill_dir)` call (line ~96) keeps working (now consistent with `project_root`). For the actionable-error guard, scope it to the per-batch path ONLY: the status read lives in `_review_code.prepare` (the function `run` invokes; ~lines 234-248, already wrapped in `try/except`) and only happens for per-batch scope, whereas a holistic review never reads status.md — so an unconditional guard would introduce a NEW hard-fail for holistic reviews. Add the guard inside the branch where a batch is targeted: `if args.batch is not None: try: _paths.require_status_path(project_root, cfg) except _paths.TaskHubError as e: print(str(e), file=sys.stderr); return 1`. (Adjust to wherever `args.batch`/`--batch` is bound in this CLI.) This gives the same actionable error as the other two CLIs for per-batch review runs from a non-hub cwd, without changing holistic behavior. Do not otherwise change review dispatch behavior. Note: no batch `verify:` in this plan exercises `millpy-review-code.py`; correctness is validated by review.
- **Commit:** `fix(review-code): resolve hub cwd-independently with actionable error (#520)`

### Card 5: Unit-test require_status_path

- **Context:**
  - `plugins/mill/scripts/_paths.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-paths.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Add unit tests for `_paths.require_status_path`. `test-paths.py` runs inline assertions inside `main()`'s single `try` block, each using a `with tempfile.TemporaryDirectory()` fixture followed by `assert ...` and `print("PASS: ...")` (no `run-all`-discovered `test_*` list). Add the new cases inline in `main()`'s `try` block in that same style (tempfile dirs, no real git required). Cover: (1) a project_root whose `_mill/status.md` does NOT exist — wrap the call in `try/except _paths.TaskHubError` and assert it raises, and assert the exception message contains both the missing status path and the project_root; (2) a project_root whose `_mill/status.md` exists returns that path. Build a minimal `cfg` dict containing `paths.status_md` set to `"_mill/status.md"` (matching the config shape `status_path` reads). Keep the `AssertionError`-to-`FAIL` flow of the existing `main()` intact.
- **Commit:** `test(paths): cover require_status_path missing/present cases`

## Batch Tests

`verify` runs `test-paths.py` (exercises the new `require_status_path` helper directly — Card 5) plus `test-millpy-implement.py` (exercises `millpy-implement.py`'s setup/finalize, regression-guarding the Card 2 anchoring change). The hub-resolution change to `millpy-fix.py`/`millpy-review-code.py` has no dedicated unit test in this batch; their behavior is identical to Card 2's verified pattern and is covered by review plus the shared helper test. The scope is intentionally two files (not the full suite) because only `_paths` and the implement-CLI setup are exercised here.
