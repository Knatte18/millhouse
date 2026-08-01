# Batch: cleanup-dead-autonomous-mode

```yaml
task: 'Non-interactive pipeline: only mill-start''s interview may prompt the operator'
batch: cleanup-dead-autonomous-mode
number: 6
cards: 3
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-config.py test-reviewers.py test-large-prompt-switch.py
depends-on: [1, 2, 3, 4]
```

## Batch Scope

Batches 1-4 removed every `pipeline.autonomous_mode` read site in `mill-plan`/`mill-go`; this batch removes the key itself and everything that only existed to serve it: the dead `_autonomous.py` flag-file module (zero callers anywhere, confirmed by grep across `scripts/` and `skills/`), its test file, the config key's template declaration, the two unit-test fixtures that reference it, `mill-autofix`'s Phase 2 (sets the flag)/Phase 4 (restores the flag) — which had no purpose beyond the now-deleted key — and a documentation-only line in `mill-start/SKILL.md` that described the key's semantics. This batch depends on batches 1-4 so the config key's read sites are already gone before the key itself is deleted (no file overlap forces this ordering — `templates/mill-config.yaml`, `mill-autofix/SKILL.md`, `_autonomous.py`, `_test_cfg.py`, `test-config.py`, and `mill-start/SKILL.md` are untouched by batches 1-5 — but leaving the key alive for even one intermediate merge state would be a broken pipeline: mill-plan/mill-go would already be unconditionally autonomous while `mill-autofix` still mutates a key nothing reads).

`verify:` runs the two test files that literally reference `autonomous_mode` (`test-config.py`, `_test_cfg.py`'s own file is a fixture module with no `main()`/test runner, so it is verified transitively) plus the two consumers of `_test_cfg.make_minimal_cfg` (`test-reviewers.py`, `test-large-prompt-switch.py`) to confirm removing the key from the fixture baseline does not break any assertion downstream — confirmed during Phase: Plan by grep that neither of those two files asserts on `autonomous_mode` directly, so this is a safety check, not an expected-failure case.

## Cards

### Card 12: Delete dead autonomous-mode code and config key

- **Context:** none
- **Edits:**
  - `plugins/mill/templates/mill-config.yaml`
  - `plugins/mill/unit_tests/_test_cfg.py`
  - `plugins/mill/unit_tests/test-config.py`
- **Creates:** none
- **Deletes:**
  - `plugins/mill/scripts/_autonomous.py`
  - `plugins/mill/unit_tests/test-autonomous.py`
- **Moves:** none
- **Requirements:**

  Delete `plugins/mill/scripts/_autonomous.py` in full (dead code: `is_autonomous`/`set_autonomous`/`clear_autonomous`, zero callers anywhere in `scripts/` or `skills/`).

  Delete `plugins/mill/unit_tests/test-autonomous.py` in full (tests only the module just deleted).

  In `plugins/mill/templates/mill-config.yaml`, inside the `pipeline:` block, the line currently reads exactly:

```
  autonomous_mode: false  # Set true by mill-autofix; read by mill-go and mill-plan for autonomous stuck-handling
```

  Delete this line (it sits between `auto_report: true` and `done_gate: null`; leave both of those and every other sibling key in `pipeline:` unchanged).

  In `plugins/mill/unit_tests/_test_cfg.py`, function `make_minimal_cfg`, the `"pipeline"` dict inside `baseline` currently reads exactly:

```python
        "pipeline": {
            "auto_merge": False,
            "auto_report": False,
            "autonomous_mode": False,
        },
```

  Replace it with:

```python
        "pipeline": {
            "auto_merge": False,
            "auto_report": False,
        },
```

  In `plugins/mill/unit_tests/test-config.py`, function `test_unknown_key_warning_emitted`, the call currently reads exactly:

```python
        _write_yaml(
            wt_root / ".millhouse" / "config.local.yaml",
            "pipeline:\n  autonomous_mode: true\n",
        )
```

  Replace it with:

```python
        _write_yaml(
            wt_root / ".millhouse" / "config.local.yaml",
            "pipeline:\n  some_unrecognized_key: true\n",
        )
```

  This test's synthetic template (`_setup_plugin_template`) has no real `pipeline:` section, so `autonomous_mode` there was always an arbitrary "any unrecognized key" example unrelated to the real schema — swapping the key name avoids a reader mistaking this line as coupled to the schema removal above, without changing what the test verifies (that unknown keys emit a stderr warning containing `"pipeline"`).
- **Commit:** `chore(config): delete pipeline.autonomous_mode and dead _autonomous.py`

### Card 13: Remove mill-autofix's autonomous-mode pre-flight/cleanup phases

- **Context:**
  - `.millhouse/config.local.yaml`
- **Edits:**
  - `plugins/mill/skills/mill-autofix/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**

  Delete the standalone paragraph that currently reads exactly:

```
**The cleanup phase is non-negotiable.** `pipeline.autonomous_mode: true` is a temporary mutation of `.millhouse/config.local.yaml`. It must be restored on every exit path: success, block, killswitch, or unhandled error.
```

  (It sits between the "You are the autonomous bug-fix orchestrator..." paragraph and the `## Arguments` heading — delete the paragraph and the blank line immediately after it, leaving the orchestrator paragraph followed directly by `## Arguments`.)

  Delete the entire `## Phase 2: Pre-flight — enable autonomous mode` section — from that heading through its final fenced bash block ending `print('autonomous_mode enabled')\n"` and the closing triple-backtick — immediately preceding the `## Phase 3: Per-bug loop` heading. Nothing else in Phase 2 has any purpose beyond setting the now-deleted config key.

  In `## Phase 3: Per-bug loop`, the intro sentence currently reads exactly:

```
For each issue in `issues` (in order), execute steps 0–10. After the loop (or after the killswitch fires), proceed to Phase 4.
```

  Replace it with:

```
For each issue in `issues` (in order), execute steps 0–10. After the loop (or after the killswitch fires), proceed to Phase 5: Report.
```

  Delete the entire `## Phase 4: Cleanup — restore autonomous mode` section — from that heading through its final paragraph ("If `original_cfg_text` was `None` ... write back the exact original text byte-for-byte.") — immediately preceding the `## Phase 5: Report` heading. Keep the `---` divider that currently sits immediately before the `## Phase 4` heading (it now separates Phase 3's content from `## Phase 5: Report` directly). Nothing else in Phase 4 has any purpose beyond restoring the now-deleted config key.

  In `## Principles`, the bullet currently reads exactly:

```
- **Cleanup is non-skippable.** Treat the per-bug loop as a try block with a guaranteed finally (Phase 4). A crashed or manually interrupted run must be re-started from scratch; bugs already fixed will be skipped via the "already present [done]" path in step 2.
```

  Replace it with:

```
- **Runs are restart-safe.** A crashed or manually interrupted run can be re-started from scratch; bugs already fixed will be skipped via the "already present [done]" path in step 2.
```
- **Commit:** `docs(mill-autofix): remove autonomous-mode pre-flight and cleanup phases`

### Card 14: Update mill-start's stale autonomous_mode doc line

- **Context:** none
- **Edits:**
  - `plugins/mill/skills/mill-start/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**

  The line currently reads exactly:

```
`--auto` is independent from `pipeline.autonomous_mode`: `--auto` is a per-invocation flag controlling Phase: Discuss / Discussion Review behaviour in mill-start; `pipeline.autonomous_mode` is a config key controlling mill-go's stuck-handling. The Auto mode subsection neither reads nor writes `pipeline.autonomous_mode`. Operators opt into each separately.
```

  Replace it with:

```
`--auto` is mill-start's own separate mechanism: a per-invocation flag controlling Phase: Discuss / Discussion Review behaviour in mill-start. mill-plan and mill-go are unconditionally autonomous outside mill-start entirely — there is no config key or flag governing their behavior, and the Auto mode subsection here neither reads nor writes any such setting.
```

  This is the only edit inside mill-start's Auto mode section (lines 13-41 as of this task's discussion) — the rest of that section (the actual `--auto` behavior for Phase: Discuss / Discussion Review) is unchanged.
- **Commit:** `docs(mill-start): update stale pipeline.autonomous_mode reference`

## Batch Tests

`verify:` runs `test-config.py` (edited directly, and the sole remaining test asserting on the unknown-key-warning behavior touched by Card 12), `test-reviewers.py` and `test-large-prompt-switch.py` (both import `make_minimal_cfg` from the edited `_test_cfg.py` and must still construct a valid cfg dict after `autonomous_mode` is removed from the baseline). `test-autonomous.py` is deleted by this batch and is correctly absent from the `--only` list. `mill-autofix/SKILL.md` and `mill-start/SKILL.md` are prose-only edits with no runnable surface, verified by plan/code review reading the diff.
