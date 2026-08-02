# Discussion: mill-config.yaml unknown-key warning for pipeline.autonomous_mode

```yaml
task: mill-config.yaml unknown-key warning for pipeline.autonomous_mode
slug: mill-config-autonomous-mode-unknown-key
status: discussing
parent: main
```

## Problem

The task as filed (from GH issues #767 and #765, both sourced from a downstream
consumer repo, `loomyard`) described `mill-config.yaml`'s template documenting
`pipeline.autonomous_mode` (with a comment claiming it was "read by mill-go and
mill-plan for autonomous stuck-handling"), while `_config.py`'s known-keys
validator did not recognize the key — producing a `[config] unknown key:
pipeline.autonomous_mode` warning on every mill invocation in any hub whose
config carried it. Grepping the scripts at the time turned up zero readers of
the key, meaning the documented feature was never actually implemented.

**Why now / what changed:** investigation during this task's Explore phase
found that the bug **no longer reproduces on current `HEAD`**. Between when
the two source issues were filed and this task branch being spawned, the
`pipeline.autonomous_mode` feature was **fully deleted** — not merely
allowlisted or wired up — by commit `6cbd6dc6` ("Non-interactive pipeline:
only mill-start's interview may prompt the operator"), which removed
`_autonomous.py`, the template key, and the mill-autofix pre-flight/cleanup
phases that referenced it. That commit is an ancestor of this branch's HEAD.
A repo-wide `git grep autonomous_mode` returns zero hits except this task's
own `_mill/status.md` title.

Separately, `_config.py` already carries two pieces of prior art directly
relevant to this class of bug:

- A generic cache-lag suppression mechanism (commit `22e2d3f5`, also an
  ancestor of HEAD) that merges the source-tree template into `template_cfg`
  specifically to prevent "key documented in template but validator doesn't
  know it yet" false warnings for self-hosting task worktrees.
- An established `deprecated_keys` set in `warn_unknown_keys` (currently
  `{"llm.claude.psmux.via_psmux"}`) that suppresses the unknown-key warning
  for keys that are known-gone, with a matching unit test
  (`test_via_psmux_does_not_trigger_unknown_key_warning`).

So the original "wire it up, or remove the stale key" framing from the task
brief is stale: the feature was never wired up **and** has since been deleted
outright, not left half-implemented. The remaining real question is narrower:
does a downstream hub whose committed `mill-config.yaml` or
`.millhouse/config.local.yaml` still carries the now-fully-removed
`pipeline.autonomous_mode` key (written before the deletion, e.g. by an older
cached mill-autofix) deserve warning suppression going forward?

## Scope

**In:**
- Add `"pipeline.autonomous_mode"` to the `deprecated_keys` set in
  `plugins/mill/scripts/_config.py`'s `warn_unknown_keys`, mirroring the
  existing `llm.claude.psmux.via_psmux` entry, so any hub/config still
  carrying the fully-removed key does not trigger the unknown-key warning.
- Add a unit test to `plugins/mill/unit_tests/test-config.py` asserting the
  warning is suppressed for this key, following the pattern of
  `test_via_psmux_does_not_trigger_unknown_key_warning`.

**Out:**
- Re-implementing `pipeline.autonomous_mode` as an actual stuck-handling
  toggle read by mill-go/mill-plan. This SKILL's own text states mill-plan
  and mill-go are now unconditionally autonomous by deliberate design (see
  commit `6cbd6dc6`); reintroducing a config-gated autonomy toggle would
  contradict that recent architectural decision.
- Any migration/back-compat shim analogous to `_apply_dispatch_shim` for
  `via_psmux`. There is no successor value or behavior for
  `pipeline.autonomous_mode` to migrate to — the feature has no replacement,
  it was simply removed. Pure suppression (no shim) is correct.
- Documentation cleanup in `mill-config.yaml` comments, `mill-autofix`
  `SKILL.md`, or `CLAUDE.md`. A repo-wide `git grep autonomous_mode` shows
  zero remaining references outside this task's own `_mill/status.md`; there
  is no stale doc to fix.
- Closing or otherwise touching GH issues #767/#765 — both are already
  closed (consolidated into this wiki task).

## Decisions

### Suppress via deprecated_keys, do not re-implement

- Decision: Add `"pipeline.autonomous_mode"` as a bare entry in
  `_config.py`'s `deprecated_keys` set. No shim, no migration logic.
- Rationale: matches the exact existing precedent (`via_psmux`) built for
  "key is known-gone, don't warn about it." Minimal, low-risk, consistent
  with codebase convention. The key's only known writer (an older
  mill-autofix) itself no longer writes it, so this only protects
  already-stale configs from before the feature deletion.
- Rejected: (a) leaving the warning as-is (pure documentation-only close) —
  leaves a real, if minor, wart for any hub whose config predates the
  deletion, with zero cost to fix; (b) reintroducing the feature — reverts
  deliberate recent architecture (`6cbd6dc6`) that made mill-plan/mill-go
  unconditionally autonomous.

### No documentation changes

- Decision: Do not touch `mill-config.yaml` template comments,
  `mill-autofix/SKILL.md`, or `CLAUDE.md`.
- Rationale: none of them currently reference `autonomous_mode` — the
  feature-deletion commit already cleaned those up. Nothing stale remains to
  document or remove.
- Rejected: adding a changelog-style note recording the historical
  feature's existence/removal — scope creep, YAGNI; the deprecated_keys
  entry's own inline comment is sufficient self-documentation.

## Technical context

- `plugins/mill/scripts/_config.py`:
  - `warn_unknown_keys` (around line 113) holds the `deprecated_keys` set
    (line 122) — add the new entry there, keeping the set sorted/grouped
    however the existing single entry is styled (currently just one string
    literal; a second entry is a plain addition to the set literal).
  - `walk_unknown_keys` (line 89) produces dotted paths like
    `"pipeline.autonomous_mode"` — confirmed by the existing
    `"llm.claude.psmux.via_psmux"` entry using the same dotted-path
    convention for a nested key.
  - `load_config` (line 193) is the entry point; its cache-lag augmentation
    block (lines ~220-242) is unrelated prior art, not something this task
    needs to touch.
- `plugins/mill/unit_tests/test-config.py`:
  - `test_via_psmux_does_not_trigger_unknown_key_warning` (around line 1323)
    is the direct template to copy: constructs a config containing the
    deprecated key, calls `load_config` (or the relevant lower-level
    helper), captures stderr, and asserts the unknown-key warning string is
    absent. The new test should assert
    `"unknown key: pipeline.autonomous_mode"` does NOT appear in stderr
    when a config sets `pipeline.autonomous_mode` to any value.
  - Test is registered in the module's test-list at the bottom of the file
    (see line ~1556 where `test_via_psmux_does_not_trigger_unknown_key_warning`
    is listed) — the new test needs the same registration.
- No other files need changes. `_autonomous.py` does not exist on this
  branch; there is nothing to delete.

## Constraints

No `CONSTRAINTS.md` present at the hub root.

## Testing

- **TDD candidate:** `test-config.py` — add
  `test_pipeline_autonomous_mode_does_not_trigger_unknown_key_warning`,
  modeled directly on `test_via_psmux_does_not_trigger_unknown_key_warning`.
  Scenario: a config with `pipeline.autonomous_mode` set to some value (e.g.
  `false`, matching the key's historical usage) must not produce
  `"unknown key: pipeline.autonomous_mode"` on stderr when loaded through
  `_config.load_config` (or `warn_unknown_keys` directly, whichever the
  existing `via_psmux` test uses).
- Run the full existing suite (`plugins/mill/unit_tests/run-all.py`) to
  confirm no regression — the change is additive to a set literal and
  should not affect any other key's warning behavior.
- No integration-test coverage needed; this is a pure `_config.py` unit
  concern with no git/wiki/LLM interaction.

## Q&A log

- **Q:** Given the original bug no longer reproduces on current HEAD (the
  `pipeline.autonomous_mode` feature was already fully deleted, and a
  generic cache-lag suppression mechanism already exists), what should this
  task deliver? **A:** [auto-pick] Add `pipeline.autonomous_mode` to
  `_config.py`'s `deprecated_keys` set, mirroring the `via_psmux` precedent,
  plus a discussion.md record of the investigation. **Why:** matches an
  established, low-risk codebase pattern built exactly for this scenario;
  pure documentation-only close leaves a real (if minor) wart for hubs with
  pre-deletion configs; reintroducing the feature would revert deliberate
  recent architecture that made mill-plan/mill-go unconditionally autonomous.
- **Q:** Should the change include a unit test? **A:** [auto-pick] Yes — add
  a test to `test-config.py` following the existing `via_psmux` suppression
  test pattern. **Why:** this repo's testing convention is one test per
  distinct behavior; a one-line set addition is still a distinct,
  cheap-to-verify behavior.
- **Q:** Any further documentation cleanup needed (mill-config.yaml
  comments, mill-autofix SKILL.md, CLAUDE.md)? **A:** [auto-pick] No — a
  repo-wide grep shows zero remaining references to `autonomous_mode`
  outside this task's own status.md. **Why:** YAGNI — nothing stale exists
  to fix; documenting removed-feature history elsewhere is scope creep.
