from typing import Any

from crewai import Agent

from app.config import settings
from app.crew.llm import get_agent_llm


def create_engineer_agent(
    tools=None,
    user_id: str | None = None,
    mcps: list[Any] | None = None,
    skills: list[Any] | None = None,
):
    return Agent(
        role="Senior Web Engineer",
        goal=(
            "Implement the approved plan and architecture as a complete browser-native HTML, CSS, and JavaScript "
            "application, writing every required file through the provided tools."
        ),
        backstory=(
            "You are Ravi, a senior web engineer who turns approved specifications into directly servable software. "
            "You prioritize functional completeness, semantic HTML, maintainable CSS, robust JavaScript, "
            "accessibility, and faithful implementation over unnecessary framework complexity. You always wire "
            "tabs and pages with data-tab/data-panel show-hide logic — never root-relative routes or iframe navigation. "
            "When GitHub or Linear MCP tools are attached, use them for issue context and repository references, "
            "but still write project files through the local code tools."
        ),
        llm=get_agent_llm(user_id, agent_id="engineer"),
        tools=tools or [],
        mcps=mcps or None,
        skills=skills or None,
        verbose=settings.crew_verbose,
        allow_delegation=False,
        memory=False,
        max_iter=settings.engineer_max_iter,
        max_execution_time=settings.engineer_max_execution_seconds,
        max_retry_limit=settings.agent_max_retry_limit,
        respect_context_window=True,
    )
