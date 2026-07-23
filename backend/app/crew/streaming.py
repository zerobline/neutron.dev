from __future__ import annotations

import json
import time
from collections.abc import Callable, Iterable
from typing import Any

from crewai.types.streaming import (
    CrewStreamingOutput,
    FlowStreamingOutput,
    StreamChunk,
    StreamChunkType,
)

try:
    from crewai.types.streaming import StreamFrame
except ImportError:  # pragma: no cover - older CrewAI
    StreamFrame = None  # type: ignore[misc, assignment]

from app.crew.presentation import looks_like_json_blob

EmitCallback = Callable[[dict], None]

AGENT_ROLE_HINTS: dict[str, str] = {
    "team leader": "team_leader",
    "research analyst": "data_scientist",
    "data scientist": "data_scientist",
    "product manager": "product_manager",
    "system architect": "architect",
    "architect": "architect",
    "full-stack engineer": "engineer",
    "software engineer": "engineer",
    "engineer": "engineer",
}

# Flow method names → agent (used when agent_hint is absent on outer flow stream).
_METHOD_AGENTS: dict[str, str] = {
    "run_leadership": "team_leader",
    "run_analysis": "data_scientist",
    "run_planning": "product_manager",
    "run_architecture": "architect",
    "run_engineering": "engineer",
}

_METHOD_LABELS: dict[str, str] = {
    "run_leadership": "Leadership",
    "run_analysis": "Analysis",
    "run_planning": "Planning",
    "run_architecture": "Architecture",
    "run_engineering": "Engineering",
    "gather_requirements": "Gathering requirements",
    "finalize": "Finalizing",
}

# CrewAI tool frame types (frame.type values from event bus).
_TOOL_START_TYPES = frozenset(
    {
        "tool_usage_started",
        "tool_usage_started_event",
    }
)
_TOOL_FINISH_TYPES = frozenset(
    {
        "tool_usage_finished",
        "tool_usage_finished_event",
    }
)
_TOOL_ERROR_TYPES = frozenset(
    {
        "tool_usage_error",
        "tool_usage_error_event",
        "tool_execution_error",
        "tool_execution_error_event",
        "tool_selection_error",
        "tool_selection_error_event",
        "tool_validate_input_error",
        "tool_validate_input_error_event",
    }
)

# High-signal step labels only (keep the activity feed scannable).
_STEP_TYPE_LABELS: dict[str, str] = {
    "task_started": "Working on task",
    "task_completed": "Task complete",
    "task_failed": "Task failed",
    "llm_call_started": "Thinking",
    "llm_call_failed": "Model call failed",
    "method_execution_started": "Running phase",
    "method_execution_finished": "Phase complete",
}

# Friendly tool labels for the activity timeline (machine names stay in tool_name).
_TOOL_LABELS: dict[str, str] = {
    "write_code_file": "Writing a project file",
    "read_project_file": "Reading a project file",
    "read_file": "Reading a project file",
    "generate_component": "Generating a component",
    "read_connector_context": "Reading connector context",
    "list_code_files": "Listing project files",
    "list_project_files": "Listing project files",
}

# Dropped as noise (duplicates phase UI or floods the feed).
_SKIP_STEP_TYPES = frozenset(
    {
        "crew_kickoff_started",
        "crew_kickoff_completed",
        "flow_started",
        "llm_call_completed",
        "agent_execution_started",
        "agent_execution_completed",
        "agent_execution_error",
    }
)

# Coalesce rapid token chunks so the UI stays readable.
_STREAM_FLUSH_CHARS = 48
_STREAM_FLUSH_MS = 80

# Outer flow stream should not re-emit crew llm/tools (crew already emits with agent_hint).
FLOW_ONLY_CHANNELS: frozenset[str] = frozenset({"flow", "lifecycle"})


def resolve_stream_agent(agent_hint: str | None, chunk: StreamChunk) -> str | None:
    if agent_hint:
        return agent_hint

    role = (chunk.agent_role or "").strip().lower()
    if not role:
        return None

    for hint, agent_name in AGENT_ROLE_HINTS.items():
        if hint in role:
            return agent_name
    return None


def _agent_from_namespace(namespace: Iterable[str]) -> str | None:
    """Match agent roles only on short namespace tokens (not task prose)."""
    for part in namespace:
        lowered = str(part).strip().lower()
        # Skip long fragments (task prompts leak into namespaces sometimes).
        if len(lowered) > 48:
            continue
        for hint, agent_name in AGENT_ROLE_HINTS.items():
            if hint == lowered or hint in lowered.split() or lowered.startswith(hint) or lowered.endswith(hint):
                return agent_name
    return None


def _agent_from_role(role: str | None) -> str | None:
    if not role:
        return None
    lowered = role.strip().lower()
    if len(lowered) > 64:
        return None
    for hint, agent_name in AGENT_ROLE_HINTS.items():
        if hint in lowered:
            return agent_name
    return None


def _agent_from_method(data: dict) -> str | None:
    method = data.get("method_name") or data.get("name")
    if not isinstance(method, str):
        return None
    return _METHOD_AGENTS.get(method.strip())


def _resolve_agent(
    agent: str | None,
    *,
    namespace: Iterable[str] = (),
    data: dict | None = None,
    agent_role: str | None = None,
) -> str | None:
    # Explicit crew hint always wins (inner kickoff_with_streaming).
    if agent:
        return agent
    data = data or {}
    # Prefer method→agent for flow frames (avoids sticky wrong roles).
    from_method = _agent_from_method(data)
    if from_method:
        return from_method
    resolved = _agent_from_role(str(data.get("agent_role") or "") or agent_role)
    if resolved:
        return resolved
    return _agent_from_namespace(namespace)


def _stringify_tool_args(arguments: Any) -> str:
    if arguments is None:
        return ""
    if isinstance(arguments, str):
        return arguments
    try:
        return json.dumps(arguments, default=str)
    except (TypeError, ValueError):
        return repr(arguments)


def _tool_name_from_data(data: dict) -> str:
    return str(data.get("tool_name") or data.get("name") or "tool")


def friendly_tool_label(tool_name: str | None) -> str:
    """Human activity title for a tool (keeps raw tool_name on the event)."""
    if tool_name is None or not str(tool_name).strip():
        return "Using a project tool"
    key = str(tool_name).strip()
    lower = key.lower()
    if lower in _TOOL_LABELS:
        return _TOOL_LABELS[lower]
    # Fall back to title-cased words without the process-y "Calling …" prefix.
    words = lower.replace("-", "_").split("_")
    return " ".join(w.capitalize() for w in words if w) or "Using a project tool"


def _tool_call_content(tool_name: str) -> str:
    return friendly_tool_label(tool_name)


def _summarize_tool_output(tool_name: str, output: Any, error: Any = None) -> str:
    if error is not None and str(error).strip():
        return f"Failed: {str(error).strip()}"[:400]
    text = str(output if output is not None else "").strip()
    if not text:
        return f"Finished {friendly_tool_label(tool_name).lower()}"
    if len(text) > 400:
        return text[:397] + "..."
    return text


def _frame_text(frame: Any, data: dict) -> str:
    content = getattr(frame, "content", None)
    if isinstance(content, str) and content:
        return content
    for key in ("chunk", "content", "text", "message", "output"):
        value = data.get(key)
        if isinstance(value, str) and value:
            return value
    return ""


def _normalized_frame_type(frame: Any) -> str:
    return str(getattr(frame, "type", "") or "").strip().lower()


def _short_label(value: Any, *, limit: int = 72) -> str | None:
    """Return a short UI label, or None if the value looks like a dumped prompt."""
    if value is None:
        return None
    text = " ".join(str(value).split())
    if not text:
        return None
    # Task descriptions often embed the full user brief after a colon.
    if len(text) > limit:
        return None
    if text.count("'") >= 2 and len(text) > 48:
        return None
    return text


def _humanize_method(name: str | None) -> str | None:
    if not name or not isinstance(name, str):
        return None
    key = name.strip()
    if key in _METHOD_LABELS:
        return _METHOD_LABELS[key]
    if key.startswith("run_"):
        return key.removeprefix("run_").replace("_", " ").strip().title()
    return key.replace("_", " ").strip().title()


def stream_frame_to_event(agent: str | None, frame: Any) -> dict | None:
    """Map a single StreamFrame to at most one WS event (legacy helper)."""
    events = stream_frame_to_events(agent, frame)
    return events[0] if events else None


def stream_frame_to_events(agent: str | None, frame: Any) -> list[dict]:
    """Map a StreamFrame to zero or more user-facing WS events."""
    data = getattr(frame, "data", {}) or {}
    if not isinstance(data, dict):
        data = {}
    namespace = getattr(frame, "namespace", ()) or ()
    resolved_agent = _resolve_agent(
        agent,
        namespace=namespace,
        data=data,
        agent_role=str(data.get("agent_role") or "") or None,
    )
    channel = getattr(frame, "channel", None)
    frame_type = _normalized_frame_type(frame)

    # --- Tools channel / tool events ---
    if channel == "tools" or frame_type in _TOOL_START_TYPES | _TOOL_FINISH_TYPES | _TOOL_ERROR_TYPES:
        if not resolved_agent:
            return []
        tool_name = _tool_name_from_data(data)
        arguments = _stringify_tool_args(data.get("tool_args") if "tool_args" in data else data.get("arguments"))

        if frame_type in _TOOL_ERROR_TYPES or "error" in frame_type:
            error = data.get("error") or data.get("message") or "Tool failed"
            return [
                {
                    "type": "tool_result",
                    "agent": resolved_agent,
                    "tool_name": tool_name,
                    "status": "error",
                    "arguments": arguments,
                    "content": _summarize_tool_output(tool_name, None, error=error),
                }
            ]

        if frame_type in _TOOL_FINISH_TYPES or frame_type.endswith("finished"):
            return [
                {
                    "type": "tool_result",
                    "agent": resolved_agent,
                    "tool_name": tool_name,
                    "status": "complete",
                    "arguments": arguments,
                    "content": _summarize_tool_output(tool_name, data.get("output")),
                }
            ]

        return [
            {
                "type": "tool_call",
                "agent": resolved_agent,
                "tool_name": tool_name,
                "arguments": arguments,
                "content": _tool_call_content(tool_name),
            }
        ]

    # --- Lifecycle / flow / task steps ---
    if frame_type in _SKIP_STEP_TYPES:
        return []
    if any(noise in frame_type for noise in ("warning", "pairing", "debug")):
        return []

    step_label = _STEP_TYPE_LABELS.get(frame_type)
    if step_label is None and channel in {"flow", "lifecycle"} and frame_type:
        # Only soft-label known-looking method/task frames, not every custom type.
        if frame_type.startswith("method_") or frame_type.startswith("task_"):
            step_label = frame_type.replace("_", " ").strip().title()
        else:
            return []

    if step_label and resolved_agent:
        method_name = data.get("method_name")
        method_label = _humanize_method(str(method_name) if method_name else None)
        short_task = _short_label(data.get("task_name"))

        if frame_type.startswith("method_") and method_label:
            title = method_label
            content = step_label
        elif frame_type.startswith("llm_"):
            title = step_label
            content = step_label
        elif short_task:
            title = short_task
            content = step_label
        else:
            title = step_label
            content = step_label

        status = "error" if "fail" in frame_type or "error" in frame_type else "active"
        if "completed" in frame_type or "finished" in frame_type:
            status = "complete"
        return [
            {
                "type": "agent_step",
                "agent": resolved_agent,
                "title": title[:120],
                "content": content[:120],
                "status": status,
                "step_type": frame_type,
            }
        ]

    # --- LLM text tokens ---
    if channel == "llm" or frame_type.startswith("llm_stream") or frame_type == "llm_stream_chunk":
        text = _frame_text(frame, data)
        if not text or not resolved_agent:
            return []
        if looks_like_json_blob(text):
            return [
                {
                    "type": "_json_stream_hint",
                    "agent": resolved_agent,
                    "content": text,
                }
            ]
        return [
            {
                "type": "stream_chunk",
                "agent": resolved_agent,
                "content": text,
            }
        ]

    # Fallback: printable content on other channels (rare)
    text = _frame_text(frame, data)
    if text and resolved_agent and not looks_like_json_blob(text):
        return [
            {
                "type": "stream_chunk",
                "agent": resolved_agent,
                "content": text,
            }
        ]
    return []


def stream_chunk_to_event(agent: str | None, chunk: StreamChunk) -> dict | None:
    events = stream_chunk_to_events(agent, chunk)
    return events[0] if events else None


def stream_chunk_to_events(agent: str | None, chunk: StreamChunk) -> list[dict]:
    resolved_agent = agent or resolve_stream_agent(None, chunk)
    if not resolved_agent:
        return []

    if chunk.chunk_type == StreamChunkType.TOOL_CALL and chunk.tool_call:
        tool_name = chunk.tool_call.tool_name or "tool"
        return [
            {
                "type": "tool_call",
                "agent": resolved_agent,
                "tool_name": tool_name,
                "arguments": chunk.tool_call.arguments,
                "content": _tool_call_content(tool_name),
            }
        ]

    content = chunk.content
    if not content:
        return []

    if looks_like_json_blob(content):
        return [
            {
                "type": "_json_stream_hint",
                "agent": resolved_agent,
                "content": content,
            }
        ]

    return [
        {
            "type": "stream_chunk",
            "agent": resolved_agent,
            "content": content,
        }
    ]


def is_consumable_stream(output: Any) -> bool:
    if output is None or isinstance(output, (str, bytes, dict, list, tuple)):
        return False

    try:
        from crewai.types.streaming import StreamSessionBase, StreamingOutputBase

        if isinstance(output, (StreamSessionBase, StreamingOutputBase)):
            return True
    except ImportError:  # pragma: no cover - older CrewAI
        pass

    output_type = type(output)
    if getattr(output_type, "__iter__", None) is None:
        return False

    name = output_type.__name__
    if name.endswith(("StreamingOutput", "StreamSession")):
        return True

    return isinstance(getattr(output_type, "result", None), property)


def _stream_item_to_events(agent_hint: str | None, item: Any) -> list[dict]:
    if StreamFrame is not None and isinstance(item, StreamFrame):
        return stream_frame_to_events(agent_hint, item)
    if isinstance(item, StreamChunk):
        return stream_chunk_to_events(agent_hint, item)
    if hasattr(item, "channel") and hasattr(item, "data"):
        return stream_frame_to_events(agent_hint, item)
    return []


class _StreamEmitState:
    """Per-kickoff state for coalescing, JSON notices, step de-dupe, and tool timing."""

    def __init__(self) -> None:
        self.json_notice_agents: set[str] = set()
        self.text_buffers: dict[str, str] = {}
        self.last_flush_ms: dict[str, float | None] = {}
        self.last_step_key: str | None = None
        # agent|tool_name → monotonic start seconds for duration_ms on tool_result
        self.tool_starts: dict[str, float] = {}

    def flush_text(self, agent: str, force: bool = False) -> dict | None:
        buf = self.text_buffers.get(agent, "")
        if not buf:
            return None
        now = time.monotonic() * 1000
        last = self.last_flush_ms.get(agent)
        if last is None:
            self.last_flush_ms[agent] = now
            if not force and len(buf) < _STREAM_FLUSH_CHARS:
                return None
        elif not force and len(buf) < _STREAM_FLUSH_CHARS and (now - last) < _STREAM_FLUSH_MS:
            return None
        self.text_buffers[agent] = ""
        self.last_flush_ms[agent] = now
        return {"type": "stream_chunk", "agent": agent, "content": buf}

    def buffer_text(self, agent: str, content: str) -> dict | None:
        self.text_buffers[agent] = self.text_buffers.get(agent, "") + content
        return self.flush_text(agent, force=False)

    def flush_all(self) -> list[dict]:
        events: list[dict] = []
        for agent in list(self.text_buffers.keys()):
            event = self.flush_text(agent, force=True)
            if event:
                events.append(event)
        return events


def _public_events_from_raw(raw_events: list[dict], state: _StreamEmitState) -> list[dict]:
    """Convert internal/raw mapped events into public WS events with buffering."""
    public: list[dict] = []
    for event in raw_events:
        event_type = event.get("type")
        agent = event.get("agent")
        if event_type == "_json_stream_hint" and isinstance(agent, str):
            if agent not in state.json_notice_agents:
                state.json_notice_agents.add(agent)
                state.text_buffers.pop(agent, None)
                public.append(
                    {
                        "type": "agent_step",
                        "agent": agent,
                        "title": "Drafting the result",
                        "content": "Putting the phase summary together…",
                        "status": "active",
                        "step_type": "structured_output",
                    }
                )
            continue

        if event_type == "stream_chunk" and isinstance(agent, str):
            if agent in state.json_notice_agents:
                continue
            content = event.get("content") or ""
            if not content:
                continue
            flushed = state.buffer_text(agent, str(content))
            if flushed:
                public.append(flushed)
            continue

        if isinstance(agent, str):
            flushed = state.flush_text(agent, force=True)
            if flushed:
                public.append(flushed)
            # Only tools end structured-output mode (not other agent_steps).
            if event_type in {"tool_call", "tool_result"}:
                state.json_notice_agents.discard(agent)

        # De-dupe identical consecutive steps (double flow+crew subscription).
        if event_type == "agent_step":
            key = f"{agent}|{event.get('step_type')}|{event.get('title')}|{event.get('status')}"
            if key == state.last_step_key:
                continue
            state.last_step_key = key

        # Attach tool timing for the activity panel.
        if event_type == "tool_call" and isinstance(agent, str):
            tool_name = str(event.get("tool_name") or "tool")
            state.tool_starts[f"{agent}|{tool_name}"] = time.monotonic()
            event = {**event, "started_at": time.time()}
        elif event_type == "tool_result" and isinstance(agent, str):
            tool_name = str(event.get("tool_name") or "tool")
            start_key = f"{agent}|{tool_name}"
            started = state.tool_starts.pop(start_key, None)
            if started is not None:
                duration_ms = max(0, int((time.monotonic() - started) * 1000))
                event = {**event, "duration_ms": duration_ms}

        public.append(event)
    return public


def consume_stream_output(
    stream_output: CrewStreamingOutput | FlowStreamingOutput | Any,
    emit: EmitCallback,
    *,
    agent_hint: str | None = None,
    channels: frozenset[str] | None = None,
) -> Any:
    """Consume a CrewAI stream and emit WS events.

    ``channels`` limits which StreamFrame channels are accepted. Use
    ``FLOW_ONLY_CHANNELS`` for the outer flow stream so crew llm/tools are not
    double-emitted (crews already emit with an agent_hint).
    """
    state = _StreamEmitState()
    for item in stream_output:
        if channels is not None and StreamFrame is not None and isinstance(item, StreamFrame):
            channel = getattr(item, "channel", None)
            if channel not in channels:
                continue
        elif channels is not None and hasattr(item, "channel") and not isinstance(item, StreamChunk):
            if getattr(item, "channel", None) not in channels:
                continue
        raw = _stream_item_to_events(agent_hint, item)
        for event in _public_events_from_raw(raw, state):
            emit(event)
    for event in state.flush_all():
        emit(event)
    return stream_output.result


def kickoff_with_streaming(
    crew: Any,
    emit: EmitCallback,
    *,
    agent_hint: str,
) -> Any:
    if getattr(crew, "stream", False) is True:
        stream_output = crew.kickoff()
        return consume_stream_output(stream_output, emit, agent_hint=agent_hint)
    return crew.kickoff()
