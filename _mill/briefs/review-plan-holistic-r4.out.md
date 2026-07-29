MILL_REVIEW_BEGIN
# Review: mill-start: tracked _mill/ files disappear from the working tree mid-review-loop; existing safeguard covers only status.md — holistic

```yaml
verdict: REQUEST_CHANGES
reviewer_model: sonnethigh
reviewed_file: plan/
date: 2026-07-29
```

## Findings

### [BLOCKING] Test-treeguard scenario 8 contradicts Card 1's mandatory disk-existence check
**Location:** Batch 1 (treeguard-helper), Card 2, scenario 8 ("Nested-hub layout ...")
**Issue:** Card 1 requirement 7 mandates `restored_paths` be built ONLY from paths where `(worktree / path).exists()` is true after the checkout call — the whole point of round 1's GAP fix (never trust returncode alone). Scenario 8 calls `check_and_restore` on plain, non-existent, non-tempdir `Path` objects with `_subprocess_util.run` mocked to `returncode=0` "without touching disk". Given Card 1's disk check, `(hub_root / "_mill/status.md").exists()` is always `False` here, so `restored_paths` is `[]` and step 9 forces `{"triggered": False, ...}` — directly contradicting scenario 8's asserted `result["triggered"] is True` and `result["restored_paths"] == ["_mill/status.md"]`. This is why `test-cleanliness.py`'s ROOD-5 (which this scenario is modeled on) works: `revert_out_of_scope_drift` trusts `returncode` alone and has no disk-existence check — `_treeguard.check_and_restore` deliberately does not, per Card 1's own round-1 fix, so the mirrored mocking pattern cannot pass as written.
**Fix:** Scenario 8 must actually create `_mill/status.md` under a real (temp) `hub_root` before/via the mocked `run`'s side effect (mirroring how scenario 10's partial-restore test creates real disk state via `side_effect`), or use a real nested git fixture instead of bare non-existent Paths.

### [BLOCKING] Card 2's Context omits `_treeguard.py`, whose functions/attributes its Requirements depend on
**Location:** Batch 1 (treeguard-helper), Card 2 (`test-treeguard.py`)
**Issue:** Card 2's `Context:` lists only `test-cleanliness.py` and `test-status.py`. Its Requirements extensively describe `check_and_restore`'s exact return-dict contract and instruct patching `_treeguard._subprocess_util.run` / `_treeguard._pygit2_util.status_porcelain` — all identifiers belonging to `plugins/mill/scripts/_treeguard.py`, which Card 2 neither Edits nor lists in Context. Per this project's Context-is-an-allowlist rule, the implementer may not read that file.
**Fix:** Add `plugins/mill/scripts/_treeguard.py` to Card 2's `Context:` list.

### [NIT] Imprecise line-range citation for `revert_out_of_scope_drift`
**Location:** `00-overview.md`, Shared Decision "git-status detection reuses..."
**Issue:** Cites `_cleanliness.py:324-445` as the "nearest existing analog", but the actual function spans lines 324-451 (the final `return` statement at 451 is excluded from the cited range).
**Fix:** Update the citation to `_cleanliness.py:324-451`.

## Verdict

REQUEST_CHANGES
Card 2's nested-hub test (scenario 8) contradicts Card 1's disk-existence check, and Card 2's Context omits `_treeguard.py`.
MILL_REVIEW_END
