# Discussion: 9 (B) — Wiki-enhance: small wiki cleanups

```yaml
task: 9 (B) — Wiki-enhance: small wiki cleanups
slug: wiki-enhance
status: discussing
parent: main
```

## Problem

Three separate quality issues were filed against the wiki and its tooling.
Two of them (Batches 2 and 3 from the original proposal) are resolved or moot:
the Bugs/Enhancements section split was removed in favour of Layer-based grouping
(commit `cefc7cb`), and the 40+ wiki-commit noise was eliminated by
container-restructure (which moved `status.md` to the task branch, leaving the
wiki only one push at task-completion). What remains is one batch.

**Config dead keys.** `wiki/config.yaml` carries three keys no script reads:
`pipeline.builder` (conceptually broken — the builder is the running CC session,
not a config value; grep over scripts returns zero matches), `implementers.code`
(the entire `implementers:` block is unused — `millpy-implement.py` directly
imports `_implementer_sonnet`), and `pipeline.implementer` (also unused). These
confuse new contributors and require maintenance for no benefit.

**Proposal-link `.md` suffix missing in generators.** Proposal links in Home.md
need a `.md` suffix for VS Code to navigate them locally. The existing entries in
Home.md were patched manually (5+ times). The three code locations that generate
new links — `millpy-add.py:_render_task_section`, `_tasks_md.append_entry`, and
`_sidebar.py:render` — still emit the old suffix-less form. Future `mill-add`
invocations regress the fix immediately.

## Scope

**In:**
- Remove `pipeline.builder`, `implementers:` block (whole block — only has `code:
  sonnet`), and `pipeline.implementer` from `wiki/config.yaml`
- Same removal from `plugins/mill/templates/wiki-config.yaml`
- Fix `millpy-add.py:_render_task_section()` to emit `(proposal-{slug}.md)`
- Fix `_tasks_md.append_entry()` to emit `(proposal-{slug}.md)`
- Fix `_sidebar.py:render()` to emit `(proposal-{slug}.md)`
- Update affected unit-test assertions

**Out:**
- Migrating existing Home.md entries — already done manually
- Removing `pipeline.auto_merge` / `pipeline.auto_report` — those are live keys
  read by mill-go SKILL.md
- Any parser changes to `_HEADING_RE` — the regex matches `proposal-[^)]+`, which
  already covers both old and new formats; `set_phase` reconstructs using the
  captured group verbatim, so old-format links in existing files are preserved
- Batch 2 (Bugs/Enhancements section contract) — removed from scope; layer
  grouping replaced that structure
- Batch 3 (wiki push cadence) — removed from scope; moot after container-restructure
- Sidebar link for `(Home)` — that is a wiki navigation link, not a proposal link;
  leave untouched

## Decisions

### Remove entire `implementers:` block vs. keep with comment

- Decision: Remove the whole block (no tombstone comment).
- Rationale: The block has one key (`code: sonnet`) and no reader. A tombstone
  comment would document a non-feature. If a multi-implementer-role system is
  built later, it will define its own config shape.
- Rejected: Keep with a `# deprecated` comment — adds noise without value.

### Remove `pipeline.builder` and `pipeline.implementer` vs. comment them out

- Decision: Delete the two keys from the `pipeline:` block; leave
  `pipeline.auto_merge` and `pipeline.auto_report` in place (they are live).
- Rationale: Commented-out dead config is worse than absent config — it suggests
  the keys might be reactivated, and scripts that defensively check for absence
  would still find them.
- Rejected: Comment out — same noise problem as above.

### `.md` suffix in sidebar

- Decision: Add `.md` to sidebar proposal links (`_sidebar.py:render`).
- Rationale: The proposal document calls for it; GitHub Wiki handles `.md` in
  links gracefully (strips extension for routing); VS Code needs it for local
  navigation. The risk of breaking GitHub Wiki sidebar navigation is low — the
  existing Home.md already uses `.md` links and GitHub renders them correctly.
- Rejected: Leave sidebar without `.md` — inconsistent with Home.md, VS Code
  can't navigate sidebar links either.

### Backwards compatibility for old-format links in Home.md

- Decision: No special handling needed.
- Rationale: `_HEADING_RE` captures the full proposal token (`proposal-foo` or
  `proposal-foo.md`) and `set_phase` reconstructs it verbatim. Old entries keep
  their format; new entries from `millpy-add` get `.md`. Mixed state is fine — the
  parser and phase-flipper are already format-agnostic.
- Rejected: Auto-upgrade all existing links on first write — out of scope; touches
  the Home.md migration path which is already done.

## Technical context

**Files to change:**

- `plugins/mill/scripts/millpy-add.py` — `_render_task_section()` at line 86:
  `f"[[{slug}]](proposal-{slug})"` → `f"[[{slug}]](proposal-{slug}.md)"`.
  This function is the sole Home.md formatter in millpy-add; it does NOT call
  `_tasks_md.append_entry` (independent implementation).

- `plugins/mill/scripts/_tasks_md.py` — `append_entry()`: same substitution.
  Called by `_spawn_core.py` (mill-add via multi-select groom flow). The parser
  regex at `_HEADING_RE` and `set_phase` logic do not need changes.

- `plugins/mill/scripts/_sidebar.py` — `render()` at line 100:
  `f"(proposal-{task['slug']})"` → `f"(proposal-{task['slug']}.md)"`.
  The `(Home)` entry in the Navigation section is hardcoded separately and must
  not receive a `.md` suffix.

- `wiki/config.yaml` — remove keys: `pipeline.builder`, `implementers:` block,
  `pipeline.implementer`. Keep: `pipeline.auto_merge`, `pipeline.auto_report`,
  `pipeline.skip_validate` comment.

- `plugins/mill/templates/wiki-config.yaml` — same key removals; this is the
  template used by `mill-setup` to seed new wiki repos.

**Unit tests to update:**

- `plugins/mill/unit_tests/test-tasks-md.py:68` — assertion
  `"[[prop-task]](proposal-prop-task)"` must change to
  `"[[prop-task]](proposal-prop-task.md)"`.

- `plugins/mill/unit_tests/test-millpy-add.py` — `test_proposal_body_file_reads_content`
  checks that `proposal-test-slug.md` is created, which is about the proposal file
  not the slug line in Home.md; no assertion changes needed unless the test also
  checks the Home.md slug line format. Re-read the test before writing to confirm.

- `plugins/mill/unit_tests/test-spawn-core.py` — `test_multi_select_groom_then_claim_with_proposal`
  checks proposal file creation, not slug line format; likely no change. Re-read
  before writing.

**No config-loader changes needed.** `_config.py:load_config` merges via
`yaml.safe_load` + deep-merge — removed keys simply disappear from the returned
dict. Callers that use `cfg.get("implementers", {})` or `cfg.get("pipeline",
{}).get("builder")` return `{}` or `None` gracefully.

## Testing

**Regression tests (update existing):**

- `test-tasks-md.py` — update the `append_entry has_proposal=True` assertion to
  expect `.md` suffix. The parse/set_phase/claim tests use a HOME_MD fixture with
  old-format links; those remain valid (parser is format-agnostic).

**New unit test for sidebar render:**

No `test-sidebar.py` exists. Add one: test `_sidebar.render()` with a task that
has `has_proposal=True` and assert the output contains `(proposal-{slug}.md)`.
One test function is enough — the existing `test-millpy-add.py` integration test
exercises the full sidebar-regeneration path end-to-end.

**Config removal — no dedicated test needed.** `test-config.py` tests
`load_config`; removed keys simply don't appear. If any test asserts on
`cfg["implementers"]` or `cfg["pipeline"]["builder"]`, update or remove that
assertion. Check before writing.

## Q&A log

- **Q:** Should Batch 2 (Bugs/Enhancements split) be kept? **A:** No — removed from scope. The Layer-based grouping replaced that structure today (commit `cefc7cb`). `mill-autofix` will handle bug classification via a different mechanism when built.
- **Q:** Should Batch 3 (wiki push cadence) be kept? **A:** No — moot after container-restructure. The wiki now gets exactly one push per task (the `[done]` flip); there is no commit noise left to batch.
- **Q:** Should old Home.md links be auto-upgraded to `.md`? **A:** No — migration is already done manually. Auto-upgrade is out of scope.
- **Q:** Should the `implementers:` block be kept with a deprecation comment? **A:** No — delete entirely. No tombstone.
- **Q:** Does the `.md` suffix in sidebar links break GitHub Wiki navigation? **A:** No — GitHub Wiki handles `.md` in links by stripping the extension. The existing Home.md `.md` links confirm this works.
