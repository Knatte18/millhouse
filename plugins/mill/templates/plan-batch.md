<!--
Template: `<WIKI_PATH>/active/<slug>/plan/NN-<batch-slug>.md` — written
by mill-plan once per batch during Phase: Plan.

Tokens: <TASK_TITLE>, <BATCH_NAME>, <BATCH_SLUG>.

Each batch is a Sonnet-sized unit of implementation. A batch groups
cards that logically hang together and that a single Sonnet session
can implement in one go, keeping context well under the 200k window.
There is no hard cap on cards — the planner picks what makes sense.
Fill every section; no heading-only skeletons.

Strip this HTML comment before writing.
-->
# Batch: <BATCH_NAME>

```yaml
task: <TASK_TITLE>
batch: <BATCH_NAME>
cards: 0
verify: null
depends-on: []
```

## Batch Scope

_One paragraph stating what this batch delivers and why it is one
batch. Call out the external interface (if any) the next batch will
consume. List the batch-local decisions that differ from `## Shared
Decisions` in the overview._

## Cards

_One `### Card N` per card. Cards are logical sub-sections, not files.
Number cards globally across all batches (no restart-from-1 inside
each batch) so the reviewer and implementer can cite card numbers
unambiguously. Fields per card:_

- **Reads:** every file the implementer reads to do this card. Non-empty. One backtick-wrapped path per indented bullet.
- **Modifies:** files the implementer edits. One backtick-wrapped path per indented bullet.
- **Creates:** files the implementer creates. One backtick-wrapped path per indented bullet. When a field has nothing, write the literal "none" on the same line as the field label.
- **Requirements:** what the card must achieve. Prose — exact
  assertions live in tests, not here.
- **Commit:** one-line commit message the implementer will use.

Reads/Modifies/Creates fields contain ONLY backtick-wrapped paths in bullet form. No inline parenthetical commentary, no line-range suffixes (e.g. ":55-65"). Inline notes belong in Requirements:. When a field has nothing, write the literal "none" on the same line as the field label.

### Card N: <short title>

- **Reads:**
  - `path/a`
  - `path/b`
- **Modifies:**
  - `path/c`
- **Creates:**
  - `path/d`
- **Requirements:** …
- **Commit:** `<type>(<scope>): <summary>`

## Batch Tests

_How the batch as a whole is verified. If `verify:` in the frontmatter
runs a test suite, name the files it covers. If `verify: null`, state
why (e.g. pure docs batch with no runnable surface)._
