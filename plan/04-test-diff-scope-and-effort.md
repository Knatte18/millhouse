# Batch: test-diff-scope-and-effort

```yaml
task: '11 (B) — Review-code: configurable holistic effort + diff-scoping via start_sha'
batch: test-diff-scope-and-effort
cards: 2
verify: python plugins/mill/unit_tests/test-reviewer-modules.py && python plugins/mill/unit_tests/test-review-common.py && python plugins/mill/unit_tests/test-review-code-flow.py
depends-on: [diff-scope-and-effort]
```

## Batch Scope

Add tests for all logic introduced in batches 02 and 03. Two test files are extended: `test-review-common.py` gets `bulk_files_with_diff` tests (requires real git repos in tempdir), and `test-review-code-flow.py` gets effort threading and diff-scoping integration tests (uses the existing `_reviewer_test_stub` infrastructure). Both files follow the existing print-based PASS/FAIL style with a non-zero exit code on failure.

## Cards

### Card 7: Add bulk_files_with_diff tests to test-review-common.py

- **Reads:**
  - `plugins/mill/unit_tests/test-review-common.py`
  - `plugins/mill/scripts/_review_common.py`
- **Modifies:**
  - `plugins/mill/unit_tests/test-review-common.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Add `bulk_files_with_diff` to the import from `_review_common` at the top of the test file. Add a new test section labelled `# bulk_files_with_diff` before the final `if errors:` block. Each test creates a temporary git repo with real commits. The git setup pattern to use for each test:

  ```python
  with tempfile.TemporaryDirectory() as tmpdir:
      repo = Path(tmpdir)
      subprocess.run(["git", "-C", str(repo), "init"], check=True, capture_output=True)
      subprocess.run(["git", "-C", str(repo), "config", "user.email", "t@t.com"], check=True, capture_output=True)
      subprocess.run(["git", "-C", str(repo), "config", "user.name", "T"], check=True, capture_output=True)
  ```

  **Test A — file with small diff uses DIFF delimiter:**
  - Create `src/a.py` with 2000 lines of content ("x\n" * 2000 = ~4000 bytes) and commit it as `start_sha`. Using 2000 lines ensures the threshold (0.25 × ~4020 ≈ 1005 bytes) is well above the diff size (~150 bytes for a git diff header + 10 added lines), so the DIFF branch is taken reliably.
  - Append 10 lines to `src/a.py` and commit.
  - Call `bulk_files_with_diff([repo / "src/a.py"], start_sha, repo, 0.25)`.
  - Assert the result contains `"--- DIFF:"` and does NOT contain `"--- FILE: "`.
  - Assert the result contains the `start_sha[:8]`.
  - Print `"PASS: bulk_files_with_diff small diff -> DIFF delimiter"`.

  **Test B — file with large diff uses FILE delimiter:**
  - Create `src/b.py` with 20 lines ("x\n" * 20) and commit as `start_sha`.
  - Rewrite the file with 20 entirely different lines ("y\n" * 20) and commit.
  - Call `bulk_files_with_diff([repo / "src/b.py"], start_sha, repo, 0.25)`.
  - The diff will be close to 100% of the file — assert result contains `"--- FILE: "` and does NOT contain `"--- DIFF:"`.
  - Print `"PASS: bulk_files_with_diff large diff -> FILE delimiter"`.

  **Test C — unchanged file (empty diff) uses FILE delimiter:**
  - Create `src/c.py` with some content and commit as `start_sha`.
  - Make a second commit that does NOT touch `src/c.py` (e.g., create `src/other.py`).
  - Call `bulk_files_with_diff([repo / "src/c.py"], start_sha, repo, 0.25)`.
  - Empty diff → full file. Assert result contains `"--- FILE: "`.
  - Print `"PASS: bulk_files_with_diff empty diff (unchanged file) -> FILE delimiter"`.

  **Test D — non-existent file is skipped:**
  - Use any `start_sha` from a real commit.
  - Call `bulk_files_with_diff([repo / "nonexistent.py"], start_sha, repo, 0.25)`.
  - Assert result == `""` (empty string — no parts).
  - Print `"PASS: bulk_files_with_diff non-existent file skipped"`.

  **Test E — git diff failure falls back to full file:**
  - Create and commit a file as `start_sha`.
  - Call `bulk_files_with_diff([repo / "src/a.py"], "deadbeef" * 5, repo, 0.25)` (invalid sha).
  - Assert result contains `"--- FILE: "` (fell back to full content) and does NOT contain `"--- DIFF:"`.
  - Print `"PASS: bulk_files_with_diff git diff failure -> FILE delimiter fallback"`.

  Note: Test E depends on `src/a.py` existing from Test A in the same tmpdir if reusing, or create a fresh repo. Use a fresh repo per test to keep them independent.
- **Commit:** `test(review_common): add bulk_files_with_diff tests`

### Card 8: Add effort threading and diff-scoping tests to test-review-code-flow.py

- **Reads:**
  - `plugins/mill/unit_tests/test-review-code-flow.py`
  - `plugins/mill/scripts/_review_code.py`
  - `plugins/mill/scripts/_reviewer_test_stub.py`
  - `plugins/mill/scripts/_status.py`
- **Modifies:**
  - `plugins/mill/unit_tests/test-review-code-flow.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Add new test cases inside the existing `main()` function, after the last existing test and before `if errors:`. Follow the existing numbered test convention (the existing tests go up to test 8 approximately — check and continue the numbering, or add a clear section header).

  Each test uses `_make_fixture` and `os.chdir(project_root)`, following the existing pattern. The fixture's `cfg` dict must be extended where needed for the new config keys.

  **Test: holistic call passes holistic_effort to reviewer**

  Use `_make_fixture` to get a standard 3-batch fixture. Set `cfg["review"]["code"]["holistic_effort"] = "medium"`. Seed one APPROVE response. Call `code_run(cfg, SLUG, mill_dir, wiki_root, project_root, batch_name=None)` (holistic). After the call, read `stub.captured_prompts()`. Assert `captured_prompts[0][1]["effort"] == "medium"`. Print `"PASS: holistic call passes holistic_effort='medium' to reviewer"`.

  **Test: per-batch call passes effort=None to reviewer**

  Use `_make_fixture`. Do NOT set `holistic_effort` in cfg (or set it to `"max"` — both should produce `effort=None` on per-batch calls). Seed one APPROVE. Call `code_run(cfg, ..., batch_name="alpha")` (per-batch). Assert `captured_prompts[0][1]["effort"] is None`. Print `"PASS: per-batch call passes effort=None (no holistic_effort override)"`.

  **Test: per-batch with start_sha present → prompt contains DIFF delimiter**

  Setup steps:
  1. Use `_make_fixture` to get `(mill_dir, wiki_root, project_root, cfg)`.
  2. In `project_root`, configure git user (`git config user.email/user.name`) and add and commit `src/a.py` with 2000 lines ("x\n" * 2000). `_make_fixture` already called `git init` on the repo; do not call it again — just configure the user and make the initial commit. Capture that commit sha as `start_sha`.
  3. Append 5 lines to `src/a.py` and make a second commit.
  4. Write a `status.md` file at `project_root / "status.md"` with a `## Batches` section containing one entry: `name: alpha, state: approved, start_sha: <start_sha>`. Use the yaml format that `_status.read_batches` expects (see `_status.py`'s `_BATCHES_HEADING` and `_serialise_batches` for the format — or write it directly as text).
  5. Seed one APPROVE response.
  6. Call `code_run(cfg, SLUG, mill_dir, wiki_root, project_root, batch_name="alpha")`.
  7. Assert `stub.captured_prompts()[0][0]` contains `"--- DIFF:"`. Print `"PASS: per-batch with start_sha uses diff-scoping (DIFF delimiter in prompt)"`.

  **Test: per-batch with missing start_sha → prompt uses FILE delimiter (no DIFF)**

  Use `_make_fixture` but write a `status.md` with the alpha batch entry having NO `start_sha` field (or with `start_sha: null`). Seed APPROVE. Call per-batch review on alpha. Assert `stub.captured_prompts()[0][0]` does NOT contain `"--- DIFF:"` (falls back to full file). Print `"PASS: per-batch with missing start_sha falls back to full file content"`.

  **Test: per-batch with large diff → prompt uses FILE delimiter (not DIFF)**

  Same setup as the `start_sha present` test, but this time make a large commit that rewrites most of `src/a.py`. The diff should exceed the 0.25 threshold. Assert `stub.captured_prompts()[0][0]` does NOT contain `"--- DIFF:"`. Print `"PASS: per-batch with large diff falls back to full file content"`.

  **Existing test 5 assertion update:** Batch 02 adds `effort` to the stub's captured kwargs dict. The existing test 5 asserts `retry_kwargs == {"session_id": "sid-1", "resume": True, "timeout": None}` — this will fail once `effort` is present. Update that assertion to `{"session_id": "sid-1", "resume": True, "timeout": None, "effort": None}`.

  **Status.md fixture format note for the implementer:** `_status.read_batches` reads the `## Batches` section's fenced yaml block. The minimal format is:

  ```
  ## Batches

  ```yaml
  batches:
    - name: alpha
      state: approved
      start_sha: <sha>
  ```
  ```

  Write this as a string to `project_root / "status.md"`. The `## Batches` section can be appended after a minimal top-level yaml block:

  ```
  # Status

  ```yaml
  phase: coding
  slug: test-slug
  branch: test-slug
  plan: plan
  parent: main
  task: 'test'
  ```

  ## Batches

  ```yaml
  batches:
    - name: alpha
      state: approved
      start_sha: <sha>
  ```
  ```

  Use `_active.write` to ensure `.millhouse/active.slug.md` is present (it is — `_make_fixture` creates it). The status.md at `project_root / "status.md"` is read via `resolve_path("status.md", slug)` which resolves to `active_worktree / "status.md"` — since `project_root` IS the active worktree, this resolves correctly.
- **Commit:** `test(review_code_flow): add effort threading and diff-scoping integration tests`

## Batch Tests

`verify: python plugins/mill/unit_tests/test-reviewer-modules.py && python plugins/mill/unit_tests/test-review-common.py && python plugins/mill/unit_tests/test-review-code-flow.py` — runs all three affected test files. All existing tests must still pass. New tests must pass. The `&&` chain means a failure in any file stops the verify and signals the implementer.
