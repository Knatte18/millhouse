# Discussion: mill-merge-in SKILL.md: _plan_dag helper calls missing signature lines

```yaml
task: mill-merge-in SKILL.md: _plan_dag helper calls missing signature lines
slug: mill-merge-in-plan-dag-signature-docs
status: discussing
parent: main
```

## Problem

`plugins/mill/skills/mill-merge-in/SKILL.md` step 4 ("Verify") describes
the "visible, counted skips" attribution logic in prose: for each batch,
"read its frontmatter via `_plan_dag._read_batch_frontmatter()` and
normalize its `verify:` via `_plan_dag.parse_verify_field()`". Neither
call has the inline `signature: ...` annotation that helper calls
elsewhere in this file family (`mill-go/SKILL.md`, `mill-finalize/SKILL.md`)
carry — `mill-merge-in/SKILL.md` itself has zero `signature:` lines
anywhere today (confirmed by grep), so this fix imports a sibling-file
convention rather than extending one already present locally.

Per `mill:workflow`'s anti-pattern #1 ("Don't Read or Grep helper
internals... If a helper fails, handle the exception then"), an
orchestrator following this skill is expected to call these helpers
from the documented signature alone, never by reading `_plan_dag.py`
source. Without the signature line, the only reasonable reading —
"normalize its `verify:`" means passing the raw `verify:` value into
`parse_verify_field()` — is wrong and raises `AttributeError` /
`TypeError` against the real functions. Two independent GitHub issues
(#768, #762) hit this from different repos following `/mill-go`'s
Handoff → `mill-finalize` → `mill-merge-in` path.

## Scope

**In:**
- Add two `signature:` lines immediately after the step-4 paragraph in
  `plugins/mill/skills/mill-merge-in/SKILL.md` (currently line 95), one
  for `_plan_dag._read_batch_frontmatter()` and one for
  `_plan_dag.parse_verify_field()`, in call order.
- Signature text verified against the actual current source in this
  task worktree (`plugins/mill/scripts/_plan_dag.py`), not copied
  verbatim from either issue body (see Decisions — the issues disagree
  with each other on `parse_verify_field`'s return type).

**Out:**
- `_plan_dag.extract_batch_index()`, `_plan_dag.topo_order()`, and
  `_plan_dag.iter_batch_verifies()` — also called in the same step-4
  section without inline signatures — are explicitly **not** touched.
  Neither issue names them; adding signatures for calls nobody reported
  a problem with is a separate consistency sweep, not this task.
- No change to `_plan_dag.py` itself. This is a documentation-only fix;
  the functions already behave correctly, only the skill's prose was
  wrong.
- No change to any other skill file. `mill-go/SKILL.md` and
  `mill-finalize/SKILL.md` already carry correct signature lines for
  every helper they call — spot-checked, not in scope to re-verify here.

## Decisions

### Signature-line placement and format

- Decision: Add two standalone `signature:` lines directly after the
  step-4 paragraph that names the calls (SKILL.md:95), each on its own
  line, in the same call order as the prose sentence
  (`_read_batch_frontmatter` first, `parse_verify_field` second).
  Exact text:
  ```
  `signature: _plan_dag._read_batch_frontmatter(batch_path: Path) -> dict`
  `signature: _plan_dag.parse_verify_field(frontmatter: dict, hub_root: Path, git_root: Path) -> tuple[str | None, Path | None]`
  ```
- Rationale: This matches the established convention for a prose
  sentence naming multiple helper calls, and specifically follows the
  closer structural precedent at `mill-go/SKILL.md:434-437` — standalone,
  unindented `signature:` lines following plain prose/a code block under
  a step, not inside a numbered-list item. (`mill-go/SKILL.md:183-186`
  is the same convention but as a numbered-list-item continuation,
  which is a looser structural match since mill-merge-in step 4 is a
  plain paragraph, not a list item.) Consistency with the sibling file
  in the same skill family outweighs any local formatting preference.
- Rejected: Rewriting the whole step-4 paragraph into a bulleted list
  (one bullet per helper, mirroring mill-go's numbered-step-with-bullets
  layout) — larger diff than the bug requires, and step 4 as written
  mixes several concerns (the `iter_batch_verifies` call, the attribution
  diff, the counter setup) in flowing prose that doesn't cleanly bullet
  without a bigger rewrite nobody asked for. Also rejected: inline
  parenthetical signatures embedded in the sentence itself — no
  precedent anywhere else in the file family, harder to scan than a
  trailing line.

### `parse_verify_field` return type: resolving the issue conflict

- Decision: Use `-> tuple[str | None, Path | None]`.
- Rationale: The two source issues disagree — #768 claims
  `-> str | None`, #762 claims `-> tuple[str | None, Path | None]`.
  Read directly from `plugins/mill/scripts/_plan_dag.py:366-368` in
  this task worktree:
  ```python
  def parse_verify_field(
      frontmatter: dict, hub_root: Path, git_root: Path
  ) -> tuple[str | None, Path | None]:
  ```
  This matches #762 and confirms #768's return-type claim is stale/
  wrong. Per CLAUDE.md's "Task-worktree path for source verification"
  rule, the task-worktree source is the authority here, not either
  issue's prose. This also matches how the same function is already
  called correctly elsewhere in this file — step 4's first paragraph
  (SKILL.md:93) calls `iter_batch_verifies`, which internally uses
  `parse_verify_field` and consumes a `(cmd, cwd)` pair, confirming the
  tuple return shape is the real contract.
- Rejected: `-> str | None` (issue #768's claim) — contradicted by the
  actual source; would re-introduce a wrong signature line, defeating
  the purpose of the fix.

### Scope boundary: only the two named call sites

- Decision: Add signatures only for `_read_batch_frontmatter` and
  `parse_verify_field`. Do not add signatures for `extract_batch_index`,
  `topo_order`, or `iter_batch_verifies`, even though they appear in the
  same step-4 section without inline signatures either.
- Rationale: The task body/brief and both source issues (#768, #762)
  name exactly these two functions as the bug. YAGNI — expanding to a
  full-file signature-consistency sweep is a different, larger task the
  operator hasn't asked for and risks unrelated review churn on this
  narrowly-scoped fix.
- Rejected: Adding signatures for all five `_plan_dag` calls in step 4
  for full internal consistency — correct instinct in the abstract, but
  out of scope for a task whose brief and both linked issues are
  specific about which two calls are broken.

## Technical context

- File to edit: `plugins/mill/skills/mill-merge-in/SKILL.md`, step 4
  ("Verify"), the paragraph currently at line 95 (the sentence starting
  "Immediately after that call, attribute and report every batch...").
- Ground-truth signatures (from `plugins/mill/scripts/_plan_dag.py` in
  this task worktree):
  - `_read_batch_frontmatter(batch_path: Path) -> dict` (source
    line 343)
  - `parse_verify_field(frontmatter: dict, hub_root: Path, git_root: Path) -> tuple[str | None, Path | None]`
    (source line 366)
- Convention reference: `plugins/mill/skills/mill-go/SKILL.md:434-437`
  — the closest structural precedent (standalone, unindented
  `signature:` lines following plain prose, not a numbered-list-item
  continuation). `mill-go/SKILL.md:183-186` shows the same convention
  in list-item form.
- No other file in the repo currently documents these two functions'
  signatures inline (confirmed: `grep -n "signature:"` against
  `mill-merge-in/SKILL.md` returns nothing before this fix).
- This is a single-file, single-paragraph documentation edit. No code
  changes, no new modules, no dependency changes.

## Testing

- No automated test covers SKILL.md prose content — these are
  instructions for an LLM orchestrator, not executable code path.
- Verification is manual/visual: after the edit, `grep -n "signature:"
  plugins/mill/skills/mill-merge-in/SKILL.md` must show exactly two new
  lines, immediately following the step-4 paragraph, with the exact
  text given in the Decisions section above.
- No regression risk to existing tests — this task touches no `.py`
  file, so `plugins/mill/unit_tests/` and
  `plugins/mill/integration_tests/` are unaffected. mill-plan should
  still route this through whatever `verify:` the plan template
  defaults to for docs-only changes (likely a no-op or lint-only
  check) — not a TDD candidate in the usual sense.

## Q&A log

- **Q:** Where/how should the two missing `signature:` lines be placed
  and formatted? **A:** [auto-pick] Add two standalone lines
  immediately after the step-4 paragraph (SKILL.md:95), one per helper
  in call order, matching `mill-go/SKILL.md:183-186`'s convention for a
  prose sentence naming multiple helpers. **Why:** established
  convention elsewhere in the same file family; no reason to deviate.
- **Q:** Which return type should the `parse_verify_field` signature
  line declare, given issues #768 and #762 disagree with each other?
  **A:** [auto-pick] `-> tuple[str | None, Path | None]`, verified
  against current source in this task worktree
  (`_plan_dag.py:366-368`), not issue #768's stale `-> str | None`
  claim. **Why:** source is ground truth per CLAUDE.md's
  task-worktree source-verification rule.
- **Q:** Should this task also add signature lines for
  `extract_batch_index`, `topo_order`, and `iter_batch_verifies`, which
  appear unsignatured in the same step-4 section but aren't named by
  either issue? **A:** [auto-pick] No — stay narrowly scoped to the two
  issue-named calls. **Why:** YAGNI; broader consistency sweep is a
  separate task the operator hasn't asked for.
