# Batch: review-code-soft-fail

```yaml
task: mill-plan/review validation false-positives, hard-fails, and truncated failure reasons
batch: review-code-soft-fail
number: 2
cards: 4
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-review-common.py test-review-code-flow.py
depends-on: []
```

## Batch Scope

This batch fixes #733: a `Context:`-only reference that resolves to a conventionally-gitignored path (e.g. under `.scratch/`) but happens to be missing on disk (didn't survive a cross-machine transfer, or was never committed) currently hard-fails the entire holistic code review with a `ReviewError`, instead of degrading to a soft warning. The fix adds an opt-in `soft_fail_gitignored` parameter to `_review_common.py`'s `resolve_ref_paths` (Card 7), then routes only the `Context:`-only refs at `_review_code.py`'s holistic `prepare()` call site through it (Card 8), leaving `Edits:`/`Creates:`/`Deletes:` resolution at hard-fail strictness unchanged. Cards 9-10 add unit- and integration-level test coverage. This batch is independent of batch 1 and batch 3 — no shared `Edits:` targets.

## Cards

### Card 7: soft_fail_gitignored parameter on resolve_ref_paths

- **Context:** none
- **Edits:**
  - `plugins/mill/scripts/_review_common.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  Add a keyword-only parameter `soft_fail_gitignored: bool = False` to `resolve_ref_paths` in `_review_common.py`.
  In the existing non-wiki candidate-building block (the `if root and git_root is not None: candidates.append(git_root / root / raw)`, `if root: candidates.append(project_root / root / raw) else: candidates.append(project_root / raw)`, `if git_root is not None: candidates.append(git_root / raw)` sequence), change `candidates` from a flat list of `Path` to a list of `(candidate, source_root)` tuples — append `(git_root / root / raw, git_root)` for the `git_root`-rooted branch, `(project_root / root / raw, project_root)` or `(project_root / raw, project_root)` for the `project_root`-rooted branch, and `(git_root / raw, git_root)` for the final `git_root`-fallback branch. Update the `hit = next((c for c in candidates if c.exists()), None)` line to unpack pairs (e.g. `next((pair for pair in candidates if pair[0].exists()), None)`) and adjust the `candidate = candidates[0]` primary-candidate-for-error-reporting line to `candidates[0][0]`. Critically, also update the `if hit is not None: resolved.append(hit); continue` branch to `resolved.append(hit[0])` — `hit` is now a `(candidate, source_root)` tuple, and `resolved` must stay `list[Path]` (this is the path taken for every already-on-disk ref, i.e. the common case; leaving it as `resolved.append(hit)` would corrupt `resolve_ref_paths`'s return contract for every caller).
  When no candidate hits AND `raw not in creates and raw not in deletes` (the existing hard-fail trigger): if `soft_fail_gitignored` is `True`, iterate the same `(candidate, source_root)` pairs in order; for each pair, call `_subprocess_util.run(["git", "-C", str(source_root), "check-ignore", "-q", str(candidate)])` (already imported — `_review_common.py` already does `import _subprocess_util`) inside a `try`/`except Exception` (any failure — including a non-git `source_root` — means "not confirmed ignored," never propagates); on the first `result.returncode == 0`, print `f"[resolve_ref_paths] warning: skipping git-ignored Context: ref {raw!r} (confirmed ignored under {source_root})"` to `sys.stderr` (ASCII only) and move to the next `raw` in the outer loop WITHOUT appending to `resolved` and WITHOUT raising. If no pair confirms git-ignored (every `check-ignore` call exits non-zero or raises, or `soft_fail_gitignored` is `False`), fall through to the existing hard-fail `ReviewError` unchanged.
  This only changes the non-wiki candidate branch; the `wiki/`-prefix branch (resolved via `wiki_root`, lines ~874-892) is untouched — a missing `wiki/`-prefixed ref still hard-fails exactly as today, `soft_fail_gitignored` or not.
  Update the function's docstring to document the new parameter and its resolution-order addition (soft-fail via git-check-ignore, tried after the existing 6-step resolution order and before the final hard-fail).
- **Commit:** `feat(review-common): add opt-in git-check-ignore soft-fail for missing Context: refs (#733)`

### Card 8: Route Context:-only refs through the soft-fail path in _review_code.py

- **Context:** none
- **Edits:**
  - `plugins/mill/scripts/_review_code.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  In `prepare()`'s ref-collection block (currently: `all_raw_refs: dict[str, None] = {}` built from `parse_batch_refs(bp)` — the default `fields=("Context", "Edits", "Creates", "Deletes")` — across `batch_files`, followed by `referenced = resolve_ref_paths(list(all_raw_refs.keys()), project_root, root, creates_union=creates_union, deletes_union=deletes_union | moves_sources_union, wiki_root=wiki_root, git_root=git_root)`):
  Replace the single `all_raw_refs` dict with two: `context_only_refs: dict[str, None] = {}` populated via `parse_batch_refs(bp, fields=("Context",))` and `other_refs: dict[str, None] = {}` populated via `parse_batch_refs(bp, fields=("Edits", "Creates", "Deletes"))`, both built in the same `for bp in batch_files:` loop that currently builds `all_raw_refs`.
  Replace the single `resolve_ref_paths(...)` call with two calls: `other_resolved = resolve_ref_paths(list(other_refs.keys()), project_root, root, creates_union=creates_union, deletes_union=deletes_union | moves_sources_union, wiki_root=wiki_root, git_root=git_root)` (unchanged hard-fail semantics — `soft_fail_gitignored` omitted, defaults `False`) and `context_resolved = resolve_ref_paths(list(context_only_refs.keys()), project_root, root, creates_union=creates_union, deletes_union=deletes_union | moves_sources_union, wiki_root=wiki_root, git_root=git_root, soft_fail_gitignored=True)`.
  Update `referenced` to be the concatenation `[*other_resolved, *context_resolved]` (order: `other_resolved` first, then `context_resolved`), feeding the existing dedup loop (`for p in (*referenced, *(extra_files or [])): ...`) unchanged. `all_raw_refs` is fully removed — grep `prepare()` for every remaining reference to that name and replace each with `raw not in other_refs and raw not in context_only_refs` (equivalently `raw not in {**other_refs, **context_only_refs}`), preserving the original exclusion semantics at each site. There are two such sites beyond the resolve_ref_paths call itself: (1) `moves_targets_on_disk = resolve_existing_paths([t for t in moves_targets_union if t not in all_raw_refs], project_root, root, wiki_root=wiki_root, git_root=git_root)` — the list-comprehension condition must become `t not in other_refs and t not in context_only_refs`; (2) the `ancestors_on_disk` computation's `raw not in all_raw_refs` filter — same replacement. Both must be updated or `prepare()` raises `NameError: all_raw_refs` at runtime the first time either code path executes.
- **Commit:** `fix(review-code): route Context:-only refs through soft-fail gitignore path (#733)`

### Card 9: Unit tests for resolve_ref_paths soft_fail_gitignored

- **Context:** none
- **Edits:**
  - `plugins/mill/unit_tests/test-review-common.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  In this file's existing `main()`, immediately after the existing `resolve_ref_paths` inline-block section (the block exercising hit-on-disk, creates_union suppression, hard-fail, wiki routing, defensive None/none filtering, deletes_union, git_root fallback — see the block starting near "resolve_ref_paths: hit on disk"), add four new inline scenario blocks in this file's existing style: `with _test_helpers.safe_temp_dir() as tmpdir:` (NOT `tempfile.TemporaryDirectory` — this file exclusively uses `_test_helpers.safe_temp_dir()`, already imported at module scope via `import _test_helpers` at the top of the file, across every existing block; `safe_temp_dir()` yields a `Path` directly, no `Path(tmpdir)` wrapping needed), inline `try`/`assert`/`except AssertionError: errors += 1`/`print("PASS: ...")`/`print("FAIL: ...", file=sys.stderr)`:
  (a) Build a real git repo via `_test_helpers.init_minimal_git_repo(repo_root, branch="main")`, write a `.gitignore` at `repo_root` covering a specific missing path (e.g. `.scratch/probe.md`), call `resolve_ref_paths([".scratch/probe.md"], repo_root, None, git_root=repo_root, soft_fail_gitignored=True)`, and assert it returns `[]` without raising (the ref is git-ignored and missing — soft-skipped).
  (b) Same repo/`.gitignore` fixture, but call `resolve_ref_paths` with a DIFFERENT missing path NOT covered by the `.gitignore`, `soft_fail_gitignored=True` → assert `ReviewError` is still raised (regression guard: soft-fail only fires on a confirmed git-ignore hit).
  (c) Same `.gitignore`-covered missing path as (a), but call `resolve_ref_paths` WITHOUT `soft_fail_gitignored` (i.e. omit the kwarg, using its `False` default) → assert `ReviewError` is still raised (confirms the parameter is fully opt-in; this represents how `Edits:`/`Creates:`/`Deletes:` refs are resolved at the `_review_code.py` call site in Card 8, which never passes `soft_fail_gitignored=True`).
  (d) Same as (c) but pass `soft_fail_gitignored=False` explicitly → assert `ReviewError` is still raised (same guarantee, explicit-default form).
- **Commit:** `test(review-common): cover soft_fail_gitignored resolve_ref_paths scenarios (#733)`

### Card 10: Integration test for Context: soft-fail in _review_code.py's prepare()

- **Context:** none
- **Edits:**
  - `plugins/mill/unit_tests/test-review-code-flow.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  Add a standalone `def test_context_only_gitignored_ref_soft_fails_prepare() -> int` to `plugins/mill/unit_tests/test-review-code-flow.py`, following this file's newer standalone-function convention (see `test_project_root_rebind_uses_resolve_active_hub_not_resolve_hub_path`), reusing `_make_fixture(tmp_path)` from this same file — `_make_fixture` already builds a real git repo at `worktree` (via `_test_helpers.init_minimal_git_repo`) with a `.gitignore` file already written at the worktree root and three batches (`alpha`/`beta`/`gamma`) each with one `Context:`-listed source file (via `_make_batch_file`'s `reads` parameter, which maps to `Context:`; that helper hardcodes `Edits: none`) that exists on disk.
  Scenario (a): after calling `_make_fixture`, append a rule to the existing `.gitignore` (e.g. `.scratch/probe.md`) and edit the `alpha` batch's file text (`01-alpha.md` under `plan_dir`) to add `.scratch/probe.md` to its `Context:` field (leave the file's hardcoded `Edits: none` as-is — do not create `.scratch/probe.md` on disk). Call `prepare(cfg, SLUG, scope="alpha", mill_dir=mill_dir, project_root=project_root, wiki_root=wiki_root, git_root=project_root)` (the real signature is `prepare(cfg, slug, *, scope, mill_dir, project_root, wiki_root, git_root, extra_files=None, max_rounds=None, prior_notes=None, agent_mode=False) -> dict`, verified in `_review_code.py`) inside a `try`/`except` and assert no exception is raised, and that `.scratch/probe.md` is absent from the returned `source_files`/`prompt_text` (soft-skipped, not hard-failed).
  Scenario (b) (regression guard, same test function or an adjacent one): same fixture, but add a DIFFERENT missing path NOT covered by the `.gitignore` to `alpha`'s `Context:` field → assert `prepare()` raises `ReviewError` (the soft-fail must not weaken hard-fail behavior for genuinely-missing, non-ignored `Context:` refs).
  Print `PASS`/`FAIL` and return 0/1 per this file's convention. **Wire the new function into `main()`**: add `errors += test_context_only_gitignored_ref_soft_fails_prepare()` to `main()`, in the same style as the existing `errors += test_project_root_rebind_uses_resolve_active_hub_not_resolve_hub_path()` call near the end of `main()` — `run-all.py` only executes what `main()` invokes; a standalone function that is never called from `main()` is dead code that silently never runs.
- **Commit:** `test(review-code): integration coverage for Context: soft-fail gitignore path (#733)`

## Batch Tests

`verify:` runs `run-all.py --only test-review-common.py test-review-code-flow.py` — `test-review-common.py` covers the `resolve_ref_paths` unit-level scenarios (Card 9), `test-review-code-flow.py` covers the `_review_code.py` `prepare()` integration-level scenario (Card 10).
