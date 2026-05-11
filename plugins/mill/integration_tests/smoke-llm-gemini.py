"""Smoke test for _llm_gemini.run_bulk + run_tool_use + resume-not-supported.

Local-dev only. Requires `gemini` in PATH. Exits 0 on success or when gemini
is not installed, 1 on failure.

Run from hub root:
    python plugins/mill/integration_tests/smoke-llm-gemini.py
"""
from __future__ import annotations

import shutil
import sys
import uuid
from pathlib import Path

HUB = Path(__file__).resolve().parent.parent.parent.parent
SCRIPTS = HUB / "plugins" / "mill" / "scripts"
SCRATCH = HUB / ".scratch"
# Gemini CLI only accesses files inside its workspace and skips gitignored paths.
# .scratch/ is gitignored, so tool-use tests use a non-gitignored tmp dir next
# to this file (integration_tests/). The dir is deleted on success.
INTEGRATION_TESTS = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS))

import _llm_gemini  # noqa: E402


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


PROMPT_TOOL = """You are a review assistant with file-reading tool access.
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
        text, sid = _llm_gemini.run_bulk(
            PROMPT_BULK,
            model="gemini-2.5-flash",
            timeout=120,
        )
    except Exception as exc:
        print(f"FAIL: run_bulk raised {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1

    print("--- run_bulk returned ---", file=sys.stderr)
    print(text, file=sys.stderr)
    print(f"--- session_id: {sid} ---", file=sys.stderr)
    print("--- end run_bulk output ---", file=sys.stderr)

    if "verdict:" not in text.lower():
        print("FAIL: no verdict: in response", file=sys.stderr)
        return 1
    if not sid:
        print("FAIL: run_bulk did not return a session_id", file=sys.stderr)
        return 1
    print("PASS: run_bulk returned text + session_id\n", file=sys.stderr)
    return 0


def test_tool_use() -> int:
    print("=" * 60, file=sys.stderr)
    print("TEST 2: run_tool_use reading a real file via built-in read tool", file=sys.stderr)
    print("=" * 60, file=sys.stderr)

    tmp = INTEGRATION_TESTS / f"_smoke_tmp_{uuid.uuid4().hex[:8]}"
    tmp.mkdir(parents=True, exist_ok=True)
    failed = False
    try:
        test_file = tmp / "sample.py"
        test_file.write_text(
            "def greet(name: str) -> str:\n"
            "    return f'Hello, {name}!'\n",
            encoding="utf-8",
        )

        prompt = PROMPT_TOOL.format(path=test_file)
        try:
            text, sid = _llm_gemini.run_tool_use(
                prompt,
                model="gemini-2.5-flash",
                timeout=180,
            )
        except Exception as exc:
            print(f"FAIL: run_tool_use raised {type(exc).__name__}: {exc}", file=sys.stderr)
            failed = True
            return 1

        print("--- run_tool_use returned ---", file=sys.stderr)
        print(text, file=sys.stderr)
        print(f"--- session_id: {sid} ---", file=sys.stderr)
        print("--- end run_tool_use output ---", file=sys.stderr)

        if "verdict:" not in text.lower():
            print("FAIL: no verdict: in response", file=sys.stderr)
            failed = True
            return 1
        if not sid:
            print("FAIL: run_tool_use did not return a session_id", file=sys.stderr)
            failed = True
            return 1
        print("PASS: run_tool_use returned text + session_id\n", file=sys.stderr)
        return 0
    finally:
        if failed:
            print(f"Scratch dir preserved for inspection: {tmp}", file=sys.stderr)
        else:
            shutil.rmtree(tmp, ignore_errors=True)


def test_resume_not_supported() -> int:
    print("=" * 60, file=sys.stderr)
    print("TEST 3: resume=True raises LLMSessionError immediately", file=sys.stderr)
    print("=" * 60, file=sys.stderr)
    try:
        _llm_gemini.run_bulk(
            "ignored",
            model="gemini-2.5-flash",
            session_id="anything",
            resume=True,
        )
    except _llm_gemini.LLMSessionError:
        print("PASS: LLMSessionError raised as expected\n", file=sys.stderr)
        return 0
    except Exception as exc:
        print(f"FAIL: wrong exception type {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    print("FAIL: no exception raised for resume=True", file=sys.stderr)
    return 1


def main() -> int:
    if shutil.which("gemini") is None:
        print("SKIP: gemini CLI not found on PATH; integration smoke skipped.", file=sys.stderr)
        return 0

    rc = 0
    rc |= test_bulk()
    rc |= test_tool_use()
    rc |= test_resume_not_supported()
    if rc == 0:
        print("OK — all Gemini smoke tests passed")
    else:
        print("FAIL — at least one Gemini smoke test failed")
    return rc


if __name__ == "__main__":
    sys.exit(main())
