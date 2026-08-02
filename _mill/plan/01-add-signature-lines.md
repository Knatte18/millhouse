# Batch: add-signature-lines

```yaml
task: 'mill-merge-in SKILL.md: _plan_dag helper calls missing signature lines'
batch: add-signature-lines
number: 1
cards: 1
verify: null
depends-on: []
```

## Batch Scope

This batch makes a single, surgical documentation edit to
`plugins/mill/skills/mill-merge-in/SKILL.md`'s step 4 ("Verify"): it adds
two missing `signature:` lines for the `_plan_dag._read_batch_frontmatter()`
and `_plan_dag.parse_verify_field()` calls that step 4's prose already
names but never documents inline, unlike every other helper call in the
same file family (`mill-go/SKILL.md`, `mill-finalize/SKILL.md`). No code
changes; the functions already behave correctly, only the skill's prose
was incomplete. This is the only batch — the whole task is one paragraph
edit with no downstream consumer to hand off to.

## Cards

### Card 1: Add signature: lines for _read_batch_frontmatter and parse_verify_field

- **Context:**
  - `plugins/mill/scripts/_plan_dag.py`
  - `plugins/mill/skills/mill-go/SKILL.md`
  - `_mill/discussion.md`
- **Edits:**
  - `plugins/mill/skills/mill-merge-in/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  In `plugins/mill/skills/mill-merge-in/SKILL.md`, step 4 ("Verify"), the
  paragraph currently at line 95 begins "Immediately after that call,
  attribute and report every batch this filtering silently dropped..."
  and, mid-paragraph, names two `_plan_dag` helper calls without inline
  `signature:` annotations: "read its frontmatter via
  `_plan_dag._read_batch_frontmatter()` and normalize its `verify:` via
  `_plan_dag.parse_verify_field()`". Immediately after that paragraph
  (i.e. after the paragraph ends, before the next paragraph — the one
  starting "Before the loop, load config..." — begins), insert two new
  standalone lines, each on its own line, in this exact call order and
  exact text (verified against `plugins/mill/scripts/_plan_dag.py:343`
  and `:366-368` in this task worktree):
  ```
  `signature: _plan_dag._read_batch_frontmatter(batch_path: Path) -> dict`
  `signature: _plan_dag.parse_verify_field(frontmatter: dict, hub_root: Path, git_root: Path) -> tuple[str | None, Path | None]`
  ```
  Follow the structural precedent at `mill-go/SKILL.md:434-437`:
  standalone, unindented `signature:` lines following plain prose, not
  indented inside a numbered-list item (mill-merge-in step 4 is a plain
  paragraph, not a list item). Do not rewrite the paragraph itself, and
  do not add signature lines for `extract_batch_index`, `topo_order`, or
  `iter_batch_verifies` — those are explicitly out of scope for this
  task (see `_mill/discussion.md`'s "Scope boundary: only the two named
  call sites" Decision).
- **Commit:** `docs(mill-merge-in): add signature lines for _plan_dag helper calls`

## Batch Tests

`verify: null` — this is a docs-only edit to an LLM-orchestrator prose
file (`SKILL.md`), not executable code. No automated test covers
SKILL.md prose content; verification is manual/visual per
`_mill/discussion.md`'s Testing section: after the edit,
`grep -n "signature:" plugins/mill/skills/mill-merge-in/SKILL.md` must
show exactly two new lines, immediately following the step-4 paragraph,
with the exact text given in the card's Requirements above. No `.py`
file is touched, so `plugins/mill/unit_tests/` and
`plugins/mill/integration_tests/` are unaffected and need no replay.
