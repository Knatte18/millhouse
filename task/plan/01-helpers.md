# Batch: helpers

```yaml
task: (A) — Add /mill-fold skill with active-task guard
batch: helpers
number: 1
cards: 3
verify: c:/Code/millhouse/wts/millhouse/plugins/mill/.venv/Scripts/python.exe c:/Code/millhouse/wts/millhouse/plugins/mill/unit_tests/run-all.py
depends-on: []
```

## Batch Scope

Adds the three foundation pieces every later batch depends on: the `LOCKED_FOLD_PHASES` constant + `append_to_body` helper in `_tasks_md.py`; the `fetch_one` helper (with state-guard) in `_gh_issues.py`; and a new unit-test file `test-fold.py` that covers the `_tasks_md` additions. Tests for `millpy-fold.py` arrive in batch 2 and extend the same file. Batch-local: cards 1 and 2 may be implemented in either order — they touch independent files — but card 3 reads card 1's output, so card 3 runs last. The implementer runs `python plugins/mill/unit_tests/run-all.py` after every card to keep the suite green.

## Cards

### Card 1: Add `LOCKED_FOLD_PHASES` constant and `append_to_body` helper to `_tasks_md.py`

- **Context:**
  - `plugins/mill/unit_tests/test-tasks-md.py`
- **Edits:**
  - `plugins/mill/scripts/_tasks_md.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  - Add a module-level constant `LOCKED_FOLD_PHASES: tuple[str, ...] = ("active", "ready-to-merge", "pr-pending")` immediately below `_VALID_PHASES`. The constant is public (no leading underscore) because two call-sites import it. Add a one-line docstring on the line above: `# Phases whose Home.md entries refuse fold operations (plan is frozen post-spawn).`
  - Add a new public function `append_to_body(text: str, slug: str, line: str) -> str` after `remove_entry`. It locates the heading for `slug` via the existing `_HEADING_RE`, walks forward to either the next `##` heading or end-of-file, isolates the body region (lines between the slug-line and the next heading/EOF), strips trailing blank lines from that region, appends `line` as a new line ensuring exactly one `\n` separates it from the prior body text, and re-emits exactly one trailing blank line before the next `##` heading (or terminates with one trailing newline at EOF).
  - When the body of the target entry is empty (heading + slug line only, no body text), the helper inserts a blank line between the slug-line and the new bullet so the bullet does not visually attach to the slug.
  - On missing slug, raise `ValueError(f"Task with slug {slug!r} not found in Home.md")` — same message shape as `remove_entry`.
  - Add a Google-style docstring matching the style of `append_entry` (Args, Returns, Raises). Reference the `_HEADING_RE` reuse explicitly in the docstring body.
- **Commit:** `feat(tasks-md): add LOCKED_FOLD_PHASES constant and append_to_body helper`

### Card 2: Add `fetch_one` helper to `_gh_issues.py` with `state` field and state guard

- **Context:** none
- **Edits:**
  - `plugins/mill/scripts/_gh_issues.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  - Add a new public function `fetch_one(number: int, *, repo: str | None = None, git_root: Path | None = None) -> dict[str, Any]` after `fetch`. It invokes `gh issue view <number> --repo <owner/repo> --json number,title,body,state,labels,createdAt,comments` via `_subprocess_util.run`, parses the JSON, and applies `_render_body_with_comments` exactly as `fetch` does (single dict, not a list).
  - The `--json` field list MUST include `state` — this is load-bearing because `gh issue view` exits 0 for both OPEN and CLOSED issues.
  - On non-zero exit (404, auth failure), raise `GhError(f"gh issue view #{number} failed: {(result.stderr or '').strip()}")` — same shape as `fetch`'s error path.
  - On JSON parse failure, raise `GhError(f"Failed to parse gh output: {exc}")` — same shape as `fetch`.
  - After a successful exit-0 response and parse, inspect the `state` field. When `state != "OPEN"` raise `GhError(f"issue #{number} is {state}; only OPEN issues can be folded")`. This raise is the load-bearing closed-issue guard.
  - Return the parsed dict including the `state` field (callers may inspect it; tests assert it).
  - Add a Google-style docstring matching `fetch`'s style. State the `state`-field requirement and the closed-issue guard explicitly in the docstring body.
  - Update the module-level docstring `Public API:` block to list `fetch_one` with a one-line description that names the `state` guard.
- **Commit:** `feat(gh-issues): add fetch_one with state guard for single-issue lookup`

### Card 3: Create `test-fold.py` with `_tasks_md` helper coverage

- **Context:**
  - `plugins/mill/scripts/_tasks_md.py`
  - `plugins/mill/unit_tests/test-tasks-md.py`
  - `plugins/mill/unit_tests/run-all.py`
- **Edits:** none
- **Creates:**
  - `plugins/mill/unit_tests/test-fold.py`
- **Deletes:** none
- **Requirements:**
  - Create the file with the same import + sys-path bootstrap pattern as `test-tasks-md.py` (resolve `plugins/mill/scripts/` and add to `sys.path` so flat `import _tasks_md` works). Imports needed for this batch: `_tasks_md`. (Batch 2 card 5 will add more imports.)
  - The file is a plain script with one `def main() -> int:` that executes a sequence of asserts inside `try:` blocks and prints `PASS: <description>` after each block. On `AssertionError` or any other exception, print `FAIL: <description>: <exc>` and return 1. On all-pass return 0. End with `if __name__ == "__main__": sys.exit(main())`. This matches the runner pattern `run-all.py` expects (returncode 0 = pass).
  - Define a module-level fixture string `_HOME_MD_FIXTURE` (a multi-line string constant, not a function) containing at minimum three entries: one `[s]` phase, one `[active]` phase, one `[done]` phase, each with a one-paragraph body.
  - Inside `main()` exercise these cases (each in its own try-block with a PASS/FAIL print):
    - **LOCKED_FOLD_PHASES constant** — assert `_tasks_md.LOCKED_FOLD_PHASES == ("active", "ready-to-merge", "pr-pending")`.
    - **append_to_body inserts before next heading** — call `append_to_body(_HOME_MD_FIXTURE, "<s-phase-slug>", "- Sources: #99 — example")`; assert the new bullet appears as the last non-blank line of that entry's body AND that the next entry's heading is untouched (string-equality check on the substring from the next `##` onward).
    - **append_to_body EOF target** — target the LAST entry in the fixture; assert the new bullet lands above a single trailing newline with no `##` following.
    - **append_to_body empty body** — use a one-entry fixture whose body is empty (heading + slug only, no body text); assert the result inserts a blank line between the slug-line and the new bullet.
    - **append_to_body missing slug** — call with a slug that is not present, wrap in `try: ... except ValueError as exc:`; assert the exception message contains the slug name in repr form (matching `f"Task with slug {slug!r} not found in Home.md"`). The absence of `ValueError` is a test failure.
  - Do NOT add `millpy-fold` tests yet — those arrive in batch 2 card 5 and extend this file's `main()`.
- **Commit:** `test(fold): cover LOCKED_FOLD_PHASES and append_to_body`

## Batch Tests

After every card the implementer runs `c:/Code/millhouse/wts/millhouse/plugins/mill/.venv/Scripts/python.exe c:/Code/millhouse/wts/millhouse/plugins/mill/unit_tests/run-all.py`. Card 1 adds no tests of its own (covered by card 3). Card 2 adds no direct tests (`fetch_one`'s subprocess wrapping is exercised end-to-end in batch 2 card 5 via the `_fetch_one` injection seam). Card 3 produces 5 passing tests in `test-fold.py`. The batch is complete when `run-all.py` reports zero failures and `test-fold.py` shows the 5 cases above as passing.
