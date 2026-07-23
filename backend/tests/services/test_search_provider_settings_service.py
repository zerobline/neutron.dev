from app.database import db_connection
from app.models import SearchProviderSettingsUpdate, UserCreate
from app.services import auth_service, search_provider_settings_service


def make_user():
    return auth_service.create_user(UserCreate(email="search-provider@example.com", password="password123"))


def test_search_provider_settings_encrypt_preserve_resolve_and_clear(temp_db, monkeypatch):
    for env_key in ("BRAVE_API_KEY", "SERPER_API_KEY", "TAVILY_API_KEY", "EXA_API_KEY"):
        monkeypatch.delenv(env_key, raising=False)
    user = make_user()

    initial = search_provider_settings_service.list_search_provider_settings(user.id)
    assert [provider.provider for provider in initial.providers] == ["brave", "serper", "tavily", "exa"]
    assert all(provider.has_api_key is False for provider in initial.providers)
    assert all(provider.has_user_api_key is False for provider in initial.providers)

    empty = search_provider_settings_service.update_search_provider_settings(
        user.id,
        SearchProviderSettingsUpdate(provider="exa", api_key=None),
    )
    assert empty.has_api_key is False

    saved = search_provider_settings_service.update_search_provider_settings(
        user.id,
        SearchProviderSettingsUpdate(provider="brave", api_key="brave-secret"),
    )
    assert saved.has_api_key is True
    assert saved.has_user_api_key is True
    assert search_provider_settings_service.resolve_search_api_key(user.id, "brave") == "brave-secret"

    with db_connection() as conn:
        row = conn.execute(
            "SELECT api_key_encrypted FROM user_search_provider_settings WHERE user_id = ? AND provider = ?",
            (user.id, "brave"),
        ).fetchone()
    assert row is not None
    assert row["api_key_encrypted"] != "brave-secret"
    assert "brave-secret" not in row["api_key_encrypted"]

    preserved = search_provider_settings_service.update_search_provider_settings(
        user.id,
        SearchProviderSettingsUpdate(provider="brave", api_key=""),
    )
    assert preserved.has_api_key is True
    assert search_provider_settings_service.resolve_search_api_key(user.id, "brave") == "brave-secret"

    cleared = search_provider_settings_service.clear_search_provider_key(user.id, "brave")
    assert cleared.has_api_key is False
    assert cleared.has_user_api_key is False
    assert search_provider_settings_service.resolve_search_api_key(user.id, "brave") is None


def test_search_provider_settings_use_environment_fallback(temp_db, monkeypatch):
    user = make_user()
    monkeypatch.setenv("SERPER_API_KEY", "server-serper-key")

    listed = search_provider_settings_service.list_search_provider_settings(user.id)
    serper = next(provider for provider in listed.providers if provider.provider == "serper")
    assert serper.has_api_key is True
    assert serper.has_user_api_key is False
    assert search_provider_settings_service.resolve_search_api_key(user.id, "serper") == "server-serper-key"

    cleared = search_provider_settings_service.clear_search_provider_key(user.id, "serper")
    assert cleared.has_api_key is True
    assert cleared.has_user_api_key is False
