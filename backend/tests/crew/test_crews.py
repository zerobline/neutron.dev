from crewai import Crew, Process, Task

from app.config import settings
from app.crew.agents.team_leader import create_team_leader_agent
from app.crew.agents.data_scientist import create_data_scientist_agent
from app.crew.agents.product_manager import create_pm_agent
from app.crew.agents.architect import create_architect_agent
from app.crew.agents.engineer import create_engineer_agent
from app.crew.crews import (
    create_leadership_crew,
    create_analysis_crew,
    create_planning_crew,
    create_architecture_crew,
    create_engineering_crew,
    create_engineering_recovery_crew,
)
from app.crew.tasks.leadership_tasks import create_leadership_task
from app.crew.tasks.analysis_tasks import create_analysis_task
from app.crew.tasks.planning_tasks import create_planning_task
from app.crew.tasks.architecture_tasks import create_architecture_task
from app.crew.tasks.engineering_tasks import create_engineering_recovery_tasks, create_engineering_task


def test_create_leadership_crew():
    agent = create_team_leader_agent()
    task = create_leadership_task(agent, "prompt")
    crew = create_leadership_crew(agent, task)
    assert isinstance(crew, Crew)
    assert crew.agents == [agent]
    assert crew.tasks == [task]
    assert crew.process == Process.sequential
    assert crew.stream is True
    assert crew.checkpoint is False
    assert crew.verbose is settings.crew_verbose


def test_create_analysis_crew_without_context():
    agent = create_data_scientist_agent()
    task = create_analysis_task(agent, "prompt")
    crew = create_analysis_crew(agent, task)
    assert crew.tasks == [task]
    assert task.context is not None


def test_create_analysis_crew_with_context():
    analyst = create_data_scientist_agent()
    analysis_task = create_analysis_task(analyst, "prompt")
    leader = create_team_leader_agent()
    leader_task = create_leadership_task(leader, "prompt")
    crew = create_analysis_crew(analyst, analysis_task, context_tasks=[leader_task])
    assert analysis_task.context == [leader_task]


def test_create_planning_crew_without_context():
    agent = create_pm_agent()
    task = create_planning_task(agent, "prompt")
    crew = create_planning_crew(agent, task)
    assert crew.tasks == [task]
    assert task.context is not None


def test_create_planning_crew_with_context():
    pm = create_pm_agent()
    plan_task = create_planning_task(pm, "prompt")
    analyst = create_data_scientist_agent()
    analysis_task = create_analysis_task(analyst, "prompt")
    crew = create_planning_crew(pm, plan_task, context_tasks=[analysis_task])
    assert plan_task.context == [analysis_task]


def test_create_architecture_crew_without_context():
    agent = create_architect_agent()
    task = create_architecture_task(agent, "prompt")
    crew = create_architecture_crew(agent, task)
    assert crew.tasks == [task]
    assert task.context is not None


def test_create_architecture_crew_with_context():
    architect = create_architect_agent()
    arch_task = create_architecture_task(architect, "prompt")
    pm = create_pm_agent()
    plan_task = create_planning_task(pm, "prompt")
    crew = create_architecture_crew(architect, arch_task, context_tasks=[plan_task])
    assert arch_task.context == [plan_task]


def test_create_engineering_crew_without_context():
    engineer = create_engineer_agent()
    eng_task = create_engineering_task(engineer, "prompt")
    crew = create_engineering_crew(engineer, eng_task)
    assert crew.tasks == [eng_task]
    assert eng_task.context is not None
    assert crew.planning is False
    assert crew.planning_llm is None


def test_create_engineering_crew_with_context():
    engineer = create_engineer_agent()
    eng_task = create_engineering_task(engineer, "prompt")
    pm = create_pm_agent()
    plan_task = create_planning_task(pm, "prompt")
    architect = create_architect_agent()
    arch_task = create_architecture_task(architect, "prompt")
    crew = create_engineering_crew(engineer, eng_task, context_tasks=[plan_task, arch_task])
    assert eng_task.context == [plan_task, arch_task]
    assert crew.planning is False
    assert crew.planning_llm is None


def test_create_engineering_crew_planning_enabled(monkeypatch):
    monkeypatch.setattr(settings, "crew_planning", True)
    engineer = create_engineer_agent()
    eng_task = create_engineering_task(engineer, "prompt")
    crew = create_engineering_crew(engineer, eng_task)
    assert crew.planning is True
    assert crew.planning_llm is engineer.llm


def test_create_engineering_recovery_crew_with_context():
    engineer = create_engineer_agent()
    recovery_tasks = create_engineering_recovery_tasks(engineer, "prompt")
    pm = create_pm_agent()
    plan_task = create_planning_task(pm, "prompt")
    crew = create_engineering_recovery_crew(engineer, recovery_tasks, context_tasks=[plan_task])
    assert crew.tasks == recovery_tasks
    assert recovery_tasks[0].context == [plan_task]
    assert crew.planning is False


def test_create_engineering_recovery_crew_planning_enabled(monkeypatch):
    monkeypatch.setattr(settings, "crew_planning", True)
    engineer = create_engineer_agent()
    recovery_tasks = create_engineering_recovery_tasks(engineer, "prompt")
    crew = create_engineering_recovery_crew(engineer, recovery_tasks)
    assert crew.planning is True
    assert crew.planning_llm is engineer.llm


def test_create_engineering_recovery_crew_without_context_or_tasks():
    engineer = create_engineer_agent()
    crew = create_engineering_recovery_crew(engineer, [])
    assert crew.tasks == []
    assert crew.planning is False


def test_gemini_crew_disables_streaming(monkeypatch):
    agent = create_engineer_agent()
    agent.llm.model = "gemini/gemini-3.5-flash-lite"
    task = create_engineering_task(agent, "prompt")
    crew = create_engineering_crew(agent, task)
    assert crew.stream is False
