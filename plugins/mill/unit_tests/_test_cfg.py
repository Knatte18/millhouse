"""
Baseline cfg dict builder for unit tests using the NEW roles: schema.

Provides make_minimal_cfg(**overrides) that returns a cfg dict shaped for
the post-batch-2-flip schema (roles: replaces review:). Tests that previously
constructed cfg dicts inline should switch to this helper to avoid repeating
the boilerplate and to stay in sync as the schema evolves.
"""
from __future__ import annotations


def _deep_merge(base: dict, override: dict) -> dict:
    """Recursively merge override into base. override wins on conflict."""
    result = base.copy()
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def make_minimal_cfg(**overrides) -> dict:
    """Return a baseline cfg dict using the new roles: schema.

    All reviewer slots reference "test_stub" so tests that use
    _reviewer_test_stub.seed() work without a real reviewers.yaml.
    The **overrides kwargs are deep-merged into the baseline.
    """
    baseline: dict = {
        "roles": {
            "discussion-review": {
                "holistic": {"rounds": 2, "reviewer": "test_stub"},
            },
            "plan-review": {
                "batch": {"rounds": 3, "reviewer": "test_stub"},
                "holistic": {"rounds": 3, "reviewer": "test_stub"},
            },
            "code-review": {
                "batch": {"rounds": 3, "reviewer": "test_stub"},
                "holistic": {"rounds": 1, "reviewer": "test_stub"},
                "diff_scope_threshold": 0.25,
            },
            "implementer": {
                "self_fix_rounds": 0,
            },
        },
        "paths": {
            "discussion_file": "task/discussion.md",
            "plan_dir": "task/plan/",
            "reviews_dir": "task/reviews/",
        },
        "llm": {
            "bulk_timeout": 600,
            "tool_use_timeout": 900,
            "holistic_timeout": 1800,
            "implementer_timeout": 1800,
        },
        "pipeline": {
            "auto_merge": False,
            "auto_report": False,
            "autonomous_mode": False,
        },
        "notify": {
            "backend": "stdout",
        },
        "groom": {
            "brevity-threshold-lines": 5,
            "brevity-threshold-chars": 500,
        },
        "merge": {},
        "repo": {
            "short_name": "TEST",
        },
        "spawn": {
            "branch_prefix": "test/",
        },
    }
    if overrides:
        return _deep_merge(baseline, overrides)
    return baseline
