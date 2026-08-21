# Plan: mill-go-base/mill-merge: documented step behavior diverges from underlying script capability

```yaml
task: 'mill-go-base/mill-merge: documented step behavior diverges from underlying script capability'
slug: mill-go-base-documented-behavior-gaps
approved: false
started: 20260821-090525
parent: main
root: ""
verify: null
```

## Batch Index

```yaml
batches:
  - number: 1
    name: detached-head-branch-detection
    file: 01-detached-head-branch-detection.md
    depends-on: []
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-marker.py test-pygit2-util.py
  - number: 2
    name: preflight-attribute-guard
    file: 02-preflight-attribute-guard.md
    depends-on: []
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-preflight.py
  - number: 3
    name: entry-gate-discussion-phases
    file: 03-entry-gate-discussion-phases.md
    depends-on: [1]
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-phase-wait.py
```

## Shared Decisions

### Decision: no code/doc changes for #847 or #842

- **Decision:** #847 (`_status.update_field` strict-key ValueError) and #842
  (`millpy-review-code.py --stage finalize` rejecting `--duration-s`) are closed as no-action.
  Neither issue's offending behavior exists in current dev-tree source — both were already fixed
  (commits `4b3ce636` and `479f806b` respectively) before the issues were filed against a stale
  deployed plugin cache. No batch in this plan touches either area.
- **Rationale:** see `_mill/discussion.md`'s `#847-#842-disposition` Decision for the full
  source-verified writeup (call sites, commit hashes, timestamps).
- **Applies to:** all batches (informational — no batch acts on this).

### Decision: no change to other skills' MarkerError halt wording

- **Decision:** Only `mill-go-base/SKILL.md`'s Entry Step 1 halt handler (batch 1, card 4) is
  changed to surface `str(e)`. `mill-plan/SKILL.md`, `mill-start/SKILL.md`, `mill-quick/SKILL.md`,
  and `mill-merge-in/SKILL.md` each have their own similar-looking blanket-message `MarkerError`
  halt text, but none of them are in scope — #850 was filed specifically against mill-go-base, and
  `_mill/discussion.md`'s Scope section names only that one call site.
- **Rationale:** widening to other skills would be scope creep beyond what discussion.md decided;
  no test or other script programmatically matches on the exact halt message text at any of those
  other call sites (confirmed via repo-wide grep during planning), so leaving them untouched
  introduces no inconsistency risk.
- **Applies to:** batch 1.

## All Files Touched

- `plugins/mill/scripts/_marker.py`
- `plugins/mill/scripts/_preflight.py`
- `plugins/mill/scripts/_pygit2_util.py`
- `plugins/mill/skills/mill-go-base/SKILL.md`
- `plugins/mill/skills/mill-merge-in/SKILL.md`
- `plugins/mill/skills/mill-merge/SKILL.md`
- `plugins/mill/unit_tests/test-marker.py`
- `plugins/mill/unit_tests/test-phase-wait.py`
- `plugins/mill/unit_tests/test-preflight.py`
- `plugins/mill/unit_tests/test-pygit2-util.py`
