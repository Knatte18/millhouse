# Batch: mill-triage-title-escape

```yaml
task: 'mill-setup/wiki/docs/build-env: misc small bugs, round 3'
batch: mill-triage-title-escape
number: 1
cards: 1
verify: null
depends-on: []
```

## Batch Scope

Fixes GitHub issue #1113: a wiki task's stored `title` field can end up with a doubled apostrophe
(`''` instead of `'`) when the title is synthesized by fold/triage tooling rather than copied
verbatim from one source issue. `discussion.md`'s `1113-investigation-in-plan` Decision confirmed
the root cause: `plugins/mill/skills/mill-triage-to-tasks/SKILL.md` Step 5 instructs the agent to
substitute free text (`title`, `brief`, `body` for new tasks; the per-item block for fold-ins)
directly as literal text inside a bash-double-quoted `python -c "..."` command. This batch removes
that splice entirely by routing the free text through a temp JSON file instead, so no
apostrophe/quote/backtick in a source item's text can ever reach the shell command line. This batch
has no external interface for another batch to consume — it is a self-contained fix to one skill
file.

## Cards

### Card 1: Route mill-triage-to-tasks Step 5's free text through a temp file instead of inline literals

- **Context:**
  - `plugins/mill/templates/triage-report.schema.md`
- **Edits:**
  - `plugins/mill/skills/mill-triage-to-tasks/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  In `## Step 5 — Apply (on approve)`, numbered item `1. **New tasks.**`: the block currently builds
  the `python -c` command by substituting `title='<title>'`, `brief='<theme>'`, and
  `body='''<concatenated per-item blocks>'''` directly as literal text inside the bash-double-quoted
  `-c` string. An apostrophe in the substituted text breaks the *inner* Python single-quoted string
  literal (`title='<title>'`) — a bash double-quoted wrapper gives no special meaning to a bare
  apostrophe, so this is a Python-syntax break, not a bash-quoting break. Separately, the whole
  `python -c "..."` block is itself one bash double-quoted string (opening with
  `"$MILL_PYTHON" -c "`, closing with a bare `"` after the Python source) — a fix that instead
  substitutes double-quote characters (e.g. a JSON-string-shaped value from `json.dumps`) would
  break at that *outer* bash layer instead. The fix below avoids both failure modes by never
  substituting item-derived text into the command line at all.
  Change the instructions so that, for each grouped new task, `slug`, `title`, `brief` (the theme
  statement), and the concatenated `body` are written first to a fresh temp JSON file via the
  `Write` tool at `.scratch/mill-triage-upsert-<n>.json` (a JSON object with keys `slug`, `title`,
  `brief`, `body`; `<n>` a per-call counter starting at 1, one file per new task), and the
  `python -c` script instead reads that file: `data = json.load(open('.scratch/mill-triage-upsert-<n>.json', encoding='utf-8'))`
  then calls `_client.upsert_task(<wiki_path>, data['slug'], title=data['title'], brief=data['brief'], body=data['body'])`.
  `<wiki_path>` stays as direct literal substitution — it is an agent-resolved filesystem path, never
  derived from source-item text, and carries no injection risk. Add `import json` to the script's
  existing `from wiki import _client` line. Add one explicit sentence after the code block stating
  that the temp file's path — never the item's own `title`/`brief`/`body`/`slug` content — is the
  only piece of item-derived text substituted into the command, so no source item's text can break
  the command's quoting. Apply the identical temp-file substitution to the
  `_client.upsert_tasks_batch(wiki_path, tasks, message=...)` optional path mentioned in the same
  numbered item: its `tasks` list also goes through one temp JSON file, `json.load()`-ed inside the
  same script, never inlined as literal Python source.

  In the same section, numbered item `2. **Fold-ins.**`: the block currently substitutes
  `'<this item per-item block>'` directly as literal text into
  `new_body = (task['body'] or '') + '<this item per-item block>'`. Change this so the per-item
  block (built per the paragraph just above numbered item 1, under the `- Sources: ...` heading) is
  written first to a fresh temp JSON file via the `Write` tool at
  `.scratch/mill-triage-foldin-<n>.json` (a JSON object `{"block": "<this item per-item block>"}`;
  `<n>` a per-call counter starting at 1, one file per fold-in candidate), and the script instead
  does `block = json.load(open('.scratch/mill-triage-foldin-<n>.json', encoding='utf-8'))['block']`
  then `new_body = (task['body'] or '') + block`. Add `import json` to this script too (it currently
  has only `from wiki import _client`). `<target_slug>` stays as direct literal substitution — like
  `<wiki_path>`, it is agent-controlled (an existing task slug already matching
  `[a-z][a-z0-9-]*`, established at Step 3), never derived from arbitrary source-item text. Add one
  sentence after the code block, mirroring the one added to numbered item 1, stating that the temp
  file's path is the only item-derived text on the command line — the item's own block content
  (which embeds `item["title"]`) never appears as literal shell text. Keep the existing closing note
  about `body` vs. `brief` placement unchanged.

  Do not change Steps 1–4, 6, 7, the Rules section, or the frontmatter of this file. Do not change
  the `- Sources: {contract["ref_prefix"]}{item["ref"]} — {item["title"]}` block-building paragraph
  that precedes numbered item 1 — it describes how the block text is assembled (in the agent's own
  reasoning), not how it reaches the shell, and that assembly step is unaffected by this fix.
- **Commit:** `fix(mill-triage-to-tasks): route Step 5 free text through a temp file, not inline shell literals`

## Batch Tests

`verify: null` — this is a prose-only `SKILL.md` instruction change with no runnable surface;
`mill-triage-to-tasks` is loaded and followed by an LLM, not executed as code, so no unit test
applies. Manual verification at implementation time: walk through the corrected Step 5 with an
apostrophe-containing title (e.g. the issue's own
`"Monitor tool: persistent:true doesn't exist, entry-gate waits break"`), confirm the temp JSON
file round-trips the value exactly (one apostrophe in, one apostrophe out via `json.load`), and
confirm the `python -c` command line itself contains only the fixed script text and the temp file's
path — no title/brief/body content — so its syntax no longer depends on what any source item's text
contains.
