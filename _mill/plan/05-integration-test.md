# Batch: integration-test

```yaml
task: "Sub-project repo (hub_relative_path) support"
batch: "integration-test"
number: 5
cards: 1
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/integration_tests/test-hub-relative-path.py
depends-on: [2, 3]
```

## Batch Scope

This batch adds one new integration test, `plugins/mill/integration_tests/test-hub-relative-path.py`, that exercises the path-resolution surface fixed in batches 1-3 against a sub-project (hub_relative_path) layout. The test follows the same shape as `test-spawn.py`: construct an isolated `.scratch/` fixture, invoke `millpy-spawn --dry-run`, then drive direct calls to `_paths.resolve_active_hub` and `_review_common.resolve_ref_paths` for the additional path-resolution assertions. No LLM is invoked; no claude / sonnet subprocess fires. The fixture's git operations run via subprocess against a real `git` in PATH.

The batch depends on batches 2 and 3 because the integration test asserts the corrected behaviour they implement. Batch 4 (SKILL.md docs) is not a runtime dependency for this test and is not in `depends-on`.

Batch-local decisions:
- The fixture is materialised under `.scratch/test-hub-relative-path/<run-id>/` where `<run-id>` is a UUID-derived suffix, mirroring `test-spawn.py`'s pattern. On test pass the directory is removed; on failure it is preserved for post-mortem.
- Wiki seeding uses the same minimal-Home.md helper that `test-spawn.py` uses (or directly writes Home.md with one `[s]` task), since the wiki daemon is not needed for `--dry-run`.
- The test prints `PASS` and exits 0 on success; on any assertion failure it prints `FAIL: <reason>` and exits 1 (matching `test-spawn.py`'s exit-code convention).

## Cards

### Card 12: add sub-project layout integration test

- **Context:**
  - `plugins/mill/integration_tests/test-spawn.py`
  - `plugins/mill/scripts/_paths.py`
  - `plugins/mill/scripts/_review_common.py`
  - `plugins/mill/scripts/_spawn_core.py`
  - `plugins/mill/scripts/_config.py`
  - `plugins/mill/scripts/_safe_rmtree.py`
- **Edits:** none
- **Creates:**
  - `plugins/mill/integration_tests/test-hub-relative-path.py`
- **Deletes:** none
- **Requirements:** Create `plugins/mill/integration_tests/test-hub-relative-path.py`. The file MUST:
  1. Follow the module-level structure used by `test-spawn.py`: `HUB`, `SCRIPTS`, `PLUGIN_ROOT`, `SCRATCH` constants derived from `Path(__file__).resolve().parent...`; `sys.path.insert(0, str(SCRIPTS))`; UTF-8 capturing `_run(cmd, *, cwd, check)` helper. Reuse the imports `_safe_rmtree`, `_spawn_core`, and any wiki-parse helpers needed for assertions.
  2. Build a sub-project fixture under `SCRATCH / "test-hub-relative-path" / <run-id>` via a `_setup_subproject_pair(container)` function. Structure per discussion.md `### Integration-test fixture sketch`:
     - `<container>/wts/outer-repo/` is a real git repo (`git init`, initial commit).
     - `<container>/wts/outer-repo/lib/example.py` exists with a trivial body (`def fn(): return 1`).
     - `<container>/wts/outer-repo/projects/sub/` is the hub subfolder; place `mill-config.yaml` here with the minimal keys the spawn flow needs (`spawn.branch_prefix:`, `paths.status_md:`, `paths.discussion_file:`, `paths.reviews_dir:`).
     - `<container>/wts/outer-repo/.millhouse/config.local.yaml` declares `hub_relative_path: projects/sub`.
     - `<container>/wiki/` is a clone (filesystem origin) containing `Home.md` with one `[s]` task and a matching `proposal-<slug>.md`. The task slug is `subproj-fixture`.
  3. Run `millpy-spawn.py --dry-run --slug subproj-fixture` from cwd `<container>/wts/outer-repo/projects/sub/` (the hub). Assert exit code 0. Assert the captured stdout contains a `[DryRun] Status:` line whose path lands under `<container>/wts/subproj-fixture/projects/sub/_mill/status.md` (not under `<container>/wts/subproj-fixture/_mill/status.md`). This validates the hub_relative_path offset is applied through spawn's dry-run path resolution.
  4. After dry-run, import `_paths` and `_config`; load the cfg with `_config.load_config(<hub-subfolder>, <hub-subfolder>)`; resolve `container_path = _paths.resolve_container_path(<outer-repo-path>)`; call `_paths.resolve_active_hub(container_path, "subproj-fixture", cfg=cfg, git_root=<outer-repo-path>)`. Note: the spawn dry-run did not create the worktree, so for the resolve_active_hub call create a stub worktree directory at `<container>/wts/subproj-fixture/projects/sub/` manually before calling — the goal is to verify the function returns the hub subfolder, not to drive a full spawn. Assert the returned path equals `<container>/wts/subproj-fixture/projects/sub`.
  5. Construct `raw_paths = ["lib/example.py"]`. Import `_review_common`; call `resolve_ref_paths(raw_paths, project_root=<hub-subfolder>, root=None, git_root=<outer-repo-path>)`. Assert the returned list has one Path whose suffix matches `<outer-repo-path>/lib/example.py`. Then call the same with `git_root=None` and assert it raises `_review_common.ReviewError` (the fallback is what makes the call succeed in sub-project layouts).
  6. On all assertions pass: print `PASS` and call `_safe_rmtree.run(SCRATCH / "test-hub-relative-path" / <run-id>)` for cleanup. On failure: print `FAIL: <message>` and `sys.exit(1)`; leave the scratch dir for post-mortem.
  7. The file is invokable directly: `PYTHONPATH= uv run --project plugins/mill python plugins/mill/integration_tests/test-hub-relative-path.py` (matches the batch's `verify:`).
  8. Add a `# pragma: no cover` or equivalent annotation only if the project uses coverage tooling on integration tests (read `pyproject.toml` to confirm — most likely not, so omit).

  Concrete cwd handling for the spawn dry-run: use `cwd=<container>/wts/outer-repo/projects/sub` when invoking `_run([sys.executable, "millpy-spawn.py", "--dry-run", "--slug", "subproj-fixture"], cwd=<hub>)`. The script will call `resolve_hub_path()` which returns the cwd-resolved hub, exercising the fixed callsite from batch 2.
- **Commit:** `test(integration): cover hub_relative_path sub-project layout end-to-end`

## Batch Tests

The batch's `verify:` runs the new integration test directly: `PYTHONPATH= uv run --project plugins/mill python plugins/mill/integration_tests/test-hub-relative-path.py`. The test is not auto-discovered by `unit_tests/run-all.py` (different directory); the verify command invokes it explicitly. Manual ad-hoc invocation from a developer shell uses the same form.

Pass criteria: the test prints `PASS` and exits 0. Any assertion failure prints `FAIL: <reason>` to stderr and exits 1.

No additional unit tests are added in this batch. The path-resolution semantics tested here are covered at the unit level by batch 1's additions to `test-paths.py` (resolve_active_hub) and `test-review-common.py` (resolve_ref_paths git_root fallback); the integration test exercises the same surface end-to-end through `millpy-spawn`'s real subprocess invocation.
