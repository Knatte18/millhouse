# Batch: core-helper

```yaml
task: "(B) — Size-based reviewer switch (mechanism + configurable target)"
batch: core-helper
number: 1
cards: 2
verify: null
depends-on: []
```

## Batch Scope

This batch adds the shared `maybe_switch_spec_for_large_prompt` helper to `_review_common.py` and extends `validate_role_refs` in `_reviewers.py` to also validate `large_prompt.reviewer` references. These two changes are the infrastructure that batches 2 and 3 depend on. No caller wiring or tests are included here — those live in batches 2 and 3.

The external interface consumed by batch 2: `maybe_switch_spec_for_large_prompt(prompt_text, spec, reviewer_name, cfg, role, scope, registry) -> tuple[dict, str]`.

## Cards

### Card 1: Add `maybe_switch_spec_for_large_prompt` to `_review_common.py`

- **Context:**
  - `plugins/mill/scripts/_reviewers.py`
- **Edits:**
  - `plugins/mill/scripts/_review_common.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  1. Add `import _reviewers` to the import block of `_review_common.py` alongside the existing `import _marker`, `import _paths`, `import _render` group (line ~51-54). `_reviewers` is not a `_review_*.py` file so it does not violate the "No dependencies on any other Layer 02 file" constraint in the module docstring.
  2. Update the module docstring's `Public API:` section to add `maybe_switch_spec_for_large_prompt() — check prompt size; return (spec, reviewer_name), possibly overridden for large prompts`.
  3. Add the function after `build_tool_rule` (line ~746) and before `render_prompt` (line ~761). Exact placement: immediately before `def render_prompt`.

  Function signature and behaviour:
  ```python
  def maybe_switch_spec_for_large_prompt(
      prompt_text: str,
      spec: dict,
      reviewer_name: str,
      cfg: dict,
      role: str,
      scope: str,
      registry: dict,
  ) -> tuple[dict, str]:
  ```

  Logic (in order):
  - Read `large_prompt_cfg = cfg.get("roles", {}).get(role, {}).get(scope, {}).get("large_prompt")`. If falsy (absent or empty), return `(spec, reviewer_name)` unchanged.
  - Read `override_name = large_prompt_cfg.get("reviewer")`. If `None` or missing, return unchanged.
  - Read `threshold_ktok = large_prompt_cfg.get("threshold_ktok", 100)`.
  - Compute `estimated_ktok = len(prompt_text) // 4000`.
  - If `estimated_ktok < threshold_ktok`, return unchanged.
  - Call `override_spec = _reviewers.resolve(registry, override_name)`. Let `ReviewerError` propagate — it signals a registry misconfiguration.
  - If `override_spec.get("type") == "cluster"`, raise `ReviewError(f"large_prompt.reviewer {override_name!r} is cluster type; only single reviewers are supported for large-prompt switch")`.
  - Build `effective_spec = dict(override_spec)`.
  - Read `original_tooluse = spec.get("tooluse", False)`. If `effective_spec.get("tooluse", False) != original_tooluse`, print to stderr: `f"[_review_common] large-prompt switch: override {override_name!r} tooluse differs; preserving original tooluse={original_tooluse}"`. Then force `effective_spec["tooluse"] = original_tooluse`.
  - Print to stderr: `f"[_review_common] large-prompt switch: estimated ~{estimated_ktok}k tok, switching reviewer {reviewer_name!r} -> {override_name!r}"`. All characters in the format string are ASCII (the `->` is two ASCII chars plus spaces, not a Unicode arrow).
  - Return `(effective_spec, override_name)`.

- **Commit:** `feat(review): add maybe_switch_spec_for_large_prompt helper to _review_common`

### Card 2: Extend `validate_role_refs` in `_reviewers.py`

- **Context:** none
- **Edits:**
  - `plugins/mill/scripts/_reviewers.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  1. In `validate_role_refs`, inside the `for scope, scope_cfg in role_cfg.items()` loop, after the existing block that checks `reviewer = scope_cfg.get("reviewer")` and appends to `errors` on `ReviewerError`, add a second block that validates `large_prompt.reviewer`:

  ```python
  lp_reviewer = (scope_cfg.get("large_prompt") or {}).get("reviewer")
  if lp_reviewer is not None:
      try:
          lp_spec = resolve(registry, lp_reviewer)
          if lp_spec.get("type") == "cluster":
              errors.append(
                  f"roles.{role}.{scope}.large_prompt.reviewer={lp_reviewer!r}: "
                  "cluster type not supported for large-prompt override"
              )
      except ReviewerError as exc:
          errors.append(
              f"roles.{role}.{scope}.large_prompt.reviewer={lp_reviewer!r}: {exc}"
          )
  ```

  2. No other changes to `_reviewers.py`. The docstring does not need updating (the function already documents that it "walks cfg.roles.<role>.<scope>.reviewer for every (role, scope) pair" — the `large_prompt.reviewer` check is a natural extension of that semantic).

- **Commit:** `feat(review): extend validate_role_refs to check large_prompt.reviewer`

## Batch Tests

`verify: null` — the unit tests for these helpers live in batch 3 (`test-large-prompt-switch.py`). The test suite (`run-all.py`) will cover this batch's changes when batch 3 is complete. Manual smoke test: import `_review_common` in the venv and call `maybe_switch_spec_for_large_prompt` with a short prompt and no `large_prompt` config; it must return the inputs unchanged.
