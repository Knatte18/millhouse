HEAD is c91bcd7f... differing from baseline 3c8768fd..., and no tracked modifications remain.

Summary of work:
- Reviewed the single finding in `/home/knatte/Code/millhouse/wts/mill-go-base-orchestration-robustness-gaps/_mill/reviews/20260918-193414-code-review-r1.md` ([NIT:consistency] stale Public API docstring in `_status.py`), verified it factually accurate against the actual function definitions, and fixed it in `/home/knatte/Code/millhouse/wts/mill-go-base-orchestration-robustness-gaps/plugins/mill/scripts/_status.py` (added `resume_batch` and the `latest=False` keyword to `phase_entry_timestamp`'s docstring index).
- Confirmed pre-existing ruff findings in `_status.py` are unrelated to this edit (verified against `git show HEAD:...` baseline) and left them untouched, per scope discipline.
- Committed as c91bcd7f and pushed.
- Ran all 7 batch `verify:` commands in order; all passed.

{"status":"success","commit_sha":"c91bcd7f235a5d483da65633be8c2212f271a623","session_id":"d96538ce-4d20-49a3-981b-9daaa1b4dc73"}

{"status":"success","commit_sha":"c91bcd7f235a5d483da65633be8c2212f271a623","session_id":"d96538ce-4d20-49a3-981b-9daaa1b4dc73"}
