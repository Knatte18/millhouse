# Batch: cleanup-live-phase-classification

```yaml
task: "mill-go verify/cleanup gates misclassify build-tag deletions and round-suffixed phases"
batch: cleanup-live-phase-classification
number: 2
cards: 1
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-cleanup.py
depends-on: []
```

## Batch Scope

Fixes #716: `millpy-cleanup.py`'s `_LIVE_PHASES` set only recognizes the
base pipeline phases; it doesn't recognize the round-suffixed and
batch-name-embedded phases `_status.append_phase` is actually called with
throughout mill-start/mill-plan/mill-go (`discussion-fix-rN`,
`plan-review-rN`, `plan-fix-rN`, `reviewing-{batch}-rN`, `fixing-{batch}-rN`,
`approved-{batch}`, `nits-fixed-{scope}`, `holistic-reviewing`,
`holistic-fixing`, `holistic-approved`), so any task sitting on one of
these live, mid-pipeline phases is reported as `"unknown phase"` on every
cleanup run. This batch replaces the flat set-membership check with a
helper that recognizes the full real phase vocabulary and covers it with
unit + integration tests. Self-contained fix to one classification
function in one file; independent of batch 1.

## Cards

### Card 2: Recognize round-suffixed and batch-embedded phases as live in millpy-cleanup

- **Context:** none
- **Edits:**
  - `plugins/mill/scripts/millpy-cleanup.py`
  - `plugins/mill/unit_tests/test-cleanup.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  - In `plugins/mill/scripts/millpy-cleanup.py`, add `import re` to the
    existing import block (~lines 8-26 — not currently imported).
  - Replace the `_LIVE_PHASES` set (~lines 115-118, currently
    `{"discussing", "discussed", "planning", "planned", "implementing", "reviewing", "fixing", "blocked"}`)
    with a module-level exact-match set (drop the two dead bare entries
    `"reviewing"` and `"fixing"` — `_status.append_phase` never writes
    those literal values, only batch-suffixed or `holistic-`-prefixed
    forms):
    `_LIVE_PHASES = {"discussing", "discussed", "planning", "planned", "implementing", "blocked", "holistic-reviewing", "holistic-fixing", "holistic-approved"}`
  - Add a module-level tuple of compiled regex patterns for the
    round-suffixed / batch-embedded forms:
    ```
    _LIVE_PHASE_PATTERNS = tuple(re.compile(p) for p in (
        r"^discussion-fix-r\d+$",
        r"^plan-review-r\d+$",
        r"^plan-fix-r\d+$",
        r"^reviewing-.+-r\d+$",
        r"^fixing-.+-r\d+$",
        r"^approved-.+$",
        r"^nits-fixed-.+$",
    ))
    ```
  - Add a new function `_is_live_phase(phase: str) -> bool` next to
    `_read_phase` (~line 53) that returns `True` when `phase` is in
    `_LIVE_PHASES` or matches any pattern in `_LIVE_PHASE_PATTERNS`
    (`any(p.match(phase) for p in _LIVE_PHASE_PATTERNS)`), else `False`.
  - Change the `build_plan` branch at ~line 179 from
    `elif phase in _LIVE_PHASES: pass` to
    `elif _is_live_phase(phase): pass`. Do NOT add `"done"`, `"abandoned"`,
    or `"pr-pending"` to `_LIVE_PHASES`/`_LIVE_PHASE_PATTERNS` — those
    three are handled by their own earlier `elif` branches in `build_plan`
    (~lines 148-178) before this branch is ever reached, and must stay
    out of `_is_live_phase`'s scope.
  - In `plugins/mill/unit_tests/test-cleanup.py`, import `_is_live_phase`
    the same way `build_plan`/`_resolve_inplace_mode` are already
    imported via `importlib.util` (~lines 17-25 — add
    `_is_live_phase = mod._is_live_phase` alongside the existing
    attribute pulls).
  - Add a new function `test_is_live_phase() -> None`, following the
    existing `test_scan_orphan_portals()` pattern (~line 89 — plain
    `assert` statements, no exception wrapping). Assert `True` for:
    `discussing`, `discussed`, `planning`, `planned`, `implementing`,
    `blocked`, `holistic-reviewing`, `holistic-fixing`,
    `holistic-approved`, `discussion-fix-r1`, `plan-review-r3`,
    `plan-fix-r2`, `reviewing-batch-a-r1`, `fixing-batch-a-r2`,
    `approved-batch-a`, `nits-fixed-holistic`, `nits-fixed-batch-a`.
    Assert `False` for: `reviewing`, `fixing` (the two dropped bare
    values), `frobnicating` (an unrecognized value), `done`, `abandoned`,
    `pr-pending` (terminal phases handled by earlier branches — must NOT
    be classified live by this helper).
  - Call `test_is_live_phase()` explicitly from within `main()`, mirroring
    exactly how `test_scan_orphan_portals()` is already called at
    ~line 1375 (place the call adjacent to that existing call).
  - Add one new `build_plan(...)` integration sub-block in `main()`
    immediately after the existing "live slug (implementing)" sub-block
    (~lines 267-285), copying its structure but using
    `_make_status_md("plan-review-r2")` in place of
    `_make_status_md("implementing")` (a different slug, e.g.
    `"live-slug-round"`, to avoid confusion with the existing block).
    Assert `plan.to_remove_done == [] and plan.to_remove_abandoned == [] and plan.to_reset_home == []`
    (matching the existing block's assertion) AND additionally assert
    `plan.to_report == []` (a new assertion not present on the existing
    block — confirms the round-suffixed phase is silently treated as
    live, not reported as unknown, end-to-end through `build_plan`).
- **Commit:** `fix(cleanup): recognize round-suffixed and batch-embedded phases as live`

## Batch Tests

`verify:` runs the entire `test-cleanup.py` file (single test file this
batch's only edited test file lives in), which includes the existing
`test_scan_orphan_portals` and `main()` suite (unchanged, must still
pass) plus the new `test_is_live_phase()` function and the new
`build_plan(...)` integration sub-block added by Card 2.
