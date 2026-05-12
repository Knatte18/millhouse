# Batch: cli-script

```yaml
task: (A) — Add /mill-fold skill with active-task guard
batch: cli-script
number: 2
cards: 2
verify: c:/Code/millhouse/wts/millhouse/plugins/mill/.venv/Scripts/python.exe c:/Code/millhouse/wts/millhouse/plugins/mill/unit_tests/run-all.py
depends-on: [1]
```

## Batch Scope

Builds `millpy-fold.py` — the CLI that does the actual fold work — and extends `test-fold.py` with full end-to-end coverage of the script using the `_fetch_one` / `_close_with_comment` injection seams introduced in shared decision `test-injection-seams`. The CLI consumes every helper added in batch 1; this batch is the integration layer. Batch-local: the script must follow the fixed operation order from shared decision `fold-operation-order`. The closed-GH-issue guard is exercised here (via injected `fetch_one` that raises `GhError`) — not via batch 1's helper tests.

## Cards

### Card 4: Create `millpy-fold.py` CLI

- **Context:**
  - `plugins/mill/scripts/millpy-add.py`
  - `plugins/mill/scripts/_tasks_md.py`
  - `plugins/mill/scripts/_gh_issues.py`
  - `plugins/mill/scripts/_wiki.py`
  - `plugins/mill/scripts/_sidebar.py`
  - `plugins/mill/scripts/_paths.py`
- **Edits:** none
- **Creates:**
  - `plugins/mill/scripts/millpy-fold.py`
- **Deletes:** none
- **Requirements:**
  - Top-of-file module docstring matching `millpy-add.py`'s style. Document: usage forms, the operation order from shared decision `fold-operation-order`, the close-comment string from shared decision `close-comment-strings`, and the LOCKED_FOLD_PHASES rule from shared decision `locked-fold-phases-tuple`.
  - Imports: `argparse`, `sys`, `pathlib.Path`, plus mill helpers `_gh_issues`, `_sidebar`, `_tasks_md`, `_wiki`, and `from _paths import resolve_git_root, resolve_wiki_path`. The slug-validation step accesses `_tasks_md._SLUG_RE` directly (the existing private regex); the script does not define its own copy, and `import re` is therefore NOT needed.
  - `argparse` setup with one positional subcommand-style argument structure using a mutually-exclusive group:
    - First positional: `target_slug` (required). Validate against `_tasks_md._SLUG_RE` — reuse the existing private regex (test-fold.py also reads from `_tasks_md` so this is consistent).
    - Mutually-exclusive group (required, exactly one):
      - `--issue` / `-i` accepting an int: GH-issue fold path.
      - `--scope` accepting a str: scope-item fold path.
  - Function `def _build_fold_line(issue_dict: dict | None, scope_text: str | None) -> str` returns the bullet text. For GH path: `f"- Sources: #{issue_dict['number']} — {issue_dict['title']}"`. For scope path: `f"- Folded in: {scope_text}"`. Exactly one of the two arguments is non-None — the function raises `AssertionError` if both or neither are supplied (defensive; CLI guarantees this).
  - Function `def main(argv: list[str] | None = None, *, _fetch_one=None, _close_with_comment=None) -> int`:
    1. Parse args. Validate `target_slug` against `_tasks_md._SLUG_RE`; on mismatch `raise SystemExit(f"Invalid slug {target_slug!r}: must match [a-z][a-z0-9-]*")`.
    2. `git_root = resolve_git_root()`. `wiki_path = resolve_wiki_path(git_root)`.
    3. Set `fetch_one_fn = _fetch_one or _gh_issues.fetch_one` and `close_with_comment_fn = _close_with_comment or _gh_issues.close_with_comment`.
    4. Acquire wiki lock via `with _wiki.wiki_lock(wiki_path, args.target_slug):`.
    5. Inside the lock:
       - Read `home_path = wiki_path / "Home.md"`. Raise `SystemExit(f"Wiki not found at {wiki_path}.")` when the file is absent.
       - Parse Home.md via `_tasks_md.parse(home_text)`. Look up the target by `slug`. On miss, `raise SystemExit(f"Slug {target_slug!r} not found in Home.md.")`.
       - **Phase guard:** when the matched `Task.phase` is in `_tasks_md.LOCKED_FOLD_PHASES`, `raise SystemExit(f"Cannot fold into {target_slug!r}: task is [{phase}]. Plan is frozen — scope additions silently invalidate it.")`. No wiki write, no GH side-effect.
       - GH path only: call `issue = fetch_one_fn(args.issue, git_root=git_root)`. Let any `_gh_issues.GhError` propagate to `SystemExit` (catch it and `raise SystemExit(str(exc)) from exc` so the error string reaches the user without a stack trace; the message already contains the issue number and state).
       - GH path only: print the draft fold line to stdout and prompt for confirmation with the numbered list `1) Use as-is (Recommended) / 2) Edit / 3) Abort` via `input()`. On `1`, keep the draft. On `2`, read one line from `input()` and use it as the new issue title (so `_build_fold_line` produces `- Sources: #N — <edited>`). On `3`, `raise SystemExit("Aborted by user.")`. Any other input re-prompts up to 3 times then aborts. The confirmation prompt is suppressed during tests by detecting `not sys.stdin.isatty()`; in non-tty mode the script accepts the draft line as-is without prompting (this matches how `_subprocess_util.run` invokes scripts).
       - Build the line via `_build_fold_line(issue, None)` (GH path) or `_build_fold_line(None, args.scope)` (scope path).
       - Compute `new_home_text = _tasks_md.append_to_body(home_text, target_slug, fold_line)`.
       - Write `home_path.write_text(new_home_text, encoding="utf-8")`.
       - Call `_sidebar.regenerate(wiki_path)` — same call as `millpy-add.py`, even though body-only edits do not change the sidebar.
       - Build commit message: `f"fold #{args.issue} into {target_slug}"` (GH path) or `f"fold scope item into {target_slug}"` (scope path).
       - Call `_wiki.write_commit_push(wiki_path, ["Home.md", "_Sidebar.md"], commit_msg, slug=target_slug)`.
    6. **After the wiki commit succeeds** (i.e. after the `with` block exits successfully), GH path only: call `close_with_comment_fn(args.issue, f"Folded into wiki task: {target_slug}", git_root=git_root)`. Use the exact close-comment string from shared decision `close-comment-strings`. Wrap the call in `try: close_with_comment_fn(...) except _gh_issues.GhError as exc: print(f"Warning: wiki commit succeeded but issue close failed: {exc}", file=sys.stderr)` and **fall through** — do not re-raise. The script still returns 0 because the wiki commit (the load-bearing side-effect) has already succeeded; the operator can close the issue manually.
    7. `print(f"Folded into wiki task: {target_slug!r}")` and `return 0`.
  - Module footer: `if __name__ == "__main__": sys.exit(main())`.
  - Add inline guards: if `args.issue is not None and args.scope is not None`, argparse's mutually-exclusive group already rejects this; no extra check needed.
- **Commit:** `feat(mill-fold): add millpy-fold.py CLI`

### Card 5: Extend `test-fold.py` with `millpy-fold.main` end-to-end coverage

- **Context:**
  - `plugins/mill/scripts/millpy-fold.py`
  - `plugins/mill/scripts/_tasks_md.py`
  - `plugins/mill/scripts/_gh_issues.py`
  - `plugins/mill/scripts/_wiki.py`
  - `plugins/mill/scripts/_paths.py`
  - `plugins/mill/scripts/_sidebar.py`
  - `plugins/mill/unit_tests/test-tasks-md.py`
  - `plugins/mill/unit_tests/run-all.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-fold.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  - `run-all.py` invokes each `test-*.py` as a subprocess; there is no `pytest` discovery and no fixture machinery. The new test cases live inside the existing `main()` `try`-block sequence from card 3, each in its own sub-`try` with a PASS/FAIL print.
  - Add module-level helpers (above `main()`):
    - `def _setup_tempfile_wiki(home_md_content: str) -> tempfile.TemporaryDirectory` returns a `TemporaryDirectory` whose `.name` path holds a `Home.md` and `_Sidebar.md`, initialised as a real git repo (`git init`, configure `user.email` / `user.name` via env, initial `git add` + `git commit -m init`). The caller is responsible for `cleanup()`. Subprocess calls use `subprocess.run(..., check=True)` to fail fast on git errors. The "no real wiki" rule from discussion's `### testing-approach` allows a throwaway on-disk git repo — it forbids real wiki clones, not real `git init` directories.
    - `def _patch_resolve_paths(wiki_path: Path) -> tuple[callable, callable]` swaps `_paths.resolve_git_root` and `_paths.resolve_wiki_path` for closures that return `wiki_path`. The two production signatures differ: `resolve_git_root()` takes no arguments; `resolve_wiki_path(git_toplevel)` takes one positional `Path`. The replacements must therefore use different shapes: `_paths.resolve_git_root = lambda: wiki_path` and `_paths.resolve_wiki_path = lambda _git_top: wiki_path` (the second closure accepts and ignores its argument so the `millpy-fold.py` call `resolve_wiki_path(git_root)` does not raise `TypeError`). Returns the original callables so the caller can restore them via `try`/`finally`. Direct module-attribute reassignment — no monkeypatch fixture.
    - `def _make_fake_fetch_one(state: str = "OPEN", title: str = "fake issue", number: int = 42)` returns a callable that — when invoked with the matching `number` — returns a dict `{"number": number, "title": title, "body": "", "state": state, "labels": [], "createdAt": "2026-05-12T00:00:00Z"}` when `state == "OPEN"`, or raises `_gh_issues.GhError(f"issue #{number} is {state}; only OPEN issues can be folded")` otherwise. The callable accepts `**kwargs` and ignores them (production signature has `*, repo=None, git_root=None`).
    - `def _make_fake_close_with_comment() -> tuple[callable, list[tuple[int, str]]]` returns a `(callable, captured_calls)` pair. The callable appends `(number, comment)` to `captured_calls` and returns None. Accepts and ignores `**kwargs`.
    - `def _suppress_stdin_isatty()` — monkey-patches `sys.stdin.isatty` to return False so the script's confirmation prompt is skipped (per card 4 requirement). Returns the original `isatty` for restoration.
  - Add to `main()` (continuing the try-block sequence from card 3) the following test cases. Each test sets up a fresh `tempfile.TemporaryDirectory` via `_setup_tempfile_wiki(...)`, calls `_patch_resolve_paths(...)` in a `try`/`finally`, and asserts behavior. `import millpy_fold` (or `import importlib; millpy_fold = importlib.import_module("millpy-fold")` if the hyphen blocks direct import — implementer chooses).
    - **locked phase active refused** — Home.md target with `[active]`; call `millpy_fold.main([target, "--scope", "x"])`; assert `SystemExit` is raised; assert post-Home.md == pre-Home.md.
    - **locked phase ready-to-merge refused** — same shape, `[ready-to-merge]`.
    - **locked phase pr-pending refused** — same shape, `[pr-pending]`.
    - **unmarked target accepts scope fold** — phase `None`; call `main([target, "--scope", "edge case X"])`; assert Home.md gains `- Folded in: edge case X` as the last non-blank line of the target body.
    - **spawn-ready target accepts scope fold** — phase `s`; assert the bullet is appended.
    - **done phase accepts fold** — phase `done`; assert the bullet is appended.
    - **abandoned phase accepts fold** — phase `abandoned`; assert the bullet is appended.
    - **missing slug errors** — slug not in Home.md; assert `SystemExit`; assert no mutation.
    - **invalid slug format errors** — pass `target_slug="Invalid-Slug"` (capital letter); assert `SystemExit` whose message contains `Invalid slug`.
    - **closed GH issue refused** — inject `_fetch_one=_make_fake_fetch_one(state="CLOSED")` and `_close_with_comment=_make_fake_close_with_comment()[0]` via the `main()` kwargs; pass `--issue 42`; assert `SystemExit`; assert no Home.md mutation; assert captured close list is empty.
    - **open GH issue accepted** — inject `_fetch_one=_make_fake_fetch_one(state="OPEN", title="bug X", number=42)` and `_close_with_comment=...`; pass `--issue 42`; assert Home.md gains `- Sources: #42 — bug X`; assert captured close list equals `[(42, f"Folded into wiki task: {target}")]`.
    - **wiki commit failure skips GH close** — inject `_fetch_one=_make_fake_fetch_one(state="OPEN")` and `_close_with_comment=...`; ALSO swap `_wiki.write_commit_push` for a function that raises `RuntimeError("simulated push failure")`; assert either `SystemExit` or `RuntimeError` propagation; assert captured close list is empty (close-with-comment runs strictly after the wiki commit; commit failure means no close).
  - Test count after this card: 5 (batch 1 card 3) + 12 (batch 2 card 5) = 17 PASS lines. A single FAIL anywhere returns 1 from `main()` and `run-all.py` records the failure.
- **Commit:** `test(fold): cover millpy-fold.py main path including locked-phase guard, closed-issue refusal, and commit-failure isolation`

## Batch Tests

The batch's `verify:` runs the full unit-test suite. After card 4 the implementer can run the suite to confirm card 3's earlier tests still pass and card 4 introduced no import-time errors. After card 5 the suite passes with all 5 (batch 1) + 12 (batch 2 card 5) = 17 `test_*` functions green. A failing `test_locked_fold_phases_constant`, `test_closed_gh_issue_refused`, or any locked-phase-refused test is a release blocker — these are the load-bearing checks per discussion's `### testing-approach` section.
