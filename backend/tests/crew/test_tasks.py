from crewai import Task

from app.config import settings
from app.crew.agents.team_leader import create_team_leader_agent
from app.crew.agents.data_scientist import create_data_scientist_agent
from app.crew.agents.product_manager import create_pm_agent
from app.crew.agents.architect import create_architect_agent
from app.crew.agents.engineer import create_engineer_agent
from app.crew.tasks.leadership_tasks import create_leadership_task
from app.crew.tasks.analysis_tasks import create_analysis_task
from app.crew.tasks.planning_tasks import create_planning_task
from app.crew.tasks.architecture_tasks import create_architecture_task
from app.crew.tasks.engineering_tasks import (
    create_engineering_recovery_tasks,
    create_engineering_task,
    create_iteration_task,
    create_navigation_recovery_task,
)


def test_create_leadership_task():
    from app.crew.schemas import ProjectBriefSpec

    agent = create_team_leader_agent()
    task = create_leadership_task(agent, "Build a SaaS")
    assert isinstance(task, Task)
    assert "Review and clarify" in task.description
    assert task.output_pydantic is ProjectBriefSpec
    assert task.guardrails
    assert task.agent == agent
    assert task.guardrail_max_retries == settings.task_guardrail_max_retries


def test_create_analysis_task():
    from app.crew.schemas import AnalysisReportSpec

    agent = create_data_scientist_agent()
    task = create_analysis_task(agent, "Build a SaaS")
    assert isinstance(task, Task)
    assert "Analyze" in task.description
    assert task.output_pydantic is AnalysisReportSpec
    assert task.guardrails
    assert task.agent == agent
    assert task.guardrail_max_retries == settings.task_guardrail_max_retries


def test_create_planning_task():
    from app.crew.schemas import ProjectPlanSpec

    agent = create_pm_agent()
    task = create_planning_task(agent, "Build a SaaS")
    assert task.output_pydantic is ProjectPlanSpec
    assert task.guardrails
    assert isinstance(task, Task)
    assert "project plan" in task.description.lower()
    assert "headline" in task.description.lower()
    assert task.guardrail_max_retries == settings.task_guardrail_max_retries


def test_create_architecture_task():
    from app.crew.schemas import ArchitectureSpec

    agent = create_architect_agent()
    task = create_architecture_task(agent, "Build a SaaS")
    assert task.output_pydantic is ArchitectureSpec
    assert task.guardrails
    assert isinstance(task, Task)
    assert "architecture" in task.description.lower()
    assert "headline" in task.description.lower()
    assert task.guardrail_max_retries == settings.task_guardrail_max_retries


def test_create_engineering_task():
    agent = create_engineer_agent()
    task = create_engineering_task(agent, "Build a SaaS")
    assert isinstance(task, Task)
    assert "write_code_file" in task.description
    assert "CRITICAL" in task.description
    assert "data-panel" in task.description
    assert "DEMO DATA" in task.description
    assert "first load" in task.description


def test_create_iteration_task():
    agent = create_engineer_agent()
    task = create_iteration_task(agent, "Build a SaaS", "add a contact page")
    assert isinstance(task, Task)
    assert "read_project_file" in task.description
    assert "add a contact page" in task.description
    assert "Build a SaaS" in task.description
    assert "write_code_file" in task.description
    assert "app.js" in task.description
    assert "tabs" in task.description
    assert "data-panel" in task.description
    assert "MOCK / SAMPLE / SEED DATA" in task.description
    assert "seed arrays" in task.description
    assert task.agent == agent


def test_create_navigation_recovery_task():
    agent = create_engineer_agent()
    task = create_navigation_recovery_task(
        agent,
        "Build finance app",
        ["index.html contains root-relative href"],
    )
    assert isinstance(task, Task)
    assert "navigation contract" in task.description.lower()
    assert "index.html contains root-relative href" in task.description
    assert "data-panel" in task.description


def test_create_engineering_recovery_tasks():
    agent = create_engineer_agent()
    tasks = create_engineering_recovery_tasks(agent, "Build a SaaS")
    assert len(tasks) == 3
    assert all(isinstance(task, Task) for task in tasks)
    assert "index.html" in tasks[0].description
    assert "styles.css" in tasks[1].description
    assert "app.js" in tasks[2].description
