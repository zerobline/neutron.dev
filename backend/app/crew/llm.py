from __future__ import annotations

import json
import logging
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from typing import Any

from crewai import LLM

from app.config import settings
from app.providers import get_provider
from app.services import provider_settings_service

logger = logging.getLogger(__name__)

# Transient provider overload (common on free/shared xAI tiers under load).
_CAPACITY_HINTS = (
    "at capacity",
    "high demand",
    "service tier",
    "priority processing",
    "midstreamfallback",
    "model is currently at capacity",
    "overloaded",
    "service unavailable",
    "temporarily unavailable",
)
_CAPACITY_RETRY_DELAYS_S = (4.0, 12.0, 28.0)


def _is_capacity_error(exc: BaseException) -> bool:
    text = str(exc).lower()
    return any(hint in text for hint in _CAPACITY_HINTS)


def _call_with_capacity_retry(label: str, fn: Callable[[], Any]) -> Any:
    """Retry transient capacity/overload errors with backoff."""
    last_exc: BaseException | None = None
    for attempt, delay in enumerate((0.0, *_CAPACITY_RETRY_DELAYS_S)):
        if delay:
            logger.warning(
                "%s hit provider capacity (attempt %s); retrying in %.0fs",
                label,
                attempt,
                delay,
            )
            time.sleep(delay)
        try:
            return fn()
        except Exception as exc:
            last_exc = exc
            if not _is_capacity_error(exc) or attempt >= len(_CAPACITY_RETRY_DELAYS_S):
                raise
    assert last_exc is not None
    raise last_exc


# CrewAI / OpenAI SDK fields that must never reach xAI's chat schema.
_XAI_MESSAGE_DROP_KEYS = frozenset(
    {
        "cache_breakpoint",
        "raw_tool_call_parts",
        "annotations",
        "audio",
        "function_call",
        "refusal",
        "reasoning_content",
    }
)
_XAI_TOOL_CALL_DROP_KEYS = frozenset({"index"})


def _to_plain_dict(value: Any) -> dict[str, Any] | None:
    """Best-effort conversion of SDK/pydantic message objects to plain dicts."""
    if isinstance(value, dict):
        return dict(value)
    model_dump = getattr(value, "model_dump", None)
    if callable(model_dump):
        dumped = model_dump(exclude_none=False)
        if isinstance(dumped, dict):
            return dict(dumped)
    if hasattr(value, "__dict__"):
        data = {k: v for k, v in vars(value).items() if not k.startswith("_")}
        if data:
            return data
    return None


def _coerce_message_content(content: Any) -> str | list[Any]:
    """Coerce message content into an xAI-safe value.

    xAI rejects JSON null for message content. OpenAI-compatible tool-call
    history often uses content=None for assistant tool-call turns and empty
    tool results. Multimodal list content is preserved when present.
    """
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        cleaned: list[Any] = []
        for block in content:
            if block is None:
                continue
            block_dict = _to_plain_dict(block)
            if block_dict is None:
                cleaned.append(block)
                continue
            next_block = dict(block_dict)
            if next_block.get("type") == "text" and next_block.get("text") is None:
                next_block["text"] = ""
            cleaned.append(next_block)
        return cleaned
    return str(content)


def _coerce_tool_arguments(arguments: Any) -> str:
    """xAI requires function.arguments to be a JSON string, never null/object."""
    if arguments is None:
        return "{}"
    if isinstance(arguments, str):
        return arguments if arguments.strip() else "{}"
    if isinstance(arguments, (dict, list)):
        import json

        return json.dumps(arguments)
    return str(arguments)


def _normalize_tool_call(call: Any, index: int) -> dict[str, Any]:
    """Normalize one tool-call entry so every string field is a real string."""
    call_dict = _to_plain_dict(call) or {}
    cleaned: dict[str, Any] = {
        k: v for k, v in call_dict.items() if k not in _XAI_TOOL_CALL_DROP_KEYS
    }

    call_id = cleaned.get("id")
    if call_id is None or call_id == "":
        cleaned["id"] = f"call_{index}"
    else:
        cleaned["id"] = str(call_id)

    call_type = cleaned.get("type")
    cleaned["type"] = "function" if call_type is None or call_type == "" else str(call_type)

    function = cleaned.get("function")
    function_dict = _to_plain_dict(function) if function is not None else None
    if function_dict is None:
        function_dict = {}
    name = function_dict.get("name")
    function_dict["name"] = "" if name is None else str(name)
    function_dict["arguments"] = _coerce_tool_arguments(function_dict.get("arguments"))
    cleaned["function"] = function_dict
    return cleaned


def normalize_xai_tool_call_messages(messages: str | list[dict[str, Any]]) -> str | list[dict[str, Any]]:
    """Make OpenAI-style message history valid for xAI's stricter schema.

    OpenAI-compatible clients and CrewAI native tool-calling retain
    ``content=None`` for assistant tool-call turns, omit or null tool-call
    ids on streaming deltas, and may attach non-API keys (cache breakpoints,
    raw parts). xAI rejects JSON null for string fields such as ``content``,
    ``tool_calls[].id``, and ``function.arguments``.
    """
    if isinstance(messages, str) or not isinstance(messages, list):
        return messages

    normalized: list[dict[str, Any]] = []
    for message in messages:
        if message is None:
            continue

        message_dict = _to_plain_dict(message)
        if message_dict is None:
            # Unknown non-mapping value — keep only if it's somehow useful.
            continue

        next_message = {
            k: v for k, v in message_dict.items() if k not in _XAI_MESSAGE_DROP_KEYS
        }
        next_message["content"] = _coerce_message_content(next_message.get("content"))

        role = next_message.get("role")
        if role is None:
            next_message["role"] = "user"
        else:
            next_message["role"] = str(role)

        tool_calls = next_message.get("tool_calls")
        if tool_calls is None:
            next_message.pop("tool_calls", None)
        elif isinstance(tool_calls, list):
            cleaned_calls = [
                _normalize_tool_call(call, index)
                for index, call in enumerate(tool_calls)
                if call is not None
            ]
            if cleaned_calls:
                next_message["tool_calls"] = cleaned_calls
            else:
                next_message.pop("tool_calls", None)

        if next_message.get("role") == "tool":
            tool_call_id = next_message.get("tool_call_id")
            if tool_call_id is None or tool_call_id == "":
                next_message["tool_call_id"] = "call_0"
            else:
                next_message["tool_call_id"] = str(tool_call_id)
            # xAI does not need the OpenAI optional name field on tool results.
            next_message.pop("name", None)

        # Drop any remaining top-level nulls so they cannot serialize as JSON null.
        next_message = {k: v for k, v in next_message.items() if v is not None}
        # Ensure content always remains a string (required by xAI).
        if "content" not in next_message:
            next_message["content"] = ""

        normalized.append(next_message)
    return normalized


def _deep_strip_nulls(value: Any) -> Any:
    """Recursively drop JSON-null values so they cannot reach xAI's schema.

    Empty strings and empty containers are preserved (they are valid). Nested
    dicts/lists are rebuilt without ``None`` entries.
    """
    if value is None:
        return None
    if isinstance(value, dict):
        cleaned: dict[str, Any] = {}
        for key, item in value.items():
            if item is None:
                continue
            cleaned[key] = _deep_strip_nulls(item)
        return cleaned
    if isinstance(value, list):
        return [_deep_strip_nulls(item) for item in value if item is not None]
    if isinstance(value, tuple):
        return [_deep_strip_nulls(item) for item in value if item is not None]
    return value


def _find_json_null_paths(value: Any, path: str = "$") -> list[str]:
    """Return JSONPath-like locations of Python None values (for diagnostics)."""
    hits: list[str] = []
    if value is None:
        hits.append(path)
        return hits
    if isinstance(value, dict):
        for key, item in value.items():
            hits.extend(_find_json_null_paths(item, f"{path}.{key}"))
    elif isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            hits.extend(_find_json_null_paths(item, f"{path}[{index}]"))
    return hits


# OpenAI/CrewAI params that some xAI models reject (e.g. grok-build-0.1).
_XAI_UNSUPPORTED_COMPLETION_KEYS = frozenset(
    {
        "stop",
        "stop_sequences",
        "logit_bias",
    }
)


def _drop_xai_unsupported_params(params: dict[str, Any]) -> dict[str, Any]:
    """Remove completion kwargs that xAI models do not accept."""
    next_params = dict(params)
    for key in _XAI_UNSUPPORTED_COMPLETION_KEYS:
        if key in next_params:
            next_params.pop(key, None)
    # Also drop empty/null optional fields that can confuse strict schemas.
    for key in ("presence_penalty", "frequency_penalty", "user"):
        if key in next_params and next_params[key] in (None, "", 0, 0.0):
            next_params.pop(key, None)
    return next_params


def _sanitize_xai_completion_kwargs(kwargs: dict[str, Any]) -> dict[str, Any]:
    """Last-mile sanitizer applied immediately before litellm.completion."""
    next_kwargs = _drop_xai_unsupported_params(dict(kwargs))
    if "messages" in next_kwargs:
        next_kwargs["messages"] = normalize_xai_tool_call_messages(next_kwargs["messages"])
        # Extra guard: drop any nested None that normalization left behind.
        next_kwargs["messages"] = _deep_strip_nulls(next_kwargs["messages"])
        # xAI requires content to be a string; re-assert after deep strip.
        messages = next_kwargs["messages"]
        if isinstance(messages, list):
            for message in messages:
                if isinstance(message, dict) and "content" not in message:
                    message["content"] = ""
    if next_kwargs.get("tools") is not None:
        next_kwargs["tools"] = _deep_strip_nulls(next_kwargs["tools"])
    return next_kwargs


def _delta_get(delta: Any, key: str) -> Any:
    if delta is None:
        return None
    if isinstance(delta, dict):
        return delta.get(key)
    return getattr(delta, key, None)


def _delta_set(delta: Any, key: str, value: Any) -> None:
    if delta is None:
        return
    if isinstance(delta, dict):
        delta[key] = value
        return
    try:
        setattr(delta, key, value)
    except Exception:
        # Some pydantic models reject assignment; try model_extra.
        extra = getattr(delta, "__dict__", None)
        if isinstance(extra, dict):
            extra[key] = value


def _promote_xai_stream_chunk(chunk: Any) -> Any:
    """Make xAI stream deltas readable to CrewAI's content extractor.

    Grok often streams ``reasoning_content`` (and tool-call deltas) with
    ``content=null``. CrewAI only reads ``delta.content``, so it logs
    \"Received N chunks but no content was extracted\" even when the stream is
    valid. Promote reasoning into content when content is empty.
    """
    try:
        choices = None
        if isinstance(chunk, dict):
            choices = chunk.get("choices")
        else:
            choices = getattr(chunk, "choices", None)
        if not choices:
            return chunk
        choice = choices[0]
        if isinstance(choice, dict):
            delta = choice.get("delta")
        else:
            delta = getattr(choice, "delta", None)
        if delta is None:
            return chunk

        content = _delta_get(delta, "content")
        reasoning = _delta_get(delta, "reasoning_content")
        if (content is None or content == "") and isinstance(reasoning, str) and reasoning:
            _delta_set(delta, "content", reasoning)
    except Exception:
        logger.debug("xAI stream chunk promote failed", exc_info=True)
    return chunk


def _wrap_xai_completion_stream(stream: Any) -> Any:
    """Wrap a litellm streaming iterator so each chunk is xAI-normalized."""
    if stream is None or isinstance(stream, (str, bytes, dict)):
        return stream
    if not hasattr(stream, "__iter__"):
        return stream

    def _generator() -> Any:
        for chunk in stream:
            yield _promote_xai_stream_chunk(chunk)

    return _generator()


@contextmanager
def _xai_safe_litellm_completion() -> Iterator[None]:
    """Monkey-patch litellm.completion for the duration of one CrewAI call.

    CrewAI / LiteLLM can reintroduce OpenAI-style nulls after our earlier
    normalization (streaming tool-call objects, optional fields). Patching at
    the call boundary is the last chance to keep the HTTP body xAI-valid.
    """
    import litellm

    original = litellm.completion

    def completion_with_xai_sanitize(*args: Any, **kwargs: Any) -> Any:
        safe_kwargs = _sanitize_xai_completion_kwargs(kwargs)
        try:
            result = original(*args, **safe_kwargs)
        except Exception as exc:
            message = str(exc)
            if "null" in message.lower() or "deserialize" in message.lower():
                null_paths = _find_json_null_paths(safe_kwargs.get("messages"))
                try:
                    preview = json.dumps(safe_kwargs.get("messages"), default=str)[:4000]
                except Exception:
                    preview = repr(safe_kwargs.get("messages"))[:4000]
                logger.error(
                    "xAI request rejected; null_paths=%s message_count=%s preview=%s error=%s",
                    null_paths,
                    len(safe_kwargs.get("messages") or [])
                    if isinstance(safe_kwargs.get("messages"), list)
                    else "n/a",
                    preview,
                    message[:500],
                )
            raise

        # Streaming: promote reasoning_content so CrewAI extracts tokens.
        if safe_kwargs.get("stream") or kwargs.get("stream"):
            return _wrap_xai_completion_stream(result)
        return result

    litellm.completion = completion_with_xai_sanitize  # type: ignore[assignment]
    try:
        yield
    finally:
        litellm.completion = original  # type: ignore[assignment]


def _normalize_completion_params(params: dict[str, Any], llm: Any | None = None) -> dict[str, Any]:
    """Return a shallow-copied params dict with xAI-safe messages and credentials."""
    next_params = _drop_xai_unsupported_params(dict(params))
    if "messages" in next_params:
        next_params["messages"] = normalize_xai_tool_call_messages(next_params["messages"])
        next_params["messages"] = _deep_strip_nulls(next_params["messages"])
        messages = next_params["messages"]
        if isinstance(messages, list):
            for message in messages:
                if isinstance(message, dict) and "content" not in message:
                    message["content"] = ""
    if next_params.get("tools") is not None:
        next_params["tools"] = _deep_strip_nulls(next_params["tools"])
    if llm is not None:
        api_key = getattr(llm, "api_key", None)
        if api_key and not next_params.get("api_key"):
            next_params["api_key"] = api_key
        base_url = getattr(llm, "base_url", None) or getattr(llm, "api_base", None)
        if base_url:
            next_params.setdefault("base_url", base_url)
            next_params.setdefault("api_base", base_url)
    return next_params


def _inject_llm_credentials(llm: Any, kwargs: dict[str, Any]) -> dict[str, Any]:
    """Ensure litellm/instructor requests keep the CrewAI LLM credentials."""
    next_kwargs = dict(kwargs)
    api_key = getattr(llm, "api_key", None)
    if api_key and not next_kwargs.get("api_key"):
        next_kwargs["api_key"] = api_key

    base_url = getattr(llm, "base_url", None) or getattr(llm, "api_base", None)
    if base_url:
        next_kwargs.setdefault("base_url", base_url)
        next_kwargs.setdefault("api_base", base_url)

    if "messages" in next_kwargs:
        next_kwargs["messages"] = normalize_xai_tool_call_messages(next_kwargs["messages"])
    return next_kwargs


def _credential_bound_completion(llm: Any) -> Callable[..., Any]:
    """Wrap litellm.completion so instructor structured-output calls keep auth."""

    def completion_with_creds(*args: Any, **kwargs: Any) -> Any:
        import litellm

        return litellm.completion(*args, **_inject_llm_credentials(llm, kwargs))

    return completion_with_creds


def _parse_model_from_text(text: str, response_model: type) -> Any | None:
    """Best-effort parse of a Pydantic model from free-form model text."""
    if not text or not str(text).strip():
        return None
    raw = str(text).strip()
    # Try direct JSON, then fenced ```json blocks.
    candidates = [raw]
    if "```" in raw:
        import re

        for match in re.finditer(r"```(?:json)?\s*([\s\S]*?)```", raw, flags=re.IGNORECASE):
            block = match.group(1).strip()
            if block:
                candidates.append(block)
    # Outermost object/array slice
    for opener, closer in (("{", "}"), ("[", "]")):
        start = raw.find(opener)
        end = raw.rfind(closer)
        if start >= 0 and end > start:
            candidates.append(raw[start : end + 1])

    for candidate in candidates:
        try:
            return response_model.model_validate_json(candidate)
        except Exception:
            try:
                data = json.loads(candidate)
                return response_model.model_validate(data)
            except Exception:
                continue
    return None


def structured_output_with_credentials(llm: Any, content: str, response_model: type) -> Any:
    """Run instructor structured output without dropping per-user API credentials.

    CrewAI's InternalInstructor builds ``instructor.from_litellm(completion)`` and
    only passes model/messages. That drops api_key/base_url, so xAI returns
    ``unauthenticated:no-credentials`` even when the agent LLM was configured.

    Prefer JSON modes over TOOLS: xAI/Grok frequently returns
    ``finish_reason=tool_calls`` with ``message.tool_calls=None``, which breaks
    instructor's default TOOLS mode with
    ``No tool calls or function call found in response``.
    """
    import instructor
    from instructor import Mode

    messages = [{"role": "user", "content": content or ""}]
    completion = _credential_bound_completion(llm)
    # JSON_SCHEMA / MD_JSON avoid the broken TOOLS path on xAI.
    modes = (Mode.JSON_SCHEMA, Mode.MD_JSON, Mode.JSON)
    last_error: Exception | None = None
    for mode in modes:
        try:
            client = instructor.from_litellm(completion, mode=mode)
            return client.chat.completions.create(
                model=llm.model,
                response_model=response_model,
                messages=messages,
            )
        except Exception as exc:
            last_error = exc
            logger.warning(
                "xAI structured output mode %s failed: %s",
                getattr(mode, "value", mode),
                str(exc)[:300],
            )

    # If the phase already streamed a JSON-looking body into ``content``, parse it.
    parsed = _parse_model_from_text(content, response_model)
    if parsed is not None:
        return parsed

    if last_error is not None:
        raise last_error
    raise ValueError(f"Unable to produce structured output for {response_model!r}")


class XAICompatibleLLM(LLM):
    """CrewAI LLM adapter that keeps xAI auth + message schema valid."""

    def _prepare_completion_params(
        self,
        messages,
        tools=None,
        skip_file_processing: bool = False,
    ):
        params = super()._prepare_completion_params(
            messages,
            tools=tools,
            skip_file_processing=skip_file_processing,
        )
        return _normalize_completion_params(params, self)

    def _handle_streaming_response(
        self,
        params,
        callbacks=None,
        available_functions=None,
        from_task=None,
        from_agent=None,
        response_model=None,
    ):
        params = _normalize_completion_params(params, self)

        def _stream_or_fallback(**handler_kwargs: Any) -> Any:
            """Stream first; on empty xAI chunks fall back to non-streaming."""

            def _attempt() -> Any:
                try:
                    return super(XAICompatibleLLM, self)._handle_streaming_response(**handler_kwargs)
                except Exception as exc:
                    if _is_capacity_error(exc):
                        raise
                    msg = str(exc)
                    empty_stream = (
                        "no content was extracted" in msg.lower()
                        or "no content received from streaming" in msg.lower()
                    )
                    if not empty_stream:
                        raise
                    logger.warning(
                        "xAI streaming returned no extractable content; retrying non-streaming"
                    )
                    non_stream_params = dict(handler_kwargs.get("params") or params)
                    non_stream_params["stream"] = False
                    non_stream_params.pop("stream_options", None)
                    return super(XAICompatibleLLM, self)._handle_non_streaming_response(
                        non_stream_params,
                        callbacks=handler_kwargs.get("callbacks", callbacks),
                        available_functions=handler_kwargs.get(
                            "available_functions", available_functions
                        ),
                        from_task=handler_kwargs.get("from_task", from_task),
                        from_agent=handler_kwargs.get("from_agent", from_agent),
                        response_model=handler_kwargs.get("response_model", response_model),
                    )

            return _call_with_capacity_retry("xAI stream", _attempt)

        with _xai_safe_litellm_completion():
            if response_model and self.is_litellm:
                # Stream text with credentials, then convert via credential-bound instructor.
                full_response = _stream_or_fallback(
                    params=params,
                    callbacks=callbacks,
                    available_functions=available_functions,
                    from_task=from_task,
                    from_agent=from_agent,
                    response_model=None,
                )
                if not isinstance(full_response, str):
                    return full_response
                if not full_response.strip():
                    # Empty stream (e.g. tool-only) — non-stream retry already attempted.
                    logger.warning("xAI structured stream empty after fallback; using empty content")
                result = structured_output_with_credentials(self, full_response or "", response_model)
                return result.model_dump_json()
            return _stream_or_fallback(
                params=params,
                callbacks=callbacks,
                available_functions=available_functions,
                from_task=from_task,
                from_agent=from_agent,
                response_model=response_model,
            )

    def _handle_non_streaming_response(
        self,
        params,
        callbacks=None,
        available_functions=None,
        from_task=None,
        from_agent=None,
        response_model=None,
    ):
        params = _normalize_completion_params(params, self)
        with _xai_safe_litellm_completion():
            if response_model and self.is_litellm:
                messages = params.get("messages", [])
                if not messages:
                    raise ValueError("Messages are required when using response_model")
                combined_content = "\n\n".join(
                    f"{msg.get('role', 'user').upper()}: {msg.get('content', '')}" for msg in messages
                )
                result = structured_output_with_credentials(self, combined_content, response_model)
                structured_response = result.model_dump_json()
                try:
                    from crewai.events.types.llm_events import LLMCallType

                    self._handle_emit_call_events(
                        response=structured_response,
                        call_type=LLMCallType.LLM_CALL,
                        from_task=from_task,
                        from_agent=from_agent,
                        messages=messages,
                        usage=None,
                    )
                except Exception:
                    pass
                return structured_response
            return super()._handle_non_streaming_response(
                params,
                callbacks=callbacks,
                available_functions=available_functions,
                from_task=from_task,
                from_agent=from_agent,
                response_model=response_model,
            )

    async def _ahandle_streaming_response(
        self,
        params,
        callbacks=None,
        available_functions=None,
        from_task=None,
        from_agent=None,
        response_model=None,
    ):
        params = _normalize_completion_params(params, self)
        with _xai_safe_litellm_completion():
            if response_model and self.is_litellm:
                full_response = await super()._ahandle_streaming_response(
                    params,
                    callbacks=callbacks,
                    available_functions=available_functions,
                    from_task=from_task,
                    from_agent=from_agent,
                    response_model=None,
                )
                if not isinstance(full_response, str):
                    return full_response
                result = structured_output_with_credentials(self, full_response, response_model)
                return result.model_dump_json()
            return await super()._ahandle_streaming_response(
                params,
                callbacks=callbacks,
                available_functions=available_functions,
                from_task=from_task,
                from_agent=from_agent,
                response_model=response_model,
            )

    async def _ahandle_non_streaming_response(
        self,
        params,
        callbacks=None,
        available_functions=None,
        from_task=None,
        from_agent=None,
        response_model=None,
    ):
        params = _normalize_completion_params(params, self)
        with _xai_safe_litellm_completion():
            if response_model and self.is_litellm:
                messages = params.get("messages", [])
                if not messages:
                    raise ValueError("Messages are required when using response_model")
                combined_content = "\n\n".join(
                    f"{msg.get('role', 'user').upper()}: {msg.get('content', '')}" for msg in messages
                )
                result = structured_output_with_credentials(self, combined_content, response_model)
                return result.model_dump_json()
            return await super()._ahandle_non_streaming_response(
                params,
                callbacks=callbacks,
                available_functions=available_functions,
                from_task=from_task,
                from_agent=from_agent,
                response_model=response_model,
            )

    def call(
        self,
        messages,
        tools=None,
        callbacks=None,
        available_functions=None,
        from_task=None,
        from_agent=None,
        response_model=None,
    ):
        def _attempt() -> Any:
            with _xai_safe_litellm_completion():
                return super(XAICompatibleLLM, self).call(
                    normalize_xai_tool_call_messages(messages),
                    tools=tools,
                    callbacks=callbacks,
                    available_functions=available_functions,
                    from_task=from_task,
                    from_agent=from_agent,
                    response_model=response_model,
                )

        return _call_with_capacity_retry("xAI call", _attempt)

    async def acall(
        self,
        messages,
        tools=None,
        callbacks=None,
        available_functions=None,
        from_task=None,
        from_agent=None,
        response_model=None,
    ):
        with _xai_safe_litellm_completion():
            return await super().acall(
                normalize_xai_tool_call_messages(messages),
                tools=tools,
                callbacks=callbacks,
                available_functions=available_functions,
                from_task=from_task,
                from_agent=from_agent,
                response_model=response_model,
            )


def get_agent_llm(user_id: str | None = None, agent_id: str | None = None) -> LLM:
    config = provider_settings_service.resolve_litellm_config(user_id) if user_id else settings.effective_litellm_config()
    # Optional per-agent model override (same provider credentials).
    if user_id and agent_id:
        from app.services import agent_settings_service
        from app.providers import prefixed_model

        override = agent_settings_service.resolve_model_for_agent(user_id, agent_id)
        if override:
            config = {**config, "model": prefixed_model(config["provider"], override)}
    provider_def = get_provider(config["provider"])
    kwargs: dict[str, Any] = {
        "model": config["model"],
        "is_litellm": True,
    }
    api_key = config["api_key"]
    if api_key:
        kwargs["api_key"] = api_key
    elif config["provider"] == "openai-compatible":
        kwargs["api_key"] = "not-needed"
    elif provider_def.requires_api_key or config["provider"] == "xai-oauth":
        credential_label = "access token" if config["provider"] == "xai-oauth" else "API key"
        raise ValueError(
            f"{provider_def.label} {credential_label} is not configured. "
            "Add it in Settings → Cloud & AI or set the corresponding environment variable."
        )
    if config["base_url"]:
        kwargs["base_url"] = config["base_url"]
    elif config["provider"] in {"xai", "xai-oauth"}:
        kwargs["base_url"] = "https://api.x.ai/v1"

    # LiteLLM-level retries for transient HTTP failures (in addition to capacity backoff).
    kwargs.setdefault("num_retries", 2)

    llm_class = XAICompatibleLLM if config["provider"] in {"xai", "xai-oauth"} else LLM
    return llm_class(**kwargs)
