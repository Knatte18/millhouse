"""Tool-use reviewer using Claude Sonnet at max effort."""
from _llm_claude import run_tool_use

MODE = "tool-use"

def run(prompt_text: str) -> str:
    text, _ = run_tool_use(prompt_text, model="claude-sonnet-4-6", effort="max")
    return text


if __name__ == "__main__":
    assert MODE == "tool-use", f"Expected MODE='tool-use', got {MODE!r}"
    assert callable(run), "run must be callable"
    print("PASS: MODE == 'tool-use'")
    print("PASS: run is callable")
    print("All smoke tests passed.")
