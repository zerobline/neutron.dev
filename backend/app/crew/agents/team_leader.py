from typing import Any

from crewai import Agent

from app.config import settings
from app.crew.llm import get_agent_llm


def create_team_leader_agent(
    tools=None,
    user_id: str | None = None,
    mcps: list[Any] | None = None,
    skills: list[Any] | None = None,
):
    return Agent(
        role="Team Leader",
        goal=(
            "Turn the user's vision into an authoritative project brief with explicit requirements, "
            "assumptions, MVP boundaries, constraints, success criteria, and clear downstream handoffs."
        ),
        backstory=(
            "You are Kai, a technical delivery lead who turns ambiguous requests into clear execution briefs. "
            "You preserve user intent, make conservative assumptions, prevent scope drift, and identify what "
            "later project phases must resolve. When MCP tools such as GitHub or Linear are available, use them "
            "to ground the brief in real repository or issue context."
        ),
        llm=get_agent_llm(user_id, agent_id="team_leader"),
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
