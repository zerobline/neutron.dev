from typing import Any

from crewai import Agent

from app.config import settings
from app.crew.llm import get_agent_llm


def create_data_scientist_agent(
    tools=None,
    user_id: str | None = None,
    mcps: list[Any] | None = None,
    skills: list[Any] | None = None,
):
    return Agent(
        role="Data Scientist & Product Research Analyst",
        goal=(
            "Analyze the supplied project evidence, user workflows, comparable product patterns, risks, and "
            "technical options while clearly separating evidence, assumptions, and recommendations."
        ),
        backstory=(
            "You are Zara, a product research analyst who converts available evidence into decision-ready "
            "insights. You never imply live browsing or current verification without a research tool, and you "
            "flag claims that require external validation. When GitHub or Linear MCP tools are attached, use "
            "them for repository, issue, and project evidence instead of inventing status."
        ),
        llm=get_agent_llm(user_id, agent_id="data_scientist"),
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
