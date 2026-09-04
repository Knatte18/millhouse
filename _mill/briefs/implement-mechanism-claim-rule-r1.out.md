Working tree is clean (no tracked modifications). 1 of 1 card committed — Card 1 fully done, verify passed.

I implemented the batch's single card: added the mechanism-claim source-verification rule to both plan-review templates and covered it with a new test.

Files changed:
- `/home/knatte/Code/millhouse/wts/review-plan-verdict-envelope-model-bugs/plugins/mill/templates/review-plan-holistic.md`
- `/home/knatte/Code/millhouse/wts/review-plan-verdict-envelope-model-bugs/plugins/mill/templates/review-plan-batch.md`
- `/home/knatte/Code/millhouse/wts/review-plan-verdict-envelope-model-bugs/plugins/mill/unit_tests/test-review-templates.py`

Commit: `8f2f4c70936eec6851932c59d2ff3e5ecddcf8ec` — `docs(review-plan): require source-verified mechanism claims in plan-review templates (#949)`

Verify command passed: `PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-review-templates.py` — all 7 tests pass, including the new `test_plan_mechanism_claim_rule_present`.

{"status":"success","commit_sha":"8f2f4c70936eec6851932c59d2ff3e5ecddcf8ec","session_id":"4a657dfd-333c-4d6e-8a76-8ff6b5b52d6f","cards_done":[1]}
