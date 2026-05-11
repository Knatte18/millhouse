# Batch: anti-pattern-walker-test

```yaml
task: 49 (A) — Defensive guards mot cwd-inni-wiki kjedereaksjoner
batch: anti-pattern-walker-test
number: 2
cards: 1
verify: python plugins/mill/unit_tests/run-all.py
depends-on: []
```

## Batch Scope

Adds one new unit test, `plugins/mill/unit_tests/test-no-wiki-cwd.py`, that walks the mill and codeguide plugin source trees and fails on any occurrence of the four documented `cd .wiki` / `os.chdir(.*wiki)` / `cwd=.*wiki` anti-patterns. The test prevents the 2026-05-11 incident from regressing — even if a future LLM thread improvises a wiki-cwd shortcut into a script or skill, this test catches it before commit.

The walker uses `re.search` per line (not `re.match`) and skips the test file itself to avoid self-match on the regex sources. Documentation files that intentionally quote the anti-pattern are exempted via a small hardcoded allowlist (CLAUDE.md plus the eight SKILL.md files updated in batch 3). The current codebase has no anti-pattern matches anywhere; the test passes today and stays passing as long as nobody introduces a regression.

The walker is independent of batch 1 (no code dependency) and independent of batch 3 (the allowlist preempts batch 3's additions — the test passes whether batch 3 has run or not).

Batch-local decision: allowlist entries are file paths relative to the worktree root, compared after normalising forward/backslashes. The test is run from the worktree root via the existing `run-all.py` runner, so relative-path comparison is reliable.

## Cards

### Card 7: Create the anti-pattern walker test

- **Context:**
  - `plugins/mill/unit_tests/test-paths.py`
  - `plugins/mill/unit_tests/test-sibling.py`
  - `plugins/mill/unit_tests/run-all.py`
- **Edits:** none
- **Creates:**
  - `plugins/mill/unit_tests/test-no-wiki-cwd.py`
- **Deletes:** none
- **Requirements:** Create `plugins/mill/unit_tests/test-no-wiki-cwd.py` as a standalone test file matching the conventions of the existing `test-paths.py` and `test-sibling.py`: a `main() -> int` function called from `if __name__ == "__main__":`, returning 0 on success and 1 on failure, printing `PASS:`/`FAIL:` lines as it goes. Specifics:
    1. Resolve the hub root via `HUB = Path(__file__).resolve().parent.parent.parent.parent` (same idiom as the existing tests).
    2. Walk these four directories: `HUB / "plugins" / "mill" / "scripts"`, `HUB / "plugins" / "mill" / "skills"`, `HUB / "plugins" / "codeguide" / "scripts"`, `HUB / "plugins" / "codeguide" / "skills"`. For each, recursively glob files ending in `.py`, `.md`, or `.sh`.
    3. Skip the test file itself (`Path(__file__).resolve()`) to avoid self-match.
    4. Skip files in the allowlist. Allowlist entries (paths relative to `HUB`, forward-slash form): `plugins/mill/skills/mill-start/SKILL.md`, `plugins/mill/skills/mill-plan/SKILL.md`, `plugins/mill/skills/mill-go/SKILL.md`, `plugins/mill/skills/mill-merge/SKILL.md`, `plugins/mill/skills/mill-wiki-push/SKILL.md`, `plugins/mill/skills/mill-setup/SKILL.md`, `plugins/mill/skills/mill-claim/SKILL.md`, `plugins/mill/skills/mill-spawn/SKILL.md`. Compare each candidate file's path relative to `HUB`, normalised to forward slashes (`relative.as_posix()`), against the allowlist set. (Do not list `CLAUDE.md` — it lives at the repo root and is outside the walker's four scoped directories, so the entry would be unreachable.)
    5. Compile these five regexes, each marked with a one-word name in the test output: `cd-wiki-junction` → `r"cd \.wiki\b"`, `cd-wiki-token` → `r"cd <wiki[^>]*>"`, `os-chdir-wiki` → `r"os\.chdir\([^)]*wiki"`, `subprocess-cwd-wiki` → `r"cwd=[^,)]*wiki"`, `cd-wiki-relative` → `r"cd \.\./[^\s]*wiki/"`.
    6. For every file walked that is not allowlisted and not the test itself, read it as text (`encoding="utf-8"`, ignore decode errors via `errors="replace"`), iterate `for lineno, line in enumerate(text.splitlines(), 1):`, and run `re.search` for each regex. Accumulate findings as `(relative_path, lineno, regex_name, line.rstrip())` tuples in a list.
    7. After the walk, if the findings list is empty, print `PASS: no wiki-cwd anti-patterns in scripts/ or skills/ across mill + codeguide` and return 0. Otherwise, print one `FAIL:` line per finding (`{rel_path}:{lineno}: {regex_name}: {line}`) and return 1.
    8. The test must NOT add allowlist entries for any code file. Adding a code file would defeat the test's purpose. Hardcode the documentation allowlist verbatim; do not load it from config.
    9. Add a module-level docstring summarising what the test prevents (a one-liner pointing at the 2026-05-11 incident and the `## Wiki access` section of CLAUDE.md is enough).
- **Commit:** `test(no-wiki-cwd): prevent cd .wiki / os.chdir(wiki) / cwd=wiki regressions`

## Batch Tests

Running `python plugins/mill/unit_tests/run-all.py` from the worktree root picks up the new file via the runner's auto-discovery and runs it. The test must print one `PASS:` line and exit 0 on the current codebase. The test exits 1 (and the suite fails) if any non-allowlisted file in the four walked directories matches one of the five regexes.
