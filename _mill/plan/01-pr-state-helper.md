# Batch: pr-state-helper

```yaml
task: "Handle pre-closed and pre-merged PRs gracefully in mill-merge"
batch: pr-state-helper
number: 1
cards: 1
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-pr-state.py
depends-on: []
```

## Batch Scope

Deliver the new shared PR-state helper `plugins/mill/scripts/_pr_state.py` and
its unit tests `plugins/mill/unit_tests/test-pr-state.py`. This is the testable
core of the task; batches 2 and 3 consume `resolve_pr_state` but add no new
logic of their own. The external interface the later batches depend on is the
function `resolve_pr_state(branch: str, cwd) -> dict` returning the normalized
state dict described in `## Shared Decisions` (overview). The helper and its
tests live in one card because the batch `verify:` runs `test-pr-state.py`, which
cannot pass until both the test and the module under test exist.

## Cards

### Card 1: Create `_pr_state.py` and its unit tests

- **Context:**
  - `plugins/mill/scripts/_subprocess_util.py`
  - `plugins/mill/scripts/millpy-cleanup.py`
  - `plugins/mill/unit_tests/test-cleanup.py`
- **Edits:** none
- **Creates:**
  - `plugins/mill/scripts/_pr_state.py`
  - `plugins/mill/unit_tests/test-pr-state.py`
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  - Create `plugins/mill/scripts/_pr_state.py` defining
    `resolve_pr_state(branch: str, cwd) -> dict`. It calls
    `_subprocess_util.run(["gh", "pr", "list", "--head", branch, "--state",
    "all", "--json", "state,mergeCommit,number,url"], cwd=cwd)` — note: NO
    `--jq` argument (mirror the existing argv in
    `millpy-cleanup.py:_apply_pr_reap_record` but drop `--jq ".[0]"` and add
    `url` to the `--json` list).
  - Return shape: a dict with keys `state` (one of the literal strings
    `"merged"`, `"open"`, `"closed"`, `"none"`), `number` (int or `None`), `url`
    (str or `None`), and `merge_commit` (the raw gh `mergeCommit` object as a
    dict, or `None`). `merge_commit` must remain the object, NOT a flattened
    `.oid` string, so `_apply_pr_reap_record`'s
    `(merge_commit or {}).get("oid")` fallback keeps working (batch 2).
  - Tolerant `"none"` path: return
    `{"state": "none", "number": None, "url": None, "merge_commit": None}` when
    any of these hold — `result.returncode != 0`; `result.stdout.strip()` is
    empty; `gh` raises (wrap the `_subprocess_util.run` call so a raised
    exception, e.g. `FileNotFoundError` when `gh` is absent, is caught and
    mapped to `"none"`); or `json.loads` raises / yields a non-list /
    yields an empty list. No exception ever propagates out of
    `resolve_pr_state`.
  - Precedence: `json.loads(result.stdout)` yields a list of PR objects. Map each
    object's uppercase `state` (`"MERGED"` / `"OPEN"` / `"CLOSED"`) and apply
    precedence MERGED > OPEN > CLOSED: if any object is `MERGED` return that one
    normalized to `"merged"`; else if any is `OPEN` return `"open"`; else if any
    is `CLOSED` return `"closed"`; else `"none"`. Populate `number`, `url`,
    `merge_commit` from the winning object (`obj.get("number")`,
    `obj.get("url")`, `obj.get("mergeCommit")`).
  - Module + function docstrings per Python conventions; ASCII-only any stdout;
    no `cwd` defaulting (caller always passes the git/hub root).
  - Create `plugins/mill/unit_tests/test-pr-state.py` following the harness style
    of `test-cleanup.py` (top-level `sys.path.insert` to `scripts/`,
    `importlib`/direct import of `_pr_state`, `unittest.mock.patch` on
    `_pr_state._subprocess_util.run` returning `MagicMock(returncode=..,
    stdout=.., stderr=..)`, `print("PASS ...")` per case, runnable as
    `__main__`). Cover: single `MERGED` array -> `merged` with `number`/`url`/
    `merge_commit` populated; single `OPEN` -> `open`; single `CLOSED` -> `closed`;
    empty array `[]` and empty stdout -> `none`; `returncode != 0` -> `none`;
    `gh`-missing (`run` raises `FileNotFoundError`) -> `none` with no exception;
    multi-PR `[CLOSED, MERGED]` -> `merged` (stale CLOSED must not mask MERGED);
    multi-PR `[CLOSED, OPEN]` -> `open` (superseded CLOSED must not mask OPEN);
    malformed JSON (`stdout="{not json"`) -> `none`. Mock stdout must be the gh
    **array** form (e.g. `'[{"state":"MERGED","mergeCommit":{"oid":"abc"},
    "number":42,"url":"https://x/1"}]'`) since the helper parses a list.
  - The test file must be discoverable by `run-all.py --only test-pr-state.py`
    (live in `plugins/mill/unit_tests/`, named `test-pr-state.py`).
- **Commit:** `feat(mill): add _pr_state helper with normalized PR-state precedence`

## Batch Tests

`verify` runs `run-all.py --only test-pr-state.py`, which executes the new
`test-pr-state.py`. That file is the sole runnable surface introduced by this
batch and fully exercises `resolve_pr_state` over mocked `gh` output (every
state, the precedence rules, and all `"none"` fallbacks). No real `gh`/git is
invoked — `_subprocess_util.run` is mocked.
