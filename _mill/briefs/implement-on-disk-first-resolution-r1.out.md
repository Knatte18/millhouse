All three cards for this batch are complete and committed.

**Summary of work:**

- **Card 3** (`00c00d1f`): `find_active_slug` in `/home/knatte/Code/millhouse/wts/mill-go-dispatch-path-gaps/plugins/mill/scripts/_review_common.py` now skips the wiki-daemon round-trip only when exactly one `_mill/*.active` marker exists AND the current branch (minus `branch_prefix`) matches it. An unconfirmed lone marker still falls through to the daemon first, and is only trusted as a fallback if the daemon call itself raises `MarkerError` — byte-for-byte identical to pre-batch behavior in every other branch.
- **Card 4** (`36c4113c`): `load_task_title` in the same file now tries `status.md`'s YAML `task:` field first (via `_paths.require_status_path` + `_status.read_full`), falling back to `_marker.task_data` on `TaskHubError`/`ValueError`/`KeyError`. Added `import _status`.
- **Card 5** (`c45bab53`): Added three new tests to `/home/knatte/Code/millhouse/wts/mill-go-dispatch-path-gaps/plugins/mill/unit_tests/test-review-common.py` — confirmed-marker daemon-skip, stale-marker-falls-through regression, and status.md daemon-skip for `load_task_title`. All pre-existing tests in that file are unmodified and still pass.

**Verify result:** `PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-review-common.py test-marker.py test-review-plan-flow.py` — `test-review-common.py` and `test-marker.py` pass fully (including all new tests). `test-review-plan-flow.py` fails on 3 pre-existing tests (test24, test25, test28), all failing with "task status file not found" from `millpy-review-plan.py`'s own direct `require_status_path` call in its `--stage prepare`/`full` validator path — a file untouched by this batch. I confirmed via `git log hanf/linux-port-more..HEAD -- <affected files>` that no same-task commit touches `millpy-review-plan.py`/`_paths.py`/`test-review-plan-flow.py`, and by checking out the actual merge-base commit (`0da60f13`, where this task branch diverged) that these exact 3 tests already fail there — this is a genuinely pre-existing condition inherited at branch-point, later fixed independently upstream on `hanf/linux-port-more`'s tip (which has diverged forward with an unrelated commit) but not yet merged into this task branch. Confirmed unrelated to Cards 3-5's diff.

**Card-count self-check:** range start = `61445c96` (via `git log --grep="^mill-go: start batch"`). `git log 61445c96..HEAD --oneline` shows exactly 3 commits matching all 3 declared `### Card N:` `Commit:` messages. 3 of 3 cards committed — all complete, no partial work.

**Working tree:** clean (`git status --porcelain --untracked-files=no` empty).

{"status":"success","commit_sha":"c45bab53","session_id":"4ba84bee-c779-4451-b3b7-8f63ff460f9c","cards_done":[3,4,5]}
