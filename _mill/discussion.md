# Discussion: (B) — Size-based reviewer switch (mechanism + configurable target)

```yaml
task: (B) — Size-based reviewer switch (mechanism + configurable target)
slug: review-large-prompt-switch
status: discussing
parent: main
```

## Problem

Large refactors can push holistic review prompts past 100K tokens. At that scale Sonnet (medium and max) drifts out of reviewer voice and starts acting like an implementer. The root cause (#278) was a 169 KTok bulk on mill-paths-cleanup: 43 files, 42 cards, holistic code review. The model is calibrated for 5–10 file tasks; oversized context breaks the review contract.

The fix is to detect oversized prompts and switch to a reviewer with larger context capacity (Opus, Gemini Pro, or a Gemini cluster). The switch must be transparent and configurable — the operator picks the override target after bench results are available.

## Scope

**In:**
- A shared helper `maybe_switch_spec_for_large_prompt()` in `_review_common.py` that checks prompt size and returns an overridden spec when the threshold is exceeded.
- Wiring the helper into all three holistic review paths: `_review_discussion.py`, `_review_plan.py`, `_review_code.py`. The call site is after `prompt_text` is built, before `_reviewer_single.run()`.
- Config schema: `roles.<role>.holistic.large_prompt: {threshold_ktok: 100, reviewer: <name>}` in `wiki/config.yaml` and the template. Works for discussion-review, plan-review, and code-review roles.
- Extending `_reviewers.validate_role_refs` to walk `large_prompt.reviewer` references so misconfiguration is caught at startup.
- `reviewer_model` in `render_prompt` kwargs updated to the override name when the switch fires, so the reviewer self-identifies correctly.
- Stderr log line when the switch triggers: `[<module>] large-prompt switch: estimated ~<N>k tok, switching reviewer <original> -> <override>`.
- Unit tests in `unit_tests/test-large-prompt-switch.py`.
- Template update: `plugins/mill/templates/wiki-config.yaml` mirrors the new `large_prompt` config key with documentation comment.

**Out:**
- Batch review paths (`code-review.batch`, `plan-review.batch`) — batch prompts are small by design. No `large_prompt` key under `batch:` scopes.
- Calling `anthropic.messages.count_tokens()` — char/4 is sufficient; no SDK dependency added.
- Choosing the concrete default override reviewer — that depends on bench results (task `bench-gemini-single-reviewers`). The config key ships with `reviewer: null` in the template (switch disabled by default).
- Cluster reviewer dispatch — not yet implemented (`_reviewer_single.py` rejects cluster specs). The override target must be a `single` type reviewer.
- Any changes to prompt templates (`review-discussion`, `review-plan-holistic`, `review-code-holistic`).

## Decisions

### Helper location: `_review_common.py`

- Decision: `maybe_switch_spec_for_large_prompt(prompt_text, spec, reviewer_name, cfg, role, scope, registry) -> tuple[dict, str]` lives in `_review_common.py`. Returns `(effective_spec, effective_reviewer_name)`. The Technical Context section's 7-arg, `-> tuple[dict, str]` signature is authoritative — always returns a name (either original or override), never `None`; the caller does not need a None check.
- Rationale: All three backends already import from `_review_common`. The logic is identical across backends — a single implementation avoids drift. Adding it to `_reviewer_single.run()` would require threading `cfg`, `role`, and `scope` through every call site, which pollutes the LLM-provider layer with config knowledge it shouldn't have. `reviewer_name` is passed explicitly so the helper can log the original name and return it unchanged when no switch fires.
- Rejected: Per-backend inline duplication (maintenance burden); `_reviewer_single.run()` hook (wrong abstraction layer).

### Scope: holistic only

- Decision: The switch applies only to holistic reviews. No `large_prompt` key is defined or checked under `batch:` scopes.
- Rationale: The task spec explicitly says `roles.<role>.holistic.large_prompt`. Per-batch prompts contain a single batch file + its source files — they are small by design and have never triggered the oversized-context failure mode.
- Rejected: Applying to batch as well — premature; adds config complexity without a known failure case.

### Config schema

- Decision: `roles.<role>.holistic.large_prompt: {threshold_ktok: 100, reviewer: <name>}`. The `large_prompt` key is optional — if absent, or if `reviewer` is null, the switch is a no-op. The threshold defaults to 100 in code if the key is present but `threshold_ktok` is missing.
- Rationale: Matches the task description verbatim. Nested key keeps holistic config cohesive. `threshold_ktok` in integer kilo-token units is readable and avoids huge raw char counts in yaml.
- Rejected: Flat `large_prompt_reviewer` / `large_prompt_threshold_ktok` keys (less readable, harder to extend).

### `tooluse` coercion on override

- Decision: The helper preserves the original spec's `tooluse` flag in the override spec (via shallow copy + forced override). If the override spec's `tooluse` differs, log a notice to stderr. The original `tooluse` value is used — not the override's.
- Rationale: The `mode` variable and `artefact_section` / `tool_rule` are built from `spec.get("tooluse")` *before* `prompt_text` is rendered. By the time the switch fires (after `prompt_text` is built), the prompt is already formatted for a specific mode. Switching mode at that point would send a bulk-formatted prompt to a tool-use session or vice versa. Preserving tooluse keeps the LLM dispatch mode consistent with the prompt.
- Rejected: Raise `ReviewError` if tooluse differs (breaks valid configs silently); use override's tooluse as-is (prompt/dispatch mismatch).

### `reviewer_model` kwarg update

- Decision: When the switch fires, `reviewer_model` in the `render_prompt` call is replaced with the override reviewer name. Since `prompt_text` is already built at switch time, this update applies to the *next* retry call if there is one (NEED_CONTEXT retry in `_review_code.py`), and it is logged to stderr rather than re-rendering.
- Wait — `reviewer_model` is embedded in the prompt via `render_prompt`. The prompt is built before the switch decision. On the first call, the prompt already contains the original reviewer name. For the NEED_CONTEXT retry, the prompt is short (just the reattach section) and does not re-embed `reviewer_model`. So `reviewer_model` in the prompt is always the original name on round 1.
- Revised decision: Leave `reviewer_model` in the prompt as-is (it is already baked in). Log the effective reviewer name to stderr so the operator knows which model ran. The review file header will show the original name; that's acceptable since the override is an operator-visible configuration choice. This avoids a two-pass prompt render.
- Rationale: Simpler implementation; the stderr log is the authoritative record of the switch. Changing `reviewer_model` in the rendered prompt would require re-rendering after the switch, which adds complexity for no operational benefit.
- Rejected: Re-rendering prompt with override reviewer name — unnecessary complexity.

### `validate_role_refs` extension

- Decision: Extend `_reviewers.validate_role_refs` to walk `roles.<role>.<scope>.large_prompt.reviewer` in the same pass. If the name is non-null and not resolvable, it is appended to the errors list alongside the regular reviewer refs.
- Rationale: Config misconfiguration (typo in override reviewer name) would otherwise only surface when a large prompt is first encountered — potentially hours into a review cycle. Startup validation catches it immediately.
- Rejected: Runtime-only validation — late failure, hard to diagnose.

### Token estimation

- Decision: `estimated_ktok = len(prompt_text) // 4000`. This is within ~10% of actual Claude token count for English + code, requires zero dependencies, and is instant. The comparison is `estimated_ktok >= threshold_ktok`.
- Rationale: Matches the task spec explicitly. No network latency, no Anthropic SDK import in a utility module. The ~10% error is acceptable for a threshold switch — the threshold is a rough operational tuning knob, not a billing boundary.
- Rejected: `anthropic.messages.count_tokens()` — network call, added SDK dependency in `_review_common.py`, latency on every holistic review even when below threshold.

## Technical context

**Affected modules:**

- `plugins/mill/scripts/_review_common.py` — add `maybe_switch_spec_for_large_prompt()`. Function signature:
  ```python
  def maybe_switch_spec_for_large_prompt(
      prompt_text: str,
      spec: dict,
      reviewer_name: str,
      cfg: dict,
      role: str,         # e.g. "code-review", "plan-review", "discussion-review"
      scope: str,        # always "holistic" for now
      registry: dict,
  ) -> tuple[dict, str]:
      """Return (effective_spec, effective_reviewer_name).
      If no large_prompt config or below threshold: returns (spec, reviewer_name) unchanged.
      If above threshold: returns (override_spec with original tooluse, override_reviewer_name).
      Logs to stderr when the switch fires.
      """
  ```

- `plugins/mill/scripts/_review_discussion.py` — call helper after `prompt_text` is built (line 109 area). Pass `role="discussion-review"`, `scope="holistic"`.

- `plugins/mill/scripts/_review_plan.py` — call helper in the holistic path after `prompt_text` is rendered (line 487 area). Pass `role="plan-review"`, `scope="holistic"`. No change to the batch path.

- `plugins/mill/scripts/_review_code.py` — call helper in the holistic path after `prompt_text` is rendered (line 306 area). Pass `role="code-review"`, `scope="holistic"`. No change to batch path. The NEED_CONTEXT retry uses `_reviewer_single.run(spec, ...)` — update the `spec` local variable so retry also uses the effective spec.

- `plugins/mill/scripts/_reviewers.py` — extend `validate_role_refs` to check `large_prompt.reviewer` alongside the main `reviewer` field.

- `plugins/mill/templates/wiki-config.yaml` — add commented-out `large_prompt` block under each holistic scope with a documentation comment.

**Call-site pattern (same for all three backends):**

```python
# After: prompt_text = render_prompt(...)
# Before: raw, session_id = _reviewer_single.run(spec, prompt_text, ...)

spec, reviewer_name = maybe_switch_spec_for_large_prompt(
    prompt_text, spec, reviewer_name, cfg, "<role>", "holistic", registry
)
```

The `reviewer_name` variable is used in the NEED_CONTEXT retry branch (code review) for logging but not re-embedded in the prompt. Updating it is correct for log accuracy.

**Config example (production wiki/config.yaml):**

```yaml
roles:
  code-review:
    holistic:
      rounds: 3
      reviewer: sonnetmedium
      large_prompt:
        threshold_ktok: 100
        reviewer: opusmax   # or g25flash, etc. — TBD after bench
```

**Unit test file:** `plugins/mill/unit_tests/test-large-prompt-switch.py`. Uses in-memory fixtures; no real LLM, no real git. Tests:
1. Below threshold — spec unchanged, no log output.
2. Above threshold — override spec returned with original tooluse preserved.
3. No `large_prompt` config — no-op.
4. `large_prompt.reviewer: null` — no-op.
5. `tooluse` coercion — original tooluse=True, override has tooluse=False; returned spec has tooluse=True, notice logged.
6. `tooluse` already matching — no notice logged.
7. `validate_role_refs` — catches bad `large_prompt.reviewer` name (unknown name raises error).
8. `validate_role_refs` — catches `large_prompt.reviewer` pointing to a valid cluster-type name (cluster resolves fine in `_reviewers.resolve()` but must be rejected since cluster dispatch is not implemented for the switch target).

## Constraints

- ASCII-only `print()` output. Em-dash → ` -- `, arrow → ` -> ` in log strings.
- `_review_common.py` is the no-dependency shared layer. The helper must not import `anthropic` SDK or any new third-party package.
- `_reviewer_single.py` raises `ReviewerError` on cluster specs. The switch helper must reject a `large_prompt.reviewer` that resolves to a cluster spec — add validation in `validate_role_refs` and in the helper at runtime.
- Windows cp1252 terminals: all `print()` strings must be ASCII.

## Testing

Unit tests in `unit_tests/test-large-prompt-switch.py`:
- Test `maybe_switch_spec_for_large_prompt` directly with a mock registry and cfg dict. No subprocess, no LLM.
- Scenarios: below threshold, above threshold, absent config, null reviewer, tooluse coercion (original True + override False → returned True), tooluse already matching (no notice), cluster reviewer rejected.
- Test `validate_role_refs` with a cfg that has a bad `large_prompt.reviewer` name — confirm error raised and bad name is mentioned.

No new integration test needed for this task: the behavior is a pure function of `prompt_text` length, cfg, and registry — all testable in-memory.

## Q&A log

- **Q:** Where should the size-switch logic live? **A:** [auto-pick] Shared helper `maybe_switch_spec_for_large_prompt()` in `_review_common.py`. **Why:** all three backends already import from there; single implementation avoids drift; adding it to `_reviewer_single.run()` would pollute the LLM layer with config knowledge.
- **Q:** Should the switch apply to batch reviews as well as holistic? **A:** [auto-pick] Holistic only. **Why:** task spec says `holistic.large_prompt`; batch prompts are small by design and have no known failure case.
- **Q:** Config schema? **A:** [auto-pick] `roles.<role>.holistic.large_prompt: {threshold_ktok: 100, reviewer: <name>}`. **Why:** matches task description verbatim; nested key keeps holistic config cohesive.
- **Q:** When override spec has different `tooluse` than original spec, what happens? **A:** [auto-pick] Preserve original `tooluse` in override spec; log notice if they differ. **Why:** prompt mode is baked in before the switch fires; mismatched dispatch would be wrong.
- **Q:** Call `anthropic.messages.count_tokens()` for exact logging? **A:** [auto-pick] No. **Why:** char/4 is sufficient; no SDK dependency, no latency.
- **Q:** Extend `validate_role_refs` for `large_prompt.reviewer`? **A:** [auto-pick] Yes. **Why:** catches misconfiguration at startup rather than when a large prompt first appears.
- **Q:** Testing approach? **A:** [auto-pick] Unit tests in `test-large-prompt-switch.py`. **Why:** the helper is a pure function over prompt_text length + cfg + registry; in-memory tests cover all branches.
