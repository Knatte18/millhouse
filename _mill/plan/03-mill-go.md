# Batch: mill-go skill fix

```yaml
task: Audit and clean up stale V2 references
batch: mill-go skill fix
number: 3
cards: 2
verify: "PYTHONPATH= bash -c \"! grep -q '_wiki[.]\\|_tasks_md[.]\\|WikiHealthError' plugins/mill/skills/mill-go/SKILL.md\""
depends-on: []
```

## Batch Scope

`mill-go/SKILL.md` is the most complex V2-to-V3 migration due to the `_wiki.WikiHealthError` try/except pattern that must become a conditional check. The file also has `_wiki.sync_pull`, `_wiki.wiki_lock`, `_tasks_md.set_phase_at`, `_wiki.write_commit_push`, and a Board-discipline footer. Two cards handle the natural splits: Entry changes (sync_pull + both health_check try/except blocks) and Handoff changes (wiki_lock + set_phase_at + write_commit_push + Board discipline). The verify grep asserts zero `_wiki.`, `_tasks_md.`, and `WikiHealthError` hits.

## Cards

### Card 10: mill-go — delete sync_pull and convert health_check try/except to conditional (both occurrences)

- **Context:**
  - `.scratch/v3-wiki-cheatsheet.md`
  - `plugins/mill/scripts/wiki/_client.py`
- **Edits:**
  - `plugins/mill/skills/mill-go/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  In Entry step 2 (line 24): remove the phrase `Sync the wiki clone: \`_wiki.sync_pull(wiki_path, slug=slug)\`.` from the sentence. Delete line 25: `` `signature: _wiki.sync_pull(wiki_path: Path, *, slug: str) -> None` ``

  First health_check block (lines 113–117): replace the try/except block:
  ```python
  hub_root = _paths.resolve_git_root()
  try:
      _wiki.health_check(hub_root)
  except _wiki.WikiHealthError as e:
      print(f'[mill-go] wiki health check failed: {e}', file=sys.stderr)
      raise SystemExit(1)
  ```
  with the conditional form using `_client.health_check(wiki_path)` (note: `wiki_path` not `hub_root` — `_client.health_check` takes the wiki clone path, not the hub):
  ```python
  if not _client.health_check(wiki_path):
      print('[mill-go] wiki daemon health check failed', file=sys.stderr)
      raise SystemExit(1)
  ```
  Add `from wiki import _client` to the import context if not already present in the pseudocode block.

  Second health_check block (lines 336–341): identical replacement. The block currently reads:
  ```python
  hub_root = _paths.resolve_git_root()
  try:
      _wiki.health_check(hub_root)
  except _wiki.WikiHealthError as e:
      print(f'[mill-go] wiki health check failed: {e}', file=sys.stderr)
      raise SystemExit(1)
  ```
  Replace with same conditional form as above.
- **Commit:** `docs(mill-go): remove sync_pull and convert health_check try/except to conditional`

### Card 11: mill-go — replace wiki_lock/set_phase_at/write_commit_push block and update Board discipline

- **Context:**
  - `.scratch/v3-wiki-cheatsheet.md`
- **Edits:**
  - `plugins/mill/skills/mill-go/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  Replace the Handoff code block (lines 473–481). The current block is:
  ```python
  home_path = wiki_path / "Home.md"
  with _wiki.wiki_lock(wiki_path, slug):
      _tasks_md.set_phase_at(home_path, slug, "ready-to-merge")
      _wiki.write_commit_push(wiki_path, ["Home.md"], f"task: ready-to-merge {slug}", slug=slug)
  ```
  followed by three signature lines for `_tasks_md.set_phase_at`, `_wiki.wiki_lock`, `_wiki.write_commit_push`.
  Replace the entire block (code fences + signature lines) with:
  ```bash
  PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" "$MILL_PYTHON" -c "
  from pathlib import Path; import _paths
  from wiki import _client
  wiki_path = _paths.resolve_wiki_path(_paths.resolve_git_root())
  _client.set_phase(wiki_path, '<slug>', 'ready-to-merge')
  "
  ```

  In the Board discipline section (line 505), replace the bullet:
  `- Home.md writes (the Handoff \`[done]\` flip) go through \`_wiki.write_commit_push(..., slug=...)\` inside a \`with _wiki.wiki_lock(wiki_path, slug):\` block. The wiki helpers acquire the lock internally; the context manager makes the read-modify-write atomic.`
  with:
  `- Wiki phase mutations (the Handoff \`[ready-to-merge]\` flip) go through \`_client.set_phase(wiki_path, slug, "ready-to-merge")\`. The daemon serializes all writes and pushes automatically.`
- **Commit:** `docs(mill-go): replace wiki_lock/set_phase_at/write_commit_push block`

## Batch Tests

`mill-go/SKILL.md` is pure documentation. The verify command greps for `_wiki[.]`, `_tasks_md[.]`, and `WikiHealthError` and asserts zero matches. `WikiHealthError` is included because it would remain if the try/except conversion were only partial.
