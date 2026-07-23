from crewai import Task, Agent

from app.config import settings
from app.crew.guardrails import validate_project_brief
from app.crew.schemas import ProjectBriefSpec


def create_leadership_task(leader: Agent, user_prompt: str) -> Task:
    return Task(
        description=(
            f"Review and clarify the following project request:\n\n"
            f"'{user_prompt}'\n\n"
            "Create an authoritative project brief and populate the structured output:\n"
            "1. headline — short card title\n"
            "2. summary — 2-4 sentence human summary for the chat card\n"
            "3. user_intent and target_users\n"
            "4. functional_requirements and non_functional_requirements\n"
            "5. assumptions that resolve ambiguity conservatively\n"
            "6. mvp_inclusions, mvp_exclusions, and constraints\n"
            "7. success_criteria that are measurable\n"
            "8. handoff_notes for analysis, planning, architecture, and engineering\n"
            "Do not invent live market facts. Prefer explicit, conservative assumptions."
        ),
        expected_output=(
            "A complete ProjectBriefSpec with headline, summary, user intent, target users, "
            "requirements, assumptions, MVP inclusions/exclusions, constraints, success criteria, "
            "and downstream handoff notes."
        ),
        agent=leader,
        output_pydantic=ProjectBriefSpec,
        guardrails=[validate_project_brief],
        guardrail_max_retries=settings.task_guardrail_max_retries,
    )
