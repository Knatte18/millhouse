# Batch: drift-guard-and-millstart-fix

```yaml
task: Fix drift-guard false positive and mill-start missing task body/brief
batch: drift-guard-and-millstart-fix
number: 1
cards: 3
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-skill-helper-drift.py
depends-on: []
```

## Batch Scope

This batch delivers both fixes for this task in one unit. Card 1 edits `mill-start/SKILL.md`
so the skill surfaces the wiki task's `body`/`brief` during Phase: Select and Phase: Explore.
Cards 2 and 3 edit `test-skill-helper-drift.py`: Card 2 fixes the #576 false-positive regex and
empties the now-dead `ALLOWLIST`; Card 3 adds focused extract-unit assertions wired into
`main()` and a regression lock asserting the Card-1 SKILL edit is present. The three cards are
one batch because Card 3's regression lock checks substrings that Card 1 writes — they must land
together for the batch `verify:` (the full drift-test file) to pass. No external interface is
produced for a later batch; this is the only batch.

## Cards

### Card 1: mill-start surfaces task body/brief

- **Context:**
  - `plugins/mill/scripts/wiki/_client.py`
  - `plugins/mill/scripts/wiki/_store.py`
- **Edits:**
  - `plugins/mill/skills/mill-start/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** In the `### Phase: Select` bash snippet, change the final `print` so `status`
  prints on its own first line as `print('STATUS:', task.get('status', ''))`, and AFTER it emit
  the summary and proposal under labeled sentinel delimiter lines — print a line `--- BRIEF ---`
  then `task.get('brief', '')`, then a line `--- BODY ---` then `task.get('body', '')`. State in
  the surrounding prose that the "status must be `active`" gate parses only the `STATUS:` first
  line, so a multi-line `body` cannot break the gate. In `### Phase: Explore`, add an explicit
  instruction that the agent re-calls `_client.get_task(wiki_path, slug)` itself (each Bash call
  is a fresh subprocess, so the `task` variable from Phase: Select does not persist) and reads
  the proposal from `task['body']` and the one-paragraph summary from `task['brief']` BEFORE
  exploring code. Add a documentation line naming the exact keys in subscript form — the literal
  strings `task['body']` and `task['brief']` (NOT `summary`/`proposal`) — and list the full
  observed `get_task()` key set: `body, brief, deferred, depends_on, id, isolated, slug, status,
  title` (this set is grounded in the task document shape assembled in `wiki/_store.py` — see the
  `"brief"`/`"body"` defaults and the `depends_on`/`isolated`/`deferred` validation there).
  Note the empty fallback: if both `body` and `brief` are empty/`None`, fall back to
  deriving scope from code, but only after confirming those exact fields are empty. Keep all
  added text ASCII-only.
- **Commit:** `fix(mill-start): surface task body/brief during Select and Explore`

### Card 2: guard drift regex against identifier-tail false positives

- **Context:**
  - `plugins/mill/skills/mill-go/SKILL.md`
- **Edits:**
  - `plugins/mill/unit_tests/test-skill-helper-drift.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** In `_extract_helper_references`, change the `pattern` to prepend a negative
  lookbehind so it reads
  `r"(?<![A-Za-z0-9_])_([a-zA-Z_][a-zA-Z0-9_]*)\.([a-zA-Z_][a-zA-Z0-9_]*)\("`. Update that
  function's docstring to note the lookbehind requires the leading `_` to be preceded by a
  non-identifier character, so the `_cmd` tail of `gate_cmd.lower()` (in `mill-go/SKILL.md:738`)
  is no longer mis-extracted as a `_cmd` module reference. Replace the populated `ALLOWLIST`
  assignment with an empty set — `ALLOWLIST: set[tuple[str, str]] = set()` — keeping the symbol
  and the `if (module_stem, fn) in ALLOWLIST` guard in `_run_drift_guard` unchanged. Update the
  `ALLOWLIST` comment to explain that the lookbehind now handles every former identifier-tail
  exemption, so the set is intentionally empty and reserved only for future true
  module-qualified (`_module.func(`) exemptions.
- **Commit:** `fix(tests): guard helper-drift regex against identifier-tail false positives`

### Card 3: add extract-unit checks and mill-start body/brief lock

- **Context:**
  - `plugins/mill/skills/mill-start/SKILL.md`
- **Edits:**
  - `plugins/mill/unit_tests/test-skill-helper-drift.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Add a new function `_run_extract_unit_checks() -> list[str]` that returns a
  list of `FAIL:` messages (empty list = pass), asserting two cases: the negative case
  `_extract_helper_references("gate_cmd.lower()") == []` and the positive case
  `_extract_helper_references("_paths.resolve_git_root()") == [("paths", "resolve_git_root")]`.
  Invoke it from `main()` as a third check group (print a `--- Card 3: Extract-unit checks ---`
  header, run it, and on any returned failure print each message to stderr and `return 1` — same
  exit-gating shape as `_run_drift_guard` and `_run_regression_locks`). In
  `_run_regression_locks`, add a lock that reads `SKILLS / "mill-start" / "SKILL.md"` and appends
  a `FAIL:` message unless the text contains BOTH literal substrings `task['body']` and
  `task['brief']`, so a future edit that drops the field-name guidance fails the suite. Also
  refresh the module header docstring (the top-of-file `"""..."""`, currently enumerating only
  "Card 1: Drift-guard scan" and "Card 2: Regression locks") to add a line for the new
  extract-unit checks and the mill-start `body`/`brief` regression lock, so the docstring stays
  in sync with `main()`'s check groups. Keep all added strings ASCII-only.
- **Commit:** `test(drift): add extract-unit checks and mill-start body/brief lock`

## Batch Tests

`verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-skill-helper-drift.py`
runs the single test file this batch edits. It covers all three cards: Card 2's regex fix makes
Card 1 of the file's existing drift scan pass on clean state (no `unresolved module 'cmd'`);
Card 3's new `_run_extract_unit_checks()` asserts the regex behaviour directly (negative +
positive case); and Card 3's regression lock confirms Card 1's SKILL edit is present. Scope is a
single file, not `run-all.py`, because nothing outside this test file is touched.
