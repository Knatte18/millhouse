"""Tool-use reviewer using Claude Sonnet at max effort."""
from _llm_claude import run_tool_use

MODE = "tool-use"

def run(prompt_text: str) -> str:
    text, _ = run_tool_use(prompt_text, model="claude-sonnet-4-6", effort="max")
    return text
