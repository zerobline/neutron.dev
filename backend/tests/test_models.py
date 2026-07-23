import pytest
from pydantic import ValidationError

from app.models import (
    AgentEvent,
    MessageResponse,
    ProjectCreate,
    ProjectFileResponse,
    ProjectResponse,
    ProjectSkillSettings,
    SearchProviderSettingsUpdate,
    SkillAssignment,
    SkillCreate,
    UserCreate,
    UserLogin,
    UserMessage,
)


def test_project_create_valid():
    model = ProjectCreate(name="Atoms", description="AI builder", template="saas")
    assert model.name == "Atoms"
    assert model.description == "AI builder"
    assert model.template == "saas"


def test_project_create_template_optional():
    model = ProjectCreate(name="Atoms", description="AI builder")
    assert model.template is None


def test_project_create_missing_name_raises():
    with pytest.raises(ValidationError):
        ProjectCreate.model_validate({"description": "AI builder"})


def test_project_response_valid():
    model = ProjectResponse(
        id="abc123",
        name="Atoms",
        description="AI builder",
        status="created",
        template="saas",
        created_at="2024-01-01T00:00:00",
        updated_at="2024-01-01T00:00:00",
    )
    assert model.id == "abc123"
    assert model.token_usage.total_tokens == 0
    assert model.token_budget == 0
    assert model.token_budget_percent is None


def test_project_file_response_valid():
    model = ProjectFileResponse(file_path="index.html", content="<h1>Hi</h1>")
    assert model.file_path == "index.html"


def test_message_response_valid():
    model = MessageResponse(
        id=1,
        project_id="abc",
        role="agent",
        agent="researcher",
        content="hello",
        created_at="2024-01-01T00:00:00",
    )
    assert model.agent == "researcher"


def test_user_create_trims_display_name_variants():
    empty = UserCreate(email=" USER@Example.com ", password="password123", display_name="   ")
    named = UserCreate(email="named@example.com", password="password123", display_name=" Named ")
    anonymous = UserCreate(email="anon@example.com", password="password123")
    assert empty.email == "user@example.com"
    assert empty.display_name is None
    assert named.display_name == "Named"
    assert anonymous.display_name is None


def test_user_login_normalizes_email():
    model = UserLogin(email=" USER@Example.com ", password="password123")
    assert model.email == "user@example.com"


def test_search_provider_settings_update_trims_optional_key():
    assert SearchProviderSettingsUpdate(provider="brave", api_key="  secret  ").api_key == "secret"
    assert SearchProviderSettingsUpdate(provider="brave", api_key="   ").api_key is None
    assert SearchProviderSettingsUpdate(provider="brave").api_key is None


def test_user_message_valid():
    model = UserMessage(content="hello")
    assert model.content == "hello"


def test_user_message_missing_content_raises():
    with pytest.raises(ValidationError):
        UserMessage.model_validate({})


def test_agent_event_minimal():
    model = AgentEvent(type="phase_start")
    assert model.type == "phase_start"
    assert model.agent is None


def test_agent_event_full():
    model = AgentEvent(
        type="file_created",
        agent="engineer",
        file_path="index.html",
        files=["index.html"],
        message="done",
    )
    assert model.files == ["index.html"]


def test_skill_assignment_normalizes_name_and_agents():
    model = SkillAssignment(name=" Brand_Voice ", enabled=True, agents=["engineer", "engineer", "all"])
    assert model.name == "brand-voice"
    assert model.agents == ["all"]

    empty_agents = SkillAssignment(name="x", agents=[])
    assert empty_agents.agents == ["all"]

    as_string = SkillAssignment(name="y", agents="architect")  # type: ignore[arg-type]
    assert as_string.agents == ["architect"]


def test_project_skill_settings_dedupes_names():
    model = ProjectSkillSettings(
        skills=[
            SkillAssignment(name="a", enabled=True),
            SkillAssignment(name="a", enabled=False),
            SkillAssignment(name="b", enabled=True),
        ]
    )
    assert [s.name for s in model.skills] == ["a", "b"]
    assert model.skills[0].enabled is True


def test_skill_create_normalizes_fields():
    model = SkillCreate(
        name=" House_Style ",
        description="  Be concise.  ",
        body="  Use short sentences.  ",
        agents=[],
    )
    assert model.name == "house-style"
    assert model.description == "Be concise."
    assert model.body == "Use short sentences."
    assert model.agents == ["all"]
