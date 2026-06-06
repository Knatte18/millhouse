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

- **Context:**
  - `plugins/mill/templates/review-output.schema.md`
- **Edits:**
  - `plugins/mill/scripts/_review_common.py`
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
  inside a present block).
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
  on Windows). Additionally broaden the `bulk_files` per-path exception
  guard to catch `PermissionError` alongside the existing
  `FileNotFoundError`, warning and continuing. A directory listed in a
  batch's Context/Creates must not crash the holistic review.
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
  that mirrors the size-threshold logic in
  `maybe_switch_spec_for_large_prompt` (`estimated_ktok = len(prompt_text)
  // 4000`, `threshold_ktok` default 100 read from
  `cfg["roles"][role][scope]["large_prompt"]`) and returns the
  `large_prompt.timeout` value when the prompt is over threshold and the
  key is set, else `default_timeout`. In `_review_plan.py`, where the
  holistic reviewer is invoked (`_reviewer_single.run(holistic_spec,
  prompt_text, timeout=holistic_timeout)` and the resume retry call), call
  the new helper with `role="plan-review"`, `scope="holistic"` and pass the
  resolved timeout instead of the bare `holistic_timeout`. In
  `templates/mill-config.yaml`, document the optional
  `roles.plan-review.holistic.large_prompt.timeout` key (commented example,
  consistent with the existing `large_prompt` documentation) so the config
  validator's known-key allowlist (the template) recognizes it.
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
