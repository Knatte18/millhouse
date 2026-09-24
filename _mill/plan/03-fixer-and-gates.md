# Batch: fixer-and-gates

```yaml
task: Remove batch review (plan-review.batch / code-review.batch)
batch: fixer-and-gates
number: 3
cards: 4
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-millpy-fix.py test-fix-finalize.py test-prior-blocking.py test-nit-gate.py test-language-skills-directive.py
depends-on: [2]
```

## Batch Scope

Removes the batch scope from the fixer CLI and the two helpers that read per-batch code-review files: the prior-BLOCKING digest (`_prior_blocking.py`) and the Handoff NIT gate (`_nit_gate.py`).
`millpy-fix.py --scope` accepts only `holistic`; `--batch-name` and `fixer-batch-brief.md` are gone.
After this batch nothing outside `_review_common.py` references `_review_common.RE_BATCH`, so batch 4 can delete it.
The skill text that still calls `build_digest(..., scope=..., batch_name=...)` is rewritten in batch 6; the cached plugin copy is what this task's own orchestrator runs, so the interim mismatch never executes.

## Cards

### Card 7: Make the prior-BLOCKING digest holistic-only

- **Context:**
  - `plugins/mill/scripts/_review_common.py`
  - `plugins/mill/scripts/millpy-fix.py`
- **Edits:**
  - `plugins/mill/scripts/_prior_blocking.py`
  - `plugins/mill/unit_tests/test-prior-blocking.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  In `plugins/mill/scripts/_prior_blocking.py`, change `build_digest(reviews_dir: Path, scope: str, batch_name: str | None = None) -> str` to `build_digest(reviews_dir: Path) -> str`.
  Delete the two `assert` lines, the `RE_BATCH` classification and the per-scope file selection: the selected files are every file whose name matches `_review_common.RE_SIMPLE` with `type == "code"`, sorted.
  A leftover per-batch code-review file on disk (`<ts>-code-review-<batch>-r<N>.md`) is ignored.
  Update the function docstring (drop the `scope` / `batch_name` Args and the RE_BATCH convention comment) and the module docstring's `build_digest()` line.
  `millpy-fix.py` does not call `build_digest` (it only reads the digest file), so no caller changes in this card.

  In `plugins/mill/unit_tests/test-prior-blocking.py`, drop the `scope=` / `batch_name=` arguments from every `build_digest` call and delete the batch-scope cases.
  Rewrite the case that mixed holistic and per-batch files so it asserts a per-batch-named file's BLOCKING headings are no longer included in the digest.
- **Commit:** `refactor(prior-blocking): scan holistic code reviews only`

### Card 8: Make the Handoff NIT gate holistic-only

- **Context:**
  - `plugins/mill/scripts/_review_common.py`
  - `plugins/mill/scripts/_status.py`
- **Edits:**
  - `plugins/mill/scripts/_nit_gate.py`
  - `plugins/mill/unit_tests/test-nit-gate.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  In `plugins/mill/scripts/_nit_gate.py`:
  - `compute_unfixed_nits`: the only approved scope is `holistic`, taken from a `holistic-approved` timeline row.
    `approved-<batch>` rows are still written by mill-go but no longer create a gate scope; delete the `phase.startswith("approved-")` branch.
    Keep the `nits-fixed-<scope>` marker scan unchanged (it still reads `nits-fixed-holistic`).
  - `_find_final_code_review(reviews_dir: Path, scope: str)` becomes `_find_final_code_review(reviews_dir: Path)`: delete the `RE_BATCH` branch and keep the `RE_SIMPLE` / `type == "code"` match.
  - Update the module and function docstrings to describe the holistic-only gate.

  In `plugins/mill/unit_tests/test-nit-gate.py`:
  - Delete the per-batch-only cases (per-batch review with/without a `nits-fixed-<batch>` marker, latest-of-two per-batch reviews, the combined per-batch-and-holistic case).
  - Rewrite the cases that test NIT counting through a per-batch file — the classed `[NIT:<class>]` heading cases and the marker-before-approval ordering case — to use a holistic `<ts>-code-review-r<N>.md` file with `holistic-approved` / `nits-fixed-holistic` rows, so that coverage stays.
  - Add a case: a timeline with `approved-01-alpha` and `holistic-approved` rows and no `nits-fixed-*` rows, a leftover `<ts>-code-review-01-alpha-r1.md` file with NITs, and a holistic `<ts>-code-review-r1.md` with NITs; `compute_unfixed_nits` returns exactly `["holistic"]`.
  - Update the file's module docstring (it says "Per-batch and holistic scopes handled together").
- **Commit:** `refactor(nit-gate): gate on the holistic code review only`

### Card 9: Restrict millpy-fix.py to the holistic scope

- **Context:**
  - `plugins/mill/scripts/_plan_dag.py`
  - `plugins/mill/scripts/_status.py`
  - `plugins/mill/templates/fixer-holistic-brief.md`
- **Edits:**
  - `plugins/mill/scripts/millpy-fix.py`
- **Creates:** none
- **Deletes:**
  - `plugins/mill/templates/fixer-batch-brief.md`
- **Moves:** none
- **Requirements:**
  In `plugins/mill/scripts/millpy-fix.py`:
  - `--scope`: `choices=["holistic"]`, still `required=True`; help text "Fix scope (only 'holistic' is supported)."
  - Delete the `--batch-name` argument and both validation blocks that check it against `--scope`.
  - Finalize stage: delete the `if args.scope == "batch":` arm; the former `elif args.scope == "holistic":` body runs unconditionally.
    Keep `cwd_override` / `verify_cmd` / `batch_verify_baseline` initialised before it.
    `nits_scope` becomes the literal `"holistic"`.
    Update the comment above `verify_cmd = None` that talks about "the batch-scope read below".
  - Prepare/full stages: delete the `if args.scope == "batch":` per-batch dispatch arm (the `set_batch_fields` state `fixing` write, the `fixing-<batch>-r<N>` phase append, its commit/push, and the `fixer-batch-brief.md` render); the former `else:` holistic body runs unconditionally.
  - `scope_label` in the prepare stage and `nits_scope` in the full stage become the literal `"holistic"`.
  - The fixer-tier advisory warning keeps reading `roles.code-review.<args.scope>.reviewer`; `args.scope` is always `holistic` now, so no change beyond what the parser enforces.
  - Update the module docstring's flag list: `--scope {holistic}` and no `--batch-name` entry; drop "Supports both per-batch and holistic scopes."
  - Remove imports left without a reference after the deletions (check each with a search of the file).

  Delete `plugins/mill/templates/fixer-batch-brief.md`.
- **Commit:** `refactor(fix): accept only --scope holistic and drop --batch-name`

### Card 10: Update fixer tests for the holistic-only CLI

- **Context:**
  - `plugins/mill/scripts/millpy-fix.py`
  - `plugins/mill/scripts/_plan_dag.py`
  - `plugins/mill/scripts/_agent_dispatch.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-millpy-fix.py`
  - `plugins/mill/unit_tests/test-fix-finalize.py`
  - `plugins/mill/unit_tests/test-language-skills-directive.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  In `plugins/mill/unit_tests/test-millpy-fix.py`:
  - Delete every case that invokes `--scope batch` / `--batch-name`, and the `fixer-batch-brief.md` template-content test.
    Before deleting a batch-scope case, check whether a holistic case already asserts the same behaviour (e.g. the fixer-tier warning, `--nits-only` carve-out rendering, `--prior-blocking` rendering, the brief-size cap); when none does, rewrite the case with `--scope holistic`.
  - Add a case: argparse rejects `--scope batch` (non-zero exit / `SystemExit`, stderr names the invalid choice).
  - Add a case: argparse rejects `--batch-name` as an unrecognised argument.

  In `plugins/mill/unit_tests/test-fix-finalize.py`:
  - Delete Test 6 (`--scope batch` forwards `batch_verify_baseline`); Test 7 already covers baseline forwarding for the holistic scope.
  - Rewrite Test 5 (nested-layout verify `cwd_override` threading at the finalize stage) against `--scope holistic`: drop `--batch-name`, mock `_plan_dag.iter_batch_verifies` to return one `(batch_name, command, cwd)` triple whose cwd is the nested hub, and keep the assertion that `finalize_from_output` receives `cwd_override == nested_hub`.
    Keep Test 5 even though Test 7 exists, because Test 7 does not assert `cwd_override`.

  In `plugins/mill/unit_tests/test-language-skills-directive.py`, delete the case that renders `fixer-batch-brief.md` (the template no longer exists); keep the holistic-brief and implementer-brief cases.
- **Commit:** `test(fix): cover the holistic-only fixer CLI`

## Batch Tests

`verify:` runs `test-millpy-fix.py` and `test-fix-finalize.py` (fixer CLI, both stages), `test-prior-blocking.py`, `test-nit-gate.py`, and `test-language-skills-directive.py` (catches a render of the deleted `fixer-batch-brief.md`).
