# Discussion: Fix drift-guard false positive and mill-start missing task body/brief

```yaml
task: Fix drift-guard false positive and mill-start missing task body/brief
slug: mill-skill-and-tooling-gaps
status: discussing
parent: main
```

## Problem

Two independent skill-and-tooling gaps, each backed by a closed GitHub issue, surfaced
during real task runs. Both are small, surgical fixes with no shared code.

1. **#576 — drift-guard false positive.** `plugins/mill/unit_tests/test-skill-helper-drift.py`
   fails on a clean `main` worktree. Its Card 1 "drift-guard scan" extracts helper
   references from every mill `SKILL.md` with the regex
   `_([a-zA-Z_][a-zA-Z0-9_]*)\.([a-zA-Z_][a-zA-Z0-9_]*)\(`. The regex has no left
   boundary, so it matches the `_cmd.lower(` substring inside `gate_cmd.lower()` — a plain
   Python local variable in the done-gate snippet of `mill-go/SKILL.md` (line 738) — and
   mis-reports it as a reference to a non-existent helper module `_cmd`. The suite then
   exits 1 on clean `main`, which poisons full-suite verification for every other task.

2. **#577 — mill-start never surfaces the proposal.** `mill-start`'s Phase: Select sample
   only reads `task.get('status')`, and nothing in the skill tells the agent to surface
   the task's full proposal. `_client.get_task()` returns the proposal in the **`body`**
   field and the one-paragraph summary in **`brief`** — NOT `summary`/`proposal`. An agent
   that improvises field names (the obvious wrong guess: `summary`/`proposal`) gets empty
   strings back and wrongly concludes "wiki proposal is empty, derive scope from code" —
   even when a detailed multi-section proposal exists in `body`. This happened on the
   `harden-path-invariant` task: a ~6KB proposal body was present but reported as empty.

**Why now:** #576 breaks full-suite verification on `main` for every task until fixed
(a false red that masks real regressions). #577 silently degrades every `mill-start`
session whose task carries a substantive proposal body — the design phase starts blind.

## Scope

**In:**

- Fix the helper-reference regex in `test-skill-helper-drift.py` so it only matches true
  module-qualified helper calls (`_module.func(`) and not the `_cmd` tail of an identifier
  like `gate_cmd`.
- Empty the now-dead `ALLOWLIST` set in the same file (every entry becomes unreachable once
  the lookbehind lands), keeping the symbol and its guard.
- Add focused regression coverage for the false-positive case (assert `gate_cmd.lower()`
  yields no extracted reference) plus a positive case, in a new `_run_extract_unit_checks()`
  ("Card 3") wired into `main()`.
- Edit `plugins/mill/skills/mill-start/SKILL.md` so Phase: Select fetches and surfaces
  `task['body']` and `task['brief']`, and Phase: Explore explicitly instructs the agent to
  read them — naming the exact schema field names so agents never guess.
- Add a lightweight regression lock (in the existing Card 2 of `test-skill-helper-drift.py`)
  asserting `mill-start/SKILL.md` references `task['body']` and `task['brief']`.

**Out:**

- The done-gate snippet in `mill-go/SKILL.md` is correct as written; `gate_cmd` is a
  legitimate local variable and is NOT renamed. The bug is in the test's regex, not the SKILL.
- No change to `_client.get_task()` or the wiki schema — the field names (`body`, `brief`)
  are already correct; only the consumer (`mill-start`) is at fault.
- No audit/change to other `get_task` consumers (`mill-go`, `mill-merge`, `mill-autofix`,
  `mill-ghissues-to-tasks`). A grep confirms only `mill-ghissues-to-tasks` reads a proposal
  field and it already uses the correct `task['body']`. The others do not read the proposal.
- No change to the cache copy under `~/.claude/plugins/cache/...` — the cache is regenerated
  from source on plugin update; the source edit is the fix.
- The two fixes share no code and could be separate batches/cards.

## Decisions

### drift-regex-left-boundary

- Decision: Add a negative lookbehind `(?<![A-Za-z0-9_])` immediately before the `_` in the
  helper-reference regex, giving
  `r"(?<![A-Za-z0-9_])_([a-zA-Z_][a-zA-Z0-9_]*)\.([a-zA-Z_][a-zA-Z0-9_]*)\("`.
- Rationale: A helper reference is always `_module.func(` where the `_` begins a fresh
  identifier — i.e. it is preceded by a non-identifier character (whitespace, `(`, `=`, `.`,
  start of line). The lookbehind excludes the `_cmd` tail of `gate_cmd` (preceded by `e`)
  while preserving every genuine `_paths.…(`, `_client.…(`, etc. Minimal, precise, one-line.
- Rejected: (a) Allowlisting `("cmd", "lower")` in `ALLOWLIST` — masks the real regex defect,
  leaves the door open for the next identifier ending in `_something`, and grows brittle.
  (b) Re-architecting the scan to AST-parse fenced Python code blocks — far more code for a
  one-character regex fix; SKILL.md prose is not reliably parseable as Python anyway.

### allowlist-prune-dead-entries

- Decision: After adding the lookbehind, **prune every current `ALLOWLIST` entry** and leave
  the declaration as an empty `set()` with an updated comment explaining it now exists only
  for true module-qualified exemptions (none currently needed). Do NOT delete the `ALLOWLIST`
  name or its membership check in `_run_drift_guard()` — only empty the set.
- Rationale: Every existing entry — `("block","get")` (from `env_block.get`),
  `("gap_titles","isdisjoint")` (from `current_gap_titles.isdisjoint`), `("ts_str","strip")`,
  and all the `("path",…)` / `("dir",…)` entries — is an **identifier-tail** match: the
  underscore is preceded by an identifier character, so the lookbehind now stops the regex
  from ever extracting them. They become unreachable dead code that misleads the next editor.
  Pruning to an empty set (rather than leaving stale exemptions) keeps the exemption list
  honest; keeping the declaration avoids a `NameError` in the membership check and leaves a
  documented hook for any genuine future `_module.func(` exemption.
- Rejected: (a) Leaving the entries in place — they are dead and imply false coverage.
  (b) Deleting the `ALLOWLIST` symbol entirely — forces an edit to the `if (module_stem, fn)
  in ALLOWLIST` guard in `_run_drift_guard()` for no benefit and removes the future hook.

### drift-regression-test

- Decision: Add a focused unit assertion in `test-skill-helper-drift.py` that
  `_extract_helper_references("gate_cmd.lower()")` returns an empty list (no `("cmd","lower")`).
- Rationale: The full-suite-passing-on-main signal is necessary but not self-documenting; a
  named assertion pins the exact false-positive case so a future regex "simplification" that
  drops the boundary fails loudly with a clear message.
- Rejected: Relying solely on the existing Card 1 scan passing — it would catch a regression
  only as long as `mill-go/SKILL.md` keeps the `gate_cmd.lower()` line, which is incidental.

### millstart-fetch-body-brief

- Decision: In Phase: Select, extend the sample snippet to also fetch and print
  `task.get('body', '')` and `task.get('brief', '')` (`.get` form is correct for safe code).
  To keep the existing "status must be `active`" single-line gate unambiguous when `body`
  spans many lines (the ~6KB harden-path-invariant case), the snippet prints **`status` on
  its own first line** (e.g. `print('STATUS:', task.get('status',''))`) and emits `brief`/`body`
  AFTER it under labeled sentinel delimiters (e.g. `--- BRIEF ---` / `--- BODY ---` lines),
  so the gate parses only the first `STATUS:` line. In Phase: Explore, add an explicit
  instruction to read the proposal and summary before exploring code, and a documentation
  line that names the exact keys in **subscript form** — the literal strings `task['body']`
  and `task['brief']` — plus the full observed key set, so agents do not guess. This
  subscript-form prose in Phase: Explore is the canonical literal that the regression lock
  (see `millstart-skill-regression-lock`) checks for.
- Data-flow source of truth: because each bash invocation is a fresh subprocess (the `task`
  variable from Phase: Select does NOT persist into Phase: Explore), **Phase: Explore
  re-calls `_client.get_task` itself** and reads `task['body']` / `task['brief']` from that
  fresh result — it does not rely on scrollback from the Select printout. The Select printout
  is for the operator's immediate visibility and the status gate; Explore's re-fetch is the
  authoritative read that informs design.
- Rationale: Phase: Select already calls `get_task`, so surfacing `body`/`brief` there is
  zero extra round-trips; Phase: Explore is where the proposal must actually inform the
  agent's reading. Naming the schema fields (`body`, `brief` — NOT `summary`/`proposal`)
  removes the guessing that caused the bug. Pinning the Explore documentation to the exact
  `task['body']` / `task['brief']` subscript strings means the SKILL literally contains the
  substrings the lock asserts, so a faithful edit and the lock agree (resolves the review
  GAP: the `.get('body', '')` snippet form does NOT contain the substring `task['body']`,
  so the lock must target the Explore prose, not the snippet).
- Rejected: (a) Surfacing only in Phase: Explore — loses the cheap fetch already in Select.
  (b) A new dedicated phase — overkill for two field reads. (c) Having the lock assert the
  `.get('body'` form — less readable as field documentation and couples the lock to the
  snippet's defaulting style rather than the human-facing field-name guidance.

### millstart-empty-fallback

- Decision: Document that when `body`/`brief` are empty/`None`, the agent falls back to
  deriving scope from code (the current behaviour) — but only after confirming the correct
  fields are empty, never because it guessed the wrong field name.
- Rationale: Some tasks legitimately have no proposal body; the fix must not turn an empty
  proposal into a hard error. The defect was guessing `summary`/`proposal`, not the fallback.
- Rejected: Making a non-empty `body` a hard requirement — breaks thin/quick tasks.

### millstart-skill-regression-lock

- Decision: Add a Card 2 regression-lock assertion in `_run_regression_locks()` that
  `mill-start/SKILL.md` contains BOTH literal substrings `task['body']` and `task['brief']`
  (mirroring the existing `#495`/`#496` `... in <skill_text>` checks). These substrings are
  guaranteed present by the Phase: Explore subscript-form documentation pinned in
  `millstart-fetch-body-brief` — the lock and the SKILL edit reference the exact same literal,
  so a faithful edit passes and a regression (dropping the field guidance) fails.
- Rationale: The repo already uses Card 2 to lock SKILL.md prose against regression; a
  string-presence check is the established, lightweight pattern and prevents a future SKILL
  edit from silently dropping the field-name guidance.
- Rejected: No test (pure prose change) — leaves the fix unguarded and re-openable.

## Technical context

- **Test file:** `plugins/mill/unit_tests/test-skill-helper-drift.py`.
  - `_extract_helper_references(skill_md_text)` holds the regex to fix (the only place the
    pattern appears). It returns `list[tuple[module_stem, fn]]`.
  - `_run_drift_guard()` consumes those references and checks them against
    `_collect_shipped_helpers()` (which strips the leading `_` from module stems).
  - `ALLOWLIST` is the exemption set — do NOT add `("cmd","lower")` here; fix the regex. After
    the lookbehind lands, every existing `ALLOWLIST` entry is an identifier-tail match that the
    regex no longer extracts, so the set is emptied (see `allowlist-prune-dead-entries`); keep
    the symbol + the `in ALLOWLIST` guard in `_run_drift_guard()`.
  - The focused extract-unit assertions get their own check group: add a new
    `_run_extract_unit_checks()` function (call it "Card 3") that returns a `list[str]` of
    failures exactly like the other two, and invoke it from `main()` alongside
    `_run_drift_guard()` / `_run_regression_locks()`, gating the exit code the same way (any
    failure -> print + `return 1`). This is where the `gate_cmd.lower()` negative case and the
    `_paths.resolve_git_root()` positive case are asserted.
  - Card 2 `_run_regression_locks()` is where the new `mill-start` SKILL string-lock belongs;
    it already pattern-matches against `mill-go/SKILL.md` content, so the shape is established.
- **The triggering line:** `mill-go/SKILL.md:738` — `if platform.system() == 'Windows' and
  'dotnet' in gate_cmd.lower():`. Leave it unchanged.
- **mill-start SKILL.md:** `plugins/mill/skills/mill-start/SKILL.md`.
  - Phase: Select is the fenced bash snippet around lines 72–83 (`task.get('status', '')`).
  - Phase: Active is lines 87–89; Phase: Explore is lines 91–99.
  - Observed `get_task()` keys: `body, brief, deferred, depends_on, id, isolated, slug,
    status, title`. The proposal is `body`; the one-paragraph summary is `brief`.
- **Run path:** tests run via `uv run --project plugins/mill`; full suite via
  `plugins/mill/unit_tests/run-all.py`. The drift test is standalone-runnable.
- **No cache edits:** the fix lands in the source tree (`plugins/mill/...`); the cache copy
  is regenerated on plugin update.

## Constraints

- No `CONSTRAINTS.md` at the hub root (none read during Explore).
- Generated/markdown conventions per `CLAUDE.md` apply to any SKILL.md prose edits
  (ASCII-only in any code/print, fenced ```` ```yaml ```` for metadata, not `---`).
- Verify commands for this Python project MUST start with `PYTHONPATH=` (literal empty value)
  so the test subprocess loads worktree code, not the cache modules.

## Testing

- **Regex fix (TDD candidate):** add the focused assertions FIRST, inside a new
  `_run_extract_unit_checks()` function wired into `main()` (see Technical context):
  `_extract_helper_references("gate_cmd.lower()") == []` (negative case — watch it fail against
  the current regex, then apply the lookbehind and watch it pass) and
  `_extract_helper_references("_paths.resolve_git_root()") == [("paths","resolve_git_root")]`
  (positive case — guards against an over-broad lookbehind). The function must contribute to
  the suite exit code so a regression actually fails the run, not sit unused.
- **Full drift scan:** after the fix, `test-skill-helper-drift.py` must exit 0 on clean state
  (Card 1 reports PASS, no `unresolved module 'cmd'`).
- **mill-start SKILL.md lock (TDD candidate):** add the Card 2 string-presence assertions for
  `task['body']` / `task['brief']`; they fail until the SKILL is edited, then pass.
- **No behavioural test for the SKILL prose itself** beyond the string lock — SKILL.md is
  agent-consumed prose, not executable; the lock is the durable guard.
- **Full suite:** `PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py`
  must stay green.

## Q&A log

- **Q:** How should the drift-guard false positive on `gate_cmd.lower()` be fixed? **A:** [auto-pick] Add a negative lookbehind `(?<![A-Za-z0-9_])` to the helper-reference regex. **Why:** Minimal one-line fix that excludes identifier-tail matches while preserving all genuine `_module.func(` references; rejected allowlisting (masks the defect) and AST rewriting (disproportionate).
- **Q:** Should the regex fix get focused regression coverage? **A:** [auto-pick] Yes — add a named assertion that `_extract_helper_references("gate_cmd.lower()")` returns no reference. **Why:** Pins the exact false-positive case so a future regex change fails loudly, rather than relying on the incidental `gate_cmd.lower()` line in mill-go staying put.
- **Q:** Where should mill-start surface the proposal body/brief? **A:** [auto-pick] Phase: Select fetches and prints `body`+`brief`; Phase: Explore instructs the agent to read them and names the exact fields. **Why:** Select already calls `get_task` (free fetch); Explore is where the proposal must inform reading; naming `body`/`brief` removes the guessing that caused the bug.
- **Q:** Should the SKILL name the exact `get_task()` schema fields? **A:** [auto-pick] Yes — document `body`/`brief` (not `summary`/`proposal`) and the full observed key set. **Why:** The root cause was an agent guessing wrong field names; explicit documentation is the durable fix.
- **Q:** Should the fix audit other `get_task` consumers too? **A:** [auto-pick] No — scope to mill-start only. **Why:** A grep shows only `mill-ghissues-to-tasks` reads a proposal field and it already uses the correct `task['body']`; the others do not read the proposal. YAGNI.
- **Q:** How should empty `body`/`brief` be handled? **A:** [auto-pick] Graceful fallback to code-derived scope, only after confirming the correct fields are empty. **Why:** Some tasks legitimately carry no proposal; the defect was guessing wrong fields, not the fallback itself.
- **Q:** Should the mill-start SKILL change be regression-locked? **A:** [auto-pick] Yes — add a Card 2 string-presence assertion that the SKILL references `task['body']` and `task['brief']`. **Why:** The repo already locks SKILL.md prose this way (#495/#496); it prevents a future edit from silently dropping the field-name guidance.
