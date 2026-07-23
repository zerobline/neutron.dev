from typing import Any

from crewai import Agent

from app.config import settings
from app.crew.llm import get_agent_llm


def create_pm_agent(
    user_id: str | None = None,
    tools=None,
    mcps: list[Any] | None = None,
    skills: list[Any] | None = None,
):
    return Agent(
        role="Product Manager",
        goal=(
            "Create a prioritized, testable product plan with clear MVP scope, user journeys, page requirements, "
            "acceptance criteria, product-level data needs, and delivery milestones."
        ),
        backstory=(
            "You are Nina, a product manager who converts ambiguous ideas into focused product contracts. "
            "You protect MVP scope, define measurable outcomes, and leave implementation architecture to the "
            "system architect. When Linear or GitHub MCP tools are available, align milestones and backlog "
            "language with real issues and project state."
        ),
        llm=get_agent_llm(user_id, agent_id="product_manager"),
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
