import json
import os

import pytest
from unittest.mock import patch

from crewai import LLM

from app.config import settings
from app.crew.llm import (
    XAICompatibleLLM,
    _call_with_capacity_retry,
    _deep_strip_nulls,
    _drop_xai_unsupported_params,
    _is_capacity_error,
    _promote_xai_stream_chunk,
    _sanitize_xai_completion_kwargs,
    get_agent_llm,
    normalize_xai_tool_call_messages,
)


def test_normalize_xai_tool_call_messages_replaces_null_assistant_content():
    messages = [
        {"role": "user", "content": "write a file"},
        {
            "role": "assistant",
            "content": None,
            "tool_calls": [{"id": "call-1", "type": "function"}],
        },
        {"role": "tool", "content": "Successfully wrote file", "tool_call_id": "call-1"},
    ]

    normalized = normalize_xai_tool_call_messages(messages)

    assert normalized[1]["content"] == ""
    assert normalized[1]["tool_calls"][0]["id"] == "call-1"
    assert normalized[1]["tool_calls"][0]["function"]["arguments"] == "{}"
    assert messages[1]["content"] is None


def test_normalize_xai_tool_call_messages_preserves_other_inputs():
    messages = [
        {"role": "assistant", "content": None},
        {"role": "assistant", "content": "Calling tool", "tool_calls": [{"id": "call-1"}]},
        {"role": "tool", "content": None, "tool_call_id": "call-1"},
    ]

    assert normalize_xai_tool_call_messages("hello") == "hello"
    normalized = normalize_xai_tool_call_messages(messages)
    assert normalized[0]["content"] == ""
    assert normalized[1]["content"] == "Calling tool"
    assert normalized[1]["tool_calls"][0]["id"] == "call-1"
    assert normalized[1]["tool_calls"][0]["function"]["arguments"] == "{}"
    assert normalized[2]["content"] == ""
    assert normalized[2]["tool_call_id"] == "call-1"


def test_normalize_xai_tool_call_messages_tolerates_provider_passthrough_values():
    assert normalize_xai_tool_call_messages(None) is None  # type: ignore[arg-type]
    messages = [None, {"role": "assistant", "content": "ready"}]
    normalized = normalize_xai_tool_call_messages(messages)  # type: ignore[arg-type]
    assert normalized == [{"role": "assistant", "content": "ready"}]


def test_normalize_xai_tool_call_messages_fills_missing_content_and_tool_fields():
    messages = [
        {"role": "user"},
        {
            "role": "assistant",
            "tool_calls": [
                {
                    "id": "call-1",
                    "type": "function",
                    "function": {"name": None, "arguments": None},
                }
            ],
        },
        {"role": "tool", "tool_call_id": "call-1"},
    ]

    normalized = normalize_xai_tool_call_messages(messages)

    assert normalized[0]["content"] == ""
    assert normalized[1]["content"] == ""
    assert normalized[1]["tool_calls"][0]["function"]["name"] == ""
    assert normalized[1]["tool_calls"][0]["function"]["arguments"] == "{}"
    assert normalized[2]["content"] == ""


def test_promote_xai_stream_chunk_copies_reasoning_into_content():
    chunk = {
        "id": "x",
        "choices": [
            {
                "index": 0,
                "delta": {"role": "assistant", "content": None, "reasoning_content": "Planning files"},
                "finish_reason": None,
            }
        ],
    }
    promoted = _promote_xai_stream_chunk(chunk)
    assert promoted["choices"][0]["delta"]["content"] == "Planning files"

    # Existing content is left alone
    chunk2 = {
        "choices": [{"delta": {"content": "visible", "reasoning_content": "hidden"}}],
    }
    assert _promote_xai_stream_chunk(chunk2)["choices"][0]["delta"]["content"] == "visible"

    # Empty / odd shapes are tolerated
    assert _promote_xai_stream_chunk({}) == {}
    assert _promote_xai_stream_chunk({"choices": []}) == {"choices": []}


def test_deep_strip_nulls_removes_nested_none_values():
    payload = {
        "role": "assistant",
        "content": "",
        "tool_calls": [
            {
                "id": "call-1",
                "type": "function",
                "function": {"name": "t", "arguments": "{}", "extra": None},
                "index": None,
            }
        ],
        "refusal": None,
    }
    cleaned = _deep_strip_nulls(payload)
    assert cleaned == {
        "role": "assistant",
        "content": "",
        "tool_calls": [
            {
                "id": "call-1",
                "type": "function",
                "function": {"name": "t", "arguments": "{}"},
            }
        ],
    }


def test_sanitize_xai_completion_kwargs_normalizes_messages_and_tools():
    kwargs = {
        "model": "xai/grok-4.5",
        "messages": [
            {"role": "user", "content": "hi"},
            {
                "role": "assistant",
                "content": None,
                "tool_calls": [
                    {
                        "id": None,
                        "type": "function",
                        "function": {"name": "write_code_file", "arguments": None},
                    }
                ],
            },
            {"role": "tool", "tool_call_id": "call_0", "content": None},
        ],
        "tools": [
            {
                "type": "function",
                "function": {
                    "name": "write_code_file",
                    "description": "write",
                    "parameters": {"type": "object", "properties": {}, "default": None},
                },
            }
        ],
    }

    sanitized = _sanitize_xai_completion_kwargs(kwargs)
    assert sanitized["messages"][1]["content"] == ""
    assert sanitized["messages"][1]["tool_calls"][0]["id"] == "call_0"
    assert sanitized["messages"][1]["tool_calls"][0]["function"]["arguments"] == "{}"
    assert sanitized["messages"][2]["content"] == ""
    assert "default" not in sanitized["tools"][0]["function"]["parameters"]
    assert "null" not in json.dumps(sanitized["messages"])


def test_sanitize_xai_completion_kwargs_strips_stop_for_grok_build():
    """grok-build-0.1 rejects stop; CrewAI often injects it for agents."""
    kwargs = {
        "model": "xai/grok-build-0.1",
        "messages": [{"role": "user", "content": "build"}],
        "stop": ["\nObservation:", "\nFinal Answer:"],
        "stop_sequences": ["END"],
        "logit_bias": {"1": 1},
        "temperature": 0.2,
    }
    sanitized = _sanitize_xai_completion_kwargs(kwargs)
    assert "stop" not in sanitized
    assert "stop_sequences" not in sanitized
    assert "logit_bias" not in sanitized
    assert sanitized["temperature"] == 0.2
    assert sanitized["model"] == "xai/grok-build-0.1"


def test_drop_xai_unsupported_params_removes_stop():
    cleaned = _drop_xai_unsupported_params({"stop": ["x"], "model": "xai/grok-build-0.1"})
    assert cleaned == {"model": "xai/grok-build-0.1"}


def test_normalize_xai_tool_call_messages_fixes_null_tool_call_ids_and_sdk_objects():
    class DeltaFunction:
        def __init__(self):
            self.name = "write_code_file"
            self.arguments = None

        def model_dump(self, exclude_none=False):
            return {"name": self.name, "arguments": self.arguments}

    class DeltaToolCall:
        def __init__(self):
            self.id = None
            self.type = "function"
            self.index = 0
            self.function = DeltaFunction()

        def model_dump(self, exclude_none=False):
            return {
                "id": self.id,
                "type": self.type,
                "index": self.index,
                "function": self.function.model_dump(),
            }

    messages = [
        {"role": "user", "content": "write files", "cache_breakpoint": True},
        {
            "role": "assistant",
            "content": None,
            "refusal": None,
            "tool_calls": [DeltaToolCall()],
            "raw_tool_call_parts": [{"foo": None}],
        },
        {"role": "tool", "tool_call_id": None, "name": "write_code_file", "content": None},
    ]

    normalized = normalize_xai_tool_call_messages(messages)

    assert "cache_breakpoint" not in normalized[0]
    assert normalized[1]["content"] == ""
    assert "refusal" not in normalized[1]
    assert "raw_tool_call_parts" not in normalized[1]
    tool_call = normalized[1]["tool_calls"][0]
    assert tool_call["id"] == "call_0"
    assert tool_call["type"] == "function"
    assert "index" not in tool_call
    assert tool_call["function"]["name"] == "write_code_file"
    assert tool_call["function"]["arguments"] == "{}"
    assert normalized[2]["tool_call_id"] == "call_0"
    assert normalized[2]["content"] == ""
    assert "name" not in normalized[2]
    # Ensure the payload has no JSON-null string fields when serialized.
    import json

    raw = json.dumps(normalized)
    assert "null" not in raw


def test_xai_compatible_llm_normalizes_sync_calls():
    llm = XAICompatibleLLM(model="xai/grok-3-mini", api_key="xai-secret")
    messages = [{"role": "assistant", "content": None, "tool_calls": [{"id": "call-1"}]}]

    with patch.object(LLM, "call", return_value="done") as call:
        result = llm.call(messages, tools=[{"type": "function"}])

    assert result == "done"
    assert call.call_args.args[0][0]["content"] == ""
    assert call.call_args.kwargs["tools"] == [{"type": "function"}]


@pytest.mark.asyncio
async def test_xai_compatible_llm_normalizes_async_calls():
    llm = XAICompatibleLLM(model="xai/grok-3-mini", api_key="xai-secret")
    messages = [{"role": "assistant", "content": None, "tool_calls": [{"id": "call-1"}]}]

    with patch.object(LLM, "acall", return_value="done") as call:
        result = await llm.acall(messages, callbacks=["callback"])

    assert result == "done"
    assert call.call_args.args[0][0]["content"] == ""
    assert call.call_args.kwargs["callbacks"] == ["callback"]


def test_xai_compatible_llm_normalizes_prepare_completion_params():
    llm = XAICompatibleLLM(model="xai/grok-3-mini", api_key="xai-secret", stream=True)
    messages = [
        {"role": "user", "content": "write a file"},
        {"role": "assistant", "content": None, "tool_calls": [{"id": "call-1", "type": "function"}]},
        {"role": "tool", "content": None, "tool_call_id": "call-1"},
    ]

    params = llm._prepare_completion_params(messages, tools=[{"type": "function"}])

    assert params["messages"][1]["content"] == ""
    assert params["messages"][2]["content"] == ""
    assert messages[1]["content"] is None


def test_xai_compatible_llm_normalizes_streaming_and_non_streaming_params():
    llm = XAICompatibleLLM(model="xai/grok-3-mini", api_key="xai-secret", stream=True)
    dirty_params = {
        "model": "xai/grok-3-mini",
        "messages": [
            {"role": "user", "content": "write a file"},
            {"role": "assistant", "content": None, "tool_calls": [{"id": "call-1"}]},
            {"role": "tool", "content": None, "tool_call_id": "call-1"},
        ],
    }

    with patch.object(LLM, "_handle_streaming_response", return_value="streamed") as stream_handler:
        streamed = llm._handle_streaming_response(dirty_params)
    assert streamed == "streamed"
    stream_params = stream_handler.call_args.kwargs.get("params") or stream_handler.call_args.args[0]
    assert stream_params["messages"][1]["content"] == ""
    assert stream_params["messages"][2]["content"] == ""
    assert stream_params["api_key"] == "xai-secret"
    # Original params must stay unchanged for callers that reuse the dict.
    assert dirty_params["messages"][1]["content"] is None

    with patch.object(LLM, "_handle_non_streaming_response", return_value="done") as non_stream_handler:
        done = llm._handle_non_streaming_response(dirty_params)
    assert done == "done"
    non_stream_params = non_stream_handler.call_args.kwargs.get("params") or non_stream_handler.call_args.args[0]
    assert non_stream_params["messages"][2]["content"] == ""
    assert non_stream_params["api_key"] == "xai-secret"


@pytest.mark.asyncio
async def test_xai_compatible_llm_normalizes_async_handler_params():
    llm = XAICompatibleLLM(model="xai/grok-3-mini", api_key="xai-secret")
    dirty_params = {
        "model": "xai/grok-3-mini",
        "messages": [
            {"role": "assistant", "content": None, "tool_calls": [{"id": "call-1"}]},
            {"role": "tool", "content": None, "tool_call_id": "call-1"},
        ],
    }

    with patch.object(LLM, "_ahandle_streaming_response", return_value="streamed") as stream_handler:
        streamed = await llm._ahandle_streaming_response(dirty_params)
    assert streamed == "streamed"
    assert stream_handler.call_args.args[0]["messages"][0]["content"] == ""
    assert stream_handler.call_args.args[0]["api_key"] == "xai-secret"

    with patch.object(LLM, "_ahandle_non_streaming_response", return_value="done") as non_stream_handler:
        done = await llm._ahandle_non_streaming_response(dirty_params)
    assert done == "done"
    assert non_stream_handler.call_args.args[0]["messages"][1]["content"] == ""


def test_structured_output_with_credentials_passes_api_key_to_litellm():
    from pydantic import BaseModel

    class Brief(BaseModel):
        summary: str

    llm = XAICompatibleLLM(model="xai/grok-3-mini", api_key="oauth-access-token", base_url="https://api.x.ai/v1")
    captured: dict = {}

    class FakeCompletions:
        def create(self, **kwargs):
            captured.update(kwargs)
            return Brief(summary="ok")

    class FakeChat:
        completions = FakeCompletions()

    class FakeClient:
        chat = FakeChat()

    with patch("instructor.from_litellm", return_value=FakeClient()) as from_litellm:
        from app.crew.llm import structured_output_with_credentials

        result = structured_output_with_credentials(llm, "USER: hello", Brief)

    assert result.summary == "ok"
    # Prefer JSON_SCHEMA over TOOLS for xAI compatibility.
    assert from_litellm.call_args.kwargs.get("mode") is not None or (
        len(from_litellm.call_args.args) >= 2
    )
    mode = from_litellm.call_args.kwargs.get("mode") or (
        from_litellm.call_args.args[1] if len(from_litellm.call_args.args) > 1 else None
    )
    from instructor import Mode

    assert mode in {Mode.JSON_SCHEMA, Mode.MD_JSON, Mode.JSON}
    bound_completion = from_litellm.call_args.args[0]
    # Invoke the bound completion wrapper to prove credentials are injected.
    with patch("litellm.completion", return_value="done") as completion:
        bound_completion(model="xai/grok-3-mini", messages=[{"role": "user", "content": "hi"}])
    assert completion.call_args.kwargs["api_key"] == "oauth-access-token"
    assert completion.call_args.kwargs["base_url"] == "https://api.x.ai/v1"


def test_structured_output_falls_back_across_modes_then_parses_text():
    from pydantic import BaseModel

    from app.crew.llm import structured_output_with_credentials

    class Brief(BaseModel):
        summary: str

    llm = XAICompatibleLLM(model="xai/grok-3-mini", api_key="k", base_url="https://api.x.ai/v1")
    calls: list = []

    def fail_from_litellm(*_a, **_k):
        calls.append(_k.get("mode") or (_a[1] if len(_a) > 1 else None))

        class Boom:
            class chat:
                class completions:
                    @staticmethod
                    def create(**_kwargs):
                        raise RuntimeError("No tool calls or function call found in response (mode: TOOLS)")

        return Boom()

    with patch("instructor.from_litellm", side_effect=fail_from_litellm):
        result = structured_output_with_credentials(
            llm,
            'Here is the plan:\n```json\n{"summary":"from text"}\n```',
            Brief,
        )
    assert result.summary == "from text"
    assert len(calls) >= 2  # tried multiple instructor modes before text parse


def test_xai_compatible_llm_structured_non_streaming_uses_credential_bound_path():
    from pydantic import BaseModel

    class Brief(BaseModel):
        summary: str

    llm = XAICompatibleLLM(model="xai/grok-3-mini", api_key="oauth-access-token")
    params = {
        "model": "xai/grok-3-mini",
        "api_key": "oauth-access-token",
        "messages": [{"role": "user", "content": "plan this"}],
    }
    with patch(
        "app.crew.llm.structured_output_with_credentials",
        return_value=Brief(summary="brief"),
    ) as structured:
        result = llm._handle_non_streaming_response(params, response_model=Brief)
    assert result == '{"summary":"brief"}'
    structured.assert_called_once()
    assert structured.call_args.args[0] is llm


def test_xai_compatible_llm_preserves_completion_params_without_messages():
    llm = XAICompatibleLLM(model="xai/grok-3-mini", api_key="xai-secret")
    with patch.object(LLM, "_prepare_completion_params", return_value={"model": "xai/grok-3-mini"}):
        params = llm._prepare_completion_params("hello")
    # Credentials are reasserted even when the parent prepare path omits them.
    assert params == {"model": "xai/grok-3-mini", "api_key": "xai-secret"}


def test_is_capacity_error_detects_xai_overload():
    assert _is_capacity_error(
        RuntimeError("The model is currently at capacity due to high demand.")
    )
    assert not _is_capacity_error(RuntimeError("invalid api key"))


def test_call_with_capacity_retry_succeeds_after_transient_failure():
    calls = {"n": 0}

    def flaky():
        calls["n"] += 1
        if calls["n"] < 3:
            raise RuntimeError("XaiException - The model is currently at capacity due to high demand.")
        return "ok"

    with patch("app.crew.llm.time.sleep") as sleep:
        assert _call_with_capacity_retry("test", flaky) == "ok"
    assert calls["n"] == 3
    assert sleep.call_count == 2


def test_call_with_capacity_retry_raises_non_capacity():
    with pytest.raises(RuntimeError, match="boom"):
        _call_with_capacity_retry("test", lambda: (_ for _ in ()).throw(RuntimeError("boom")))


def test_get_agent_llm_default():
    llm = get_agent_llm()
    assert getattr(llm, "model") == "ollama/llama3.1"


def test_get_agent_llm_uses_authenticated_users_selected_model():
    with patch(
        "app.crew.llm.provider_settings_service.resolve_litellm_config",
        return_value={
            "provider": "mistral",
            "model": "mistral/mistral-large-latest",
            "api_key": "mistral-key",
            "base_url": "https://api.mistral.ai/v1",
        },
    ) as resolve:
        llm = get_agent_llm("user-123")

    resolve.assert_called_once_with("user-123")
    assert getattr(llm, "model") == "mistral/mistral-large-latest"
    assert getattr(llm, "api_key") == "mistral-key"
    assert getattr(llm, "base_url") == "https://api.mistral.ai/v1"


def test_get_agent_llm_custom_provider_does_not_set_provider_env_var():
    with patch(
        "app.crew.llm.provider_settings_service.resolve_litellm_config",
        return_value={
            "provider": "custom",
            "model": "vendor/model",
            "api_key": "custom-key",
            "base_url": "https://llm.example/v1",
        },
    ):
        llm = get_agent_llm("user-123")

    assert getattr(llm, "api_key") == "custom-key"
    assert getattr(llm, "base_url") == "https://llm.example/v1"


def test_get_agent_llm_openai_compatible():
    settings.llm_provider = "openai-compatible"
    settings.llm_model = "kimchi/kimi-k2.7"
    settings.openai_base_url = "http://localhost:20128/v1"
    settings.openai_api_key = None

    llm = get_agent_llm()
    assert getattr(llm, "model") == "openai/kimchi/kimi-k2.7"
    assert getattr(llm, "base_url") == "http://localhost:20128/v1"
    assert getattr(llm, "api_key") == "not-needed"


def test_get_agent_llm_openai_compatible_with_key():
    settings.llm_provider = "openai-compatible"
    settings.llm_model = "kimchi/kimi-k2.7"
    settings.openai_base_url = "http://localhost:20128/v1"
    settings.openai_api_key = "real-key"

    llm = get_agent_llm()
    assert getattr(llm, "api_key") == "real-key"


def test_get_agent_llm_openai_compatible_does_not_mutate_moonshot_env():
    settings.llm_provider = "openai-compatible"
    settings.llm_model = "test-model"
    settings.openai_base_url = "http://localhost:1234/v1"
    settings.openai_api_key = None

    with patch.dict(os.environ, {"KIMI_API_KEY": "secret", "MOONSHOT_API_KEY": "secret2"}):
        llm = get_agent_llm()
        assert os.environ.get("KIMI_API_KEY") == "secret"
        assert os.environ.get("MOONSHOT_API_KEY") == "secret2"
    assert llm is not None


def test_get_agent_llm_moonshot():
    settings.llm_provider = "moonshot"
    settings.llm_model = "kimi-k2"
    settings.moonshot_api_key = "moon-key"

    llm = get_agent_llm()
    assert getattr(llm, "model") == "moonshot/kimi-k2"
    assert getattr(llm, "api_key") == "moon-key"


def test_get_agent_llm_openai():
    settings.llm_provider = "openai"
    settings.llm_model = "gpt-4o"
    settings.openai_api_key = "oai-key"

    llm = get_agent_llm()
    assert getattr(llm, "model") == "openai/gpt-4o"
    assert getattr(llm, "api_key") == "oai-key"


def test_get_agent_llm_does_not_mirror_api_key_into_process_environment():
    settings.llm_provider = "xai"
    settings.llm_model = "grok-3-mini"
    settings.xai_api_key = "xai-secret"

    with patch.dict(os.environ, {}, clear=False):
        os.environ.pop("XAI_API_KEY", None)
        get_agent_llm()
        assert os.environ.get("XAI_API_KEY") is None


def test_get_agent_llm_no_base_url():
    settings.llm_provider = "openai"
    settings.llm_model = "gpt-4o"
    settings.openai_api_key = "oai-key"
    settings.openai_base_url = None

    llm = get_agent_llm()
    assert getattr(llm, "base_url", None) is None or getattr(llm, "base_url") is None


def test_get_agent_llm_raises_when_provider_requires_key_but_none_set():
    settings.llm_provider = "xai"
    settings.llm_model = "xai/grok-3-mini"
    settings.xai_api_key = None

    with pytest.raises(ValueError, match="Grok / xAI API key is not configured"):
        get_agent_llm()


def test_get_agent_llm_raises_for_authenticated_user_without_key():
    with patch(
        "app.crew.llm.provider_settings_service.resolve_litellm_config",
        return_value={
            "provider": "xai",
            "model": "xai/grok-3-mini",
            "api_key": None,
            "base_url": None,
        },
    ):
        with pytest.raises(ValueError, match="Grok / xAI API key is not configured"):
            get_agent_llm("user-456")


def test_get_agent_llm_raises_for_xai_oauth_without_access_token():
    with patch(
        "app.crew.llm.provider_settings_service.resolve_litellm_config",
        return_value={
            "provider": "xai-oauth",
            "model": "xai/grok-4.5",
            "api_key": None,
            "base_url": "https://api.x.ai/v1",
        },
    ):
        with pytest.raises(ValueError, match="access token is not configured"):
            get_agent_llm("user-oauth")


def test_get_agent_llm_gemini_disables_streaming():
    with patch(
        "app.crew.llm.provider_settings_service.resolve_litellm_config",
        return_value={
            "provider": "gemini",
            "model": "gemini/gemini-3.5-flash-lite",
            "api_key": "gemini-key",
            "base_url": None,
        },
    ):
        llm = get_agent_llm("user-gemini")

    # CrewAI strips the provider prefix when it instantiates the native Gemini
    # adapter; the important checks are native routing, stored credentials, and
    # non-streaming execution.
    assert getattr(llm, "api_key") == "gemini-key"
    assert getattr(llm, "stream") is False
    assert getattr(llm, "llm_type", None) == "gemini"


def test_get_agent_llm_gemini_sets_google_env_for_structured_fallback(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    with patch(
        "app.crew.llm.provider_settings_service.resolve_litellm_config",
        return_value={
            "provider": "gemini",
            "model": "gemini/gemini-3.5-flash-lite",
            "api_key": "gemini-user-key",
            "base_url": None,
        },
    ):
        get_agent_llm("user-gemini-env")

    assert os.environ["GEMINI_API_KEY"] == "gemini-user-key"
    assert os.environ["GOOGLE_API_KEY"] == "gemini-user-key"
