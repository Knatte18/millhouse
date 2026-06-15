# Batch: review-plan-cli

```yaml
task: Fix millpy-review-plan validator gaps and resolve_ref_paths path-doubling
batch: review-plan-cli
number: 3
cards: 3
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-review-plan-flow.py
depends-on: [2]
```

## Batch Scope

Wires the validator correctly in `millpy-review-plan.py`: (#466) threads `git_root` + overview `root` into the existing `--stage full` validator call so its source-ref checks match the three-roots model; (#465) runs the validator gate inside `--stage prepare` so agent-mode dispatch can no longer silently skip it, emitting the same `errors`/`summary` envelope on findings. Depends on batch 2 because both cards pass `git_root` into `_plan_validate.run`, which requires the new `git_root` parameter. External interface the SKILL (batch 4) consumes: the new `--stage prepare` validator-failure envelope `{"errors":[...],"summary":...}` (exit 1), distinct from the prepare-success envelope `{"stage":"prepare","brief_path":...}` (exit 0). Batch-local decision: the prepare branch must independently derive `plan_dir` and `root` (it does not today) by mirroring the `--stage full` branch.

## Cards

### Card 6: thread git_root + root into --stage full validator

- **Context:**
  - `plugins/mill/scripts/_review_common.py`
  - `plugins/mill/scripts/_plan_validate.py`
- **Edits:**
  - `plugins/mill/scripts/millpy-review-plan.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** In the `--stage full` branch of `millpy-review-plan.py` (the `else:` branch, validator call at `millpy-review-plan.py:186`), pass `git_root=git_root` and `root=<overview root>` into the `validate_run(...)` call. Derive the overview root with `_load_root_from_overview(plan_dir / "00-overview.md")`. Import `_load_root_from_overview` by APPENDING it to the existing `from _review_common import ReviewError, find_active_slug, load_config, resolve_path` block at `millpy-review-plan.py:98` (one import line, alphabetical order preserved) — do not add a second `from _review_common import` line. `_load_root_from_overview` is defined at `_review_common.py:730`. `plan_dir` is already computed via `resolve_path(cfg["paths"]["plan_dir"], slug)` immediately above — reuse it; do NOT change how `plan_dir` is resolved. `git_root` is already available in `main()` (`millpy-review-plan.py:103`). Leave the rest of the call (`wiki_root`, `skip_checks`, `max_cards_per_batch`, `max_batch_context_tokens`) and the errors-envelope emission unchanged.
- **Commit:** `fix(review-plan): pass git_root and root into full-stage validator`

### Card 7: run validator gate in --stage prepare

- **Context:**
  - `plugins/mill/scripts/_review_common.py`
  - `plugins/mill/scripts/_plan_validate.py`
  - `plugins/mill/scripts/_agent_dispatch.py`
- **Edits:**
  - `plugins/mill/scripts/millpy-review-plan.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** In the `--stage prepare` branch of `millpy-review-plan.py` (`millpy-review-plan.py:124`), add the pre-review validator gate BEFORE the `prepare(...)`/`write_brief(...)` call, gated on `if not args.skip_validate:`. Mirror the `--stage full` branch (after card 6): compute `plan_dir = resolve_path(cfg["paths"]["plan_dir"], slug)`, `root = _load_root_from_overview(plan_dir / "00-overview.md")`, then call `_plan_validate.run(plan_dir, project_root, root=root, git_root=git_root, wiki_root=wiki_root, skip_checks=frozenset(args.skip_checks), max_cards_per_batch=cfg.get("pipeline", {}).get("max_cards_per_batch", 10), max_batch_context_tokens=cfg.get("pipeline", {}).get("max_batch_context_tokens", 120000))`. If it returns errors, print the SAME envelope shape the full branch uses — `json.dumps({"errors": errors, "summary": f"{n} finding(s) across {m} batch(es)"})` where `n = len(errors)` and `m = len({e["batch"] for e in errors if e["batch"]})` — and `return 1` WITHOUT writing a brief. On no errors, fall through to the existing `prepare(...)` + `write_brief(...)` + prepare-envelope path unchanged. The prepare-success envelope (`{"stage":"prepare","brief_path":...}`) and validator-failure envelope (`{"errors":...,"summary":...}`) must be distinguishable by the presence of the `errors` key. Honor `args.skip_validate` and `args.skip_check` exactly as the full branch does.
- **Commit:** `fix(review-plan): run validator gate in prepare stage (agent mode)`

### Card 8: flow tests for prepare-stage validator gate

- **Context:**
  - `plugins/mill/scripts/millpy-review-plan.py`
  - `plugins/mill/scripts/_paths.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-review-plan-flow.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Add `--stage prepare` flow cases to `test-review-plan-flow.py`: (a) a plan containing a known validator error (e.g. a `non-existent-path` ref) — assert the prepare invocation exits 1, prints a JSON line containing the `errors` and `summary` keys, and writes NO brief file; (b) a clean plan — assert prepare exits 0, prints the prepare envelope containing `stage: "prepare"` and `brief_path`, and the brief file exists. The prepare-stage validator gate lives in `millpy-review-plan.py`'s `main()`, NOT in `_review_plan.run` (`plan_run`) — so these cases MUST invoke the CLI entry point `main(["--stage", "prepare", "--holistic-only"])` (import it as `from importlib import import_module` / `import_module("millpy-review-plan")` is not valid due to the hyphen; instead exec/`runpy` the script or add a thin import shim — the implementer picks the mechanism the harness already uses for hyphenated CLIs, or invokes via `subprocess` running the actual script). Reuse `_make_plan_fixture` + `os.chdir(project_root)` as the other cases do. Because `main()` calls `_paths.resolve_git_root()` and `resolve_hub_path()` (unlike `plan_run`, which receives `git_root` explicitly), the test must satisfy those — either `git init` the fixture `project_root` or monkeypatch `_paths.resolve_git_root` / `resolve_hub_path` / `resolve_wiki_path` to return the fixture paths. Capture stdout (the JSON envelope line) and the process/`main` return code. Do NOT reuse the `plan_run` harness for these two cases — it would exercise the `--stage full` backend and miss the prepare gate entirely (the #465 surface).
- **Commit:** `test(review-plan): cover prepare-stage validator gate envelopes`

## Batch Tests

`verify:` runs `test-review-plan-flow.py` only. Card 8 proves both #465 outcomes: the gate fires in prepare (error → envelope + no brief) and stays out of the way on a clean plan (brief written). Scope is the single review-plan flow test file; per-batch scoping is correct, no cross-cutting helper touched.
