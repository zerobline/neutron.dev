from crewai import Task, Agent

from app.config import settings
from app.crew.guardrails import validate_project_plan
from app.crew.schemas import ProjectPlanSpec


def create_planning_task(pm: Agent, user_prompt: str) -> Task:
    return Task(
        description=(
            f"Create a project plan focused on product behavior for the following idea:\n\n"
            f"'{user_prompt}'\n\n"
            "Use the accepted requirements and analysis context. Own product behavior rather than implementation "
            "architecture. Populate the structured output:\n"
            "1. headline and summary for the chat card\n"
            "2. overview — product objectives, users, and scope\n"
            "3. mvp_features and future_features — prioritized capabilities\n"
            "4. pages — each page with name, purpose, and key_elements\n"
            "5. data_model_summary — product-level entities and information needs, not database design\n"
            "6. milestones — ordered delivery outcomes and dependencies\n"
            "7. acceptance_criteria — measurable conditions for MVP completion\n"
            "8. user_flows — key journeys across pages and features\n"
            "9. handoff_constraints — product decisions the architect and engineer must preserve\n"
            "Leave technical_architecture empty; the System Architect owns routing, components, state, persistence, "
            "file structure, and implementation technology."
        ),
        expected_output=(
            "A complete ProjectPlanSpec with headline, summary, product scope, prioritized features, pages, "
            "product-level data needs, milestones, acceptance criteria, user flows, and downstream constraints."
        ),
        agent=pm,
        output_pydantic=ProjectPlanSpec,
        guardrails=[validate_project_plan],
        guardrail_max_retries=settings.task_guardrail_max_retries,
    )
