# Batch: plan-validate-fixes

```yaml
task: '_plan_validate.py: subprocess trace noise, batch-oversized TDD cap, unrelated-test-file and fence-unaware parser bugs'
batch: plan-validate-fixes
number: 1
cards: 5
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-subprocess-util.py
depends-on: []
```

## Batch Scope

Implements all four source-code fixes from `_mill/discussion.md`'s Decisions, entirely within `plugins/mill/scripts/_plan_validate.py` and `plugins/mill/scripts/_subprocess_util.py`. No test file other than `test-subprocess-util.py` (small) is touched here — every `test-plan-validate.py` change is deferred to batch `plan-validate-tests`, per the overview's `source-edits and test-edits must stay in separate batches` Shared Decision (the combined byte estimate of `_plan_validate.py` + `test-plan-validate.py` exceeds `pipeline.max_batch_context_tokens` under the currently-installed validator). This batch's own `verify:` therefore only re-runs `test-subprocess-util.py` (the one test file it does touch); the other three fixes are verified in the dependent batch once their new tests land.

## Cards

### Card 1: `_subprocess_util.run` quiet_nonzero flag + check-ignore call site (#1040)

- **Context:** none
- **Edits:**
  - `plugins/mill/scripts/_subprocess_util.py`
  - `plugins/mill/scripts/_plan_validate.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Add a keyword-only parameter `quiet_nonzero: bool = False` to `_subprocess_util.run`'s signature (currently `run(argv, *, cwd=None, input=None, check=False, timeout=None, env=None, stdout=None, stderr=None)`), inserted after `stderr=None`. The function's existing non-zero-exit breadcrumb block reads `if proc.returncode != 0:` followed by two `print(..., file=sys.stderr)` calls (the spawn-argv breadcrumb, then the exit-code/duration breadcrumb) — change only that condition, to `if proc.returncode != 0 and not quiet_nonzero:`; leave both `print` calls' own bodies untouched. Do NOT change the timeout-path breadcrumbs (the `except subprocess.TimeoutExpired` branch's two `print(...)` calls) or the `Popen`-raised-exception breadcrumbs (the `except Exception as exc:` branch immediately after the `subprocess.Popen(...)` call) — both stay unconditional; only the plain non-zero-return-code breadcrumb is gated by `quiet_nonzero`. Add one line to the function's `Args:` docstring section documenting `quiet_nonzero`: state that it suppresses the spawn/exit breadcrumb on a plain non-zero exit, for a call site where non-zero is a known routine outcome rather than an error (name `git check-ignore`'s "not ignored" result as the motivating example), and that timeout/Popen-raise breadcrumbs are unaffected. In `_plan_validate.py`, update the sole `_subprocess_util.run(...)` call inside `_is_confirmed_git_ignored` — the one invoking `git -C <source_root> check-ignore -q <candidate>` via a single positional `argv` list argument, with no other keyword arguments today — to also pass `quiet_nonzero=True` on that same call. Update `_is_confirmed_git_ignored`'s docstring where it currently states that the function runs `git -C <source_root> check-ignore -q <candidate>` and treats returncode 0 as ignored, to note the call now passes `quiet_nonzero=True` because exit 1 ("not ignored") is this probe's own routine, non-error outcome.
- **Commit:** `fix(plan-validate): suppress subprocess breadcrumb on routine check-ignore exit 1 (#1040)`

### Card 2: fence-delimiter indentation tolerance, three call sites (#992)

- **Context:** none
- **Edits:**
  - `plugins/mill/scripts/_plan_validate.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** In three places in this file, a line consisting of a run of three backtick characters (optionally followed by a language tag, e.g. a fence-opening line) toggles a boolean `in_fence` via a statement shaped `if line.startswith(<three-backtick-prefix>): in_fence = not in_fence`. In all three places, change the condition so it tolerates leading whitespace before that three-backtick run — i.e. test `line.lstrip()`'s prefix instead of `line`'s own prefix — leaving the assignment body (`in_fence = not in_fence`) and every other line unchanged:
  1. `_parse_cards` — its per-line loop's final such statement (card-boundary detection).
  2. `_requirements_fence_aware_body` — the identical statement inside its forward `while j < len(card_lines):` walk (Requirements: field body extraction).
  3. `_check_context_completeness`'s Requirements: token scan — the identical statement inside its `for line in requirements_lines:` loop, immediately following the `line_is_quoted = in_fence or line.lstrip().startswith(">")` computation (note this sibling line already strips leading whitespace before checking its own prefix — the fence check should match that same convention).
  This closes a gap left by the already-merged `#776` fix (commit `101a4897`): a `Requirements:` field's fenced code block is conventionally written as an indented list sub-bullet (e.g. a fence-opening line at 2-space indent under `- **Requirements:**`), while `requirements-quote-indent-drift`'s byte-exact-substring matching can force the fence's *content* (not its delimiter lines) to column 0 so it matches the quoted source file's own indentation — the indented delimiter line never matched the old unindented prefix check, so `in_fence` never went `True`, and a column-0 heading or field-header-shaped line inside such a fence was wrongly read as a real card/field boundary. Update `_parse_cards`'s docstring, which currently describes the toggle as matching "lines starting with" the three-backtick run, to note the match now tolerates leading whitespace.
- **Commit:** `fix(plan-validate): tolerate indented fence delimiters in card/field parsing (#992)`

### Card 3: naming-convention exemption for verify-unrelated-test-file (#999)

- **Context:** none
- **Edits:**
  - `plugins/mill/scripts/_plan_validate.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** In `_check_verify_unrelated_test_files`, immediately after the existing line `touched_basenames = {Path(t).name for t in touched}` and before the `for token in candidates:` loop, add a second derived set, `derived_test_basenames`, built from the same `touched` set: for each path in `touched` whose basename ends in `.py` and does NOT already start with `test-`, derive `"test-" + Path(t).stem.lstrip("_").replace("_", "-") + ".py"` and add it; for each path in `touched` whose basename ends in `.go` and does NOT already end in `_test.go`, derive `Path(t).stem + "_test.go"` and add it. (A touched path that is itself already test-named per either convention contributes no derived name — derivation is source-to-test only, one direction.) In the `for token in candidates:` loop, change the existing exemption line `if Path(token).name in touched_basenames: continue` so a token is also skipped when its basename is in `derived_test_basenames` — either widen the same condition with `or` or add a second early-`continue` check, whichever reads more clearly against the surrounding code. Add one sentence to the function's docstring describing the new exemption: a `--only` token naming the convention-derived test file for one of the batch's own touched source files (Python `test-<stem>.py` for `<stem>.py`, stripping any leading underscore and converting remaining underscores to hyphens; Go `<stem>_test.go` for `<stem>.go`) is exempt exactly like a directly-touched test file. Do not otherwise change this function's control flow, its other docstring content, or its return shape.
- **Commit:** `fix(plan-validate): exempt convention-named test files from verify-unrelated-test-file (#999)`

### Card 4: batch-oversized context-size sub-check evaluated per card (#1000)

- **Context:**
  - `plugins/mill/scripts/_review_common.py`
- **Edits:**
  - `plugins/mill/scripts/_plan_validate.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Add three new card-scoped helper functions immediately after `_card_creates_tokens`, mirroring that function's and `_card_edits_tokens`'s existing shape (same inline-vs-multi-line-sub-bullet walk via `_RE_REFS_HEADER`/`_RE_REFS_SUB`, same backtick-delimited-token regex extraction already used by both existing functions):
  - `_card_context_tokens(card_text: str) -> list[str]` — identical to `_card_creates_tokens` but scoped to the `"Context"` field.
  - `_card_deletes_tokens(card_text: str) -> list[str]` — identical shape, scoped to the `"Deletes"` field.
  - `_card_moves_tokens(card_text: str) -> list[tuple[str, str]]` — mirrors the module-level `_RE_MOVES_HEADER`/`_RE_MOVE_PAIR` inline-vs-multi-line-sub-bullet walk (both regexes already defined in this file), scoped to one card's `card_lines`/`card_text`; skip a sub-bullet that does not match `_RE_MOVE_PAIR` (malformed-`Moves:` reporting stays `move-format`'s job).
  Then restructure `_check_batch_oversized`'s "Check 2: context size" block. It currently builds one whole-batch `context_tokens` set via `parse_batch_refs(batch_path)` (a `plugins/mill/scripts/_review_common.py` import, already visible in this card's own `Context:`), `_parse_deletes_only(batch_path)`, and `parse_moves(batch_path)` (also a `_review_common.py` import), resolves existing paths, sums bytes, divides by 4, and appends at most one `batch-oversized` error per batch with `"card": None`. Replace this with a loop over the `cards` list this same function already computes earlier (`cards = _parse_cards(text)`, immediately followed by `card_count = len(cards)` — reuse this exact call; do not re-parse the batch text a second time). For each `(card_num, card_lines)` pair: join `card_lines` into `card_text = "\n".join(card_lines)`; call the three new helpers above plus the existing `_card_edits_tokens`/`_card_creates_tokens` to build that card's own token set as `(context ∪ edits ∪ creates - deletes - move_targets) | move_sources` (identical set algebra to today's whole-batch version, now card-scoped); resolve existing paths via `resolve_existing_paths(list(card_tokens), project_root, root, wiki_root=wiki_root, git_root=git_root)` (same keyword arguments the current whole-batch call already uses); sum the resolved paths' byte sizes and divide by 4 for the token estimate; when the estimate exceeds `max_context_tokens`, append one `batch-oversized` error with `"card": card_num` (not `None`) and `"message": f"card {card_num} context ~{token_estimate} tokens (cap {max_context_tokens})"` (same message shape as today, "card N" substituted for "batch"). Leave "Check 1: card count" (the `if card_count > max_cards:` block immediately above) completely unchanged — it stays batch-level. Update the "Check 10 — batch-oversized" comment header immediately above the function to note Check 2 is now evaluated per card rather than per batch. The file's own top-of-file module docstring has no dedicated `batch-oversized` bullet under "Checks performed" to update (that check is named only in `run()`'s own docstring, as a plain prose mention in its checks-summary line, and in its `Args:` section's `max_cards_per_batch`/`max_batch_context_tokens` descriptions) — update those two `Args:` lines instead, so each states its cap applies per card for the context-token estimate (card count itself stays batch-level, per `max_cards_per_batch`'s own unchanged meaning).
- **Commit:** `fix(plan-validate): evaluate batch-oversized context-size cap per card (#1000)`

### Card 5: quiet_nonzero regression test in test-subprocess-util.py

- **Context:**
  - `plugins/mill/scripts/_subprocess_util.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-subprocess-util.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** This test file's `main()` already contains lettered cases up through `(r)` (the last is `# (r) scrub_env() with no argument reads live os.environ`, ending just before the `if failures:` block). Add a new case `(s)` immediately after `(r)` and before that `if failures:` block: reuse case `(o)`'s exact non-zero-exit invocation shape (`run([sys.executable, "-c", "import sys; sys.exit(7)"], check=False)`) but add `quiet_nonzero=True`, capture stderr the same way `(o)` does (`io.StringIO()` + `contextlib.redirect_stderr`), and assert that NEITHER `"[subprocess] spawn argv="` NOR `"[subprocess] exit code="` appears in the captured stderr — the mirror image of `(o)`'s own two `in stderr_out` assertions, now `not in`. On success print `"PASS (s): quiet_nonzero=True suppresses both breadcrumbs on non-zero exit"`; on `AssertionError`, append `f"FAIL (s) quiet-nonzero-silence: {exc}"` to `failures`, following the exact same `try`/`except AssertionError as exc:` structure every other lettered case in this file already uses. Do not modify case `(o)` or any other existing case.
- **Commit:** `test(subprocess-util): cover quiet_nonzero breadcrumb suppression (#1040)`

## Batch Tests

`verify:` runs `test-subprocess-util.py` only (card 5's own new test plus the full existing suite in that file, confirming card 1's `_subprocess_util.run` change doesn't regress the other lettered cases — most directly `(n)`/`(o)`, which assert the unchanged default (`quiet_nonzero=False`) breadcrumb behavior). Cards 2-4 (the `_parse_cards`/`_requirements_fence_aware_body`/context-completeness fence fix, the naming-convention exemption, and the per-card batch-oversized restructure) have no test coverage in this batch by design — `test-plan-validate.py` cannot be touched here without exceeding the batch context-token cap (see Batch Scope above); their tests land in the dependent `plan-validate-tests` batch, whose own `verify:` runs the full `test-plan-validate.py` file once those tests exist alongside the already-implemented source changes from this batch.
