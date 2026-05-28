# Batch: plan-review-cli-and-validator

```yaml
task: "mill-go / mill-plan loop hardening"
batch: plan-review-cli-and-validator
number: 3
cards: 4
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-review-cli-error-envelope.py test-plan-validate.py
depends-on: []
```

## Batch Scope

Bundles the three issues that share the plan-review CLI and the static plan validator:
#372 (the CLI can exit without a JSON line on an uncaught exception), #371 (no enforced
batch-sizing gate), and #363 (no plan-time rejection of out-of-worktree edit targets).
Card 5 guarantees the CLI always emits an envelope. Cards 6-8 add the two new validator
checks and the config keys that parameterise the sizing gate. `millpy-review-plan.py` is
edited by cards 5 and 7 (both within this batch, so no cross-batch overlap); the validator
and config are edited by cards 6-8.

External interface consumed downstream (batch 6, mill-plan-skill prose): the two new
validator check names `batch-oversized` and `out-of-worktree-target` (both step-1.5 "halt"
rows), the absent-JSON two-pass retry behaviour, and the `pipeline.max_cards_per_batch` /
`pipeline.max_batch_context_tokens` config keys.

## Cards

### Card 5: guarantee a JSON envelope from millpy-review-plan

- **Context:**
  - `plugins/mill/scripts/_review_cli.py`
- **Edits:**
  - `plugins/mill/scripts/millpy-review-plan.py`
  - `plugins/mill/unit_tests/test-review-cli-error-envelope.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** In `millpy-review-plan.py`'s `main()`, the final `try` block around the `run(...)` call currently catches only `ReviewError` (`except ReviewError as exc: print_error_envelope("plan", str(exc)); return 1`). Add a broad fallback `except Exception as exc:` immediately after the `ReviewError` handler that calls `print_error_envelope("plan", f"unhandled review error: {exc}")` and returns `1`, so any uncaught exception from `run(...)` still emits a `verdict: ERROR` envelope on stdout instead of a bare traceback with no JSON. Keep the `ReviewError` handler first (it produces the cleaner message). Do not alter the validator-failure path (the `errors` JSON block) or the pre-launch handlers. Add a test to `test-review-cli-error-envelope.py` that monkeypatches `_review_plan.run` (or the imported `run`) to raise a generic `RuntimeError`, invokes `main()` with a fixture cwd, captures stdout, and asserts the captured line parses as JSON with `verdict == "ERROR"` and `type == "plan"`, and that `main()` returns `1`.
- **Commit:** `fix(review): always emit JSON envelope from plan-review CLI (#372)`

### Card 6: add batch-sizing config keys

- **Context:**
  - `plugins/mill/scripts/_plan_validate.py`
- **Edits:**
  - `mill-config.yaml`
  - `plugins/mill/templates/mill-config.yaml`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Add two keys under the existing `pipeline:` mapping in BOTH `mill-config.yaml` (hub) and `plugins/mill/templates/mill-config.yaml` (template), keeping the two files in sync per CLAUDE.md: `max_cards_per_batch: 10` and `max_batch_context_tokens: 120000`. In the template, add a short trailing comment on each line (e.g. `# batch-oversized validator gate (#371)`) matching the template's existing comment style. Place them after the existing `pipeline:` entries (`auto_merge` / `auto_report` / `autonomous_mode`). No code reads these yet — card 7 wires them.
- **Commit:** `feat(config): add batch-sizing thresholds to pipeline config (#371)`

### Card 7: add batch-oversized validator check

- **Context:**
  - `mill-config.yaml`
  - `plugins/mill/scripts/_review_common.py`
  - `plugins/mill/scripts/millpy-review-code.py`
- **Edits:**
  - `plugins/mill/scripts/_plan_validate.py`
  - `plugins/mill/scripts/millpy-review-plan.py`
  - `plugins/mill/unit_tests/test-plan-validate.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Add a `_check_batch_oversized(batch_files, project_root, root, *, max_cards, max_context_tokens, wiki_root=None)` helper to `_plan_validate.py` and call it from `run()`. For each batch file: (1) count cards via the existing `_parse_cards(text)` — if the count exceeds `max_cards`, append an error dict `{"check": "batch-oversized", "batch": batch_path.stem, "card": None, "path": None, "message": "batch has N cards (cap M)"}`. (2) Estimate context size: collect the union of every card's `Context:` + `Edits:` + `Creates:` tokens for the batch (reuse `parse_batch_refs` for the batch file), resolve each via `resolve_existing_paths(...)` (skip tokens that do not resolve — Creates: targets do not exist yet), sum the byte size (`Path.stat().st_size`) of the resolved files, divide by 4 for a token estimate, and if it exceeds `max_context_tokens` append a `batch-oversized` error whose message names the estimate and cap. A batch may produce at most one card-count error and one context-size error. Extend `run()`'s signature with keyword-only `max_cards_per_batch: int = 10` and `max_batch_context_tokens: int = 120000`, and call `_check_batch_oversized` with them. In `millpy-review-plan.py`, change the `validate_run(...)` call to pass `max_cards_per_batch=cfg.get("pipeline", {}).get("max_cards_per_batch", 10)` and `max_batch_context_tokens=cfg.get("pipeline", {}).get("max_batch_context_tokens", 120000)`. Add tests to `test-plan-validate.py`: a batch exceeding the card cap flags `batch-oversized`; a batch whose resolved Context/Edits/Creates bytes exceed the token budget flags `batch-oversized`; a batch at/under both caps produces no `batch-oversized` error; the defaults apply when `run()` is called without the new kwargs.
- **Commit:** `feat(plan-validate): add batch-oversized check (#371)`

### Card 8: add out-of-worktree-target validator check

- **Context:**
  - `plugins/mill/scripts/_review_common.py`
- **Edits:**
  - `plugins/mill/scripts/_plan_validate.py`
  - `plugins/mill/unit_tests/test-plan-validate.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Add a `_check_out_of_worktree_target(batch_files, project_root)` helper to `_plan_validate.py` and call it from `run()`. For each batch file, collect every `Edits:` and `Creates:` token (reuse `_parse_edits_only` and a parallel `_parse_creates_only` — add the latter mirroring `_parse_edits_only` if it does not exist), skipping the literal `none`. For each token: expand `~` via `os.path.expanduser(token)`, build a candidate `Path`; if absolute use it directly, else `(project_root / token)`; resolve with `Path.resolve()` (non-strict — Creates: targets need not exist). Let `wt = project_root.resolve()`. Flag the token when the resolved path is neither `wt` itself nor has `wt` in its `.parents`, appending `{"check": "out-of-worktree-target", "batch": batch_path.stem, "card": None, "path": token, "message": "Edits/Creates target '<token>' resolves outside the worktree root; home-dir and absolute targets must be handled manually, not by the implementer"}`. Import `os` at module top if needed. Add tests to `test-plan-validate.py`: a `~/.claude/CLAUDE.md` token flags; an absolute path outside the tree flags; an in-tree relative `Edits:` path does not flag; an in-tree `Creates:` path that does not yet exist does not flag.
- **Commit:** `feat(plan-validate): reject out-of-worktree edit targets (#363)`

## Batch Tests

`verify:` runs `test-review-cli-error-envelope.py` (card 5 — uncaught-exception envelope)
and `test-plan-validate.py` (cards 7-8 — the two new checks). Card 6 is config-only and has
no test surface; it is exercised indirectly because card 7's default-kwargs test asserts the
10 / 120000 defaults that the config now mirrors. No real LLM is invoked.
