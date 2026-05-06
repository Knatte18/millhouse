# Discussion: 6 (A) — Plan reviewer: detect self-applying layout changes that strand in-flight state

```yaml
task: '6 (A) — Plan reviewer: detect self-applying layout changes that strand in-flight state'
slug: plan-reviewer-self-apply
status: discussing
parent: main
```

## Problem

The `container-restructure` task shipped a plan that retargeted `wiki/config.yaml` `paths:` keys in batch 03 (Card 14) and added a `--halt-on-in-flight` migration gate in batch 05 (Card 23). The task was itself in-flight when the plan ran. As soon as Card 14 landed, every reviewer and cleanup script expected task state at `<worktree>/plan/`, `<worktree>/reviews/` etc., but those files still lived at the old wiki-relative paths. The batch-05 migration refused to run while the task was in flight. mill-go bridged this manually with a bootstrap commit — a plan deviation that should never be required.

The plan went through three review rounds (r1–r3) and was approved each time. The LLM reviewer has no rule for detecting when a plan modifies the layout that the shipping task itself runs under. The fix adds both a static pre-check (programmatic, pre-LLM) and an LLM reviewer rule (in the prompt templates) so this class of bug is caught before the plan is approved.

## Scope

**In:**
- New static check in `_plan_validate.py`: flag any batch that lists `wiki/config.yaml` as a `Modifies:` or `Creates:` target. Check key: `wiki-config-mutation`. Returns the same error dict shape as all other checks (`{check, batch, card, path, message}`).
- New criterion in `plugins/mill/templates/review-plan-batch.md`: the LLM reviewer must flag any batch that modifies `wiki/config.yaml`, cross-checked against the task running under those same paths. BLOCKING severity.
- New criterion in `plugins/mill/templates/review-plan-holistic.md`: same rule, evaluated holistically across all batches.
- Unit tests in `plugins/mill/unit_tests/test-plan-validate.py`: clean and dirty fixtures for the new check.
- `plugins/mill/scripts/millpy-validate-plan.py` docstring update (the check-keys list in the module docstring of `_plan_validate.py`).

**Out:**
- No changes to `_review_plan.py` (the backend). The new check lives entirely in `_plan_validate.py` which already gates `millpy-review-plan.py`.
- No auto-suppression or bootstrap-card detection. Static check always fires on `wiki/config.yaml` mutation; author suppresses with `--skip-validate` if justified.
- No broader "layout change" detection beyond `wiki/config.yaml`. Do not scan for changes to path-resolution helpers, layout scripts, or other infrastructure.
- No changes to discussion review or code review templates.
- No changes to `millpy-migrate-layout.py`.

## Decisions

### static-check-scope

- Decision: Flag any plan batch that lists `wiki/config.yaml` as a `Modifies:` target — regardless of whether a `--halt-on-in-flight` guard or migration script is also present.
- Rationale: The root cause is modifying the shared config that governs where task state lives, while that task is in flight. A plan that moves paths without a migration gate is strictly worse than the incident case. Narrowing to "only flag when halt-check co-present" would miss the more dangerous case. Broadening to all mill infrastructure files risks high false-positive rates.
- Rejected: (A) Narrow — flag only when `wiki/config.yaml` mutation AND halt-check co-present. Too narrow: misses cases without migration gates. (B) Broad — flag any modification to infrastructure paths or path helpers. Too many false positives for legitimate refactors.

### implementation-layer

- Decision: Both layers — programmatic check in `_plan_validate.py` (runs pre-LLM, deterministic) AND LLM reviewer rule added to both batch and holistic templates.
- Rationale: The three-round miss in the incident shows LLM-only rules are insufficient. The static check catches the structural pattern before the LLM even sees the plan. The LLM rule provides semantic coverage: it can understand *why* the bootstrap is needed and whether a proposed fix is coherent.
- Rejected: (A) Programmatic only — misses semantic validation of bootstrap cards. (B) LLM only — already proven insufficient; three review rounds missed it.

### static-check-suppression

- Decision: The static check is a hard block (like all other `_plan_validate.py` checks). `--skip-validate` suppresses it. No auto-pass path for "bootstrap card present" — we cannot verify bootstrap correctness statically.
- Rationale: Consistent with how `non-existent-path` works today. The plan author acknowledges the risk by suppressing explicitly. The LLM reviewer then validates the suppression is justified (it sees the plan; the static check does not).
- Rejected: (A) Require explicit bootstrap card for auto-pass. Can't verify correctness statically. (B) Only warn, don't block. Three warnings already failed in the incident.

### detection-signal

- Decision: Scan `Modifies:` fields in batch cards for the token `wiki/config.yaml`. Any batch with this token triggers the check.
- Rationale: Simplest, lowest false-negative rate. Wiki config mutation is always structurally risky for in-flight tasks. Checking for presence in `Modifies:` is already done by `_parse_modifies_only()` in `_plan_validate.py` — reuse that helper.
- Rejected: (A) Also check `wiki/config.yaml` in `Creates:` — creating the file from scratch is equally dangerous, add it. Wait — `Creates:` should also be checked since writing a new config is as dangerous as modifying one. (B) Limit to checking if `paths:` key is mentioned in plan prose — too fragile, LLM concerns only.

> **Correction to the above:** The detection should cover both `Modifies:` and `Creates:` for `wiki/config.yaml`. A plan that creates a new wiki config as part of a migration is equally self-applying.

## Technical context

### `_plan_validate.py`

The module at `plugins/mill/scripts/_plan_validate.py`. All checks follow the pattern:

```python
def _check_<name>(...) -> list[dict]:
    errors = []
    # ... scan batch files ...
    errors.append({
        "check": "<check-key>",
        "batch": batch_path.stem,
        "card": None,     # or card number if per-card
        "path": t,        # the offending path token
        "message": "...",
    })
    return errors
```

The `run()` function at line 643 calls all check functions and collects results. The new check must be added to `run()` and to the module docstring's `Checks performed` list.

The helper `_parse_modifies_only(batch_path: Path) -> set[str]` already exists and returns raw Modifies: tokens. Add a parallel `_parse_creates_only(batch_path: Path) -> set[str]` using identical logic but restricted to `Creates:` headers. The new check unions both: `_parse_modifies_only(batch_path) | _parse_creates_only(batch_path)`, then checks if `"wiki/config.yaml"` is in the result. Do not use `parse_batch_refs` (returns Reads too) and do not add a third helper — two helpers + inline union is the right shape.

### `review-plan-batch.md` and `review-plan-holistic.md`

Templates at `plugins/mill/templates/`. Both have a `## Criteria` section with bullet-list rules. The new rule belongs in that section. Format matches existing criteria:

```
- **Self-applying layout change** — BLOCKING if any batch modifies `wiki/config.yaml`
  (the shared config governing where task state lives) without an explicit bootstrap
  step for the shipping task. A plan running under the old layout cannot safely migrate
  its own state mid-flight.
```

The holistic template gets a parallel entry under its "Criteria (apply to the plan as a whole)" section.

### Static check integration

`millpy-review-plan.py` at line ~66 calls `validate_run(plan_dir, project_root, wiki_root=wiki_root)` before invoking the LLM reviewer. `validate_run` is `_plan_validate.run`. The `run()` function signature:

```python
def run(plan_dir, project_root, *, root=None, wiki_root=None) -> list[dict]:
```

The new check needs `wiki_root` to resolve `wiki/config.yaml` paths (the token `wiki/config.yaml` is wiki-root-relative per the plan file convention). However, the check only needs to detect the *string* `wiki/config.yaml` in Modifies/Creates tokens — it does not need to resolve the path to disk. Simple string match on the token is sufficient.

### Unit test patterns

`plugins/mill/unit_tests/test-plan-validate.py` uses `tempfile.TemporaryDirectory` and `_make_batch_file()` / `_make_overview()` helpers. Each check has a `test_check_<name>_clean` and `test_check_<name>_dirty` function. The dirty fixture writes a batch with `wiki/config.yaml` in Modifies, the clean fixture does not. The test calls `_plan_validate.run(plan_dir, project_root)` and asserts on returned errors.

## Constraints

- No new external dependencies.
- The check key must be unique among all check keys in `_plan_validate.py`. Use `wiki-config-mutation`. (Do not use `wiki-config-paths-mutation` — the check covers any wiki/config.yaml mutation, not only paths changes.)
- Error dict shape must match exactly: `{check, batch, card, path, message}`. `card` is `None` for file-level checks.
- `run-all.py` runs tests as subprocesses; new tests go in the existing `test-plan-validate.py` file.
- Windows path separators — existing code uses `Path` throughout; no raw string slashes in new code.
- No `if __name__ == "__main__":` blocks in helper modules.

## Testing

**`test-plan-validate.py`** (unit, in-memory fixtures, no LLM, no git):
- `test_wiki_config_mutation_clean` — batch with `wiki/config.yaml` only in `Reads:` → zero errors.
- `test_wiki_config_mutation_modifies` — batch with `wiki/config.yaml` in `Modifies:` → one `wiki-config-mutation` error.
- `test_wiki_config_mutation_creates` — batch with `wiki/config.yaml` in `Creates:` → one `wiki-config-mutation` error.
- `test_wiki_config_mutation_multi_batch` — two batches, each with `wiki/config.yaml` in `Modifies:` → two errors (one per batch).
- `test_wiki_config_mutation_modifies_and_creates` — one batch with `wiki/config.yaml` in both `Modifies:` and `Creates:` → one error (file-level check, one error per batch regardless of how many fields reference the token).
- Verify error dict shape: `check == "wiki-config-mutation"`, `batch == <stem>`, `card is None`, `path == "wiki/config.yaml"`.

No new integration tests needed — the check is purely structural (string matching on batch text).

Template changes have no automated tests (LLM output is not deterministic). The review runs themselves are the integration test.

## Q&A log

- **Q:** What scope for the static check — narrow (halt-check co-presence), medium (any wiki/config.yaml Modifies), broad (any infrastructure path)? **A:** Medium — any `wiki/config.yaml` in `Modifies:` or `Creates:`.
- **Q:** Programmatic check only, LLM rule only, or both? **A:** Both.
- **Q:** Should the static check auto-pass if a bootstrap card is present? **A:** No — always block; `--skip-validate` for suppression; LLM validates the suppression.
- **Q:** Should the detection cover only `Modifies:` or also `Creates:`? **A:** Both. One error per batch maximum (deduplicated).
- **Q:** What check key to use? **A:** `wiki-config-mutation` (not `wiki-config-paths-mutation` — the check covers any wiki/config.yaml write, not only paths changes).
- **Q:** How to union Modifies+Creates? **A:** Add `_parse_creates_only` mirroring `_parse_modifies_only`; union inline. Do not use `parse_batch_refs`.
