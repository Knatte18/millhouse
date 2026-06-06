# Batch: review-backend

```yaml
task: "Fix infrastructure bugs across merge, wiki-daemon, config, plan, and cleanup"
batch: review-backend
number: 2
cards: 4
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-review-common.py test-review-plan-flow.py
depends-on: []
```

## Batch Scope

Hardens the review backend: tolerant verdict parsing (#431), directory-ref
crash fix in bulk reading (#432), and a large-prompt timeout override for
plan holistic review (#423). All three live in `_review_common.py` (with
#423 also touching `_review_plan.py` and documenting one optional key in
the config template), so they are grouped to avoid parallel writes to
`_review_common.py`. No public-signature changes except the new optional
config key.

## Cards

### Card 3: Tolerant `parse_verdict` (unfenced fallback)

- **Context:** none
- **Edits:**
  - `plugins/mill/scripts/_review_common.py`
  - `plugins/mill/templates/review-output.schema.md`
- **Creates:** none
- **Deletes:** none
- **Requirements:** In `parse_verdict`, keep the existing fenced
  ` ```yaml ` block path as primary. When no opening ` ```yaml ` fence is
  found (the current `open_idx is None` branch that raises), first attempt
  a fallback: scan `raw_output` lines for the first line matching an
  unfenced `verdict: <VALUE>` (allow leading whitespace; strip quotes).
  If `<VALUE>` is one of `APPROVE`, `REQUEST_CHANGES`, `GAPS_FOUND`,
  `NEED_CONTEXT`, return it. Only if neither the fenced block nor an
  unfenced verdict line yields a valid value, raise `ReviewError` with the
  existing preview message. An invalid value found in the fenced block must
  still raise as today (do not let the fallback mask an explicit bad value
  inside a present block). Update `review-output.schema.md`: revise the
  "Raises `ReviewError` if: No ` ```yaml ` opening fence is found" wording
  to document that an unfenced `verdict:` line is now tried as a fallback
  before raising, so the doc matches the code contract.
- **Commit:** `fix(review): tolerate unfenced verdict line in parse_verdict`

### Card 4: Skip directory refs in bulk reading

- **Context:**
  - `plugins/mill/scripts/_review_code.py`
- **Edits:**
  - `plugins/mill/scripts/_review_common.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** In `_read_for_bulk`, detect `p.is_dir()` at the top and
  skip it -- emit an ASCII stderr warning and return an empty string rather
  than calling `read_text()` on a directory (which raises `PermissionError`
  on Windows). Additionally broaden the per-path exception guard to catch
  `PermissionError` alongside the existing `FileNotFoundError` in BOTH
  `bulk_files` AND `bulk_files_with_diff` (both have an identical
  `except FileNotFoundError` block calling `_read_for_bulk(p)` that would
  otherwise still crash on a directory path), warning and continuing. A
  directory listed in a batch's Context/Creates must not crash the holistic
  review.
- **Commit:** `fix(review): skip directory paths in _read_for_bulk/bulk_files`

### Card 5: Large-prompt timeout override for plan holistic review

- **Context:**
  - `plugins/mill/scripts/_reviewers.py`
- **Edits:**
  - `plugins/mill/scripts/_review_common.py`
  - `plugins/mill/scripts/_review_plan.py`
  - `plugins/mill/templates/mill-config.yaml`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Add a pure helper to `_review_common.py` (e.g.
  `resolve_large_prompt_timeout(prompt_text, cfg, role, scope, default_timeout)`)
  that returns the `large_prompt.timeout` value when the prompt is over
  threshold and the key is set, else `default_timeout`. To avoid a DRY
  violation with `maybe_switch_spec_for_large_prompt`, extract the shared
  size/threshold computation into one small named internal helper
  `_check_large_prompt(prompt_text, cfg, role, scope) -> tuple[bool, int]`
  returning `(is_over_threshold, estimated_ktok)` (where
  `estimated_ktok = len(prompt_text) // 4000` and `threshold_ktok` default
  100 is read from `cfg["roles"][role][scope]["large_prompt"]`), and have
  BOTH `maybe_switch_spec_for_large_prompt` and
  `resolve_large_prompt_timeout` call `_check_large_prompt`, so the
  threshold formula lives in exactly one place. Do NOT
  change the public signature/return of `maybe_switch_spec_for_large_prompt`
  (it is also used by code-review). Wire the new helper into
  `_review_plan.py`'s `run()` function (NOT `prepare()`, which does not
  invoke the reviewer): at BOTH `_reviewer_single.run` holistic call sites
  in `run()` -- the primary call (`timeout=holistic_timeout`) and the
  resume-retry call (`session_id=..., resume=True, timeout=holistic_timeout`)
  -- replace the bare `holistic_timeout` with the value returned by the new
  helper called with `role="plan-review"`, `scope="holistic"`,
  `default_timeout=holistic_timeout`. In `templates/mill-config.yaml`,
  document the optional `roles.plan-review.holistic.large_prompt.timeout`
  key (commented example, consistent with the existing `large_prompt`
  documentation) so the config validator's known-key allowlist (the
  template) recognizes it. Also add a one-line clarifying comment near the
  existing `llm.claude.psmux.response_poll_timeout_s.bulk` key noting that
  the review-layer timeout overrides it when invoked via
  `_llm_claude._build_psmux_argv` (the `--response-poll-timeout` path added
  in batch psmux-dispatch); this key applies only to direct
  `millpy-claude-sub.py` invocations without that flag. (This comment lives
  here, not in the psmux-dispatch batch, because `templates/mill-config.yaml`
  is owned by this batch -- keeping it here avoids a parallel-edit conflict.)
- **Commit:** `feat(review): honor large_prompt.timeout for plan holistic review`

### Card 6: Tests for review-backend fixes

- **Context:**
  - `plugins/mill/scripts/_review_common.py`
  - `plugins/mill/scripts/_review_plan.py`
  - `plugins/mill/unit_tests/test-review-common.py`
  - `plugins/mill/unit_tests/test-review-plan-flow.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-review-common.py`
  - `plugins/mill/unit_tests/test-review-plan-flow.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** In `test-review-common.py` add: parse_verdict still
  parses a fenced block; parse_verdict parses an unfenced
  `verdict: GAPS_FOUND` line; output with no verdict at all still raises;
  an invalid value inside a fenced block still raises. Add `_read_for_bulk`
  / `bulk_files` cases using a tempdir containing a real file and a
  subdirectory in the path list -> directory skipped (no exception), file
  content returned. Add `resolve_large_prompt_timeout` cases: under
  threshold or key unset -> returns the default; over threshold with key
  set -> returns the override. In `test-review-plan-flow.py` add a case
  asserting the plan holistic invocation passes the resolved (overridden)
  timeout when a large prompt + `large_prompt.timeout` are configured
  (monkeypatch `_reviewer_single.run` to capture the `timeout` kwarg).
- **Commit:** `test(review): cover verdict parsing, dir-skip, large-prompt timeout`

## Batch Tests

`verify:` runs `test-review-common.py` (parse_verdict, bulk reading,
timeout helper -- all pure functions) and `test-review-plan-flow.py`
(timeout wiring, with `_reviewer_single.run` monkeypatched). Both are
scoped to the edited modules; no real LLM dispatch occurs.
