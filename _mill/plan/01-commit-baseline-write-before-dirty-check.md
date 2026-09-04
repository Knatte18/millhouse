# Batch: commit-baseline-write-before-dirty-check

```yaml
task: 'millpy-implement/fix.py: stuck-type false positives and session-hygiene gaps'
batch: commit-baseline-write-before-dirty-check
number: 1
cards: 4
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-implementer-common.py
depends-on: []
```

## Batch Scope

Fixes #954: `millpy-implement.py --stage finalize`'s in-scope dirty-tree gate (`_in_scope_dirty_stuck`) flags its own just-written, uncommitted `verify_baseline_failures` write to `status.md` as dirt, producing a false `stuck_type: logic`. The root cause is a write-then-check-without-commit race entirely inside `_implementer_common.py`: `_run_verify_gates`'s corroboration-waiver branch persists an expanded baseline to `status.md` via `_status.set_batch_field`, and `_in_scope_dirty_stuck` (called later in the same `finalize_from_output` invocation) observes that uncommitted write as dirt. This batch adds `git_name`/`git_email` plumbing to `_implementer_common.py` (absent today) and commits the corroboration write immediately after it succeeds, before the dirty-check ever runs — mirroring the existing commit-after-write idiom already used at `millpy-implement.py`'s `_prepare_reuse_entry` fresh-mint branch. `verify:` still runs the full existing `test-implementer-common.py` regression suite as a safety net even though this batch adds no new test cases of its own — new coverage for this fix lands in batch 2, split out separately to keep this batch's context estimate under the per-batch cap (`test-implementer-common.py` is a 5400+ line file; combining it with this batch's four implementation cards pushed the estimate over `pipeline.max_batch_context_tokens`). The external interface batches 2-4 consume: `finalize_from_output` gains two new optional keyword parameters, `git_name` and `git_email`, both `None`-defaulting and both already resolved locally by every existing caller.

## Cards

### Card 1: `_run_verify_gates` — add git identity parameters and commit-after-write

- **Context:**
  - `plugins/mill/scripts/_subprocess_util.py`
  - `plugins/mill/scripts/_status.py`
- **Edits:**
  - `plugins/mill/scripts/_implementer_common.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  Add two new keyword-only parameters to `_run_verify_gates`'s signature, immediately after the existing `batch_name: str | None = None,` parameter: `git_name: str | None = None,` and `git_email: str | None = None,`. Add a matching `Args:` docstring entry for each, stating they are the git commit identity used to persist an expanded `verify_baseline_failures` corroboration result to `status.md`; `None` (the default) disables the persist-commit, matching every other optional parameter's fail-safe-absent convention in this function.

  Inside the corroboration-waiver branch, the existing block reads:
  ```python
                        if status_path is not None and batch_name is not None:
                            try:
                                _status.set_batch_field(
                                    status_path,
                                    batch_name,
                                    "verify_baseline_failures",
                                    expanded,
                                )
                            except Exception:
                                pass
                        batch_result = None
  ```
  Add an `else:` clause to that `try`/`except` (fires only when `_status.set_batch_field` did not raise) that stages and commits `status_path` when both `git_name` and `git_email` are non-`None`, wrapped in its own `try`/`except Exception: pass` (best-effort — a commit failure here must never crash finalize; the pre-existing `_in_scope_dirty_stuck` gate, still running afterward, is the fallback authority):
  ```python
                            except Exception:
                                pass
                            else:
                                if git_name is not None and git_email is not None:
                                    try:
                                        _subprocess_util.run(
                                            [
                                                "git",
                                                "add",
                                                status_path.relative_to(project_root).as_posix(),
                                            ],
                                            cwd=project_root,
                                        )
                                        _subprocess_util.git_commit(
                                            project_root,
                                            f"mill-go: persist corroborated verify baseline for {batch_name}",
                                            name=git_name,
                                            email=git_email,
                                        )
                                    except Exception:
                                        pass
                        batch_result = None
  ```
  Use `_subprocess_util.run` (already imported at module level, line 14) and `_subprocess_util.git_commit` (`plugins/mill/scripts/_subprocess_util.py:219-234`, signature `git_commit(cwd: Path | str, message: str, *, name: str, email: str) -> subprocess.CompletedProcess[str]`) exactly as `millpy-implement.py`'s own `_prepare_reuse_entry` fresh-mint branch already does for its "mill-go: start batch {batch_name}" commit — same two-call shape (`git add` then `git_commit`), no push (this commit only needs to land locally before the dirty-check in the same `finalize_from_output` invocation; it is pushed later along with the batch's other commits).
- **Commit:** `fix(implementer-common): thread git identity into _run_verify_gates and commit corroboration write`

### Card 2: `finalize_from_output`/`_forward_output` — thread git identity to all four `_run_verify_gates` call sites

- **Context:** none
- **Edits:**
  - `plugins/mill/scripts/_implementer_common.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  Add `git_name: str | None = None,` and `git_email: str | None = None,` as new keyword-only parameters to both `finalize_from_output` (immediately after its existing `batch_name: str | None = None,` parameter) and `_forward_output` (same position in its signature). Add a one-line `Args:` docstring entry to each mirroring Card 1's wording.

  In `finalize_from_output`'s body, its `return _forward_output(...)` call currently ends with `batch_name=batch_name,` as its last keyword argument before the closing parenthesis — add `git_name=git_name,` and `git_email=git_email,` immediately after it.

  Inside `_forward_output`, there are exactly **four** call sites of `_run_verify_gates` (confirmed during planning: none, one per success-inference path), each structurally identical and each currently ending with `batch_name=batch_name,` as the last keyword argument before its closing parenthesis:
  1. The explicit-JSON `status: success` path (the call immediately preceded by `_gate_session_id = session_id or parsed.get("session_id")` and `_cards_done = parsed.get("cards_done")` a few lines above it).
  2. and 3. and 4. Three no-JSON-inference success branches, each reached when no parseable JSON `status` line was found in the sub-agent's output.

  Add `git_name=git_name,` and `git_email=git_email,` immediately after `batch_name=batch_name,` at **all four** call sites — every one of them can trigger the corroboration-waiver branch Card 1 modified, since that branch lives inside `_run_verify_gates` itself, reachable from any caller. (Only the first of the four can reproduce #954's own reported dirty-gate self-trip, since `_in_scope_dirty_stuck` is called exactly once, exclusively downstream of the first call site — the other three commits close a related but distinct uncommitted-write hygiene gap, so a `verify_baseline_failures` write from those paths does not sit uncommitted until mill-go's separate terminal cleanliness gate at task end.)
- **Commit:** `fix(implementer-common): forward git identity through finalize_from_output to all four verify-gate call sites`

### Card 3: `millpy-implement.py` — pass resolved git identity into `finalize_from_output`

- **Context:**
  - `plugins/mill/scripts/_implementer_common.py`
- **Edits:**
  - `plugins/mill/scripts/millpy-implement.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  `main()` already resolves `git_name` and `git_email` near the top (via `git config --global --get user.name`/`user.email`, with a fail-fast stderr message + `return 1` if either is unset — this happens before slug resolution). The `--stage finalize` branch's `finalize_from_output(...)` call currently ends with `module_wide_cwd_override=module_wide_cwd_override,` as its last keyword argument before the closing parenthesis. Add `git_name=git_name,` and `git_email=git_email,` immediately after it, passing the same already-resolved local variables.
- **Commit:** `fix(implement): pass resolved git identity into finalize_from_output`

### Card 4: `millpy-fix.py` — pass resolved git identity into `finalize_from_output`

- **Context:**
  - `plugins/mill/scripts/_implementer_common.py`
- **Edits:**
  - `plugins/mill/scripts/millpy-fix.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  `main()` already resolves `git_name` and `git_email` near the top (same `git config --global --get` pattern and fail-fast posture as `millpy-implement.py`, resolved before slug resolution). The `--stage finalize` branch's `finalize_from_output(...)` call (shared by both `--scope batch` and `--scope holistic`) currently ends with `cwd_override=cwd_override,` as its last keyword argument before the closing parenthesis. Add `git_name=git_name,` and `git_email=git_email,` immediately after it, passing the same already-resolved local variables. This call site is edited again by batch 3 (adding `batch_verify_baseline`/`module_verify_baseline`/etc.) — this card only adds the two identity kwargs; do not add any other parameter here.
- **Commit:** `fix(fix): pass resolved git identity into finalize_from_output`

## Batch Tests

`verify:` runs `plugins/mill/unit_tests/test-implementer-common.py` directly (the file's own `if __name__ == "__main__": sys.exit(main())` entry point) — the file's full existing regression suite for `_run_verify_gates`/`finalize_from_output`/`_forward_output` and the in-scope dirty-tree gate, confirming this batch's plumbing changes introduce no regression. New test coverage specifically for #954 (the corroboration-write commit-before-dirty-check behavior) is added by batch 2, split out to keep this batch's context estimate under `pipeline.max_batch_context_tokens`.
