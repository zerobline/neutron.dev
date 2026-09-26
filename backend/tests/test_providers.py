from app.providers import prefixed_model, provider_model


def test_prefixed_model_leaves_existing_prefixes_and_custom_unchanged():
    assert prefixed_model("openai", "openai/gpt-4o") == "openai/gpt-4o"
    assert prefixed_model("custom", " vendor/model ") == "vendor/model"


def test_provider_model_strips_and_leaves_models_correctly():
    assert prefixed_model("mistral", "mistral-large-latest") == "mistral/mistral-large-latest"
    assert provider_model("mistral", "mistral/mistral-large-latest") == "mistral-large-latest"
    assert provider_model("openai", "openai/gpt-4o") == "gpt-4o"
    assert provider_model("kimi", "openai/kimi-for-coding") == "kimi-for-coding"
    assert provider_model("openai", "gpt-4o") == "gpt-4o"
    assert provider_model("custom", "vendor/model") == "vendor/model"


def test_gemini_prefix_round_trip():
    assert prefixed_model("gemini", "gemini-3.5-flash-lite") == "gemini/gemini-3.5-flash-lite"
    assert provider_model("gemini", "gemini/gemini-3.5-flash-lite") == "gemini-3.5-flash-lite"
