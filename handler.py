"""👋 THIS is the file you edit.

Two ways to build your agent:

  1) NO-CODE  — leave this file alone and just edit `prompt.txt`. The default
     handler below feeds the meeting task + summary to the LLM using your prompt
     and returns the result as a Markdown artifact.

  2) CODE     — edit handler() to do anything: call multiple LLM steps, hit
     external APIs, generate files, scrape data, build a slide outline, etc.

`input`  carries the meeting context (see AgentInput in sitrep_agent/sdk.py).
`ctx`    gives you ctx.llm.complete(system, prompt), ctx.instructions, ctx.log().

Return a dict: {"artifacts": [{"type": "markdown"|"html"|"link", "title", "content"}]}
"""
from __future__ import annotations

from pathlib import Path

from sitrep_agent.sdk import AgentInput, Ctx

# The no-code prompt. Edit prompt.txt — no Python required.
SYSTEM_PROMPT = Path(__file__).with_name("prompt.txt").read_text(encoding="utf-8").strip()


async def handler(input: AgentInput, ctx: Ctx) -> dict:
    task = input.task
    title = task.get("title") or "Draft"

    user = (
        f"Action item: {title}\n"
        f"{('Details: ' + task['description']) if task.get('description') else ''}\n\n"
        f"Meeting summary:\n{input.summary}"
    )

    # Prefer the prompt the creator wrote in the Studio (ctx.instructions); fall
    # back to prompt.txt for local/no-code runs.
    system = ctx.instructions.strip() or SYSTEM_PROMPT
    ctx.log(f"generating with model={ctx.llm.model}")

    draft = await ctx.llm.complete(system=system, prompt=user)

    return {
        "artifacts": [
            {"type": "markdown", "title": title, "content": draft},
        ]
    }
