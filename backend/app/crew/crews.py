from crewai import Crew, Process, Task, Agent

from app.config import settings


def _planning_kwargs(agent: Agent) -> dict:
    # planning=True adds a full extra LLM call per crew kickoff; keep it
    # opt-in so default builds stay cheap.
    if not settings.crew_planning:
        return {}
    return {"planning": True, "planning_llm": agent.llm}


def _agent_uses_gemini(agent: Agent) -> bool:
    model = str(getattr(getattr(agent, "llm", None), "model", "") or "").lower()
    return model.startswith("gemini/")


def _base_crew_kwargs(agent: Agent) -> dict:
    return {
        "process": Process.sequential,
        # When crew_verbose is True, CrewAI prints agent thoughts/tool use to the
        # server console so local debugging can follow the build. User-facing
        # progress still comes from structured streaming events.
        "verbose": settings.crew_verbose,
        # CrewAI's native Gemini adapter can intermittently yield empty stream
        # chunks on tool-heavy tasks. Keep Gemini crews non-streaming; the
        # outer Neutron Flow still emits lifecycle/progress events.
        "stream": not _agent_uses_gemini(agent),
        "checkpoint": False,
    }


def create_leadership_crew(leader: Agent, task: Task) -> Crew:
    return Crew(
        agents=[leader],
        tasks=[task],
        **_base_crew_kwargs(leader),
    )


def create_analysis_crew(analyst: Agent, task: Task, context_tasks: list[Task] | None = None) -> Crew:
    if context_tasks:
        task.context = context_tasks
    return Crew(
        agents=[analyst],
        tasks=[task],
        **_base_crew_kwargs(analyst),
    )


def create_planning_crew(pm: Agent, task: Task, context_tasks: list[Task] | None = None) -> Crew:
    if context_tasks:
        task.context = context_tasks
    return Crew(
        agents=[pm],
        tasks=[task],
        **_base_crew_kwargs(pm),
    )


def create_architecture_crew(architect: Agent, task: Task, context_tasks: list[Task] | None = None) -> Crew:
    if context_tasks:
        task.context = context_tasks
    return Crew(
        agents=[architect],
        tasks=[task],
        **_base_crew_kwargs(architect),
    )


def create_consult_crew(agent: Agent, task: Task) -> Crew:
    return Crew(
        agents=[agent],
        tasks=[task],
        **_base_crew_kwargs(agent),
    )


def create_engineering_crew(engineer: Agent, task: Task, context_tasks: list[Task] | None = None) -> Crew:
    if context_tasks:
        task.context = context_tasks
    return Crew(
        agents=[engineer],
        tasks=[task],
        **_planning_kwargs(engineer),
        **_base_crew_kwargs(engineer),
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
        **_base_crew_kwargs(engineer),
    )
