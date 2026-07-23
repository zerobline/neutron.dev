from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock

from crewai.types.streaming import StreamChunk, StreamChunkType, StreamFrame, ToolCallChunk

from app.crew.streaming import (
    consume_stream_output,
    is_consumable_stream,
    kickoff_with_streaming,
    resolve_stream_agent,
    stream_chunk_to_event,
    stream_chunk_to_events,
    stream_frame_to_event,
    stream_frame_to_events,
)


class _FakeStreamOutput:
    def __init__(self, items: list | None = None, result: Any = "done"):
        self._items = items or []
        self._result = result

    def __iter__(self):
        return iter(self._items)

    @property
    def result(self):
        return self._result


def test_is_consumable_stream_detects_iterable_results():
    stream = _FakeStreamOutput()
    assert is_consumable_stream(stream) is True
    assert is_consumable_stream("plain") is False


def test_stream_frame_to_event_maps_llm_content():
    frame = SimpleNamespace(channel="llm", namespace=["Team Leader"], content="Planning", data={}, type="llm_stream_chunk")
    event = stream_frame_to_event("team_leader", frame)
    assert event == {"type": "stream_chunk", "agent": "team_leader", "content": "Planning"}


def test_stream_frame_to_event_maps_tool_calls():
    from app.crew.streaming import friendly_tool_label

    frame = SimpleNamespace(
        channel="tools",
        namespace=["engineer"],
        content="",
        type="tool_usage_started",
        data={"tool_name": "write_code_file", "arguments": "{}"},
    )
    event = stream_frame_to_event("engineer", frame)
    assert event["type"] == "tool_call"
    assert event["tool_name"] == "write_code_file"
    assert event["content"] == "Writing a project file"
    assert friendly_tool_label("write_code_file") == "Writing a project file"
    assert friendly_tool_label("custom_helper") == "Custom Helper"
    assert friendly_tool_label("") == "Using a project tool"
    assert friendly_tool_label(None) == "Using a project tool"


def test_stream_frame_to_events_maps_tool_result_finished():
    frame = SimpleNamespace(
        channel="tools",
        namespace=["Full-Stack Engineer"],
        content="",
        type="tool_usage_finished",
        data={
            "tool_name": "write_code_file",
            "tool_args": {"file_path": "index.html"},
            "output": "Successfully wrote 120 bytes to index.html",
            "agent_role": "Senior Full-Stack Engineer",
        },
    )
    events = stream_frame_to_events(None, frame)
    assert len(events) == 1
    assert events[0]["type"] == "tool_result"
    assert events[0]["status"] == "complete"
    assert events[0]["agent"] == "engineer"
    assert "120 bytes" in events[0]["content"]
    assert "index.html" in events[0]["arguments"]


def test_stream_frame_to_events_maps_tool_error():
    frame = SimpleNamespace(
        channel="tools",
        namespace=["engineer"],
        content="",
        type="tool_execution_error",
        data={"tool_name": "write_code_file", "error": "path escapes project", "tool_args": {}},
    )
    events = stream_frame_to_events("engineer", frame)
    assert events[0]["type"] == "tool_result"
    assert events[0]["status"] == "error"
    assert "path escapes" in events[0]["content"]


def test_stream_frame_to_events_maps_agent_step_from_task_started():
    frame = SimpleNamespace(
        channel="lifecycle",
        namespace=["Product Manager"],
        content="",
        type="task_started",
        data={"task_name": "Define milestones", "agent_role": "Product Manager"},
    )
    events = stream_frame_to_events(None, frame)
    assert len(events) == 1
    assert events[0]["type"] == "agent_step"
    assert events[0]["agent"] == "product_manager"
    assert events[0]["title"] == "Define milestones"
    assert events[0]["content"] == "Working on task"


def test_stream_chunk_to_event_text():
    chunk = StreamChunk(content="Hello", agent_role="Senior Full-Stack Engineer")
    event = stream_chunk_to_event("engineer", chunk)
    assert event == {"type": "stream_chunk", "agent": "engineer", "content": "Hello"}


def test_stream_chunk_to_event_skips_empty_content():
    chunk = StreamChunk(content="", agent_role="Team Leader")
    assert stream_chunk_to_event(None, chunk) is None


def test_resolve_stream_agent_returns_none_for_empty_role():
    chunk = StreamChunk(content="x", agent_role="")
    assert resolve_stream_agent(None, chunk) is None


def test_stream_chunk_to_event_tool_call():
    chunk = StreamChunk(
        content="",
        chunk_type=StreamChunkType.TOOL_CALL,
        agent_role="Senior Full-Stack Engineer",
        tool_call=ToolCallChunk(tool_name="write_code_file", arguments='{"file_path":"index.html"}'),
    )
    event = stream_chunk_to_event("engineer", chunk)
    assert event["type"] == "tool_call"
    assert event["tool_name"] == "write_code_file"


def test_resolve_stream_agent_uses_explicit_hint():
    chunk = StreamChunk(content="x", agent_role="Unknown Role")
    assert resolve_stream_agent("engineer", chunk) == "engineer"


def test_resolve_stream_agent_returns_none_for_unknown_role():
    chunk = StreamChunk(content="x", agent_role="Unknown Role")
    assert resolve_stream_agent(None, chunk) is None


def test_resolve_stream_agent_from_role():
    chunk = StreamChunk(content="x", agent_role="Product Manager")
    assert resolve_stream_agent(None, chunk) == "product_manager"


def test_consume_stream_output_skips_unmapped_chunks():
    emitted: list[dict] = []
    stream = MagicMock()
    stream.__iter__.return_value = iter([
        StreamChunk(content="Hello", agent_role="Unknown Role"),
        StreamChunk(content="Mapped", agent_role="Team Leader"),
    ])
    stream.result = "done"

    result = consume_stream_output(stream, emitted.append)
    assert result == "done"
    assert len(emitted) == 1
    assert emitted[0]["agent"] == "team_leader"
    assert emitted[0]["content"] == "Mapped"


def test_consume_stream_output_emits_and_returns_result():
    emitted: list[dict] = []
    stream = MagicMock()
    stream.__iter__.return_value = iter([
        StreamChunk(content="A", agent_role="Team Leader"),
        StreamChunk(content="B", agent_role="Team Leader"),
    ])
    stream.result = "done"

    result = consume_stream_output(stream, emitted.append, agent_hint="team_leader")
    assert result == "done"
    # Short token chunks are coalesced and flushed at end of stream.
    assert len(emitted) == 1
    assert emitted[0] == {"type": "stream_chunk", "agent": "team_leader", "content": "AB"}


def test_consume_stream_output_emits_json_status_step_once():
    emitted: list[dict] = []
    stream = MagicMock()
    stream.__iter__.return_value = iter([
        StreamChunk(content='{"headline":', agent_role="Team Leader"),
        StreamChunk(content='"scope"}', agent_role="Team Leader"),
    ])
    stream.result = "done"

    consume_stream_output(stream, emitted.append, agent_hint="team_leader")
    steps = [e for e in emitted if e["type"] == "agent_step"]
    assert len(steps) == 1
    assert steps[0]["title"] == "Drafting the result"
    assert not any(e["type"] == "stream_chunk" for e in emitted)


def test_kickoff_with_streaming_consumes_stream_when_streaming():
    emitted: list[dict] = []
    crew = MagicMock(stream=True)
    crew.kickoff.return_value = _FakeStreamOutput(
        items=[StreamChunk(content="Hi", agent_role="Team Leader")], result="streamed"
    )
    result = kickoff_with_streaming(crew, emitted.append, agent_hint="team_leader")
    assert result == "streamed"
    assert emitted == [{"type": "stream_chunk", "agent": "team_leader", "content": "Hi"}]


def test_kickoff_with_streaming_uses_plain_kickoff_when_not_streaming():
    crew = MagicMock(stream=False)
    crew.kickoff.return_value = "plain"
    result = kickoff_with_streaming(crew, lambda _event: None, agent_hint="engineer")
    assert result == "plain"


def test_stream_chunk_to_event_returns_none_without_agent():
    chunk = StreamChunk(content="Hello", agent_role="")
    assert stream_chunk_to_event(None, chunk) is None


def test_stream_chunk_to_event_ignores_empty_text():
    chunk = StreamChunk(content="", agent_role="Team Leader")
    assert stream_chunk_to_event(None, chunk) is None


def test_stream_frame_to_event_resolves_agent_from_namespace():
    frame = SimpleNamespace(
        channel="llm", namespace=["flow", "Product Manager"], content="Plan", data={}, type="llm_stream_chunk"
    )
    event = stream_frame_to_event(None, frame)
    assert event == {"type": "stream_chunk", "agent": "product_manager", "content": "Plan"}


def test_stream_frame_to_event_tool_call_without_agent_is_dropped():
    frame = SimpleNamespace(
        channel="tools", namespace=["flow"], content="", type="tool_usage_started", data={"tool_name": "search"}
    )
    assert stream_frame_to_event(None, frame) is None


def test_stream_frame_to_event_skips_empty_content():
    frame = SimpleNamespace(channel="llm", namespace=["Team Leader"], content="", data={}, type="llm_stream_chunk")
    assert stream_frame_to_event("team_leader", frame) is None


def test_stream_frame_to_event_resolves_agent_from_data_role():
    frame = SimpleNamespace(
        channel="llm",
        namespace=["flow"],
        content="Designing",
        data={"agent_role": "System Architect"},
        type="llm_stream_chunk",
    )
    event = stream_frame_to_event(None, frame)
    assert event == {"type": "stream_chunk", "agent": "architect", "content": "Designing"}


def test_stream_frame_to_event_unknown_data_role_is_dropped():
    frame = SimpleNamespace(
        channel="llm", namespace=["flow"], content="Text", data={"agent_role": "Mystery Role"}, type="llm_stream_chunk"
    )
    assert stream_frame_to_event(None, frame) is None


def test_stream_frame_to_event_no_role_anywhere_is_dropped():
    frame = SimpleNamespace(channel="llm", namespace=["flow"], content="Text", data={}, type="llm_stream_chunk")
    assert stream_frame_to_event(None, frame) is None


def test_is_consumable_stream_detects_crewai_base_classes():
    from crewai.types.streaming import StreamingOutputBase

    class _Concrete(StreamingOutputBase):
        pass

    assert is_consumable_stream(_Concrete(sync_iterator=iter([]))) is True


def test_is_consumable_stream_rejects_non_iterable_object():
    class NotIterable:
        pass

    assert is_consumable_stream(NotIterable()) is False


def test_is_consumable_stream_detects_by_type_name():
    class CustomCrewStreamingOutput:
        def __iter__(self):
            return iter([])

    assert is_consumable_stream(CustomCrewStreamingOutput()) is True


def test_is_consumable_stream_rejects_plain_iterable_without_result_property():
    class PlainIterable:
        result = "value"

        def __iter__(self):
            return iter([])

    assert is_consumable_stream(PlainIterable()) is False


def test_consume_stream_output_handles_stream_frames():
    frame = StreamFrame(
        id="f1",
        type="llm_stream_chunk",
        channel="llm",
        namespace=["Team Leader"],
        timestamp=datetime.now(timezone.utc),
        data={"chunk": "Working"},
    )
    emitted: list[dict] = []
    stream = _FakeStreamOutput(items=[frame, object()], result="done")
    result = consume_stream_output(stream, emitted.append)
    assert result == "done"
    assert emitted == [{"type": "stream_chunk", "agent": "team_leader", "content": "Working"}]


def test_tool_result_without_matching_start_omits_duration():
    finished = SimpleNamespace(
        channel="tools",
        namespace=["engineer"],
        content="",
        type="tool_usage_finished",
        data={"tool_name": "read_file", "output": "ok"},
    )
    emitted: list[dict] = []
    consume_stream_output(_FakeStreamOutput([finished], "ok"), emitted.append, agent_hint="engineer")
    assert emitted[0]["type"] == "tool_result"
    assert "duration_ms" not in emitted[0]


def test_consume_stream_output_tool_lifecycle():
    started = SimpleNamespace(
        channel="tools",
        namespace=["engineer"],
        content="",
        type="tool_usage_started",
        data={"tool_name": "read_file", "tool_args": {"file_path": "index.html"}},
    )
    finished = SimpleNamespace(
        channel="tools",
        namespace=["engineer"],
        content="",
        type="tool_usage_finished",
        data={
            "tool_name": "read_file",
            "tool_args": {"file_path": "index.html"},
            "output": "file contents here",
        },
    )
    emitted: list[dict] = []
    stream = _FakeStreamOutput(items=[started, finished], result="ok")
    consume_stream_output(stream, emitted.append, agent_hint="engineer")
    assert emitted[0]["type"] == "tool_call"
    assert "started_at" in emitted[0]
    assert emitted[1]["type"] == "tool_result"
    assert emitted[1]["status"] == "complete"
    assert emitted[1]["content"] == "file contents here"
    assert isinstance(emitted[1].get("duration_ms"), int)
    assert emitted[1]["duration_ms"] >= 0


def test_stream_chunk_to_events_json_hint():
    chunk = StreamChunk(content='{"a":1}', agent_role="Team Leader")
    events = stream_chunk_to_events("team_leader", chunk)
    assert events[0]["type"] == "_json_stream_hint"


def test_stringify_and_summarize_edge_cases():
    from app.crew.streaming import _stringify_tool_args, _summarize_tool_output, _frame_text

    assert _stringify_tool_args(None) == ""
    assert _stringify_tool_args('{"a":1}') == '{"a":1}'
    assert '"x"' in _stringify_tool_args({"x": 1})

    class Boom:
        def __str__(self):
            raise TypeError("nope")

    # json.dumps(default=str) may still fail; fallback uses repr.
    assert isinstance(_stringify_tool_args(Boom()), str)

    assert "Finished write file" in _summarize_tool_output("write_file", None)
    assert "Finished write file" in _summarize_tool_output("write_file", "   ")
    assert _summarize_tool_output("t", "ok") == "ok"
    long = "x" * 500
    assert _summarize_tool_output("t", long).endswith("...")
    assert _summarize_tool_output("t", None, error="  bad  ").startswith("Failed:")

    frame = SimpleNamespace(content=None)
    assert _frame_text(frame, {"chunk": "from-data"}) == "from-data"
    assert _frame_text(frame, {"chunk": 123}) == ""
    assert _frame_text(SimpleNamespace(), {}) == ""


def test_stream_frame_flow_soft_step_and_noise_skip():
    noisy = SimpleNamespace(
        channel="flow",
        namespace=["Team Leader"],
        content="",
        type="event_pairing_warning",
        data={},
    )
    assert stream_frame_to_events("team_leader", noisy) == []

    # Unknown custom markers are dropped (keeps the feed scannable).
    step = SimpleNamespace(
        channel="flow",
        namespace=["Team Leader"],
        content="",
        type="custom_flow_marker",
        data={},
    )
    assert stream_frame_to_events("team_leader", step) == []

    method = SimpleNamespace(
        channel="flow",
        namespace=["flow"],
        content="",
        type="method_execution_started",
        data={"method_name": "run_engineering"},
    )
    events = stream_frame_to_events(None, method)
    assert events[0]["type"] == "agent_step"
    assert events[0]["agent"] == "engineer"
    assert events[0]["title"] == "Engineering"


def test_stream_frame_task_completed_status():
    frame = SimpleNamespace(
        channel="lifecycle",
        namespace=["engineer"],
        content="",
        type="task_completed",
        data={"task_name": "Write files"},
    )
    events = stream_frame_to_events("engineer", frame)
    assert events[0]["status"] == "complete"
    assert events[0]["title"] == "Write files"
    assert events[0]["content"] == "Task complete"


def test_stream_frame_drops_long_task_prompt_from_title():
    long_prompt = (
        "Build the project based on the accepted plan and architecture: "
        "'Build an admin dashboard with a sidebar navigation, top stats cards...'"
    )
    frame = SimpleNamespace(
        channel="lifecycle",
        namespace=["Full-Stack Engineer"],
        content="",
        type="task_started",
        data={"task_name": long_prompt, "agent_role": "Senior Full-Stack Engineer"},
    )
    events = stream_frame_to_events("engineer", frame)
    assert events[0]["title"] == "Working on task"
    assert len(events[0]["title"]) < 80


def test_consume_stream_respects_channel_filter():
    from app.crew.streaming import FLOW_ONLY_CHANNELS

    llm = SimpleNamespace(
        channel="llm",
        namespace=["Team Leader"],
        content="secret token",
        type="llm_stream_chunk",
        data={},
    )
    flow = SimpleNamespace(
        channel="flow",
        namespace=["flow"],
        content="",
        type="method_execution_started",
        data={"method_name": "run_leadership"},
    )
    emitted: list[dict] = []
    stream = _FakeStreamOutput(items=[llm, flow], result="ok")
    consume_stream_output(stream, emitted.append, channels=FLOW_ONLY_CHANNELS)
    assert all(e.get("type") != "stream_chunk" for e in emitted)
    assert any(e.get("type") == "agent_step" and e.get("agent") == "team_leader" for e in emitted)


def test_stream_frame_llm_json_and_fallback_channel():
    json_frame = SimpleNamespace(
        channel="llm",
        namespace=["Team Leader"],
        content='{"headline":"x"}',
        type="llm_stream_chunk",
        data={},
    )
    events = stream_frame_to_events("team_leader", json_frame)
    assert events[0]["type"] == "_json_stream_hint"

    other = SimpleNamespace(
        channel="messages",
        namespace=["Team Leader"],
        content="Note from messages channel",
        type="conversation_message_added",
        data={},
    )
    events = stream_frame_to_events("team_leader", other)
    assert events[0]["type"] == "stream_chunk"
    assert "Note" in events[0]["content"]


def test_stream_frame_tool_name_fallback_and_args_string():
    frame = SimpleNamespace(
        channel="tools",
        namespace=["engineer"],
        content="",
        type="tool_usage_started",
        data={"name": "search", "arguments": "plain"},
    )
    events = stream_frame_to_events("engineer", frame)
    assert events[0]["tool_name"] == "search"
    assert events[0]["arguments"] == "plain"

    bare = SimpleNamespace(
        channel="tools",
        namespace=["engineer"],
        content="",
        type="tool_usage_started",
        data={},
    )
    events = stream_frame_to_events("engineer", bare)
    assert events[0]["tool_name"] == "tool"


def test_consume_stream_flushes_on_size_and_clears_json_mode():
    emitted: list[dict] = []
    big = "word " * 20  # > 48 chars
    stream = MagicMock()
    stream.__iter__.return_value = iter([
        StreamChunk(content=big, agent_role="Team Leader"),
        StreamChunk(content='{"x":', agent_role="Team Leader"),
        StreamChunk(content="1}", agent_role="Team Leader"),
        StreamChunk(
            content="",
            chunk_type=StreamChunkType.TOOL_CALL,
            agent_role="Team Leader",
            tool_call=ToolCallChunk(tool_name="read_file", arguments="{}"),
        ),
        StreamChunk(content="after", agent_role="Team Leader"),
    ])
    stream.result = "done"
    consume_stream_output(stream, emitted.append, agent_hint="team_leader")
    types = [e["type"] for e in emitted]
    assert "stream_chunk" in types
    assert "agent_step" in types
    assert "tool_call" in types
    # After tool_call, JSON mode clears and prose can stream again.
    assert any(e["type"] == "stream_chunk" and e["content"] == "after" for e in emitted)


def test_tool_name_from_empty_data():
    from app.crew.streaming import _tool_name_from_data

    assert _tool_name_from_data({}) == "tool"


def test_stream_frame_non_dict_data():
    frame = SimpleNamespace(
        channel="llm",
        namespace=["Team Leader"],
        content="ok",
        type="llm_stream_chunk",
        data="not-a-dict",
    )
    events = stream_frame_to_events("team_leader", frame)
    assert events[0]["content"] == "ok"


def test_stream_frame_to_event_empty_events_list():
    frame = SimpleNamespace(channel="custom", namespace=[], content="", type="", data={})
    assert stream_frame_to_event(None, frame) is None


def test_consume_stream_json_hint_deduped_and_buffer_flush_before_tool():
    emitted: list[dict] = []
    stream = MagicMock()
    stream.__iter__.return_value = iter([
        StreamChunk(content="partial ", agent_role="Team Leader"),
        StreamChunk(content='{"headline":"x"}', agent_role="Team Leader"),
        StreamChunk(content='{"headline":"y"}', agent_role="Team Leader"),  # second JSON hint
        # agent_step must NOT clear structured-output mode
        SimpleNamespace(
            channel="lifecycle",
            namespace=["Team Leader"],
            content="",
            type="task_completed",
            data={"task_name": "Brief", "agent_role": "Team Leader"},
        ),
        StreamChunk(content='{"headline":"z"}', agent_role="Team Leader"),
        StreamChunk(
            content="",
            chunk_type=StreamChunkType.TOOL_CALL,
            agent_role="Team Leader",
            tool_call=ToolCallChunk(tool_name="read_file", arguments="{}"),
        ),
    ])
    stream.result = "done"
    consume_stream_output(stream, emitted.append, agent_hint="team_leader")
    steps = [e for e in emitted if e["type"] == "agent_step" and e.get("step_type") == "structured_output"]
    assert len(steps) == 1
    assert any(e["type"] == "tool_call" for e in emitted)


def test_agent_namespace_role_and_method_helpers():
    from app.crew.streaming import (
        _agent_from_namespace,
        _agent_from_role,
        _humanize_method,
        _short_label,
    )

    assert _agent_from_namespace(["x" * 60, "Team Leader"]) == "team_leader"
    assert _agent_from_namespace(["the product manager"]) == "product_manager"

    assert _agent_from_role(None) is None
    assert _agent_from_role("x" * 80) is None
    assert _short_label(None) is None
    assert _short_label("   ") is None
    assert _short_label("Short label") == "Short label"
    assert _short_label("It's a 'quoted' task name that is quite long enough") is None
    assert _humanize_method(None) is None
    assert _humanize_method("run_unknown_phase") == "Unknown Phase"
    assert _humanize_method("finalize") == "Finalizing"
    assert _humanize_method("custom_step") == "Custom Step"


def test_skip_step_types_and_llm_call_short_title():
    skipped = SimpleNamespace(
        channel="lifecycle",
        namespace=["Team Leader"],
        content="",
        type="llm_call_completed",
        data={"agent_role": "Team Leader"},
    )
    assert stream_frame_to_events("team_leader", skipped) == []

    started = SimpleNamespace(
        channel="lifecycle",
        namespace=["Team Leader"],
        content="",
        type="llm_call_started",
        data={"agent_role": "Team Leader", "task_name": "Huge " * 40},
    )
    events = stream_frame_to_events("team_leader", started)
    assert events[0]["title"] == "Thinking"


def test_soft_task_frame_type_and_step_dedupe():
    frame = SimpleNamespace(
        channel="lifecycle",
        namespace=["engineer"],
        content="",
        type="task_paused",
        data={"task_name": "Pause"},
    )
    events = stream_frame_to_events("engineer", frame)
    assert events[0]["type"] == "agent_step"

    emitted: list[dict] = []
    stream = _FakeStreamOutput(
        items=[
            SimpleNamespace(
                channel="flow",
                namespace=["flow"],
                content="",
                type="method_execution_started",
                data={"method_name": "run_analysis"},
            ),
            SimpleNamespace(
                channel="flow",
                namespace=["flow"],
                content="",
                type="method_execution_started",
                data={"method_name": "run_analysis"},
            ),
        ],
        result="ok",
    )
    consume_stream_output(stream, emitted.append)
    assert len([e for e in emitted if e["type"] == "agent_step"]) == 1


def test_consume_stream_filters_streamframe_channel():
    from datetime import datetime, timezone

    from crewai.types.streaming import StreamFrame
    from app.crew.streaming import FLOW_ONLY_CHANNELS

    llm = StreamFrame(
        id="1",
        type="llm_stream_chunk",
        channel="llm",
        namespace=["Team Leader"],
        timestamp=datetime.now(timezone.utc),
        data={"chunk": "token"},
    )
    flow = StreamFrame(
        id="2",
        type="method_execution_finished",
        channel="flow",
        namespace=["flow"],
        timestamp=datetime.now(timezone.utc),
        data={"method_name": "run_planning"},
    )
    emitted: list[dict] = []
    consume_stream_output(_FakeStreamOutput([llm, flow], "ok"), emitted.append, channels=FLOW_ONLY_CHANNELS)
    assert emitted[0]["agent"] == "product_manager"
    assert emitted[0]["status"] == "complete"


def test_public_events_empty_stream_chunk_and_flush_empty_buffer():
    from app.crew.streaming import _StreamEmitState, _public_events_from_raw

    state = _StreamEmitState()
    # Empty content is ignored.
    assert _public_events_from_raw(
        [{"type": "stream_chunk", "agent": "team_leader", "content": ""}],
        state,
    ) == []
    # Non-text with agent but empty buffer: flush is a no-op, event still emits.
    out = _public_events_from_raw(
        [{"type": "phase_start", "agent": "team_leader", "phase": "leading"}],
        state,
    )
    assert out == [{"type": "phase_start", "agent": "team_leader", "phase": "leading"}]
    # Non-text with no agent still passes through.
    out = _public_events_from_raw([{"type": "phase_start", "phase": "leading"}], state)
    assert out == [{"type": "phase_start", "phase": "leading"}]
    # Empty buffer keys still flush cleanly.
    state.text_buffers["team_leader"] = ""
    assert state.flush_all() == []

    # Non-text event flushes pending text for that agent.
    state2 = _StreamEmitState()
    state2.buffer_text("team_leader", "hello")
    flushed = _public_events_from_raw(
        [{"type": "tool_call", "agent": "team_leader", "tool_name": "read_file", "content": "Calling..."}],
        state2,
    )
    assert flushed[0] == {"type": "stream_chunk", "agent": "team_leader", "content": "hello"}
    assert flushed[1]["type"] == "tool_call"
