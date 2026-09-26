from unittest.mock import MagicMock, patch

import pytest

from app.crew.flows.project_flow import (
    GOAL_MODE_DIRECTIVE,
    INVALID_NAVIGATION_ERROR,
    ITERATION_NO_FILES_WRITTEN_ERROR,
    NO_FILES_WRITTEN_ERROR,
    ProjectCreationFlow,
    ProjectFlowState,
    TokenUsageSummary,
    _has_written_required_files,
    _safe_raw,
)
from app.crew.schemas import REQUIRED_PROJECT_FILES
from app.crew.tools.code_writer import CodeWriterTool
from app.models import CustomMcpServerConfig, ProjectConnectorSettings
from app.crew.tools.code_writer import CodeWriterTool
from app.models import CustomMcpServerConfig, ProjectConnectorSettings


def fake_crew_factory():
    """Return a mock crew whose kickoff returns a deterministic result."""
    crew = MagicMock()
    result = MagicMock()
    result.raw = "fake crew output"
    crew.kickoff.return_value = result
    return crew


@pytest.fixture
def mocked_crews():
    captured_writers: list[CodeWriterTool] = []

    class CapturingCodeWriter(CodeWriterTool):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            captured_writers.append(self)

    def write_required_files(writer: CodeWriterTool) -> None:
        writer._run("index.html", "<html></html>")
        writer._run("styles.css", "body {}")
        writer._run("app.js", "console.log('ok');")

    def default_engineering_kickoff():
        for writer in captured_writers:
            write_required_files(writer)
        return MagicMock(raw="fake crew output")

    engineering_crew = fake_crew_factory()
    engineering_crew.kickoff.side_effect = default_engineering_kickoff
    with (
        patch("app.crew.flows.project_flow.create_leadership_crew", return_value=fake_crew_factory()) as leadership,
        patch("app.crew.flows.project_flow.create_analysis_crew", return_value=fake_crew_factory()) as analysis,
        patch("app.crew.flows.project_flow.create_planning_crew", return_value=fake_crew_factory()) as planning,
        patch("app.crew.flows.project_flow.create_architecture_crew", return_value=fake_crew_factory()) as architecture,
        patch("app.crew.flows.project_flow.create_engineering_crew", return_value=engineering_crew) as engineering,
        patch("app.crew.flows.project_flow.create_engineering_recovery_crew", return_value=engineering_crew) as engineering_recovery,
        patch("app.crew.flows.project_flow.CodeWriterTool", CapturingCodeWriter),
    ):
        yield {
            "leadership": leadership,
            "analysis": analysis,
            "planning": planning,
            "architecture": architecture,
            "engineering": engineering,
            "engineering_recovery": engineering_recovery,
            "writers": captured_writers,
        }


def connector_settings():
    return ProjectConnectorSettings(
        custom_mcp_servers=[
            CustomMcpServerConfig(
                id="remote",
                name="Remote MCP",
                transport="http",
                command_or_url="https://example.com/mcp",
                notes="Use specs",
            )
        ]
    )


def test_safe_raw_with_none():
    assert _safe_raw(None) == ""


def test_safe_raw_with_string():
    result = MagicMock()
    result.raw = "hello world"
    assert _safe_raw(result) == "hello world"


def test_safe_raw_with_plain_string():
    assert _safe_raw("plain output") == "plain output"


def test_safe_raw_with_non_string():
    result = MagicMock()
    result.raw = [{"type": "function", "id": "call_123"}]
    output = _safe_raw(result)
    assert isinstance(output, str)
    assert "call_123" in output


def test_safe_raw_with_pydantic_model():
    from app.crew.schemas import PageSpec, ProjectPlanSpec

    spec = ProjectPlanSpec(
        overview="A modern portfolio website for a developer showcasing projects and skills.",
        mvp_features=["Hero section"],
        pages=[PageSpec(name="Home", purpose="Landing page", key_elements=["Hero"])],
        data_model_summary="Static content only.",
        technical_architecture="Single-page HTML/CSS/JS app.",
        milestones=["Build landing page"],
    )
    result = MagicMock(pydantic=spec, raw="ignored")
    output = _safe_raw(result)
    # Prefer human overview/summary fields over raw JSON dumps.
    assert "portfolio website" in output
    assert not output.lstrip().startswith("{")


def test_safe_raw_prefers_summary_field():
    from app.crew.schemas import PageSpec, ProjectPlanSpec

    spec = ProjectPlanSpec(
        summary="Human-facing plan summary for the chat card.",
        overview="A modern portfolio website for a developer showcasing projects and skills.",
        mvp_features=["Hero section"],
        pages=[PageSpec(name="Home", purpose="Landing page", key_elements=["Hero"])],
        data_model_summary="Static content only.",
        milestones=["Build landing page"],
    )
    result = MagicMock(pydantic=spec, raw="ignored")
    assert _safe_raw(result) == "Human-facing plan summary for the chat card."


def test_accumulate_tokens_with_usage():
    flow = ProjectCreationFlow(project_id="abc", user_prompt="prompt")
    result = MagicMock()
    result.token_usage = MagicMock(
        total_tokens=100,
        prompt_tokens=60,
        completion_tokens=40,
        successful_requests=2,
    )
    flow._accumulate_tokens(result)
    assert flow.state.token_usage.total_tokens == 100
    assert flow.state.token_usage.prompt_tokens == 60
    assert flow.state.token_usage.completion_tokens == 40
    assert flow.state.token_usage.successful_requests == 2
    flow._accumulate_tokens(result)
    assert flow.state.token_usage.total_tokens == 200


def test_accumulate_tokens_emits_cumulative_usage_event(monkeypatch):
    from app.config import settings

    events = []
    monkeypatch.setattr(settings, "max_build_tokens", 1000)
    flow = ProjectCreationFlow(project_id="abc", user_prompt="prompt", event_callback=events.append)
    flow.state.status = "planning"

    flow._accumulate_tokens({"token_usage": "not read"})
    result = MagicMock(token_usage={
        "total_tokens": 250,
        "prompt_tokens": 175,
        "completion_tokens": 75,
        "successful_requests": 3,
    })
    flow._accumulate_tokens(result)

    usage_event = next(event for event in events if event["type"] == "token_usage")
    assert usage_event == {
        "type": "token_usage",
        "phase": "planning",
        "usage": {
            "total_tokens": 250,
            "prompt_tokens": 175,
            "completion_tokens": 75,
            "successful_requests": 3,
        },
        "token_budget": 1000,
        "percent": 25.0,
    }


def test_usage_value_rejects_non_integer_and_boolean_counts():
    assert ProjectCreationFlow._usage_value({"total_tokens": True}, "total_tokens") == 0
    assert ProjectCreationFlow._usage_value({"total_tokens": 1.5}, "total_tokens") == 0


def test_accumulate_tokens_omits_percent_for_unlimited_budget(monkeypatch):
    from app.config import settings

    events = []
    monkeypatch.setattr(settings, "max_build_tokens", 0)
    flow = ProjectCreationFlow(project_id="abc", user_prompt="prompt", event_callback=events.append)
    result = MagicMock(token_usage={"total_tokens": 10})

    flow._accumulate_tokens(result)

    usage_event = next(event for event in events if event["type"] == "token_usage")
    assert usage_event["token_budget"] == 0
    assert "percent" not in usage_event


def test_accumulate_tokens_enforces_budget(monkeypatch):
    from app.config import settings
    from app.crew.flows.project_flow import TOKEN_BUDGET_ERROR

    monkeypatch.setattr(settings, "max_build_tokens", 150)
    flow = ProjectCreationFlow(project_id="abc", user_prompt="prompt")
    result = MagicMock()
    result.token_usage = MagicMock(
        total_tokens=100,
        prompt_tokens=60,
        completion_tokens=40,
        successful_requests=2,
    )
    flow._accumulate_tokens(result)
    with pytest.raises(RuntimeError, match=TOKEN_BUDGET_ERROR):
        flow._accumulate_tokens(result)
    assert flow.state.token_usage.total_tokens == 200


def test_accumulate_tokens_without_usage():
    flow = ProjectCreationFlow(project_id="abc", user_prompt="prompt")
    result = MagicMock(spec=[])
    flow._accumulate_tokens(result)
    assert flow.state.token_usage.total_tokens == 0


def test_flow_initial_state():
    flow = ProjectCreationFlow(project_id="abc", user_prompt="Build a SaaS")
    assert flow.state.project_id == "abc"
    assert flow.state.user_prompt == "Build a SaaS"
    assert flow.state.status == "created"
    assert flow.state.mode == "team"
    assert flow.state.files_created == []
    assert flow.state.connector_settings.custom_mcp_servers == []


def test_flow_initial_state_engineer_mode():
    flow = ProjectCreationFlow(project_id="abc", user_prompt="Build it", mode="engineer")
    assert flow.state.mode == "engineer"


def test_flow_initial_state_goal_mode():
    flow = ProjectCreationFlow(project_id="abc", user_prompt="Reach a goal", mode="goal")
    assert flow.state.mode == "goal"


def test_flow_initial_state_with_inline_connectors():
    flow = ProjectCreationFlow(project_id="abc", user_prompt="Build it", connector_settings=connector_settings())
    assert flow.state.connector_settings.custom_mcp_servers[0].name == "Remote MCP"


def test_emit_without_callback_is_noop():
    flow = ProjectCreationFlow(project_id="abc", user_prompt="Build a SaaS")
    flow._emit({"type": "phase_start"})
    assert flow.state.status == "created"


def test_gather_requirements_team_mode():
    events = []
    flow = ProjectCreationFlow(project_id="abc", user_prompt="prompt", event_callback=events.append)
    with patch("app.crew.flows.project_flow.get_upload_context", return_value=""):
        result = flow.gather_requirements()
    assert result == "prompt"
    assert flow.state.status == "leading"
    assert events[0]["type"] == "phase_start"
    assert events[0]["phase"] == "leading"


def test_gather_requirements_engineer_mode():
    events = []
    flow = ProjectCreationFlow(project_id="abc", user_prompt="prompt", event_callback=events.append, mode="engineer")
    with patch("app.crew.flows.project_flow.get_upload_context", return_value=""):
        result = flow.gather_requirements()
    assert result == "prompt"
    assert flow.state.status == "building"
    assert events[0]["phase"] == "building"


def test_gather_requirements_goal_mode():
    events = []
    flow = ProjectCreationFlow(project_id="abc", user_prompt="prompt", event_callback=events.append, mode="goal")
    with patch("app.crew.flows.project_flow.get_upload_context", return_value=""):
        result = flow.gather_requirements()
    assert GOAL_MODE_DIRECTIVE in result
    assert flow.state.status == "leading"
    assert events[0]["phase"] == "leading"
    assert "Goal mode" in events[0]["message"]


def test_gather_requirements_with_connector_context():
    events = []
    flow = ProjectCreationFlow(
        project_id="abc",
        user_prompt="prompt",
        event_callback=events.append,
        connector_settings=connector_settings(),
    )
    with patch("app.crew.flows.project_flow.get_upload_context", return_value=""):
        result = flow.gather_requirements()
    assert "Connected tool context" in result
    assert "Remote MCP" in result


def test_gather_requirements_with_uploads():
    events = []
    flow = ProjectCreationFlow(project_id="abc", user_prompt="prompt", event_callback=events.append)
    with patch("app.crew.flows.project_flow.get_upload_context", return_value="\n\n--- Uploaded file: notes.txt ---\nfoo"):
        result = flow.gather_requirements()
    assert "notes.txt" in result
    assert flow.state.user_prompt.endswith("foo")


def test_gather_requirements_prepares_external_context_once():
    flow = ProjectCreationFlow(project_id="abc", user_prompt="prompt", mode="goal")
    with (
        patch("app.crew.flows.project_flow.get_upload_context", return_value=" upload") as uploads,
        patch("app.crew.flows.project_flow.get_connector_context", return_value=" connector") as connectors,
    ):
        flow.gather_requirements()
        first_prompt = flow.state.user_prompt
        flow.gather_requirements()

    assert flow.state.user_prompt == first_prompt
    assert flow.state.context_prepared is True
    uploads.assert_called_once()
    connectors.assert_called_once()


def test_phase_progress_metadata_for_unknown_phase():
    flow = ProjectCreationFlow(project_id="abc", user_prompt="prompt")
    assert flow._phase_details("unknown", complete=True) == {
        "step": 5,
        "total_steps": 5,
        "percent": 100,
    }


def test_run_leadership_team_mode(mocked_crews):
    events = []
    flow = ProjectCreationFlow(project_id="abc", user_prompt="prompt", event_callback=events.append)
    with patch("app.crew.flows.project_flow.get_upload_context", return_value=""):
        flow.gather_requirements()
    result = flow.run_leadership()
    assert result == "fake crew output"
    assert flow.state.leadership_output == "fake crew output"
    assert any(e["type"] == "agent_complete" and e["agent"] == "team_leader" for e in events)
    assert any(e["type"] == "phase_result" and e["agent"] == "team_leader" and e["kind"] == "brief" for e in events)
    mocked_crews["leadership"].assert_called_once()


def test_run_leadership_engineer_mode_skips():
    events = []
    flow = ProjectCreationFlow(project_id="abc", user_prompt="prompt", event_callback=events.append, mode="engineer")
    result = flow.run_leadership()
    assert result == ""
    assert flow.state.leadership_output == ""


def test_run_analysis_team_mode(mocked_crews):
    events = []
    flow = ProjectCreationFlow(project_id="abc", user_prompt="prompt", event_callback=events.append)
    flow.state.leadership_output = "leader done"
    result = flow.run_analysis()
    assert result == "fake crew output"
    assert flow.state.analysis_output == "fake crew output"
    assert flow.state.status == "analyzing"
    assert any(e["type"] == "agent_complete" and e["agent"] == "data_scientist" for e in events)
    assert any(e["type"] == "phase_result" and e["agent"] == "data_scientist" and e["kind"] == "analysis" for e in events)


def test_run_analysis_engineer_mode_skips():
    flow = ProjectCreationFlow(project_id="abc", user_prompt="prompt", mode="engineer")
    result = flow.run_analysis()
    assert result == ""


def test_run_planning_team_mode(mocked_crews):
    events = []
    flow = ProjectCreationFlow(project_id="abc", user_prompt="prompt", event_callback=events.append)
    flow.state.analysis_output = "analysis done"
    result = flow.run_planning()
    assert result == "fake crew output"
    assert flow.state.plan_output == "fake crew output"
    assert flow.state.status == "planning"
    mocked_crews["planning"].assert_called_once()


def test_run_planning_engineer_mode_skips():
    flow = ProjectCreationFlow(project_id="abc", user_prompt="prompt", mode="engineer")
    result = flow.run_planning()
    assert result == ""


def test_run_architecture_team_mode(mocked_crews):
    events = []
    flow = ProjectCreationFlow(project_id="abc", user_prompt="prompt", event_callback=events.append)
    flow.state.plan_output = "plan done"
    result = flow.run_architecture()
    assert result == "fake crew output"
    assert flow.state.architecture_output == "fake crew output"
    assert flow.state.status == "architecting"
    mocked_crews["architecture"].assert_called_once()


def test_run_architecture_engineer_mode_skips():
    flow = ProjectCreationFlow(project_id="abc", user_prompt="prompt", mode="engineer")
    result = flow.run_architecture()
    assert result == ""


def test_track_code_writer_deduplicates_file_paths(settings_projects_dir):
    flow = ProjectCreationFlow(project_id="abc", user_prompt="prompt")
    writer = CodeWriterTool(project_id="abc")
    flow._track_code_writer(writer)
    writer._run("index.html", "<h1>One</h1>")
    writer._run("index.html", "<h1>Two</h1>")
    # Tracker now updates PrivateAttr during execution; sync makes it visible in
    # pydantic state (done automatically after real crew runs).
    flow._sync_files_created()
    assert flow.state.files_created == ["index.html"]


def test_run_engineering_team_mode(mocked_crews, settings_projects_dir):
    events = []

    def engineering_kickoff():
        for writer in mocked_crews["writers"]:
            writer._run("index.html", "<h1>Hello</h1>")
            writer._run("styles.css", "body {}")
            writer._run("app.js", "console.log('ok');")
        return MagicMock(raw="engineering output")

    mocked_crews["engineering"].return_value.kickoff.side_effect = engineering_kickoff

    flow = ProjectCreationFlow(project_id="abc", user_prompt="prompt", event_callback=events.append)
    flow.state.plan_output = "plan done"
    flow.state.architecture_output = "design done"
    # Pre-populate to exercise the seeding of private _files_created inside run_engineering
    flow.state.files_created = ["preexisting.html"]
    result = flow.run_engineering()

    assert result == "engineering output"
    assert flow.state.engineering_output == "engineering output"
    assert flow.state.status == "building"
    assert "index.html" in flow.state.files_created
    assert "preexisting.html" in flow.state.files_created
    assert (settings_projects_dir / "abc" / "index.html").read_text() == "<h1>Hello</h1>"
    assert any(e["type"] == "file_created" for e in events)
    assert any(e["type"] == "phase_start" and e["phase"] == "building" for e in events)


def test_run_engineering_seeds_files_without_dupes(mocked_crews, settings_projects_dir):
    """Cover the case where a file from state.files_created is already in _files_created (no append)."""
    flow = ProjectCreationFlow(project_id="abc", user_prompt="prompt", mode="engineer")
    # Simulate prior state where _files_created already has the item
    flow._files_created = ["index.html"]
    flow.state.files_created = ["index.html"]  # will hit the if False branch
    flow.state.plan_output = "p"
    flow.state.architecture_output = "a"

    # Patch everything after the seeding for to avoid needing full crew setup
    with patch.object(flow, "_engineering_context_tasks", return_value=[]), \
         patch.object(flow, "_missing_required_files", return_value=[]), \
         patch.object(flow, "_ensure_engineering_files_created"), \
         patch("app.crew.agents.engineer.create_engineer_agent"), \
         patch("app.crew.tasks.engineering_tasks.create_engineering_task"), \
         patch("app.crew.flows.project_flow.create_engineering_crew") as eng_crew, \
         patch("app.crew.flows.project_flow.kickoff_with_streaming", return_value=MagicMock(raw="ok")):
        eng_crew.return_value = MagicMock()
        flow.run_engineering()

    # The duplicate was not appended again (branch not append taken)
    assert flow._files_created.count("index.html") == 1


def test_run_engineering_retries_when_initial_crew_skips_tools(mocked_crews, settings_projects_dir):
    events = []
    kickoff_calls = {"count": 0}

    def engineering_kickoff():
        kickoff_calls["count"] += 1
        if kickoff_calls["count"] == 1:
            return MagicMock(raw="claimed files but wrote nothing")
        for writer in mocked_crews["writers"]:
            writer._run("index.html", "<html></html>")
            writer._run("styles.css", "body {}")
            writer._run("app.js", "console.log('ok');")
        return MagicMock(raw="recovery output")

    mocked_crews["engineering"].return_value.kickoff.side_effect = engineering_kickoff

    flow = ProjectCreationFlow(project_id="abc", user_prompt="prompt", event_callback=events.append)
    result = flow.run_engineering()

    assert result == "recovery output"
    assert kickoff_calls["count"] == 2
    assert flow.state.files_created == ["index.html", "styles.css", "app.js"]
    assert any("Retrying those file writes" in e.get("content", "") for e in events if e["type"] == "stream_chunk")


def test_run_engineering_raises_when_no_files_written(mocked_crews, settings_projects_dir):
    mocked_crews["engineering"].return_value.kickoff.side_effect = lambda: MagicMock(raw="no files")
    flow = ProjectCreationFlow(project_id="abc", user_prompt="prompt")
    with pytest.raises(RuntimeError, match=NO_FILES_WRITTEN_ERROR):
        flow.run_engineering()


def test_run_engineering_engineer_mode_no_context(mocked_crews, settings_projects_dir):
    events = []
    flow = ProjectCreationFlow(project_id="abc", user_prompt="prompt", event_callback=events.append, mode="engineer")
    # No plan_output or architecture_output set — engineer mode skips them
    result = flow.run_engineering()
    assert result == "fake crew output"
    assert flow.state.status == "building"
    # Should NOT emit a phase_start for building (it was already emitted in gather_requirements)
    building_phase_events = [e for e in events if e.get("type") == "phase_start" and e.get("phase") == "building"]
    assert len(building_phase_events) == 0


def test_run_engineering_adds_connector_tool(mocked_crews):
    captured_tools = []
    captured_mcps = []

    def capture_engineer(tools=None, user_id=None, mcps=None, skills=None):
        captured_tools.extend(tools or [])
        captured_mcps.extend(mcps or [])
        return MagicMock()

    flow = ProjectCreationFlow(project_id="abc", user_prompt="prompt", connector_settings=connector_settings())
    with (
        patch("app.crew.flows.project_flow.create_engineer_agent", side_effect=capture_engineer),
        patch("app.crew.flows.project_flow.create_engineering_task", return_value=MagicMock()),
        patch("app.crew.flows.project_flow.resolve_agent_mcps", return_value=["github-mcp", "linear-mcp"]),
    ):
        flow.run_engineering()

    assert any(tool.name == "read_connector_context" for tool in captured_tools)
    assert captured_mcps == ["github-mcp", "linear-mcp"]


def test_finalize():
    events = []
    flow = ProjectCreationFlow(project_id="abc", user_prompt="prompt", event_callback=events.append)
    flow.state.files_created = ["index.html"]
    flow.state.token_usage = TokenUsageSummary(total_tokens=500, prompt_tokens=300, completion_tokens=200, successful_requests=5)
    state = flow.finalize()
    assert state.status == "complete"
    complete_event = next(e for e in events if e["type"] == "project_complete")
    assert complete_event["message"] == "Project generation complete!"
    assert complete_event["usage"]["total_tokens"] == 500
    assert complete_event["usage"]["prompt_tokens"] == 300
    assert complete_event["usage"]["completion_tokens"] == 200
    assert complete_event["usage"]["successful_requests"] == 5
    assert complete_event["mode"] == "team"
    assert "checklist" in complete_event
    assert isinstance(complete_event["suggestions"], list)
    assert len(complete_event["suggestions"]) >= 1


def test_finalize_goal_mode_message():
    events = []
    flow = ProjectCreationFlow(project_id="abc", user_prompt="prompt", event_callback=events.append, mode="goal")
    flow.finalize()
    assert events[0]["message"] == "Goal mode build complete!"


def test_finalize_iterate_mentions_changed_files():
    events = []
    flow = ProjectCreationFlow(
        project_id="abc",
        user_prompt="prompt",
        event_callback=events.append,
        mode="iterate",
    )
    flow._files_written_this_run = ["app.js", "styles.css"]
    flow.state.files_created = ["index.html", "app.js", "styles.css"]
    flow.finalize()
    complete_event = next(e for e in events if e["type"] == "project_complete")
    assert "2 file" in complete_event["message"]
    assert complete_event["files_changed"] == ["app.js", "styles.css"]
    assert complete_event["mode"] == "iterate"


def test_full_flow_kickoff_team_mode(mocked_crews):
    events = []
    flow = ProjectCreationFlow(project_id="abc", user_prompt="prompt", event_callback=events.append)
    with patch("app.crew.flows.project_flow.get_upload_context", return_value=""):
        flow.gather_requirements()
        flow.run_leadership()
        flow.run_analysis()
        flow.run_planning()
        flow.run_architecture()
        flow.run_engineering()
        flow.finalize()
    assert flow.state.status == "complete"
    assert flow.state.leadership_output == "fake crew output"
    assert flow.state.analysis_output == "fake crew output"
    assert flow.state.plan_output == "fake crew output"
    assert flow.state.architecture_output == "fake crew output"
    assert flow.state.engineering_output == "fake crew output"
    assert any(e["type"] == "project_complete" for e in events)


def test_full_flow_kickoff_engineer_mode(mocked_crews):
    events = []
    flow = ProjectCreationFlow(project_id="abc", user_prompt="prompt", event_callback=events.append, mode="engineer")
    with patch("app.crew.flows.project_flow.get_upload_context", return_value=""):
        flow.gather_requirements()
        flow.run_engineering()
        flow.finalize()
    assert flow.state.status == "complete"
    assert flow.state.leadership_output == ""
    assert flow.state.analysis_output == ""
    assert flow.state.plan_output == ""
    assert flow.state.architecture_output == ""
    assert flow.state.engineering_output == "fake crew output"


def test_full_flow_kickoff_goal_mode(mocked_crews):
    events = []
    flow = ProjectCreationFlow(project_id="abc", user_prompt="prompt", event_callback=events.append, mode="goal")
    with patch("app.crew.flows.project_flow.get_upload_context", return_value=""):
        flow.gather_requirements()
        flow.run_leadership()
        flow.run_analysis()
        flow.run_planning()
        flow.run_architecture()
        flow.run_engineering()
        flow.finalize()
    assert flow.state.status == "complete"
    assert flow.state.leadership_output == "fake crew output"
    assert flow.state.analysis_output == "fake crew output"
    assert flow.state.plan_output == "fake crew output"
    assert flow.state.architecture_output == "fake crew output"
    assert flow.state.engineering_output == "fake crew output"
    assert not any(e["type"] == "human_feedback_request" for e in events)


def test_state_model():
    state = ProjectFlowState(project_id="x", user_prompt="y")
    assert state.status == "created"
    assert state.mode == "team"
    assert state.files_created == []


def test_kickoff_flow_consumes_flow_streaming_output():
    events = []
    flow = ProjectCreationFlow(project_id="abc", user_prompt="prompt", event_callback=events.append)

    class _StreamStub:
        def __iter__(self):
            return iter([])

        @property
        def result(self):
            return "done"

    stream = _StreamStub()

    with (
        patch.object(flow, "kickoff", return_value=stream),
        patch("app.crew.flows.project_flow.consume_stream_output", return_value="done") as consume,
    ):
        result = flow.kickoff_flow()

    consume.assert_called_once_with(
        stream,
        flow._emit,
        channels=frozenset({"flow", "lifecycle"}),
    )
    assert result == "done"


def test_kickoff_flow_returns_plain_output_when_not_streaming():
    flow = ProjectCreationFlow(project_id="abc", user_prompt="prompt")

    with patch.object(flow, "kickoff", return_value="plain-result"):
        assert flow.kickoff_flow() == "plain-result"


def test_has_written_required_files_true_when_present(monkeypatch, tmp_path):
    monkeypatch.setattr("app.config.settings.projects_dir", tmp_path)
    proj_id = "covtest1"
    proj_dir = tmp_path / proj_id
    proj_dir.mkdir(parents=True, exist_ok=True)
    for name in REQUIRED_PROJECT_FILES:
        (proj_dir / name).touch()

    assert _has_written_required_files(proj_id) is True


def test_has_written_required_files_false_when_missing(monkeypatch, tmp_path):
    monkeypatch.setattr("app.config.settings.projects_dir", tmp_path)
    proj_id = "covtest2"
    # no files created
    assert _has_written_required_files(proj_id) is False


def test_has_written_required_files_returns_false_on_error(monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("disk fail")
    monkeypatch.setattr("app.config.settings", type("s", (), {"projects_dir": None})())
    assert _has_written_required_files("any") is False


def test_kickoff_flow_swallows_stream_error_when_files_present(monkeypatch, tmp_path):
    monkeypatch.setattr("app.config.settings.projects_dir", tmp_path)
    proj_id = "covtest3"
    proj_dir = tmp_path / proj_id
    proj_dir.mkdir(parents=True, exist_ok=True)
    for name in REQUIRED_PROJECT_FILES:
        (proj_dir / name).touch()

    flow = ProjectCreationFlow(project_id=proj_id, user_prompt="prompt")

    with patch("app.crew.flows.project_flow.is_consumable_stream", return_value=True):
        with patch.object(flow, "kickoff", return_value=MagicMock()):
            with patch("app.crew.flows.project_flow.consume_stream_output", side_effect=RuntimeError("No result available")):
                result = flow.kickoff_flow()
                assert result is None


def test_kickoff_flow_reraises_stream_error_when_no_files(monkeypatch, tmp_path):
    monkeypatch.setattr("app.config.settings.projects_dir", tmp_path)
    proj_id = "covtest4"
    # no files on disk
    flow = ProjectCreationFlow(project_id=proj_id, user_prompt="prompt")

    with patch("app.crew.flows.project_flow.is_consumable_stream", return_value=True):
        with patch.object(flow, "kickoff", return_value=MagicMock()):
            with patch("app.crew.flows.project_flow.consume_stream_output", side_effect=RuntimeError("No result available")):
                with pytest.raises(RuntimeError, match="No result available"):
                    flow.kickoff_flow()


def test_kickoff_flow_restore_path():
    """Cover the if self._restore_from branch in kickoff_flow."""
    flow = ProjectCreationFlow(project_id="p", user_prompt="u", restore_from="db#1")
    with patch.object(flow, "build_kickoff_checkpoint") as b, \
         patch.object(flow, "kickoff", return_value="restored") as k:
        b.return_value = MagicMock()
        res = flow.kickoff_flow()
        assert res == "restored"
        b.assert_called_once()
        k.assert_called_once()


def test_fork_from_checkpoint_rehydrates_flow_state(mocked_crews):
    forked = ProjectCreationFlow(project_id="old", user_prompt="old prompt")
    with patch.object(ProjectCreationFlow, "fork", return_value=forked) as mock_fork:
        flow = ProjectCreationFlow.fork_from_checkpoint(
            "abc",
            "new prompt",
            restore_from="db#saved",
            branch="experiment",
            mode="goal",
            iteration_request="add nav",
        )

    mock_fork.assert_called_once()
    assert flow.state.project_id == "abc"
    assert flow.state.user_prompt == "new prompt"
    assert flow.state.context_prepared is False
    assert flow.state.mode == "goal"
    assert flow.state.iteration_request == "add nav"


def test_build_kickoff_checkpoint_uses_restore_from():
    flow = ProjectCreationFlow(project_id="abc", user_prompt="prompt", restore_from="db#saved")
    config = flow.build_kickoff_checkpoint()
    assert config.restore_from == "db#saved"


def test_run_planning_stores_structured_plan_spec(mocked_crews):
    from app.crew.schemas import PageSpec, ProjectPlanSpec

    spec = ProjectPlanSpec(
        overview="A modern portfolio website for a developer showcasing projects and skills.",
        mvp_features=["Hero section"],
        pages=[PageSpec(name="Home", purpose="Landing page", key_elements=["Hero"])],
        data_model_summary="Static content only.",
        technical_architecture="Single-page HTML/CSS/JS app.",
        milestones=["Build landing page"],
    )
    mocked_crews["planning"].return_value.kickoff.return_value = MagicMock(raw="ignored", pydantic=spec)

    flow = ProjectCreationFlow(project_id="abc", user_prompt="prompt")
    flow.state.analysis_output = "analysis done"
    flow.run_planning()

    assert flow.state.plan_spec is not None
    assert flow.state.plan_spec["pages"][0]["name"] == "Home"


def test_kickoff_with_streaming_emits_stream_chunks(mocked_crews):
    from crewai.types.streaming import StreamChunk

    events = []
    flow = ProjectCreationFlow(project_id="abc", user_prompt="prompt", event_callback=events.append)

    stream = MagicMock()
    stream.__iter__.return_value = iter([StreamChunk(content="Planning ", agent_role="Product Manager")])
    stream.result = MagicMock(raw="fake crew output")
    mocked_crews["planning"].return_value.stream = True
    mocked_crews["planning"].return_value.kickoff.return_value = stream

    flow.state.analysis_output = "analysis done"
    flow.run_planning()

    assert any(e["type"] == "stream_chunk" and e["agent"] == "product_manager" for e in events)


def _run_reviewed_phase_for_test(flow, *, output: str = "output", on_second_attempt=None):
    attempts: list[str] = []
    call_count = {"value": 0}

    def run_attempt(prompt: str):
        attempts.append(prompt)
        call_count["value"] += 1
        if call_count["value"] == 2 and on_second_attempt:
            on_second_attempt()
        return MagicMock(raw=output)

    def store_result(_result, _output: str):
        return None

    result = flow._run_reviewed_phase(
        phase="leading",
        agent_name="team_leader",
        task_label="Reviewing your brief",
        run_attempt=run_attempt,
        store_result=store_result,
    )
    return result, attempts


def test_request_review_without_feedback_provider():
    flow = ProjectCreationFlow(project_id="abc", user_prompt="prompt")
    result, attempts = _run_reviewed_phase_for_test(flow)
    assert result == "output"
    assert attempts == ["prompt"]


def test_request_review_goal_mode_skips_feedback_provider():
    from app.crew.feedback import WebSocketFeedbackProvider

    provider = MagicMock(spec=WebSocketFeedbackProvider)
    events = []
    flow = ProjectCreationFlow(
        project_id="abc",
        user_prompt="prompt",
        event_callback=events.append,
        feedback_provider=provider,
        mode="goal",
    )
    result, attempts = _run_reviewed_phase_for_test(flow)
    assert result == "output"
    assert attempts == ["prompt"]
    provider.request_feedback.assert_not_called()
    assert not any(e["type"] == "human_feedback_request" for e in events)


def test_request_review_approve(mocked_crews):
    provider = MagicMock()
    provider.request_feedback.return_value = {"action": "approve", "feedback": ""}
    events = []
    flow = ProjectCreationFlow(
        project_id="abc",
        user_prompt="prompt",
        event_callback=events.append,
        feedback_provider=provider,
    )

    result, attempts = _run_reviewed_phase_for_test(flow)

    assert result == "output"
    assert attempts == ["prompt"]
    provider.request_feedback.assert_called_once()
    assert any(e["type"] == "human_feedback_request" for e in events)
    assert any(e["type"] == "human_feedback_response" and e["action"] == "approve" for e in events)


def test_request_review_revise_appends_feedback(mocked_crews):
    provider = MagicMock()
    provider.request_feedback.side_effect = [
        {"action": "revise", "feedback": "add dark mode"},
        {"action": "approve", "feedback": ""},
    ]
    events = []
    flow = ProjectCreationFlow(
        project_id="abc",
        user_prompt="original prompt",
        event_callback=events.append,
        feedback_provider=provider,
    )

    result, attempts = _run_reviewed_phase_for_test(flow)

    assert result == "output"
    assert flow.state.user_prompt == "original prompt"
    assert len(attempts) == 2
    assert "add dark mode" in attempts[1]
    assert "Revision request for this phase" in attempts[1]
    assert provider.request_feedback.call_count == 2
    assert any(e["type"] == "human_feedback_response" and e["action"] == "revise" for e in events)


def test_flow_initial_state_iterate_mode():
    flow = ProjectCreationFlow(project_id="abc", user_prompt="Build it", mode="iterate", iteration_request="add contact page")
    assert flow.state.mode == "iterate"
    assert flow.state.iteration_request == "add contact page"


def test_gather_requirements_iterate_mode():
    events = []
    flow = ProjectCreationFlow(project_id="abc", user_prompt="prompt", event_callback=events.append, mode="iterate")
    with patch("app.crew.flows.project_flow.get_upload_context", return_value=""):
        result = flow.gather_requirements()
    assert result == "prompt"
    assert flow.state.status == "building"
    assert events[0]["phase"] == "building"
    assert "updates" in events[0]["message"].lower() or "updating" in events[0]["message"].lower()


def test_run_leadership_iterate_mode_skips():
    flow = ProjectCreationFlow(project_id="abc", user_prompt="prompt", mode="iterate")
    result = flow.run_leadership()
    assert result == ""


def test_run_analysis_iterate_mode_skips():
    flow = ProjectCreationFlow(project_id="abc", user_prompt="prompt", mode="iterate")
    result = flow.run_analysis()
    assert result == ""


def test_run_planning_iterate_mode_skips():
    flow = ProjectCreationFlow(project_id="abc", user_prompt="prompt", mode="iterate")
    result = flow.run_planning()
    assert result == ""


def test_run_architecture_iterate_mode_skips():
    flow = ProjectCreationFlow(project_id="abc", user_prompt="prompt", mode="iterate")
    result = flow.run_architecture()
    assert result == ""


def test_run_engineering_iterate_mode_uses_iteration_task(mocked_crews, settings_projects_dir):
    events = []
    flow = ProjectCreationFlow(
        project_id="abc",
        user_prompt="original prompt",
        event_callback=events.append,
        mode="iterate",
        iteration_request="add a contact page",
    )

    with patch("app.crew.flows.project_flow.create_iteration_task") as mock_iter_task:
        mock_iter_task.return_value = MagicMock()
        result = flow.run_engineering()

    mock_iter_task.assert_called_once()
    assert mock_iter_task.call_args[0][1] == "original prompt"
    assert mock_iter_task.call_args[0][2] == "add a contact page"
    assert result == "fake crew output"
    assert any("changes" in e.get("task", "").lower() for e in events if e["type"] == "agent_start")


def test_run_navigation_recovery(mocked_crews, settings_projects_dir):
    from app.crew.agents.engineer import create_engineer_agent

    flow = ProjectCreationFlow(project_id="abc", user_prompt="prompt", event_callback=[])
    engineer = create_engineer_agent()
    with patch.object(flow, "_engineering_context_tasks", return_value=[]), patch(
        "app.crew.flows.project_flow.create_engineering_crew"
    ) as crew_factory, patch(
        "app.crew.flows.project_flow.kickoff_with_streaming", return_value=MagicMock(raw="fixed")
    ):
        crew_factory.return_value = MagicMock()
        result = flow._run_navigation_recovery(engineer, [], ["index.html contains root-relative href"])
    assert result == "fixed"


def test_run_engineering_recovers_invalid_navigation(mocked_crews, settings_projects_dir):
    project_dir = settings_projects_dir / "abc"
    project_dir.mkdir(parents=True, exist_ok=True)
    (project_dir / "index.html").write_text('<a href="/transactions">Tx</a>', encoding="utf-8")
    (project_dir / "styles.css").write_text("body {}", encoding="utf-8")
    (project_dir / "app.js").write_text("console.log('ok');", encoding="utf-8")

    flow = ProjectCreationFlow(project_id="abc", user_prompt="prompt", mode="engineer")

    def nav_recovery(_engineer, _context_tasks, _violations):
        (project_dir / "index.html").write_text(
            '<button data-tab="transactions">Tx</button><section data-panel="transactions" hidden></section>',
            encoding="utf-8",
        )
        return "fixed"

    with patch.object(flow, "_engineering_context_tasks", return_value=[]), patch(
        "app.crew.tasks.engineering_tasks.create_engineering_task"
    ), patch("app.crew.flows.project_flow.create_engineering_crew"), patch(
        "app.crew.flows.project_flow.kickoff_with_streaming", return_value=MagicMock(raw="ok")
    ), patch.object(flow, "_missing_required_files", return_value=[]), patch.object(
        flow, "_ensure_engineering_files_created"
    ), patch.object(flow, "_run_navigation_recovery", side_effect=nav_recovery):
        result = flow.run_engineering()

    assert result == "fixed"
    assert flow._navigation_violations() == []


def test_run_engineering_raises_when_navigation_stays_invalid(mocked_crews, settings_projects_dir):
    project_dir = settings_projects_dir / "abc"
    project_dir.mkdir(parents=True, exist_ok=True)
    (project_dir / "index.html").write_text('<a href="/transactions">Tx</a>', encoding="utf-8")
    (project_dir / "styles.css").write_text("body {}", encoding="utf-8")
    (project_dir / "app.js").write_text("console.log('ok');", encoding="utf-8")

    flow = ProjectCreationFlow(project_id="abc", user_prompt="prompt", mode="engineer")
    with patch.object(flow, "_engineering_context_tasks", return_value=[]), patch(
        "app.crew.tasks.engineering_tasks.create_engineering_task"
    ), patch("app.crew.flows.project_flow.create_engineering_crew"), patch(
        "app.crew.flows.project_flow.kickoff_with_streaming", return_value=MagicMock(raw="ok")
    ), patch.object(flow, "_missing_required_files", return_value=[]), patch.object(
        flow, "_ensure_engineering_files_created"
    ), patch.object(flow, "_run_navigation_recovery", return_value="still bad"):
        with pytest.raises(RuntimeError, match=INVALID_NAVIGATION_ERROR):
            flow.run_engineering()


def test_navigation_violations_detect_forbidden_routes(settings_projects_dir):
    flow = ProjectCreationFlow(project_id="abc", user_prompt="prompt")
    project_dir = settings_projects_dir / "abc"
    project_dir.mkdir(parents=True, exist_ok=True)
    (project_dir / "index.html").write_text('<a href="/transactions">Tx</a>', encoding="utf-8")
    (project_dir / "styles.css").write_text("body {}", encoding="utf-8")
    (project_dir / "app.js").write_text("console.log('ok');", encoding="utf-8")

    violations = flow._navigation_violations()
    assert any("index.html" in item for item in violations)


def test_run_engineering_iterate_mode_raises_when_no_files_written(mocked_crews, settings_projects_dir):
    mocked_crews["engineering"].return_value.kickoff.side_effect = lambda: MagicMock(raw="no files written")

    flow = ProjectCreationFlow(project_id="abc", user_prompt="prompt", mode="iterate", iteration_request="tweak colors")
    with patch("app.crew.flows.project_flow.create_iteration_task", return_value=MagicMock()):
        with pytest.raises(RuntimeError, match=ITERATION_NO_FILES_WRITTEN_ERROR):
            flow.run_engineering()

    mocked_crews["engineering_recovery"].assert_not_called()


def test_full_flow_kickoff_iterate_mode(mocked_crews):
    events = []
    flow = ProjectCreationFlow(
        project_id="abc",
        user_prompt="prompt",
        event_callback=events.append,
        mode="iterate",
        iteration_request="add nav links",
    )
    with patch("app.crew.flows.project_flow.get_upload_context", return_value=""):
        with patch("app.crew.flows.project_flow.create_iteration_task", return_value=MagicMock()):
            flow.gather_requirements()
            flow.run_engineering()
            flow.finalize()
    assert flow.state.status == "complete"
    assert flow.state.leadership_output == ""
    assert flow.state.analysis_output == ""
    assert flow.state.plan_output == ""
    assert flow.state.architecture_output == ""
    assert flow.state.engineering_output == "fake crew output"


def test_finalize_iterate_mode_message():
    events = []
    flow = ProjectCreationFlow(project_id="abc", user_prompt="prompt", event_callback=events.append, mode="iterate")
    flow.finalize()
    assert events[0]["message"] == "Project updated!"


def test_request_review_revise_empty_feedback_no_append():
    provider = MagicMock()
    provider.request_feedback.side_effect = [
        {"action": "revise", "feedback": ""},
        {"action": "approve", "feedback": ""},
    ]
    flow = ProjectCreationFlow(
        project_id="abc",
        user_prompt="original",
        event_callback=lambda e: None,
        feedback_provider=provider,
    )

    _run_reviewed_phase_for_test(flow)

    assert flow.state.user_prompt == "original"


def test_request_review_revision_limit_raises_on_final_attempt():
    provider = MagicMock()
    provider.request_feedback.return_value = {"action": "revise", "feedback": "more detail"}
    flow = ProjectCreationFlow(
        project_id="abc",
        user_prompt="prompt",
        event_callback=lambda _event: None,
        feedback_provider=provider,
    )

    with pytest.raises(RuntimeError, match="Revision limit reached"):
        _run_reviewed_phase_for_test(flow)

    assert provider.request_feedback.call_count == 3


def test_request_review_revision_limit_when_max_attempts_zero():
    flow = ProjectCreationFlow(project_id="abc", user_prompt="prompt", feedback_provider=MagicMock())

    with (
        patch("app.crew.flows.project_flow.MAX_PHASE_ATTEMPTS", 0),
        pytest.raises(RuntimeError, match="Revision limit reached"),
    ):
        flow._run_reviewed_phase(
            phase="leading",
            agent_name="team_leader",
            task_label="Reviewing your brief",
            run_attempt=lambda _prompt: MagicMock(raw="output"),
            store_result=lambda _result, _output: None,
        )


def test_project_flow_allows_zero_arg_construction_for_crewai_fork():
    flow = ProjectCreationFlow()
    assert flow.state.project_id == ""
    assert flow.state.user_prompt == ""
    assert flow.checkpoint is False
