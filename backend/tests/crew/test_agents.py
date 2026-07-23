from crewai import Agent
from crewai.tools import BaseTool
from pydantic import BaseModel, Field

from app.config import settings
from app.crew.agents.team_leader import create_team_leader_agent
from app.crew.agents.data_scientist import create_data_scientist_agent
from app.crew.agents.product_manager import create_pm_agent
from app.crew.agents.architect import create_architect_agent
from app.crew.agents.engineer import create_engineer_agent


class DummyInput(BaseModel):
    value: str = Field(default="x")


class DummyTool(BaseTool):
    name: str = "dummy_tool"
    description: str = "A dummy tool for testing."
    args_schema: type[BaseModel] = DummyInput

    def _run(self, value: str) -> str:
        return value


def test_create_team_leader_agent():
    agent = create_team_leader_agent()
    assert isinstance(agent, Agent)
    assert "Team Leader" in agent.role
    assert getattr(agent.llm, "model") == "ollama/llama3.1"
    assert agent.verbose is settings.crew_verbose
    assert agent.max_iter == settings.agent_max_iter
    assert agent.max_execution_time == settings.agent_max_execution_seconds
    assert agent.max_retry_limit == settings.agent_max_retry_limit
    assert agent.respect_context_window is True


def test_create_team_leader_agent_with_tools():
    tool = DummyTool()
    agent = create_team_leader_agent(tools=[tool])
    assert agent.tools == [tool]


def test_create_team_leader_agent_with_mcps():
    agent = create_team_leader_agent(mcps=["https://example.com/mcp"])
    assert agent.mcps == ["https://example.com/mcp"]


def test_create_team_leader_agent_with_skills():
    from crewai.skills.loader import activate_skill, load_skill_metadata

    skill = activate_skill(load_skill_metadata(settings.skills_dir / "mvp-scope-discipline"))
    agent = create_team_leader_agent(skills=[skill])
    assert agent.skills is not None
    assert agent.skills[0].name == "mvp-scope-discipline"


def test_create_data_scientist_agent():
    agent = create_data_scientist_agent()
    assert isinstance(agent, Agent)
    assert "Data Scientist" in agent.role


def test_create_data_scientist_agent_with_tools():
    tool = DummyTool()
    agent = create_data_scientist_agent(tools=[tool])
    assert agent.tools == [tool]


def test_create_pm_agent():
    agent = create_pm_agent()
    assert isinstance(agent, Agent)
    assert "Product Manager" in agent.role


def test_create_pm_agent_with_mcps():
    agent = create_pm_agent(mcps=["https://example.com/mcp"])
    assert agent.mcps == ["https://example.com/mcp"]


def test_create_architect_agent():
    agent = create_architect_agent()
    assert isinstance(agent, Agent)
    assert "System Architect" in agent.role


def test_create_architect_agent_with_mcps():
    agent = create_architect_agent(mcps=["https://example.com/mcp"])
    assert agent.mcps == ["https://example.com/mcp"]


def test_create_engineer_agent():
    agent = create_engineer_agent()
    assert isinstance(agent, Agent)
    assert "Engineer" in agent.role
    assert agent.verbose is settings.crew_verbose
    assert agent.max_iter == settings.engineer_max_iter
    assert agent.max_execution_time == settings.engineer_max_execution_seconds


def test_create_engineer_agent_with_tools():
    tool = DummyTool()
    agent = create_engineer_agent(tools=[tool])
    assert agent.tools == [tool]


def test_create_engineer_agent_with_mcps():
    agent = create_engineer_agent(mcps=["https://example.com/mcp"])
    assert agent.mcps == ["https://example.com/mcp"]


def test_create_engineer_agent_with_skills():
    from crewai.skills.loader import activate_skill, load_skill_metadata

    skill = activate_skill(load_skill_metadata(settings.skills_dir / "browser-native-spa"))
    agent = create_engineer_agent(skills=[skill])
    assert agent.skills is not None
    assert agent.skills[0].name == "browser-native-spa"


def test_create_pm_agent_with_skills():
    from crewai.skills.loader import activate_skill, load_skill_metadata

    skill = activate_skill(load_skill_metadata(settings.skills_dir / "product-acceptance-criteria"))
    agent = create_pm_agent(skills=[skill])
    assert agent.skills is not None
    assert agent.skills[0].name == "product-acceptance-criteria"


def test_create_architect_agent_with_skills():
    from crewai.skills.loader import activate_skill, load_skill_metadata

    skill = activate_skill(load_skill_metadata(settings.skills_dir / "architecture-simplicity"))
    agent = create_architect_agent(skills=[skill])
    assert agent.skills is not None
    assert agent.skills[0].name == "architecture-simplicity"


def test_create_data_scientist_agent_with_skills():
    from crewai.skills.loader import activate_skill, load_skill_metadata

    skill = activate_skill(load_skill_metadata(settings.skills_dir / "evidence-based-analysis"))
    agent = create_data_scientist_agent(skills=[skill])
    assert agent.skills is not None
    assert agent.skills[0].name == "evidence-based-analysis"
