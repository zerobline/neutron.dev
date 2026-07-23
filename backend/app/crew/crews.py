from crewai import Crew, Process, Task, Agent

from app.config import settings


def _planning_kwargs(agent: Agent) -> dict:
    # planning=True adds a full extra LLM call per crew kickoff; keep it
    # opt-in so default builds stay cheap.
    if not settings.crew_planning:
        return {}
    return {"planning": True, "planning_llm": agent.llm}


def _base_crew_kwargs() -> dict:
    return {
        "process": Process.sequential,
        # When crew_verbose is True, CrewAI prints agent thoughts/tool use to the
        # server console so local debugging can follow the build. User-facing
        # progress still comes from structured streaming events.
        "verbose": settings.crew_verbose,
        "stream": True,
        "checkpoint": False,
    }


def create_leadership_crew(leader: Agent, task: Task) -> Crew:
    return Crew(
        agents=[leader],
        tasks=[task],
        **_base_crew_kwargs(),
    )


def create_analysis_crew(analyst: Agent, task: Task, context_tasks: list[Task] | None = None) -> Crew:
    if context_tasks:
        task.context = context_tasks
    return Crew(
        agents=[analyst],
        tasks=[task],
        **_base_crew_kwargs(),
    )


def create_planning_crew(pm: Agent, task: Task, context_tasks: list[Task] | None = None) -> Crew:
    if context_tasks:
        task.context = context_tasks
    return Crew(
        agents=[pm],
        tasks=[task],
        **_base_crew_kwargs(),
    )


def create_architecture_crew(architect: Agent, task: Task, context_tasks: list[Task] | None = None) -> Crew:
    if context_tasks:
        task.context = context_tasks
    return Crew(
        agents=[architect],
        tasks=[task],
        **_base_crew_kwargs(),
    )


def create_consult_crew(agent: Agent, task: Task) -> Crew:
    return Crew(
        agents=[agent],
        tasks=[task],
        **_base_crew_kwargs(),
    )


def create_engineering_crew(engineer: Agent, task: Task, context_tasks: list[Task] | None = None) -> Crew:
    if context_tasks:
        task.context = context_tasks
    return Crew(
        agents=[engineer],
        tasks=[task],
        **_planning_kwargs(engineer),
        **_base_crew_kwargs(),
    )


def create_engineering_recovery_crew(
    engineer: Agent,
    tasks: list[Task],
    context_tasks: list[Task] | None = None,
) -> Crew:
    if context_tasks and tasks:
        tasks[0].context = context_tasks
    return Crew(
        agents=[engineer],
        tasks=tasks,
        **_planning_kwargs(engineer),
        **_base_crew_kwargs(),
    )
