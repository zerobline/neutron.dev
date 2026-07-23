from app.services import agent_settings_service, auth_service, provider_settings_service
from app.models import ProviderSettingsUpdate, UserCreate


def test_agent_models_default_and_override(temp_db):
    user = auth_service.create_user(UserCreate(email="agents@example.com", password="password123"))
    provider_settings_service.update_provider_settings(
        user.id,
        ProviderSettingsUpdate(provider="openai", model="gpt-4o-mini", api_key="sk-test"),
    )

    data = agent_settings_service.get_agent_models(user.id)
    assert data["default_model"] == "gpt-4o-mini"
    assert len(data["agents"]) == 5
    assert all(a["model"] == "gpt-4o-mini" for a in data["agents"])

    updated = agent_settings_service.update_agent_models(
        user.id,
        {"engineer": "gpt-4o", "team_leader": "gpt-4o-mini", "ghost": "nope"},
    )
    by_id = {a["id"]: a for a in updated["agents"]}
    assert by_id["engineer"]["model"] == "gpt-4o"
    assert by_id["engineer"]["is_override"] is True
    assert agent_settings_service.resolve_model_for_agent(user.id, "engineer") == "gpt-4o"
    assert agent_settings_service.resolve_model_for_agent(user.id, "product_manager") is None
