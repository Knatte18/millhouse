# Batch: test-registry-local-overlay-redirect

```yaml
task: 'Self-discovered mill pipeline bugs: silent archive-tag push failure, ignored --max-rounds override, dead test-registry helper, truncated commit_sha in implementer reports'
batch: test-registry-local-overlay-redirect
number: 3
cards: 3
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-reviewers.py test-review-plan-flow.py test-review-discussion-flow.py
depends-on: []
```

## Batch Scope

Redirects `_test_registry.write_to` from the dead legacy `wiki_root/agents.yaml` fallback to the `.millhouse/agents.local.yaml` layer `_reviewers.load()` actually merges, and consolidates the file-write mechanics with the pre-existing `_test_helpers.write_local_overlay` duplicate (independently added by two prior implementer batches as a workaround) behind one shared low-level writer. One batch: the two helper modules and the round-trip test that proves the redirect works form one indivisible change. No batch-local decisions differ from `## Shared Decisions` in the overview, with one addition below.

### Decision: Consolidation mechanic — shared low-level writer, zero call-site changes

- **Decision:** `_test_registry.py` gains a new `_write_registry_file(mill_dir, registry) -> Path` helper that performs the actual file write; `write_to(mill_dir, **overrides)` builds its registry via the existing `make_minimal_registry(**overrides)` (baseline `sonnetmax`/`sonnetmax_bulk` entries + overrides) and delegates to `_write_registry_file`. `_test_helpers.write_local_overlay(mill_dir, **entries)` delegates to the same `_write_registry_file(mill_dir, entries)`, writing its raw `entries` dict verbatim with no baseline merge — its existing behavior is unchanged. Both functions still write to `mill_dir / "agents.local.yaml"`.
- **Rationale:** `write_to` and `write_local_overlay` build genuinely different content (baseline-merged vs. raw-verbatim) — `write_local_overlay`'s 13 existing call sites (`test-review-plan-flow.py` x7, `test-review-discussion-flow.py` x6) pass exact named specs and would break if a `sonnetmax`/`sonnetmax_bulk` baseline were silently merged in. Sharing only the low-level file-write step (not the content-building step) eliminates the duplicate write mechanics the issue flagged while requiring zero changes to any of the 13 existing `write_local_overlay(...)` call sites or the 11 existing `write_to(wiki_root)` call sites (the latter keep passing `wiki_root` positionally — still a harmless no-op after the redirect, per the overview's "Items explicitly out of scope" decision, just for a different reason: wrong directory instead of wrong filename).
- **Applies to:** this batch only

## Cards

### Card 6: Redirect `_test_registry.write_to` to the local-overlay layer

- **Context:** none
- **Edits:**
  - `plugins/mill/unit_tests/_test_registry.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  - Add a new module-level function `_write_registry_file(mill_dir: Path, registry: dict) -> Path` that creates `mill_dir` (`mill_dir.mkdir(parents=True, exist_ok=True)`), writes `registry` as YAML to `mill_dir / "agents.local.yaml"` (`yaml.safe_dump(registry, default_flow_style=False)`, `encoding="utf-8"`), and returns that path.
  - Rewrite `write_to(mill_dir: Path, **overrides) -> Path`'s body (renaming its parameter from `wiki_root` to `mill_dir`) to call `make_minimal_registry(**overrides)` then `return _write_registry_file(mill_dir, registry)`.
  - Update the module docstring at the top of the file and `write_to`'s own docstring: state that it now writes `mill_dir / "agents.local.yaml"` — the layer `_reviewers.load(hub_dir)` merges from `hub_dir / ".millhouse" / "agents.local.yaml"` — and that callers must pass the hub's `.millhouse` directory as `mill_dir`, not the wiki root.
- **Commit:** `refactor(test-registry): redirect write_to to the local-overlay layer`

### Card 7: Consolidate `_test_helpers.write_local_overlay` onto the shared writer

- **Context:**
  - `plugins/mill/unit_tests/_test_registry.py`
- **Edits:**
  - `plugins/mill/unit_tests/_test_helpers.py`
- **Creates:** none
- **Deletes:**
  - `plugins/mill/scripts/_test_registry.py`
- **Moves:** none
- **Requirements:**
  - Add `import _test_registry` to `_test_helpers.py`'s existing flat-import block (same convention as its other bare `import _safe_rmtree` / `import pygit2` lines — no package prefix).
  - Rewrite `write_local_overlay(mill_dir: Path, **entries) -> None`'s body to `_test_registry._write_registry_file(mill_dir, entries)`, discarding the returned path (the function's own return type stays `-> None`). Preserve its existing external behavior exactly: it must still write the raw `entries` dict verbatim (no baseline merge) to `mill_dir / "agents.local.yaml"`.
  - Update the docstring: the sentence "the legacy wiki `agents.yaml` fallback used by `_test_registry.write_to` is only consulted when both the template and the local overlay are empty" is now stale — `_test_registry.write_to` no longer targets the wiki `agents.yaml`; it writes the same `.millhouse/agents.local.yaml` file this function does (via the shared `_write_registry_file` helper). Rewrite that sentence to say so while keeping the surrounding explanation of `_reviewers.load()`'s merge order (plugin template + local overlay, wiki fallback only when both are empty) intact.
  - Delete `plugins/mill/scripts/_test_registry.py` — an unreferenced duplicate of `plugins/mill/unit_tests/_test_registry.py` (identical `make_minimal_registry`/`write_to` pair, pre-dating this batch, no in-scripts importer) discovered mid-implementation: `test-review-plan-flow.py` and `test-review-discussion-flow.py` insert `plugins/mill/scripts` onto `sys.path` ahead of their own directory, so `import _test_registry` there resolved to this stale scripts-dir copy instead of the redirected `unit_tests` module, silently shadowing Card 6's redirect and breaking `write_local_overlay`'s delegation. Before the redirect both copies wrote identical content, so the shadowing was harmless; the redirect exposed it. Deleting the dead copy lets `import _test_registry` fall through to the real module on `sys.path`.
- **Commit:** `refactor(test-helpers): delegate write_local_overlay to the shared registry writer`

### Card 8: Add a round-trip test proving the redirected write_to resolves through _reviewers.load

- **Context:**
  - `plugins/mill/unit_tests/_test_registry.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-reviewers.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  - Change the existing `from _test_registry import make_minimal_registry` import line to `from _test_registry import make_minimal_registry, write_to`.
  - Add a new test function `test_write_to_round_trips_through_reviewers_load() -> None`, modeled on `test_load_happy_path` (same file, ~line 80): create a `tempfile.TemporaryDirectory()`, `hub_dir = tmp_path / "hub"`, `hub_dir.mkdir()`; call `write_to(hub_dir / ".millhouse")`; patch `_reviewers.resolve_plugin_template_path` (via `unittest.mock.patch.object`) to return a nonexistent path and `_paths.resolve_wiki_path` to `side_effect=SystemExit`, exactly as `test_load_happy_path` does, so the local-overlay layer is the sole source; call `registry = _reviewers.load(hub_dir)`; assert `"sonnetmax" in registry`, `registry["sonnetmax"]["type"] == "single"`, `registry["sonnetmax"]["provider"] == "claude"`, and `"sonnetmax_bulk" in registry`. End with `print("PASS: write_to round-trips through reviewers.load")`.
  - Register the new function in `main()`'s `tests = [...]` list (`plugins/mill/unit_tests/test-reviewers.py`, ~line 1150), appended immediately after the `test_load_raises_cluster_use_referencing_cluster` entry (~line 1162) — the last entry in the main `test_load_*` cluster (lines 1151-1162) before unrelated `test_resolve_*`/`test_validate_role_refs_*` entries follow. Do not insert after `test_load_falls_back_to_reviewers_yaml` (~line 1172), which sits between unrelated `test_validate_role_refs_*` entries, not near the main cluster.
- **Commit:** `test(reviewers): round-trip write_to through _reviewers.load`

## Batch Tests

`verify:` runs `test-reviewers.py` (Card 8's new round-trip test plus every existing `_reviewers.load`/`resolve` test — `write_to`'s new target is exercised directly), `test-review-plan-flow.py`, and `test-review-discussion-flow.py` (the two files with all 13 existing `write_local_overlay(...)` call sites — Card 7 changes that function's internals, so both consuming files re-run in full to confirm the delegation preserves exact prior behavior) via `run-all.py --only`. Not run against the full suite: `_test_registry.write_to`'s other 11 call sites (`test-agent-mode-dispatch.py`, `test-review-code-flow.py`, plus the 2 already-included files) all seed the `"test_stub"` reviewer, which bypasses registry lookup entirely (see `_mill/discussion.md`'s Technical Context) — the redirect is a no-op for them either way, so re-running them adds no coverage.
