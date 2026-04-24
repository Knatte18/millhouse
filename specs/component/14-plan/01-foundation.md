# Batch: foundation

```yaml
task: junction-rule enforcement + _paths.py consolidation
batch: foundation
cards: 2
verify: python plugins/mill/unit_tests/test-paths.py
depends-on: []
```

## Batch Scope

Create `plugins/mill/scripts/_paths.py` — the single resolver surface for git-root, wiki, and sibling paths. Add a unit test that covers every branch: the `paths.wiki:` override, the sibling default, the git-root detection, and the error path when neither config nor wiki exists.

No call-sites are touched in this batch. Batch 02 does the migration.

## Cards

### Card 1: `plugins/mill/scripts/_paths.py`

- **Reads:** `plugins/mill/scripts/_sibling.py`, `plugins/mill/scripts/mill-add.py` (the existing `_resolve_git_root` / `_resolve_wiki_path` for reference), `plugins/mill/scripts/mill-spawn.py`, `plugins/mill/scripts/mill-list.py`, `plugins/mill/scripts/_subprocess_util.py` (pattern for git subprocess calls).
- **Modifies:** (none)
- **Creates:** `plugins/mill/scripts/_paths.py`
- **Requirements:**
  - Module docstring explains: "Single home for path resolution in the mill plugin. Collects helpers that turn (git context, config) into concrete paths. Scripts MUST use these helpers instead of reaching for `.millhouse/wiki` or other junctions directly — junctions are IDE/terminal convenience, not a code contract. See CLAUDE.md `## Path invariants`."
  - `from _sibling import resolve_path` — re-export, do NOT duplicate the function.
  - `def resolve_git_root() -> Path:`
    - Runs `git rev-parse --show-toplevel` via `_subprocess_util.run` (match the existing pattern in `mill-spawn._resolve_git_root`).
    - Returns `Path(result.stdout.strip())`.
    - Raises `SystemExit` with the existing message `"Not in a git repository: {stderr!r}"` on non-zero exit. Keep CLI ergonomics.
  - `def resolve_wiki_path(git_toplevel: Path) -> Path:`
    - Reads `<git-toplevel>/.millhouse/config.local.yaml` if it exists. Parses via `yaml.safe_load`. Looks for `paths.wiki:` (nested — `(cfg.get("paths") or {}).get("wiki")`).
    - If the override is set and non-empty: if absolute, return as-is; if relative, resolve against `git_toplevel`.
    - Otherwise: return `resolve_path("wiki", git_toplevel)`.
    - Does NOT check for on-disk existence — that's the caller's concern (some callers may want to know the EXPECTED path for error messages before the wiki exists, e.g. mill-setup's Phase 3).
  - `__all__ = ["resolve_path", "resolve_git_root", "resolve_wiki_path"]` so the re-export is intentional.
  - No `if __name__ == "__main__":` block — helper-only, per the repo convention for `_*.py` files (see CLAUDE.md "Repo layout pointers").
- **Commit:** `feat(paths): add _paths.py — resolve_git_root, resolve_wiki_path, re-exports resolve_path`

### Card 2: `plugins/mill/unit_tests/test-paths.py`

- **Reads:** `plugins/mill/scripts/_paths.py` (post-Card-1), `plugins/mill/unit_tests/test-sibling.py` (pattern), `plugins/mill/unit_tests/test-worktree.py` (tempfile fixture pattern).
- **Modifies:** (none)
- **Creates:** `plugins/mill/unit_tests/test-paths.py`
- **Requirements:**
  - Test `resolve_path` re-export: a single assertion that `_paths.resolve_path is _sibling.resolve_path` (identity check — confirms no accidental duplication).
  - Test `resolve_wiki_path` sibling default (hub-form): fixture `<tmp>/hub/` with no `.millhouse/`, assert result is `<tmp>/wiki`.
  - Test `resolve_wiki_path` sibling default (prefix-form): fixture `<tmp>/foo/`, assert result is `<tmp>/foo.wiki`.
  - Test `resolve_wiki_path` absolute override: fixture `<tmp>/hub/.millhouse/config.local.yaml` with `paths:\n  wiki: /elsewhere/wiki`, assert result is `Path("/elsewhere/wiki")`.
  - Test `resolve_wiki_path` relative override: same fixture but `paths.wiki: ../custom-wiki`, assert result is `<tmp>/custom-wiki` (relative to git-toplevel).
  - Test `resolve_wiki_path` with an empty `paths:` block or missing key: falls through to sibling default (does NOT crash).
  - Test `resolve_wiki_path` with malformed YAML: currently undefined — document the chosen behaviour (propagate the `yaml.YAMLError` — mill-setup handles surfacing). One test confirming the exception propagates.
  - `resolve_git_root` is NOT unit-tested here — it's a thin wrapper around `git rev-parse` and the integration tests already exercise it. Add an inline comment at the top of `test-paths.py`: `# resolve_git_root is exercised end-to-end by test-spawn.py and test-merge.py.` so reviewers don't flag the gap.
  - Follow the `test-sibling.py` pattern: `main()` function with `try/except AssertionError`, PASS prints per check, exit 0/1.
- **Commit:** `test(paths): unit tests for _paths.resolve_wiki_path + re-export identity`

## Batch Tests

`python plugins/mill/unit_tests/test-paths.py` must pass on its own. The full `run-all.py` sweep happens at task-level verify. Batch 02 depends on this batch passing so the migration is not flying blind.
