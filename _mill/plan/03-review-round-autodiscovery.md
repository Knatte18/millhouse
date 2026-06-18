# Batch: review-round-autodiscovery

```yaml
task: Fix nested-junction teardown, Windows verify gate in merge-in, and review-plan --round threading
batch: review-round-autodiscovery
number: 3
cards: 3
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-review-plan-finalize-round.py
depends-on: []
```

## Batch Scope

Removes the hard error `"--round is required for finalize stage"` from `millpy-review-plan.py` and `millpy-review-discussion.py` by auto-discovering the current round via `discover_round` when `--round` is absent. The round-equivalence invariant makes auto-discovery safe: prepare and finalize both call `discover_round(reviews_dir, review_type, "holistic")`; the review file for round N is not written until finalize completes, so both calls return the same N. A new test file exercises the CLI-level `--round` defaulting path for both review scripts.

## Cards

### Card 5: auto-discover round in millpy-review-plan.py finalize

- **Context:**
  - `plugins/mill/scripts/_review_common.py`
- **Edits:**
  - `plugins/mill/scripts/millpy-review-plan.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  Add `discover_round` to the `from _review_common import ...` line (~line 98). The existing import already contains `_load_root_from_overview, find_active_slug, load_config, resolve_path, ReviewError`; add `, discover_round` to that list.

  In the `elif args.stage == "finalize":` branch (~line 171): replace the block:
  ```python
  if args.round is None:
      print_error_envelope("plan", "--round is required for finalize stage")
      return 1
  ```
  with:
  ```python
  round_n = args.round
  if round_n is None:
      reviews_dir_for_discovery = resolve_path(cfg["paths"]["reviews_dir"], slug)
      round_n = discover_round(reviews_dir_for_discovery, "plan", "holistic")
  ```

  Replace every occurrence of `args.round` with `round_n` in the finalize branch. There are two occurrences:
  - Line 183: `round_n=args.round` in the `finalize(...)` call — change to `round_n=round_n`.
  - Line 190: `"round": args.round` in the `result_dict` — change to `"round": round_n`.

  Update the `--round` argparse help string (wherever it is defined) from the existing text (which says "--round is required") to: `"Review round number from prepare envelope; auto-discovered when absent in finalize stage."`.
- **Commit:** `fix(millpy-review-plan): auto-discover round in finalize when --round absent (#507)`

### Card 6: auto-discover round in millpy-review-discussion.py finalize

- **Context:**
  - `plugins/mill/scripts/_review_common.py`
- **Edits:**
  - `plugins/mill/scripts/millpy-review-discussion.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  Add `discover_round` to the `from _review_common import ...` line (~line 66). The existing import already contains `ReviewError, find_active_slug, load_config, resolve_path`; add `, discover_round` to that list.

  In the `elif args.stage == "finalize":` branch (~line 116): replace the block:
  ```python
  if args.round is None:
      print_error_envelope("discussion", "--round is required for finalize stage")
      return 1
  ```
  with:
  ```python
  round_n = args.round
  if round_n is None:
      reviews_dir_for_discovery = resolve_path(cfg["paths"]["reviews_dir"], slug)
      round_n = discover_round(reviews_dir_for_discovery, "discussion", "holistic")
  ```

  In the `finalize(...)` call below (~line 127): replace every occurrence of `args.round` with `round_n`.

  Update the `--round` argparse help string to: `"Review round number from prepare envelope; auto-discovered when absent in finalize stage."`.
- **Commit:** `fix(millpy-review-discussion): auto-discover round in finalize when --round absent (#507)`

### Card 7: CLI-level tests for --round auto-discovery

- **Context:**
  - `plugins/mill/scripts/_review_common.py`
  - `plugins/mill/unit_tests/test-merge-in-subagent.py`
- **Edits:** none
- **Creates:**
  - `plugins/mill/unit_tests/test-review-plan-finalize-round.py`
- **Deletes:** none
- **Requirements:**
  Create `test-review-plan-finalize-round.py`. The test file must be runnable as a standalone script (same pattern as other test files in that directory: `if __name__ == "__main__": sys.exit(main())`). Import standard library: `sys, tempfile, pathlib.Path, importlib.util, unittest.mock`. Import `discover_round` from `_review_common` for direct verification.

  **Module loading**: load `millpy_review_plan` via `importlib.util.spec_from_file_location("millpy_review_plan", Path(__file__).parent.parent / "scripts" / "millpy-review-plan.py")` and similarly `millpy_review_discussion`. Use the same pattern as `test-merge-in-subagent.py` for loading a CLI module from a `scripts/` sibling directory.

  **Shared fixture builder** `_make_fixture(tmp: Path) -> tuple[Path, Path]`: creates `reviews_dir = tmp / "reviews"` (empty), `stub_out = tmp / "agent.out.md"` with content `"MILL_REVIEW_BEGIN\n# stub\n\n\`\`\`yaml\nverdict: APPROVE\n\`\`\`\nMILL_REVIEW_END\n"`, returns `(reviews_dir, stub_out)`.

  **Stub config** `_stub_cfg(reviews_dir: Path) -> dict`: returns a minimal config dict:
  ```python
  {"paths": {"reviews_dir": str(reviews_dir), "discussion_file": "x", "plan_dir": "x", "status_md": "x"}}
  ```

  **Stub review entry**: `{"scope": "holistic", "verdict": "APPROVE", "file": str(reviews_dir / "r1.md"), "session_id": None, "blocking_count": 0, "nit_count": 0, "round": 1}`.

  **Test case `review-plan-finalize-round-empty`**: create a temp dir; build fixture. Mock `_paths.resolve_hub_path`, `_paths.resolve_git_root`, `_paths.resolve_wiki_path` as `lambda *a, **kw: tmp` (or appropriate temp paths). Mock `_review_common.load_config` to return `_stub_cfg(reviews_dir)`. Mock `_review_common.find_active_slug` to return `"test-slug"`. Mock `_reviewers.load` to return `{}`. Mock `_reviewers.validate_role_refs` to return `None`. Mock `_review_common.resolve_path` to return `reviews_dir`. Mock `_review_plan.finalize` to return the stub review entry and capture the call. Call `millpy_review_plan.main(["--stage", "finalize", "--agent-output", str(stub_out)])`. Assert: (1) call does NOT return 1 (the `--round is required` error code); (2) `_review_plan.finalize` was called; (3) the `round_n` kwarg passed to `finalize` equals `1` (empty reviews_dir → `discover_round` returns 1).

  **Test case `review-plan-finalize-round-with-existing`**: same setup but add file `reviews_dir / "20260618-120000-plan-review-r1.md"` (zero-byte) to reviews_dir before calling main(). Assert `round_n` kwarg equals `2`.

  **Test case `review-discussion-finalize-round-empty`** and **`review-discussion-finalize-round-with-existing`**: repeat the same two sub-cases for `millpy_review_discussion.main`. Use `"discussion"` wherever `"plan"` appears in mock targets. Note: `millpy-review-discussion.py` finalize calls `result.to_dict()` on the value returned by `_review_discussion.finalize` (line 132 of that script). The mock finalize for discussion sub-cases must therefore return an object that exposes `.to_dict()`, not a plain dict. Use `unittest.mock.Mock(to_dict=unittest.mock.Mock(return_value=stub_review_entry))` as the mock return value for the discussion finalize mock.

  **Pass/fail reporting**: follow the same `pass_count / fail_count` pattern and `print(f"[case] (a) ...")` style used in the other test files.

  All patches targeting modules imported lazily inside `main()` (via `from X import Y`) must patch at the **source module** level (`mock.patch("_review_common.load_config", ...)`) rather than at the importer's namespace. This works because `from _review_common import load_config` inside `main()` evaluates `_review_common.load_config` at call time, which picks up the mock.
- **Commit:** `test(millpy-review-{plan,discussion}): CLI --round auto-discovery tests (#507)`

## Batch Tests

`verify:` runs the new `test-review-plan-finalize-round.py` standalone. The four test cases exercise auto-discovery for both CLIs under empty-reviews and existing-review conditions. Scoped to the CLI finalize path only — the `_review_plan.finalize` backend is mocked, so backend flow tests are not re-covered here.
