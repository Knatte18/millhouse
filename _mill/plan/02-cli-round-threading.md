# Batch: cli-round-threading

```yaml
task: 'millpy-review-plan finalize: usage-error indistinguishability, flag issues, verdict rendering stale'
batch: cli-round-threading
number: 2
cards: 5
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-review-cli-error-envelope.py test-review-plan-finalize-round.py
depends-on: [1]
```

## Rename mechanic

N/A — no `Moves:` in this batch.

## Batch Scope

Thread a `round=` argument through every `print_error_envelope` call site in all three review
CLIs' `main()` functions (`millpy-review-plan.py`, `millpy-review-discussion.py`,
`millpy-review-code.py`), using Batch 1's new parameter. Two threading rules, chosen per call
site by whether an already-resolved `round_n` local is in scope at that point in the control flow
(see each card's Requirements for the exact per-site rule): every site *except* the finalize-stage
outer `except ReviewError` catch passes `args.round if args.round is not None else 0`; the
finalize-stage outer catch in `millpy-review-plan.py` and `millpy-review-discussion.py` passes the
already-resolved `round_n` local instead (never raw `args.round`) because `round_n` may have been
computed via `discover_round` when `--round` was omitted, and using raw `args.round` there would
silently discard that disk-discovered value. `millpy-review-code.py`'s finalize stage requires
`--round` explicitly (it already errors out before its try block if absent), so `args.round` is
the only value in scope there — no `round_n`-vs-`args.round` distinction applies to that file's
outer catch.

All three CLIs are grouped in one batch (rather than three) because the fix is the mechanically
identical threading rule applied to the mechanically identical call-site shape in each file, and
the regression tests for all three naturally share the same two existing test files
(`test-review-cli-error-envelope.py`, `test-review-plan-finalize-round.py`) — splitting into
per-CLI batches would force three batches to edit the same two shared test files in parallel with
no dependency edge between them, which the `parallel-modifies-overlap` check would (correctly)
reject.

No `error_kind` argument is passed at any call site in this batch — every site here defaults to
`error_kind="usage"` per the overview's "error_kind defaulting" Shared Decision, since every one of
these sites is a pre-reviewer usage error.

## Cards

### Card 3: thread `round=` through every `print_error_envelope` call site in `millpy-review-plan.py`

- **Context:**
  - `plugins/mill/scripts/_review_cli.py`
- **Edits:**
  - `plugins/mill/scripts/millpy-review-plan.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  - In the `except (ReviewError, ValueError, SystemExit) as exc:` block wrapping the `project_root`/`git_root`/`mill_dir`/`wiki_root`/`cfg` resolution (the first `print_error_envelope("plan", str(exc))` call in `main()`), change the call to `print_error_envelope("plan", str(exc), round=args.round if args.round is not None else 0)`.
  - Apply the identical `round=args.round if args.round is not None else 0` change to the `print_error_envelope("plan", str(exc))` call in the `except _reviewers.ReviewerError as exc:` block (registry load/validation).
  - Apply the identical change to the `print_error_envelope("plan", str(exc))` call in the `except ReviewError as exc:` block around `slug = args.slug or find_active_slug(...)`.
  - Apply the identical change to the `print_error_envelope("plan", str(exc))` call in the prepare stage's `except ReviewError as exc:` block (inside `if args.stage == "prepare":`).
  - Apply the identical change to the `print_error_envelope("plan", f"unhandled review error: {exc}")` call in the prepare stage's `except Exception as exc:` block.
  - Apply the identical change to the `print_error_envelope("plan", "--agent-output required for finalize stage")` call at the top of `elif args.stage == "finalize":` (the `if not args.agent_output:` guard).
  - In the finalize stage's `except ReviewError as exc:` block (the one wrapping the call to `finalize(...)`, i.e. the outer catch after `round_n` has already been resolved via the `if round_n is None: round_n = discover_round(...)` fallback earlier in the same `elif` branch), change `print_error_envelope("plan", str(exc))` to `print_error_envelope("plan", str(exc), round=round_n)` — use the already-resolved `round_n` local, not `args.round`.
  - Apply the `round=args.round if args.round is not None else 0` change to both `print_error_envelope` calls in the `else:  # full` branch (the `except ReviewError as exc:` call and the `except Exception as exc:` call with the `f"unhandled review error: {exc}"` message).
  - Every `print_error_envelope` call site in this file must be covered — grep the file for `print_error_envelope(` after editing and confirm every call passes a `round=` keyword argument.
  - Do not add an `error_kind=` argument at any site in this file.
- **Commit:** `fix(review-plan): thread round number through every print_error_envelope call site`

### Card 4: thread `round=` through every `print_error_envelope` call site in `millpy-review-discussion.py`

- **Context:**
  - `plugins/mill/scripts/_review_cli.py`
- **Edits:**
  - `plugins/mill/scripts/millpy-review-discussion.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  - In the `except (ReviewError, ValueError, SystemExit) as exc:` block wrapping `git_root`/`hub_dir`/`mill_dir`/`wiki_root`/`cfg`/`project_root` resolution, change `print_error_envelope("discussion", str(exc))` to `print_error_envelope("discussion", str(exc), round=args.round if args.round is not None else 0)`.
  - Apply the identical change to the `print_error_envelope("discussion", str(exc))` call in the `except _reviewers.ReviewerError as exc:` block.
  - Apply the identical change to the `print_error_envelope("discussion", str(exc))` call in the `except ReviewError as exc:` block around `slug = args.slug or find_active_slug(...)`.
  - Apply the identical change to the `print_error_envelope("discussion", str(exc))` call in the prepare stage's `except ReviewError as exc:` block.
  - Apply the identical change to the `print_error_envelope("discussion", "--agent-output required for finalize stage")` call at the top of `elif args.stage == "finalize":`.
  - In the finalize stage's `except ReviewError as exc:` block (the one wrapping the call to `finalize(...)`, after `round_n` has already been resolved via the `if round_n is None: round_n = discover_round(...)` fallback earlier in the same `elif` branch), change `print_error_envelope("discussion", str(exc))` to `print_error_envelope("discussion", str(exc), round=round_n)` — use the already-resolved `round_n` local, not `args.round`.
  - Apply the `round=args.round if args.round is not None else 0` change to the `print_error_envelope("discussion", str(exc))` call in the `else:  # full` branch.
  - Every `print_error_envelope` call site in this file must be covered — grep the file for `print_error_envelope(` after editing and confirm every call passes a `round=` keyword argument.
  - Do not add an `error_kind=` argument at any site in this file.
- **Commit:** `fix(review-discussion): thread round number through every print_error_envelope call site`

### Card 5: thread `round=` through every `print_error_envelope` call site in `millpy-review-code.py`

- **Context:**
  - `plugins/mill/scripts/_review_cli.py`
- **Edits:**
  - `plugins/mill/scripts/millpy-review-code.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  - In the `except (ReviewError, ValueError, SystemExit) as exc:` block wrapping `project_root`/`git_root`/`mill_dir`/`wiki_root`/`cfg` resolution, change `print_error_envelope("code", str(exc))` to `print_error_envelope("code", str(exc), round=args.round if args.round is not None else 0)`.
  - Apply the identical change to the `print_error_envelope("code", str(exc))` call in the `except _reviewers.ReviewerError as exc:` block.
  - Apply the identical change to the `print_error_envelope("code", f"--extra-file not found: {p}")` call inside the `for raw in args.extra_file:` loop.
  - Apply the identical change to the `print_error_envelope("code", str(exc))` call in the `except ReviewError as exc:` block around `slug = args.slug or find_active_slug(...)`.
  - Apply the identical change to the `print_error_envelope("code", str(exc))` call in the prepare stage's `except ReviewError as exc:` block.
  - Apply the identical change to the `print_error_envelope("code", "--agent-output required for finalize stage")` call at the top of `elif args.stage == "finalize":`.
  - In the same `elif args.stage == "finalize":` branch, the `print_error_envelope("code", "--round is required for finalize stage")` call (the `if args.round is None:` guard, which fires before `round_n`/`args.round` can be non-`None`) stays `round=0` (equivalently, apply `round=args.round if args.round is not None else 0`, which evaluates to `0` here since `args.round is None` is exactly the condition that triggered this branch) — do not hardcode a bare `0` literal; use the same coalescing expression as every other non-outer-catch site for consistency.
  - In the finalize stage's `except ReviewError as exc:` block (the one wrapping the call to `finalize(...)`), change `print_error_envelope("code", str(exc))` to `print_error_envelope("code", str(exc), round=args.round)` — use `args.round` directly, not the coalescing expression, since this file's finalize stage already requires `--round` explicitly (the preceding `if args.round is None:` guard above returns before this point is ever reached with `args.round is None`), so no `None`-fallback is needed or correct here.
  - Apply the `round=args.round if args.round is not None else 0` change to the `print_error_envelope("code", str(exc))` call in the `else:  # full` branch.
  - Every `print_error_envelope` call site in this file must be covered — grep the file for `print_error_envelope(` after editing and confirm every call passes a `round=` keyword argument.
  - Do not add an `error_kind=` argument at any site in this file.
- **Commit:** `fix(review-code): thread round number through every print_error_envelope call site`

### Card 6: assert round threading at each CLI's pre-launch usage-error sites

- **Context:**
  - `plugins/mill/scripts/millpy-review-plan.py`
  - `plugins/mill/scripts/millpy-review-discussion.py`
  - `plugins/mill/scripts/millpy-review-code.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-review-cli-error-envelope.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  - In `TestReviewCliErrorEnvelope._run_cli_test`, add a new optional parameter `round_arg: int | None = None`; when it is not `None`, append `["--round", str(round_arg)]` to the `argv` list that is built before the CLI module is invoked (after the existing `--skip-validate` handling for the `"plan"` CLI case — the append applies to all three `cli_name` values, not just `"plan"`).
  - Add a new test method `test_plan_pre_launch_error_includes_round` that calls `self._run_cli_test("plan", raise_find_slug=True, round_arg=7)` and asserts the parsed JSON envelope's `result["round"] == 7`.
  - Add a new test method `test_discussion_pre_launch_error_includes_round` that calls `self._run_cli_test("discussion", raise_find_slug=True, round_arg=7)` and asserts `result["round"] == 7`.
  - Add a new test method `test_code_pre_launch_error_includes_round` that calls `self._run_cli_test("code", raise_find_slug=True, round_arg=7)` and asserts `result["round"] == 7`.
  - All three new methods follow this file's existing `unittest.TestCase` style exactly (method naming, `self.assertEqual(...)` assertions with an explanatory message, no bare `assert`).
  - Do not modify any existing test method's behavior — the `round_arg` parameter must default to `None` and leave every existing `_run_cli_test` call site (which does not pass `round_arg`) producing the exact same `argv` it does today.
- **Commit:** `test(review-cli): assert --round threads through pre-launch usage-error envelopes`

### Card 7: dead-path unit tests for the finalize-stage outer `except ReviewError` round/error_kind threading

- **Context:**
  - `plugins/mill/scripts/millpy-review-plan.py`
  - `plugins/mill/scripts/millpy-review-discussion.py`
  - `plugins/mill/scripts/millpy-review-code.py`
  - `plugins/mill/scripts/_review_cli.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-review-plan-finalize-round.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  - This file already loads `millpy-review-plan.py` and `millpy-review-discussion.py` via `importlib` at module scope (see the existing `_plan_path`/`_plan_spec`/`millpy_review_plan` and `_disc_path`/`_disc_spec`/`millpy_review_discussion` blocks). Add an identical third block that loads `millpy-review-code.py` the same way, producing a module-level `millpy_review_code` object, mirroring the existing two blocks' variable-naming pattern exactly (`_code_path`, `_code_spec`, `millpy_review_code`).
  - Add a new test case (following this file's existing `try:`/`except Exception as exc:` per-case pattern inside `main()`, with its own `pass_count`/`fail_count` bookkeeping and a `print("[case] ...")` on success) named `review-plan-finalize-outer-catch-error-kind-usage`: reuse the same mocking pattern as the existing `review-plan-finalize-round-with-existing` case (same fixture via `_make_fixture`, same set of `unittest.mock.patch` context managers for `_paths.*`/`_review_common.*`/`_reviewers.*`), but mock `_review_plan.finalize` with `side_effect=ReviewError("boom")` instead of `return_value=stub_review_entry` (import `ReviewError` from `_review_common`, already imported at module scope in this file). Invoke `millpy_review_plan.main(["--stage", "finalize", "--agent-output", str(stub_out), "--round", "3"])` and assert: the return code is `1`; parsing stdout as JSON succeeds; the parsed envelope's `"round"] == 3`; and `envelope["reviews"][0]["error_kind"] == "usage"`.
  - Add an analogous test case `review-discussion-finalize-outer-catch-error-kind-usage` for `millpy_review_discussion`, mocking `_review_discussion.finalize` with `side_effect=ReviewError("boom")`, invoking with `["--stage", "finalize", "--agent-output", str(stub_out), "--round", "3"]`, and asserting the same three properties (`rc == 1`, `envelope["round"] == 3`, `envelope["reviews"][0]["error_kind"] == "usage"`).
  - Add an analogous test case `review-code-finalize-outer-catch-error-kind-usage` for the newly-loaded `millpy_review_code`, mocking `_review_code.finalize` with `side_effect=ReviewError("boom")`. `millpy-review-code.py`'s finalize stage requires `--round` explicitly, so invoke with `["--stage", "finalize", "--agent-output", str(stub_out), "--round", "3"]` and assert the same three properties (`rc == 1`, `envelope["round"] == 3`, `envelope["reviews"][0]["error_kind"] == "usage"`) — this exercises the `round=args.round` (not the coalescing form) threading rule Card 5 applied to this file's outer catch.
  - Add all three new case labels to the printed pass/fail summary the same way every existing case already is (the file's `main()` accumulates `pass_count`/`fail_count` across all cases and prints a final tally — no separate summary mechanism to add).
- **Commit:** `test(review-finalize): cover the outer except ReviewError round_n/error_kind dead path in all three CLIs`

## Batch Tests

`verify:` runs `test-review-cli-error-envelope.py` (Card 6's three new pre-launch round-assertion
methods plus the file's existing exit-code-contract tests) and `test-review-plan-finalize-round.py`
(Card 7's three new outer-catch dead-path cases plus the file's existing four round-auto-discovery
cases) via `run-all.py --only`, scoped to exactly the two files this batch's test cards touch.
