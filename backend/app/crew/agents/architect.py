from typing import Any

from crewai import Agent

from app.config import settings
from app.crew.llm import get_agent_llm


def create_architect_agent(
    user_id: str | None = None,
    tools=None,
    mcps: list[Any] | None = None,
    skills: list[Any] | None = None,
):
    return Agent(
        role="System Architect",
        goal=(
            "Turn the approved product plan into an implementation-ready architecture for a directly served "
            "static web application, including files, components, interactions, responsive behavior, and accessibility."
        ),
        backstory=(
            "You are Theo, a pragmatic software architect who selects the simplest browser-native architecture "
            "that satisfies the approved scope. You resolve upstream conflicts and avoid unsupported servers, "
            "framework runtimes, build steps, and persistence mechanisms. When repository MCP tools are "
            "available, inspect existing code structure before inventing a file layout."
        ),
        llm=get_agent_llm(user_id, agent_id="architect"),
        tools=tools or [],
        mcps=mcps or None,
        skills=skills or None,
        verbose=settings.crew_verbose,
        allow_delegation=False,
        memory=False,
        max_iter=settings.agent_max_iter,
        max_execution_time=settings.agent_max_execution_seconds,
        max_retry_limit=settings.agent_max_retry_limit,
        respect_context_window=True,
    )
