"""Smoke test for _llm_claude.run_bulk + run_tool_use against a tiny review task.

Local-dev only. Requires `claude` in PATH. Exits 0 on success, 1 on failure.

Run from hub root:
    python plugins/mill/integration_tests/smoke-llm-claude.py
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

HUB = Path(__file__).parent.parent
SCRIPTS = HUB / "scripts"
sys.path.insert(0, str(SCRIPTS))

import _llm_claude


PROMPT_BULK = """You are a review assistant. Evaluate the file content below.
If the file is a valid Python function definition, return verdict APPROVE.
Otherwise return verdict REQUEST_CHANGES.

Respond ONLY with a short YAML frontmatter block and a one-line summary. Exact format:

---
verdict: APPROVE
---

Looks good.

Do NOT include anything else. Do NOT use any tools.

--- FILE CONTENT ---

def greet(name: str) -> str:
    return f"Hello, {name}!"

--- END FILE CONTENT ---
"""


PROMPT_TOOL = """You are a review assistant with Read/Grep/Glob tool access.
Read the file at the path below. If it contains a valid Python function
definition, return verdict APPROVE. Otherwise return REQUEST_CHANGES.

Respond ONLY with a short YAML frontmatter block and a one-line summary. Exact format:

---
verdict: APPROVE
---

Looks good.

File to review: {path}
"""


def test_bulk() -> int:
    print("=" * 60, file=sys.stderr)
    print("TEST 1: run_bulk with inline file content", file=sys.stderr)
    print("=" * 60, file=sys.stderr)
    try:
        text = _llm_claude.run_bulk(
            PROMPT_BULK,
            model="claude-sonnet-4-5",
            timeout=120,
        )
    except Exception as exc:
        print(f"FAIL: run_bulk raised {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1

    print("--- run_bulk returned ---", file=sys.stderr)
    print(text, file=sys.stderr)
    print("--- end run_bulk output ---", file=sys.stderr)

    if "verdict:" not in text.lower():
        print("FAIL: no verdict: in response", file=sys.stderr)
        return 1
    print("PASS: run_bulk returned text with verdict\n", file=sys.stderr)
    return 0


def test_tool_use() -> int:
    print("=" * 60, file=sys.stderr)
    print("TEST 2: run_tool_use reading a real file via Read tool", file=sys.stderr)
    print("=" * 60, file=sys.stderr)

    with tempfile.TemporaryDirectory(prefix="mill-smoke-llm-") as tmp:
        test_file = Path(tmp) / "sample.py"
        test_file.write_text(
            "def greet(name: str) -> str:\n"
            "    return f'Hello, {name}!'\n",
            encoding="utf-8",
        )

        prompt = PROMPT_TOOL.format(path=test_file)
        try:
            text = _llm_claude.run_tool_use(
                prompt,
                model="claude-sonnet-4-5",
                timeout=180,
            )
        except Exception as exc:
            print(f"FAIL: run_tool_use raised {type(exc).__name__}: {exc}", file=sys.stderr)
            return 1

        print("--- run_tool_use returned ---", file=sys.stderr)
        print(text, file=sys.stderr)
        print("--- end run_tool_use output ---", file=sys.stderr)

        if "verdict:" not in text.lower():
            print("FAIL: no verdict: in response", file=sys.stderr)
            return 1
        print("PASS: run_tool_use returned text with verdict\n", file=sys.stderr)
        return 0


def main() -> int:
    rc = 0
    rc |= test_bulk()
    rc |= test_tool_use()
    if rc == 0:
        print("OK — both LLM smoke tests passed")
    else:
        print("FAIL — at least one LLM smoke test failed")
    return rc


if __name__ == "__main__":
    sys.exit(main())
