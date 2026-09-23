{"status":"success","commit_sha":"5e2de5913cb3297d348bfb918d64ad76d888c122","session_id":"46ac5e77-0b5d-4e2a-8c7a-30e2501c4e2d","cards_done":[3]}

Batch status-path-coercion (02-status-path-coercion.md), 1 of 1 card committed.

Card 3 — coerce str/PathLike status_path in _status helpers:
- /home/hanf/Code/millhouse/wts/mill-plan-verify-implement-misc-r3/plugins/mill/scripts/_status.py: replaced `_require_path` (reject-only guard) with `_as_path` (coerces Path/str/os.PathLike to Path; raises TypeError naming the calling function for anything else). Added `import os`. Rebound `status_path = _as_path(status_path, "<fn>")` as the first statement in every public function that previously called `_require_path`, plus `resume_batch` (which had no `_require_path` call before). Widened every such function's `status_path` annotation to `Path | str` and added a one-sentence coercion note to each docstring's Args entry. Left the private `_write_batches` helper's annotation as plain `Path` (per plan) since it only ever receives an already-coerced Path from its public caller.
- /home/hanf/Code/millhouse/wts/mill-plan-verify-implement-misc-r3/plugins/mill/unit_tests/test-status.py: replaced the old "str-input-raises-TypeError" (#597) regression block with coercion tests — `append_phase`, `update_field`, `set_blocked`, `read_status` called with `str(path)` produce identical effects/results to the `Path` form; a local `_FakePathLike` (non-str `os.PathLike`) works for `append_phase`; `append_phase(None, ...)` and `append_phase(123, ...)` still raise `TypeError` naming `append_phase`. Updated the leading comment to reference GitHub #1114 and the coercion contract.

Verify: `PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-status.py` — PASS (all tests green).

`grep -rn "_require_path" plugins/` returns nothing, confirming the full call-site migration.

Ran `uvx ruff check` on both changed files: found 6 pre-existing findings (import-order was mine and is fixed; the other 5 — TRY203/RUF059/TRY004 — were confirmed present in `main`'s copy of `_status.py` via `git show main:plugins/mill/scripts/_status.py`, so left untouched as out of this batch's scope).

Working tree clean after commit (`git status --porcelain --untracked-files=no` empty). Commit pushed to `hanf/mill-plan-verify-implement-misc-r3`.
