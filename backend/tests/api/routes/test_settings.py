from app.config import settings


def reset_provider_settings():
    settings.llm_provider = None
    settings.llm_model = "ollama/llama3.1"
    settings.openai_api_key = None
    settings.openai_base_url = None
    settings.moonshot_api_key = None
    settings.moonshot_base_url = "https://api.moonshot.ai/v1"


def test_get_provider_models_requires_auth(client):
    assert client.get("/api/settings/providers/openai/models").status_code == 401


def test_get_provider_models_returns_synced_list(client, monkeypatch):
    register_user(client)
    monkeypatch.setattr(
        "app.api.routes.settings.model_catalog_service.list_provider_models",
        lambda user_id, provider: {
            "provider": provider,
            "models": [{"value": "gpt-4o", "label": "gpt 4o"}],
            "current": "gpt-4o",
            "source": "catalog",
        },
    )

    response = client.get("/api/settings/providers/openai/models")
    assert response.status_code == 200
    assert response.json()["source"] == "catalog"
    assert response.json()["models"][0]["value"] == "gpt-4o"


def test_get_provider_settings_requires_auth(client):
    list_response = client.get("/api/settings/providers")
    assert list_response.status_code == 401

    response = client.get("/api/settings/provider")
    assert response.status_code == 401


def test_put_provider_settings_requires_auth(client):
    reset_provider_settings()

    response = client.put(
        "/api/settings/provider",
        json={
            "provider": "openai-compatible",
            "model": "kimchi/kimi-k2.7",
            "api_key": "router-key",
            "base_url": "http://localhost:20128/v1",
        },
    )

    assert response.status_code == 401


def test_put_provider_settings_rejects_blank_model(client):
    reset_provider_settings()

    response = client.put("/api/settings/provider", json={"provider": "openai", "model": "   "})

    assert response.status_code == 422


def test_get_available_models_includes_presets(client):
    reset_provider_settings()
    response = client.get("/api/settings/models")
    assert response.status_code == 200
    data = response.json()
    assert "models" in data
    assert "current" in data
    labels = [m["label"] for m in data["models"]]
    assert "OpenAI GPT-4o" in labels


def test_get_available_models_includes_custom_current(client):
    reset_provider_settings()
    settings.llm_model = "custom/my-model"
    response = client.get("/api/settings/models")
    data = response.json()
    assert data["current"] == "custom/my-model"
    assert data["models"][0]["value"] == "custom/my-model"
    assert data["models"][0]["label"] == "custom/my-model"


def test_get_available_models_no_duplicate_for_preset(client):
    reset_provider_settings()
    settings.llm_model = "openai/gpt-4o"
    response = client.get("/api/settings/models")
    data = response.json()
    values = [m["value"] for m in data["models"]]
    assert values.count("openai/gpt-4o") == 1


def test_put_provider_settings_response_value_error(client):
    register_user(client, email="valerr@example.com")

    response = client.put(
        "/api/settings/provider",
        json={"provider": "openai-compatible", "model": "some-model"},
    )
    assert response.status_code == 400
    assert "requires a base URL" in response.json()["detail"]


def register_user(client, email="settings@example.com"):
    response = client.post("/api/auth/register", json={"email": email, "password": "password123"})
    assert response.status_code == 201
    return response.json()


def test_authenticated_settings_provider_list_get_update_activate_and_clear(client):
    # Ensure first-time default for this user derives to openai (tests use ollama by default -> custom)
    settings.llm_provider = "openai"
    settings.llm_model = "openai/gpt-4o"

    register_user(client)

    providers = client.get("/api/settings/providers")
    assert providers.status_code == 200
    assert providers.json()["active_provider"] == "openai"
    assert len(providers.json()["providers"]) == 12

    active = client.get("/api/settings/provider")
    assert active.status_code == 200
    assert active.json()["provider"] == "openai"

    update = client.put(
        "/api/settings/provider",
        json={"provider": "groq", "model": "llama-3.3-70b-versatile", "api_key": "groq-key"},
    )
    assert update.status_code == 200
    assert update.json()["provider"] == "groq"
    assert update.json()["has_api_key"] is True
    assert "groq-key" not in update.text

    mistral = client.put(
        "/api/settings/provider",
        json={"provider": "mistral", "model": "mistral-large-latest", "api_key": "mistral-key"},
    )
    assert mistral.status_code == 200
    assert mistral.json()["effective_model"] == "mistral/mistral-large-latest"
    assert "mistral-key" not in mistral.text

    activate = client.post("/api/settings/provider/openai/activate")
    assert activate.status_code == 200
    assert activate.json() == {
        "provider": "openai",
        "model": "gpt-4o",
        "base_url": None,
        "has_api_key": False,
        "effective_model": "openai/gpt-4o",
    }

    clear = client.delete("/api/settings/provider/groq/key")
    assert clear.status_code == 200
    assert clear.json()["provider"] == "groq"
    assert clear.json()["has_api_key"] is False


def test_authenticated_provider_update_value_error(client):
    register_user(client)

    response = client.put(
        "/api/settings/provider",
        json={"provider": "openai-compatible", "model": "local-model"},
    )

    assert response.status_code == 400
    assert "requires a base URL" in response.json()["detail"]


def test_activate_and_clear_provider_require_auth(client):
    assert client.post("/api/settings/provider/openai/activate").status_code == 401
    assert client.delete("/api/settings/provider/openai/key").status_code == 401


def test_search_provider_settings_require_auth(client):
    assert client.get("/api/settings/search-providers").status_code == 401
    assert client.put(
        "/api/settings/search-provider",
        json={"provider": "brave", "api_key": "secret"},
    ).status_code == 401
    assert client.delete("/api/settings/search-provider/brave/key").status_code == 401


def test_authenticated_search_provider_settings_list_update_and_clear(client, monkeypatch):
    monkeypatch.delenv("BRAVE_API_KEY", raising=False)
    register_user(client, email="search-settings@example.com")

    listed = client.get("/api/settings/search-providers")
    assert listed.status_code == 200
    assert len(listed.json()["providers"]) == 4

    saved = client.put(
        "/api/settings/search-provider",
        json={"provider": "brave", "api_key": "brave-secret"},
    )
    assert saved.status_code == 200
    assert saved.json()["has_api_key"] is True
    assert saved.json()["has_user_api_key"] is True
    assert "brave-secret" not in saved.text

    cleared = client.delete("/api/settings/search-provider/brave/key")
    assert cleared.status_code == 200
    assert cleared.json()["provider"] == "brave"
    assert cleared.json()["has_api_key"] is False
    assert cleared.json()["has_user_api_key"] is False


def test_mcp_connector_settings_require_auth(client):
    assert client.get("/api/settings/mcp-connectors").status_code == 401
    assert client.put(
        "/api/settings/mcp-connector",
        json={"key": "github", "api_key": "secret"},
    ).status_code == 401
    assert client.delete("/api/settings/mcp-connector/github/key").status_code == 401


def test_authenticated_mcp_connector_settings_list_update_and_clear(client, monkeypatch):
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    monkeypatch.delenv("LINEAR_API_KEY", raising=False)
    register_user(client, email="mcp-settings@example.com")

    listed = client.get("/api/settings/mcp-connectors")
    assert listed.status_code == 200
    assert [item["key"] for item in listed.json()["connectors"]] == ["github", "linear"]
    assert all(item["enabled_by_default"] is True for item in listed.json()["connectors"])

    saved = client.put(
        "/api/settings/mcp-connector",
        json={"key": "github", "api_key": "ghp-secret"},
    )
    assert saved.status_code == 200
    assert saved.json()["key"] == "github"
    assert saved.json()["has_api_key"] is True
    assert saved.json()["has_user_api_key"] is True
    assert "ghp-secret" not in saved.text

    cleared = client.delete("/api/settings/mcp-connector/github/key")
    assert cleared.status_code == 200
    assert cleared.json()["key"] == "github"
    assert cleared.json()["has_api_key"] is False
    assert cleared.json()["has_user_api_key"] is False
